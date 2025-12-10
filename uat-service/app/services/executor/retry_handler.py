"""
Smart retry logic and flaky test detection.

This module implements intelligent retry mechanisms for failed tests,
tracks flakiness metrics, and provides utilities for identifying
and managing flaky tests.
"""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Any, TypeVar, Awaitable
from dataclasses import dataclass, field
from collections import defaultdict

from app.core.config import get_config
from app.core.logging import get_logger


logger = get_logger(__name__)


T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_attempts: int = 2  # Initial attempt + 1 retry
    delay_ms: int = 2000
    exponential_backoff: bool = False
    backoff_multiplier: float = 2.0
    max_delay_ms: int = 10000
    
    def get_delay_for_attempt(self, attempt: int) -> int:
        """
        Calculate delay for a given retry attempt.
        
        Args:
            attempt: Retry attempt number (0-indexed)
        
        Returns:
            Delay in milliseconds
        """
        if not self.exponential_backoff:
            return self.delay_ms
        
        # Exponential backoff: delay * (multiplier ^ attempt)
        delay = self.delay_ms * (self.backoff_multiplier ** attempt)
        return min(int(delay), self.max_delay_ms)


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    
    attempt_number: int
    timestamp: str
    success: bool
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class RetryResult:
    """Result of retry execution."""
    
    success: bool
    result: Any
    total_attempts: int
    retry_attempts: list[RetryAttempt] = field(default_factory=list)
    is_flaky: bool = False
    
    @property
    def failed_on_first_attempt(self) -> bool:
        """Check if the operation failed on the first attempt."""
        return self.total_attempts > 1
    
    @property
    def passed_after_retry(self) -> bool:
        """Check if the operation passed after retry (flaky indicator)."""
        return self.success and self.total_attempts > 1


class RetryHandler:
    """
    Handles retry logic for test execution.
    
    Implements configurable retry strategies with delay, exponential backoff,
    and flaky test detection.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry handler.
        
        Args:
            config: Retry configuration (None = use defaults from app config)
        """
        self.app_config = get_config()
        
        if config is None:
            config = RetryConfig(
                max_attempts=self.app_config.retry_attempts + 1,  # +1 for initial attempt
                delay_ms=self.app_config.retry_delay,
                exponential_backoff=False
            )
        
        self.config = config
        
        logger.debug(
            "retry_handler_initialized",
            extra={
                "max_attempts": self.config.max_attempts,
                "delay_ms": self.config.delay_ms,
                "exponential_backoff": self.config.exponential_backoff
            }
        )
    
    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_name: str,
        should_retry: Optional[Callable[[Exception], bool]] = None
    ) -> RetryResult:
        """
        Execute an async operation with retry logic.
        
        Args:
            operation: Async function to execute
            operation_name: Name of the operation (for logging)
            should_retry: Optional function to determine if exception should trigger retry
        
        Returns:
            RetryResult with execution details
        """
        retry_attempts: list[RetryAttempt] = []
        last_exception: Optional[Exception] = None
        
        for attempt in range(self.config.max_attempts):
            attempt_start = datetime.now()
            
            try:
                logger.debug(
                    "retry_attempt_started",
                    extra={
                        "operation": operation_name,
                        "attempt": attempt + 1,
                        "max_attempts": self.config.max_attempts
                    }
                )
                
                # Execute the operation
                result = await operation()
                
                # Success
                attempt_duration = int((datetime.now() - attempt_start).total_seconds() * 1000)
                
                retry_attempts.append(RetryAttempt(
                    attempt_number=attempt,
                    timestamp=attempt_start.isoformat(),
                    success=True,
                    duration_ms=attempt_duration
                ))
                
                # Check if this is a flaky success (passed after retry)
                is_flaky = attempt > 0
                
                if is_flaky:
                    logger.warning(
                        "operation_passed_after_retry",
                        extra={
                            "operation": operation_name,
                            "attempt": attempt + 1,
                            "total_attempts": attempt + 1
                        }
                    )
                
                return RetryResult(
                    success=True,
                    result=result,
                    total_attempts=attempt + 1,
                    retry_attempts=retry_attempts,
                    is_flaky=is_flaky
                )
                
            except Exception as e:
                last_exception = e
                attempt_duration = int((datetime.now() - attempt_start).total_seconds() * 1000)
                
                retry_attempts.append(RetryAttempt(
                    attempt_number=attempt,
                    timestamp=attempt_start.isoformat(),
                    success=False,
                    error_message=str(e),
                    duration_ms=attempt_duration
                ))
                
                # Check if we should retry
                should_retry_exception = True
                if should_retry is not None:
                    should_retry_exception = should_retry(e)
                
                # If this is the last attempt or we shouldn't retry, fail
                if attempt >= self.config.max_attempts - 1 or not should_retry_exception:
                    logger.error(
                        "operation_failed_after_retries",
                        extra={
                            "operation": operation_name,
                            "total_attempts": attempt + 1,
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    
                    return RetryResult(
                        success=False,
                        result=None,
                        total_attempts=attempt + 1,
                        retry_attempts=retry_attempts,
                        is_flaky=False
                    )
                
                # Wait before retry
                delay = self.config.get_delay_for_attempt(attempt)
                
                logger.info(
                    "retrying_after_failure",
                    extra={
                        "operation": operation_name,
                        "attempt": attempt + 1,
                        "delay_ms": delay,
                        "error": str(e)
                    }
                )
                
                await asyncio.sleep(delay / 1000.0)
        
        # Should not reach here, but handle it
        return RetryResult(
            success=False,
            result=None,
            total_attempts=self.config.max_attempts,
            retry_attempts=retry_attempts,
            is_flaky=False
        )


class FlakyTestTracker:
    """
    Tracks flaky test metrics across test runs.
    
    Identifies tests that pass inconsistently and provides
    statistics for flakiness analysis.
    """
    
    def __init__(self):
        """Initialize flaky test tracker."""
        # scenario_id -> list of results (True = passed, False = failed)
        self._test_history: dict[str, list[bool]] = defaultdict(list)
        
        # scenario_id -> list of retry counts
        self._retry_history: dict[str, list[int]] = defaultdict(list)
        
        # scenario_id -> count of times it was flaky
        self._flaky_count: dict[str, int] = defaultdict(int)
        
        logger.debug("flaky_test_tracker_initialized")
    
    def record_result(
        self,
        scenario_id: str,
        passed: bool,
        retry_count: int = 0,
        is_flaky: bool = False
    ) -> None:
        """
        Record a test result.
        
        Args:
            scenario_id: ID of the scenario
            passed: Whether the test passed
            retry_count: Number of retries needed
            is_flaky: Whether the test was identified as flaky
        """
        self._test_history[scenario_id].append(passed)
        self._retry_history[scenario_id].append(retry_count)
        
        if is_flaky:
            self._flaky_count[scenario_id] += 1
        
        logger.debug(
            "test_result_recorded",
            extra={
                "scenario_id": scenario_id,
                "passed": passed,
                "retry_count": retry_count,
                "is_flaky": is_flaky
            }
        )
    
    def get_flakiness_score(self, scenario_id: str) -> float:
        """
        Calculate flakiness score for a scenario.
        
        Score is between 0.0 (never flaky) and 1.0 (always flaky).
        
        Args:
            scenario_id: ID of the scenario
        
        Returns:
            Flakiness score (0.0 to 1.0)
        """
        if scenario_id not in self._test_history:
            return 0.0
        
        history = self._test_history[scenario_id]
        if not history:
            return 0.0
        
        # Calculate based on:
        # 1. Number of times marked as flaky
        # 2. Inconsistency in results
        # 3. Average retry count
        
        flaky_count = self._flaky_count[scenario_id]
        total_runs = len(history)
        
        # Flaky ratio
        flaky_ratio = flaky_count / total_runs
        
        # Result inconsistency (how often results change)
        inconsistency = 0.0
        if len(history) > 1:
            changes = sum(
                1 for i in range(len(history) - 1)
                if history[i] != history[i + 1]
            )
            inconsistency = changes / (len(history) - 1)
        
        # Average retry count
        retry_history = self._retry_history[scenario_id]
        avg_retries = sum(retry_history) / len(retry_history) if retry_history else 0
        retry_score = min(avg_retries / 3.0, 1.0)  # Normalize to 0-1
        
        # Weighted combination
        score = (flaky_ratio * 0.5) + (inconsistency * 0.3) + (retry_score * 0.2)
        
        return min(score, 1.0)
    
    def is_flaky(self, scenario_id: str, threshold: float = 0.3) -> bool:
        """
        Check if a scenario is considered flaky.
        
        Args:
            scenario_id: ID of the scenario
            threshold: Flakiness threshold (0.0 to 1.0)
        
        Returns:
            True if scenario is flaky
        """
        return self.get_flakiness_score(scenario_id) >= threshold
    
    def get_flaky_scenarios(self, threshold: float = 0.3) -> list[str]:
        """
        Get list of flaky scenario IDs.
        
        Args:
            threshold: Flakiness threshold
        
        Returns:
            List of scenario IDs that are flaky
        """
        return [
            scenario_id
            for scenario_id in self._test_history.keys()
            if self.is_flaky(scenario_id, threshold)
        ]
    
    def get_statistics(self, scenario_id: str) -> dict:
        """
        Get detailed statistics for a scenario.
        
        Args:
            scenario_id: ID of the scenario
        
        Returns:
            Dictionary with statistics
        """
        if scenario_id not in self._test_history:
            return {
                "total_runs": 0,
                "passed_runs": 0,
                "failed_runs": 0,
                "flaky_count": 0,
                "pass_rate": 0.0,
                "avg_retry_count": 0.0,
                "flakiness_score": 0.0
            }
        
        history = self._test_history[scenario_id]
        retry_history = self._retry_history[scenario_id]
        
        total_runs = len(history)
        passed_runs = sum(history)
        failed_runs = total_runs - passed_runs
        flaky_count = self._flaky_count[scenario_id]
        pass_rate = passed_runs / total_runs if total_runs > 0 else 0.0
        avg_retry_count = sum(retry_history) / len(retry_history) if retry_history else 0.0
        
        return {
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "failed_runs": failed_runs,
            "flaky_count": flaky_count,
            "pass_rate": pass_rate,
            "avg_retry_count": avg_retry_count,
            "flakiness_score": self.get_flakiness_score(scenario_id)
        }
    
    def get_all_statistics(self) -> dict[str, dict]:
        """
        Get statistics for all tracked scenarios.
        
        Returns:
            Dictionary mapping scenario IDs to their statistics
        """
        return {
            scenario_id: self.get_statistics(scenario_id)
            for scenario_id in self._test_history.keys()
        }
    
    def clear_history(self, scenario_id: Optional[str] = None) -> None:
        """
        Clear tracking history.
        
        Args:
            scenario_id: Specific scenario to clear (None = clear all)
        """
        if scenario_id:
            self._test_history.pop(scenario_id, None)
            self._retry_history.pop(scenario_id, None)
            self._flaky_count.pop(scenario_id, None)
            logger.info(
                "scenario_history_cleared",
                extra={"scenario_id": scenario_id}
            )
        else:
            self._test_history.clear()
            self._retry_history.clear()
            self._flaky_count.clear()
            logger.info("all_history_cleared")


# ============================================================================
# Global Tracker Instance
# ============================================================================

_global_tracker: Optional[FlakyTestTracker] = None


def get_flaky_test_tracker() -> FlakyTestTracker:
    """
    Get the global flaky test tracker instance.
    
    Returns:
        FlakyTestTracker instance
    """
    global _global_tracker
    
    if _global_tracker is None:
        _global_tracker = FlakyTestTracker()
    
    return _global_tracker


# ============================================================================
# Utility Functions
# ============================================================================

def should_retry_on_timeout(exception: Exception) -> bool:
    """
    Determine if a timeout exception should trigger retry.
    
    Args:
        exception: The exception that occurred
    
    Returns:
        True if should retry
    """
    from app.core.exceptions import TimeoutException
    return isinstance(exception, TimeoutException)


def should_retry_on_element_not_found(exception: Exception) -> bool:
    """
    Determine if an element not found exception should trigger retry.
    
    Args:
        exception: The exception that occurred
    
    Returns:
        True if should retry
    """
    from app.core.exceptions import ElementNotFoundException
    return isinstance(exception, ElementNotFoundException)


def should_retry_on_any_execution_error(exception: Exception) -> bool:
    """
    Determine if any execution exception should trigger retry.
    
    Args:
        exception: The exception that occurred
    
    Returns:
        True if should retry
    """
    from app.core.exceptions import ExecutionException
    return isinstance(exception, ExecutionException)
