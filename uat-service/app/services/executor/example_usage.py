"""
Example usage of the test execution engine.

This file demonstrates how to use the test execution engine components
to run test scenarios with full diagnostics and retry logic.
"""

import asyncio

from app.services.executor import (
    PlaywrightWrapper,
    TestRunner,
    ExecutionConfig,
    DiagnosticsCapture,
    get_flaky_test_tracker
)
from app.models.test_scenario import (
    TestScenario,
    TestStep,
    ActionType,
    ScenarioType
)
from app.models.story import Priority


async def example_basic_execution():
    """Example: Basic test execution with a single scenario."""
    
    # Create a test scenario
    scenario = TestScenario(
        id="login-test-1",
        criterion_id="login-crit-1",
        type=ScenarioType.POSITIVE,
        priority=Priority.HIGH,
        given=["User is on the login page"],
        when=["User enters valid credentials and clicks submit"],
        then=["User is redirected to the dashboard"],
        test_steps=[
            TestStep(
                action=ActionType.NAVIGATE,
                target="/login",
                expected_outcome="Login page is displayed"
            ),
            TestStep(
                action=ActionType.TYPE,
                target="[data-testid='login-email']",
                value="user@example.com",
                expected_outcome="Email is entered"
            ),
            TestStep(
                action=ActionType.TYPE,
                target="[data-testid='login-password']",
                value="password123",
                expected_outcome="Password is entered"
            ),
            TestStep(
                action=ActionType.CLICK,
                target="[data-testid='login-submit']",
                expected_outcome="Login form is submitted"
            ),
            TestStep(
                action=ActionType.ASSERT,
                target="[data-testid='dashboard']",
                expected_outcome="Dashboard is visible"
            )
        ]
    )
    
    # Create Playwright wrapper and test runner
    async with PlaywrightWrapper(browser_type="chromium", headless=True) as wrapper:
        runner = TestRunner(wrapper)
        
        # Run the scenario
        result = await runner.run_scenarios(
            story_id="login-story-1",
            scenarios=[scenario]
        )
        
        # Print results
        print(f"Test Run ID: {result.id}")
        print(f"Status: {result.status.value}")
        print(f"Duration: {(result.completed_at - result.started_at).total_seconds():.2f}s")
        print(f"Scenarios: {result.diagnostics.passed_scenarios}/{result.diagnostics.total_scenarios} passed")
        print(f"Steps: {result.diagnostics.passed_steps}/{result.diagnostics.total_steps} passed")
        
        # Check for flaky tests
        if result.diagnostics.flaky_scenarios:
            print(f"Flaky scenarios detected: {result.diagnostics.flaky_scenarios}")


async def example_parallel_execution():
    """Example: Parallel execution of multiple scenarios."""
    
    # Create multiple test scenarios
    scenarios = [
        TestScenario(
            id=f"test-{i}",
            criterion_id=f"crit-{i}",
            type=ScenarioType.POSITIVE,
            priority=Priority.MEDIUM,
            given=[f"Precondition {i}"],
            when=[f"Action {i}"],
            then=[f"Expected result {i}"],
            test_steps=[
                TestStep(
                    action=ActionType.NAVIGATE,
                    target=f"/page-{i}"
                ),
                TestStep(
                    action=ActionType.ASSERT,
                    target=f"[data-testid='content-{i}']"
                )
            ]
        )
        for i in range(5)
    ]
    
    # Configure execution with custom settings
    config = ExecutionConfig(
        concurrency=3,  # Run 3 scenarios in parallel
        test_timeout=30000,
        retry_attempts=1,
        retry_delay=2000,
        headless=True,
        screenshot_on_failure=True
    )
    
    async with PlaywrightWrapper() as wrapper:
        runner = TestRunner(wrapper, config=config)
        
        result = await runner.run_scenarios(
            story_id="parallel-test-story",
            scenarios=scenarios
        )
        
        print(f"Parallel execution completed in {(result.completed_at - result.started_at).total_seconds():.2f}s")
        print(f"Average scenario duration: {result.diagnostics.performance_metrics['avg_scenario_duration_ms']:.0f}ms")


async def example_with_diagnostics():
    """Example: Test execution with comprehensive diagnostics capture."""
    
    scenario = TestScenario(
        id="diagnostics-test-1",
        criterion_id="diag-crit-1",
        type=ScenarioType.POSITIVE,
        priority=Priority.HIGH,
        given=["Application is running"],
        when=["User performs actions"],
        then=["Actions are successful"],
        test_steps=[
            TestStep(action=ActionType.NAVIGATE, target="/"),
            TestStep(action=ActionType.CLICK, target="button")
        ]
    )
    
    run_id = "test-run-123"
    
    async with PlaywrightWrapper() as wrapper:
        # Create diagnostics capture
        diagnostics = DiagnosticsCapture(
            run_id=run_id,
            scenario_id=scenario.id
        )
        
        # Create a page with diagnostics
        async with wrapper.page() as page:
            # Setup listeners
            diagnostics.setup_page_listeners(page)
            
            # Navigate and capture
            await page.goto("http://localhost:5173")
            diagnostics.add_timeline_event(
                event_type="navigation",
                description="Navigated to home page"
            )
            
            # Capture screenshot
            await diagnostics.capture_screenshot(page, "home_page")
            
            # Capture DOM snapshot
            await diagnostics.capture_dom_snapshot(page, "home_page_dom")
            
            # Save diagnostics report
            report_path = await diagnostics.save_diagnostics_report()
            print(f"Diagnostics saved to: {report_path}")
            
            # Print summary
            summary = diagnostics.get_timeline_summary()
            print(f"Timeline events: {summary['total_events']}")
            print(f"Console logs: {len(diagnostics.console_logs)}")
            print(f"Network requests: {len(diagnostics.network_requests)}")


async def example_flaky_test_tracking():
    """Example: Track and analyze flaky tests."""
    
    tracker = get_flaky_test_tracker()
    
    # Simulate recording test results
    scenario_id = "flaky-test-1"
    
    # First run: failed
    tracker.record_result(scenario_id, passed=False, retry_count=0)
    
    # Second run: passed after retry (flaky!)
    tracker.record_result(scenario_id, passed=True, retry_count=1, is_flaky=True)
    
    # Third run: passed immediately
    tracker.record_result(scenario_id, passed=True, retry_count=0)
    
    # Fourth run: passed after retry (flaky again!)
    tracker.record_result(scenario_id, passed=True, retry_count=1, is_flaky=True)
    
    # Get statistics
    stats = tracker.get_statistics(scenario_id)
    print(f"Scenario: {scenario_id}")
    print(f"Total runs: {stats['total_runs']}")
    print(f"Pass rate: {stats['pass_rate']:.1%}")
    print(f"Flaky count: {stats['flaky_count']}")
    print(f"Flakiness score: {stats['flakiness_score']:.2f}")
    print(f"Is flaky: {tracker.is_flaky(scenario_id)}")
    
    # Get all flaky scenarios
    flaky_scenarios = tracker.get_flaky_scenarios(threshold=0.3)
    print(f"All flaky scenarios: {flaky_scenarios}")


async def example_custom_retry_logic():
    """Example: Custom retry logic with specific conditions."""
    
    from app.services.executor import RetryHandler, RetryConfig
    from app.core.exceptions import TimeoutException
    
    # Configure retry behavior
    config = RetryConfig(
        max_attempts=3,
        delay_ms=1000,
        exponential_backoff=True,
        backoff_multiplier=2.0
    )
    
    retry_handler = RetryHandler(config)
    
    # Define an operation that might fail
    attempt_count = 0
    
    async def flaky_operation():
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count < 2:
            raise TimeoutException("Operation timed out")
        
        return "Success!"
    
    # Execute with retry
    result = await retry_handler.execute_with_retry(
        operation=flaky_operation,
        operation_name="flaky_operation"
    )
    
    print(f"Operation result: {result.result}")
    print(f"Total attempts: {result.total_attempts}")
    print(f"Is flaky: {result.is_flaky}")
    print(f"Passed after retry: {result.passed_after_retry}")


async def main():
    """Run all examples."""
    
    print("=" * 60)
    print("Example 1: Basic Execution")
    print("=" * 60)
    try:
        await example_basic_execution()
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("Example 2: Parallel Execution")
    print("=" * 60)
    try:
        await example_parallel_execution()
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("Example 3: Diagnostics Capture")
    print("=" * 60)
    try:
        await example_with_diagnostics()
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("Example 4: Flaky Test Tracking")
    print("=" * 60)
    await example_flaky_test_tracking()
    
    print("\n" + "=" * 60)
    print("Example 5: Custom Retry Logic")
    print("=" * 60)
    await example_custom_retry_logic()


if __name__ == "__main__":
    asyncio.run(main())
