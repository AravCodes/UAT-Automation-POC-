"""
Custom exception hierarchy for UAT automation service.

This module defines a comprehensive exception hierarchy that provides
clear error categorization and handling throughout the application.

Requirements: 1.5
"""

from typing import Optional, Any


class UATServiceException(Exception):
    """
    Base exception for all UAT service errors.
    
    All custom exceptions in the UAT service should inherit from this class.
    This allows for centralized exception handling and logging.
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message
            details: Additional context about the error
            original_exception: The original exception if this is a wrapped error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/API responses."""
        result = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }
        
        if self.original_exception:
            result["original_error"] = str(self.original_exception)
        
        return result


# ============================================================================
# LLM-Related Exceptions
# ============================================================================

class LLMException(UATServiceException):
    """Base exception for LLM-related errors."""
    pass


class GroqAPIException(LLMException):
    """Exception raised when Groq API calls fail."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if status_code:
            details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body
        
        super().__init__(message, details=details, **kwargs)
        self.status_code = status_code
        self.response_body = response_body


class RateLimitException(LLMException):
    """
    Exception raised when API rate limits are exceeded.
    
    This exception triggers the rate limiting and queuing mechanism.
    """
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if retry_after:
            details["retry_after_seconds"] = retry_after
        
        super().__init__(message, details=details, **kwargs)
        self.retry_after = retry_after


class LLMTimeoutException(LLMException):
    """Exception raised when LLM API calls timeout."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        
        super().__init__(message, details=details, **kwargs)
        self.timeout_seconds = timeout_seconds


class LLMResponseValidationException(LLMException):
    """
    Exception raised when LLM response fails schema validation.
    
    This indicates the LLM returned data that doesn't match expected format.
    """
    
    def __init__(
        self,
        message: str,
        response: Optional[str] = None,
        validation_errors: Optional[list] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if response:
            details["response"] = response
        if validation_errors:
            details["validation_errors"] = validation_errors
        
        super().__init__(message, details=details, **kwargs)
        self.response = response
        self.validation_errors = validation_errors


class ModelNotAvailableException(LLMException):
    """Exception raised when requested LLM model is not available."""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if model_name:
            details["model_name"] = model_name
        
        super().__init__(message, details=details, **kwargs)
        self.model_name = model_name


# ============================================================================
# Parsing-Related Exceptions
# ============================================================================

class ParsingException(UATServiceException):
    """Base exception for story parsing failures."""
    pass


class InvalidStoryFormatException(ParsingException):
    """Exception raised when user story format is invalid or incomplete."""
    
    def __init__(
        self,
        message: str,
        story_text: Optional[str] = None,
        missing_fields: Optional[list[str]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if story_text:
            details["story_text"] = story_text
        if missing_fields:
            details["missing_fields"] = missing_fields
        
        super().__init__(message, details=details, **kwargs)
        self.story_text = story_text
        self.missing_fields = missing_fields


class ScenarioGenerationException(ParsingException):
    """Exception raised when test scenario generation fails."""
    
    def __init__(
        self,
        message: str,
        acceptance_criterion: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if acceptance_criterion:
            details["acceptance_criterion"] = acceptance_criterion
        
        super().__init__(message, details=details, **kwargs)
        self.acceptance_criterion = acceptance_criterion


class ValidationException(ParsingException):
    """Exception raised when parsed data fails validation."""
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[list] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if validation_errors:
            details["validation_errors"] = validation_errors
        
        super().__init__(message, details=details, **kwargs)
        self.validation_errors = validation_errors


# ============================================================================
# Test Execution Exceptions
# ============================================================================

class ExecutionException(UATServiceException):
    """Base exception for test execution failures."""
    pass


class BrowserException(ExecutionException):
    """Exception raised when browser operations fail."""
    
    def __init__(
        self,
        message: str,
        browser_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if browser_type:
            details["browser_type"] = browser_type
        
        super().__init__(message, details=details, **kwargs)
        self.browser_type = browser_type


class ElementNotFoundException(ExecutionException):
    """
    Exception raised when element cannot be found on page.
    
    This exception triggers alternative selector suggestions via LLM.
    """
    
    def __init__(
        self,
        message: str,
        element_description: Optional[str] = None,
        page_url: Optional[str] = None,
        strategies_tried: Optional[list[str]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if element_description:
            details["element_description"] = element_description
        if page_url:
            details["page_url"] = page_url
        if strategies_tried:
            details["strategies_tried"] = strategies_tried
        
        super().__init__(message, details=details, **kwargs)
        self.element_description = element_description
        self.page_url = page_url
        self.strategies_tried = strategies_tried


class TimeoutException(ExecutionException):
    """Exception raised when test step times out."""
    
    def __init__(
        self,
        message: str,
        timeout_ms: Optional[int] = None,
        step_description: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if timeout_ms:
            details["timeout_ms"] = timeout_ms
        if step_description:
            details["step_description"] = step_description
        
        super().__init__(message, details=details, **kwargs)
        self.timeout_ms = timeout_ms
        self.step_description = step_description


class AssertionFailedException(ExecutionException):
    """Exception raised when test assertion fails."""
    
    def __init__(
        self,
        message: str,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
        assertion_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if expected is not None:
            details["expected"] = str(expected)
        if actual is not None:
            details["actual"] = str(actual)
        if assertion_type:
            details["assertion_type"] = assertion_type
        
        super().__init__(message, details=details, **kwargs)
        self.expected = expected
        self.actual = actual
        self.assertion_type = assertion_type


class NavigationException(ExecutionException):
    """Exception raised when page navigation fails."""
    
    def __init__(
        self,
        message: str,
        target_url: Optional[str] = None,
        current_url: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if target_url:
            details["target_url"] = target_url
        if current_url:
            details["current_url"] = current_url
        
        super().__init__(message, details=details, **kwargs)
        self.target_url = target_url
        self.current_url = current_url


class TestContextException(ExecutionException):
    """Exception raised when test context is invalid or corrupted."""
    pass


# ============================================================================
# Storage and Database Exceptions
# ============================================================================

class StorageException(UATServiceException):
    """Base exception for storage-related errors."""
    pass


class DatabaseException(StorageException):
    """Exception raised when database operations fail."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if operation:
            details["operation"] = operation
        
        super().__init__(message, details=details, **kwargs)
        self.operation = operation


class CacheException(StorageException):
    """Exception raised when cache operations fail."""
    
    def __init__(
        self,
        message: str,
        cache_key: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if cache_key:
            details["cache_key"] = cache_key
        
        super().__init__(message, details=details, **kwargs)
        self.cache_key = cache_key


class FileStorageException(StorageException):
    """Exception raised when file storage operations fail."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if file_path:
            details["file_path"] = file_path
        if operation:
            details["operation"] = operation
        
        super().__init__(message, details=details, **kwargs)
        self.file_path = file_path
        self.operation = operation


# ============================================================================
# Reporting Exceptions
# ============================================================================

class ReportingException(UATServiceException):
    """Base exception for reporting-related errors."""
    pass


class ReportGenerationException(ReportingException):
    """Exception raised when report generation fails."""
    
    def __init__(
        self,
        message: str,
        report_format: Optional[str] = None,
        run_id: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if report_format:
            details["report_format"] = report_format
        if run_id:
            details["run_id"] = run_id
        
        super().__init__(message, details=details, **kwargs)
        self.report_format = report_format
        self.run_id = run_id


class TemplateException(ReportingException):
    """Exception raised when template rendering fails."""
    
    def __init__(
        self,
        message: str,
        template_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if template_name:
            details["template_name"] = template_name
        
        super().__init__(message, details=details, **kwargs)
        self.template_name = template_name


# ============================================================================
# Configuration Exceptions
# ============================================================================

class ConfigurationException(UATServiceException):
    """Exception raised when configuration is invalid or missing."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if config_key:
            details["config_key"] = config_key
        
        super().__init__(message, details=details, **kwargs)
        self.config_key = config_key


# ============================================================================
# API and Integration Exceptions
# ============================================================================

class APIException(UATServiceException):
    """Base exception for API-related errors."""
    pass


class AuthenticationException(APIException):
    """Exception raised when authentication fails."""
    pass


class AuthorizationException(APIException):
    """Exception raised when authorization fails."""
    pass


class WebhookException(APIException):
    """Exception raised when webhook delivery fails."""
    
    def __init__(
        self,
        message: str,
        webhook_url: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if webhook_url:
            details["webhook_url"] = webhook_url
        if status_code:
            details["status_code"] = status_code
        
        super().__init__(message, details=details, **kwargs)
        self.webhook_url = webhook_url
        self.status_code = status_code


class IntegrationException(APIException):
    """Exception raised when external integration fails."""
    
    def __init__(
        self,
        message: str,
        integration_name: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if integration_name:
            details["integration_name"] = integration_name
        
        super().__init__(message, details=details, **kwargs)
        self.integration_name = integration_name
