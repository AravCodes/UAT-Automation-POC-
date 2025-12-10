"""
Parallel test execution runner.

This module implements the test execution engine that runs test scenarios
in parallel with configurable concurrency. It maintains test context and
state across steps, implements retry logic, and captures comprehensive diagnostics.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field
from playwright.async_api import Page, BrowserContext, Error as PlaywrightError

from app.core.config import get_config
from app.core.exceptions import (
    ExecutionException,
)
from app.core.logging import get_logger
from app.models.test_scenario import TestScenario, TestStep, ActionType
from app.models.test_result import (
    TestRunResult,
    ScenarioResult,
    StepResult,
    RunDiagnostics,
    RunStatus,
    ScenarioStatus,
    StepStatus
)
from app.services.executor.playwright_wrapper import PlaywrightWrapper


logger = get_logger(__name__)


class TestContext:
    """
    Maintains test context and state across steps.
    
    Stores variables, page state, and execution history for a test scenario.
    """
    
    def __init__(self, scenario_id: str):
        """
        Initialize test context.
        
        Args:
            scenario_id: ID of the scenario this context belongs to
        """
        self.scenario_id = scenario_id
        self.variables: dict[str, Any] = {}
        self.page_url: Optional[str] = None
        self.execution_history: list[dict] = []
        self.start_time: datetime = datetime.now()
    
    def set_variable(self, key: str, value: Any) -> None:
        """Store a variable in the context."""
        self.variables[key] = value
        logger.debug(
            "context_variable_set",
            extra={
                "scenario_id": self.scenario_id,
                "key": key,
                "value_type": type(value).__name__
            }
        )
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """Retrieve a variable from the context."""
        return self.variables.get(key, default)
    
    def update_page_url(self, url: str) -> None:
        """Update the current page URL."""
        self.page_url = url
    
    def add_execution_event(self, event_type: str, details: dict) -> None:
        """Add an execution event to the history."""
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        })


class ExecutionConfig(BaseModel):
    """Configuration for test execution."""
    
    concurrency: int = Field(default=3, ge=1, le=10)
    test_timeout: int = Field(default=30000, ge=5000)
    retry_attempts: int = Field(default=1, ge=0)
    retry_delay: int = Field(default=2000, ge=0)
    headless: bool = Field(default=True)
    screenshot_on_step: bool = Field(default=False)
    screenshot_on_failure: bool = Field(default=True)
    capture_console_logs: bool = Field(default=True)
    capture_network: bool = Field(default=True)
    base_url: Optional[str] = None


class TestRunner:
    """
    Parallel test execution engine.
    
    Executes test scenarios in parallel with configurable concurrency,
    maintains test context, implements retry logic, and captures diagnostics.
    """
    
    def __init__(
        self,
        playwright_wrapper: PlaywrightWrapper,
        config: Optional[ExecutionConfig] = None
    ):
        """
        Initialize the test runner.
        
        Args:
            playwright_wrapper: Playwright wrapper for browser management
            config: Execution configuration (None = use defaults from app config)
        """
        self.playwright_wrapper = playwright_wrapper
        self.app_config = get_config()
        
        # Use provided config or create from app config
        if config is None:
            config = ExecutionConfig(
                concurrency=self.app_config.concurrency,
                test_timeout=self.app_config.test_timeout,
                retry_attempts=self.app_config.retry_attempts,
                retry_delay=self.app_config.retry_delay,
                headless=self.app_config.headless_mode,
                screenshot_on_step=self.app_config.screenshot_on_step,
                screenshot_on_failure=self.app_config.screenshot_on_failure,
                capture_console_logs=self.app_config.capture_console_logs,
                capture_network=self.app_config.capture_network,
                base_url=self.app_config.sample_app_url
            )
        
        self.config = config
        self._semaphore = asyncio.Semaphore(self.config.concurrency)
        
        logger.info(
            "test_runner_initialized",
            extra={
                "concurrency": self.config.concurrency,
                "test_timeout": self.config.test_timeout,
                "retry_attempts": self.config.retry_attempts
            }
        )
    
    async def run_scenarios(
        self,
        story_id: str,
        scenarios: list[TestScenario]
    ) -> TestRunResult:
        """
        Execute multiple test scenarios in parallel.
        
        Args:
            story_id: ID of the story being tested
            scenarios: List of test scenarios to execute
        
        Returns:
            TestRunResult: Complete test run results with diagnostics
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now()
        
        logger.info(
            "test_run_started",
            extra={
                "run_id": run_id,
                "story_id": story_id,
                "scenario_count": len(scenarios),
                "concurrency": self.config.concurrency
            }
        )
        
        # Execute scenarios in parallel with concurrency limit
        tasks = [
            self._execute_scenario_with_semaphore(scenario)
            for scenario in scenarios
        ]
        
        scenario_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions from scenario execution
        processed_results = []
        for i, result in enumerate(scenario_results):
            if isinstance(result, Exception):
                logger.error(
                    "scenario_execution_exception",
                    extra={
                        "scenario_id": scenarios[i].id,
                        "error": str(result)
                    },
                    exc_info=result
                )
                # Create error result
                processed_results.append(
                    ScenarioResult(
                        scenario_id=scenarios[i].id,
                        status=ScenarioStatus.ERROR,
                        step_results=[],
                        duration_ms=0,
                        error_summary=str(result)
                    )
                )
            else:
                processed_results.append(result)
        
        completed_at = datetime.now()
        
        # Calculate diagnostics
        diagnostics = self._calculate_diagnostics(processed_results)
        
        # Determine overall run status
        run_status = self._determine_run_status(processed_results)
        
        # Build test run result
        test_run_result = TestRunResult(
            id=run_id,
            story_id=story_id,
            started_at=started_at,
            completed_at=completed_at,
            status=run_status,
            scenario_results=processed_results,
            diagnostics=diagnostics,
            environment={
                "browser_type": self.playwright_wrapper.browser_type,
                "headless": self.config.headless,
                "base_url": self.config.base_url
            },
            configuration={
                "concurrency": self.config.concurrency,
                "test_timeout": self.config.test_timeout,
                "retry_attempts": self.config.retry_attempts
            }
        )
        
        logger.info(
            "test_run_completed",
            extra={
                "run_id": run_id,
                "status": run_status.value,
                "duration_ms": (completed_at - started_at).total_seconds() * 1000,
                "total_scenarios": diagnostics.total_scenarios,
                "passed_scenarios": diagnostics.passed_scenarios,
                "failed_scenarios": diagnostics.failed_scenarios
            }
        )
        
        return test_run_result
    
    async def _execute_scenario_with_semaphore(
        self,
        scenario: TestScenario
    ) -> ScenarioResult:
        """
        Execute a scenario with concurrency control.
        
        Args:
            scenario: Test scenario to execute
        
        Returns:
            ScenarioResult: Scenario execution result
        """
        async with self._semaphore:
            return await self._execute_scenario(scenario)
    
    async def _execute_scenario(
        self,
        scenario: TestScenario
    ) -> ScenarioResult:
        """
        Execute a single test scenario with retry logic.
        
        Args:
            scenario: Test scenario to execute
        
        Returns:
            ScenarioResult: Scenario execution result
        """
        logger.info(
            "scenario_execution_started",
            extra={
                "scenario_id": scenario.id,
                "scenario_type": scenario.type.value,
                "priority": scenario.priority.value,
                "step_count": len(scenario.test_steps)
            }
        )
        
        start_time = datetime.now()
        retry_count = 0
        last_result: Optional[ScenarioResult] = None
        
        # Try executing the scenario (initial + retries)
        for attempt in range(self.config.retry_attempts + 1):
            if attempt > 0:
                retry_count = attempt
                logger.info(
                    "scenario_retry_attempt",
                    extra={
                        "scenario_id": scenario.id,
                        "attempt": attempt + 1,
                        "max_attempts": self.config.retry_attempts + 1
                    }
                )
                # Wait before retry
                await asyncio.sleep(self.config.retry_delay / 1000.0)
            
            # Execute scenario
            result = await self._execute_scenario_once(scenario)
            last_result = result
            
            # If passed, return immediately
            if result.status == ScenarioStatus.PASSED:
                # Mark as flaky if it passed after retry
                if retry_count > 0:
                    result.is_flaky = True
                    logger.warning(
                        "flaky_scenario_detected",
                        extra={
                            "scenario_id": scenario.id,
                            "retry_count": retry_count
                        }
                    )
                
                result.retry_count = retry_count
                return result
        
        # All attempts failed
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        logger.error(
            "scenario_execution_failed",
            extra={
                "scenario_id": scenario.id,
                "retry_count": retry_count,
                "duration_ms": duration_ms
            }
        )
        
        # Return the last result with updated retry count
        if last_result:
            last_result.retry_count = retry_count
            return last_result
        
        # Fallback error result (should not happen)
        return ScenarioResult(
            scenario_id=scenario.id,
            status=ScenarioStatus.ERROR,
            step_results=[],
            duration_ms=duration_ms,
            retry_count=retry_count,
            error_summary="Scenario execution failed with no result"
        )

    async def _execute_scenario_once(
        self,
        scenario: TestScenario
    ) -> ScenarioResult:
        """
        Execute a scenario once (single attempt).
        
        Args:
            scenario: Test scenario to execute
        
        Returns:
            ScenarioResult: Scenario execution result
        """
        start_time = datetime.now()
        step_results: list[StepResult] = []
        context = TestContext(scenario.id)
        
        # Create a new browser context for this scenario
        async with self.playwright_wrapper.context() as browser_context:
            # Create a new page
            page = await browser_context.new_page()
            
            try:
                # Setup page listeners if needed
                if self.config.capture_console_logs:
                    page.on("console", lambda msg: context.add_execution_event(
                        "console",
                        {"type": msg.type, "text": msg.text}
                    ))
                
                # Execute each test step
                for step_index, step in enumerate(scenario.test_steps):
                    logger.debug(
                        "executing_step",
                        extra={
                            "scenario_id": scenario.id,
                            "step_index": step_index,
                            "action": step.action.value,
                            "target": step.target
                        }
                    )
                    
                    step_result = await self._execute_step(
                        step=step,
                        page=page,
                        context=context,
                        step_index=step_index
                    )
                    
                    step_results.append(step_result)
                    
                    # Stop execution if step failed
                    if step_result.status in [StepStatus.FAILED, StepStatus.ERROR]:
                        logger.warning(
                            "step_failed_stopping_scenario",
                            extra={
                                "scenario_id": scenario.id,
                                "step_index": step_index,
                                "status": step_result.status.value
                            }
                        )
                        break
                
                # Close page
                await page.close()
                
            except Exception as e:
                logger.error(
                    "scenario_execution_error",
                    extra={
                        "scenario_id": scenario.id,
                        "error": str(e)
                    },
                    exc_info=True
                )
                
                # Try to close page
                try:
                    await page.close()
                except:
                    pass
                
                # Return error result
                end_time = datetime.now()
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                
                return ScenarioResult(
                    scenario_id=scenario.id,
                    status=ScenarioStatus.ERROR,
                    step_results=step_results,
                    duration_ms=duration_ms,
                    error_summary=str(e)
                )
        
        # Calculate scenario status
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        scenario_status = self._determine_scenario_status(step_results)
        
        return ScenarioResult(
            scenario_id=scenario.id,
            status=scenario_status,
            step_results=step_results,
            duration_ms=duration_ms
        )
    
    async def _execute_step(
        self,
        step: TestStep,
        page: Page,
        context: TestContext,
        step_index: int
    ) -> StepResult:
        """
        Execute a single test step.
        
        Args:
            step: Test step to execute
            page: Playwright page
            context: Test context
            step_index: Index of the step in the scenario
        
        Returns:
            StepResult: Step execution result
        """
        start_time = datetime.now()
        
        try:
            # Execute action based on type
            if step.action == ActionType.NAVIGATE:
                await self._action_navigate(page, step, context)
            elif step.action == ActionType.CLICK:
                await self._action_click(page, step, context)
            elif step.action == ActionType.TYPE:
                await self._action_type(page, step, context)
            elif step.action == ActionType.SELECT:
                await self._action_select(page, step, context)
            elif step.action == ActionType.ASSERT:
                await self._action_assert(page, step, context)
            elif step.action == ActionType.WAIT:
                await self._action_wait(page, step, context)
            elif step.action == ActionType.HOVER:
                await self._action_hover(page, step, context)
            elif step.action == ActionType.SCROLL:
                await self._action_scroll(page, step, context)
            else:
                raise ExecutionException(
                    f"Unsupported action type: {step.action}",
                    details={"action": step.action.value}
                )
            
            # Step passed
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Capture screenshot if configured
            screenshot_path = None
            if self.config.screenshot_on_step:
                screenshot_path = await self._capture_screenshot(
                    page,
                    context.scenario_id,
                    step_index,
                    "step"
                )
            
            return StepResult(
                step=step,
                status=StepStatus.PASSED,
                screenshot_path=screenshot_path,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            # Step failed
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(
                "step_execution_failed",
                extra={
                    "scenario_id": context.scenario_id,
                    "step_index": step_index,
                    "action": step.action.value,
                    "error": str(e)
                },
                exc_info=True
            )
            
            # Capture failure screenshot
            screenshot_path = None
            if self.config.screenshot_on_failure:
                screenshot_path = await self._capture_screenshot(
                    page,
                    context.scenario_id,
                    step_index,
                    "failure"
                )
            
            # Capture DOM snapshot
            dom_snapshot = None
            try:
                dom_snapshot = await page.content()
            except:
                pass
            
            return StepResult(
                step=step,
                status=StepStatus.FAILED,
                screenshot_path=screenshot_path,
                error_message=str(e),
                dom_snapshot=dom_snapshot,
                duration_ms=duration_ms
            )
    
    # ========================================================================
    # Action Implementations (Placeholders for now)
    # ========================================================================
    
    async def _action_navigate(
        self,
        page: Page,
        step: TestStep,
        context: TestContext
    ) -> None:
        """Navigate to a URL."""
        url = step.target
        if self.config.base_url and not url.startswith("http"):
            url = f"{self.config.base_url.rstrip('/')}/{url.lstrip('/')}"
        
        await page.goto(url, timeout=self.config.test_timeout)
        context.update_page_url(page.url)
    
    async def _action_click(
        self,
        page: Page,
        step: TestStep,
        context: TestContext
    ) -> None:
        """Click an element."""
        # Placeholder - will be implemented with element finder
        locator = page.locator(step.target)
        await locator.click(timeout=self.config.test_timeout)
    
    async def _action_type(
        self,
        page: Page,
        step: TestStep,
        context: TestContext
    ) -> None:
        """Type text into an element."""
        # Placeholder - will be implemented with element finder
        locator = page.locator(step.target)
        await locator.fill(step.value or "", timeout=self.config.test_timeout)
    
    async def _action_select(
        self,
        page: Page,
        step: TestStep,
        context: TestContext
    ) -> None:
        """Select an option from a dropdown."""
        # Placeholder - will be implemented with element finder
        locator = page.locator(step.target)
        await locator.select_option(step.value or "", timeout=self.config.test_timeout)
    
    async def _action_assert(
        self,
        page: Page,
        step: TestStep,
        context: TestContext
    ) -> None:
        """Assert element state or content."""
        # Placeholder - will be implemented with element finder
        locator = page.locator(step.target)
        await locator.wait_for(state="visible", timeout=self.config.test_timeout)
    
    async def _action_wait(
        self,
        page: Page,
        step: TestStep,
        context: TestContext
    ) -> None:
        """Wait for a condition or duration."""
        # Placeholder - will be implemented with smart waiter
        if step.value and step.value.isdigit():
            await asyncio.sleep(int(step.value) / 1000.0)
        else:
            locator = page.locator(step.target)
            await locator.wait_for(state="visible", timeout=self.config.test_timeout)
    
    async def _action_hover(
        self,
        page: Page,
        step: TestStep,
        context: TestContext
    ) -> None:
        """Hover over an element."""
        # Placeholder - will be implemented with element finder
        locator = page.locator(step.target)
        await locator.hover(timeout=self.config.test_timeout)
    
    async def _action_scroll(
        self,
        page: Page,
        step: TestStep,
        context: TestContext
    ) -> None:
        """Scroll to an element or position."""
        # Placeholder - will be implemented with element finder
        locator = page.locator(step.target)
        await locator.scroll_into_view_if_needed(timeout=self.config.test_timeout)
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    async def _capture_screenshot(
        self,
        page: Page,
        scenario_id: str,
        step_index: int,
        screenshot_type: str
    ) -> Optional[str]:
        """Capture a screenshot."""
        try:
            # This will be implemented properly with file storage
            screenshot_path = f"screenshots/{scenario_id}/step_{step_index}_{screenshot_type}.png"
            # await page.screenshot(path=screenshot_path)
            return screenshot_path
        except Exception as e:
            logger.warning(
                "screenshot_capture_failed",
                extra={"error": str(e)}
            )
            return None
    
    def _determine_scenario_status(
        self,
        step_results: list[StepResult]
    ) -> ScenarioStatus:
        """Determine overall scenario status from step results."""
        if not step_results:
            return ScenarioStatus.SKIPPED
        
        failed_count = sum(
            1 for r in step_results
            if r.status in [StepStatus.FAILED, StepStatus.ERROR]
        )
        
        if failed_count == 0:
            return ScenarioStatus.PASSED
        elif failed_count == len(step_results):
            return ScenarioStatus.FAILED
        else:
            return ScenarioStatus.PARTIAL
    
    def _determine_run_status(
        self,
        scenario_results: list[ScenarioResult]
    ) -> RunStatus:
        """Determine overall run status from scenario results."""
        if not scenario_results:
            return RunStatus.ERROR
        
        failed_count = sum(
            1 for r in scenario_results
            if r.status in [ScenarioStatus.FAILED, ScenarioStatus.ERROR]
        )
        
        if failed_count == 0:
            return RunStatus.PASSED
        elif failed_count == len(scenario_results):
            return RunStatus.FAILED
        else:
            return RunStatus.PARTIAL
    
    def _calculate_diagnostics(
        self,
        scenario_results: list[ScenarioResult]
    ) -> RunDiagnostics:
        """Calculate diagnostic information from scenario results."""
        total_scenarios = len(scenario_results)
        passed_scenarios = sum(
            1 for r in scenario_results
            if r.status == ScenarioStatus.PASSED
        )
        failed_scenarios = sum(
            1 for r in scenario_results
            if r.status in [ScenarioStatus.FAILED, ScenarioStatus.ERROR]
        )
        skipped_scenarios = sum(
            1 for r in scenario_results
            if r.status == ScenarioStatus.SKIPPED
        )
        
        # Count steps
        total_steps = sum(len(r.step_results) for r in scenario_results)
        passed_steps = sum(
            sum(1 for s in r.step_results if s.status == StepStatus.PASSED)
            for r in scenario_results
        )
        failed_steps = sum(
            sum(1 for s in r.step_results if s.status in [StepStatus.FAILED, StepStatus.ERROR])
            for r in scenario_results
        )
        
        # Find flaky scenarios
        flaky_scenarios = [
            r.scenario_id for r in scenario_results
            if r.is_flaky
        ]
        
        # Calculate performance metrics
        if scenario_results:
            avg_scenario_duration = sum(r.duration_ms for r in scenario_results) / len(scenario_results)
            avg_step_duration = sum(
                sum(s.duration_ms for s in r.step_results)
                for r in scenario_results
            ) / max(total_steps, 1)
        else:
            avg_scenario_duration = 0
            avg_step_duration = 0
        
        performance_metrics = {
            "avg_scenario_duration_ms": avg_scenario_duration,
            "avg_step_duration_ms": avg_step_duration
        }
        
        return RunDiagnostics(
            total_scenarios=total_scenarios,
            passed_scenarios=passed_scenarios,
            failed_scenarios=failed_scenarios,
            skipped_scenarios=skipped_scenarios,
            total_steps=total_steps,
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            flaky_scenarios=flaky_scenarios,
            performance_metrics=performance_metrics
        )


# Add missing import
from pydantic import BaseModel, Field
