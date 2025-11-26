"""
Test execution engine module.

This module provides the complete test execution infrastructure including:
- Playwright browser management
- Parallel test execution with configurable concurrency
- Comprehensive diagnostics capture (screenshots, logs, network)
- Smart retry logic and flaky test detection

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

from .playwright_wrapper import (
    PlaywrightWrapper,
    BrowserType,
    create_playwright_wrapper
)
from .test_runner import (
    TestRunner,
    TestContext,
    ExecutionConfig
)
from .diagnostics import (
    DiagnosticsCapture,
    NetworkCapture,
    ConsoleCapture,
    TimelineEvent,
    create_diagnostics_capture
)
from .retry_handler import (
    RetryHandler,
    RetryConfig,
    RetryResult,
    RetryAttempt,
    FlakyTestTracker,
    get_flaky_test_tracker,
    should_retry_on_timeout,
    should_retry_on_element_not_found,
    should_retry_on_any_execution_error
)


__all__ = [
    # Playwright wrapper
    "PlaywrightWrapper",
    "BrowserType",
    "create_playwright_wrapper",
    
    # Test runner
    "TestRunner",
    "TestContext",
    "ExecutionConfig",
    
    # Diagnostics
    "DiagnosticsCapture",
    "NetworkCapture",
    "ConsoleCapture",
    "TimelineEvent",
    "create_diagnostics_capture",
    
    # Retry and flaky test detection
    "RetryHandler",
    "RetryConfig",
    "RetryResult",
    "RetryAttempt",
    "FlakyTestTracker",
    "get_flaky_test_tracker",
    "should_retry_on_timeout",
    "should_retry_on_element_not_found",
    "should_retry_on_any_execution_error",
]
