"""
Structured logging setup for UAT automation service.

This module provides a comprehensive logging system with structured output,
context management, and integration with the configuration system.
"""

import logging
import sys
import json
from typing import Any, Optional
from datetime import datetime
from pathlib import Path
import traceback

from .config import get_config
from .exceptions import UATServiceException


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in structured JSON format.
    
    This formatter converts log records into JSON objects with consistent
    structure, making them easy to parse and analyze.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON-formatted log string
        """
        # Base log structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from the record
        # These are added via logger.info("message", extra={...})
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add any custom attributes that were added to the record
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
                "extra_fields"
            ]:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


class TextFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in human-readable text format.
    
    This formatter is useful for development and debugging.
    """
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as text.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log string
        """
        # Format the base message
        result = super().format(record)
        
        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            extra_str = " | ".join(
                f"{k}={v}" for k, v in record.extra_fields.items()
            )
            result += f" | {extra_str}"
        
        # Add exception information if present
        if record.exc_info:
            result += "\n" + "".join(traceback.format_exception(*record.exc_info))
        
        return result


class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that adds contextual information to all log messages.
    
    This allows adding request IDs, user IDs, or other context that should
    be included in all logs within a specific scope.
    """
    
    def __init__(self, logger: logging.Logger, extra: Optional[dict[str, Any]] = None):
        """
        Initialize the context logger.
        
        Args:
            logger: The underlying logger
            extra: Additional context to include in all logs
        """
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """
        Process the log message and add context.
        
        Args:
            msg: The log message
            kwargs: Additional keyword arguments
            
        Returns:
            Tuple of (message, kwargs) with context added
        """
        # Merge extra fields from both the adapter and the log call
        extra_fields = {}
        extra_fields.update(self.extra)
        
        if "extra" in kwargs:
            extra_fields.update(kwargs["extra"])
        
        # Store extra fields in a way that our formatter can access them
        if extra_fields:
            kwargs["extra"] = {"extra_fields": extra_fields}
        
        return msg, kwargs


def setup_logging() -> logging.Logger:
    """
    Set up the logging system based on configuration.
    
    This function configures the root logger with appropriate handlers,
    formatters, and log levels based on the application configuration.
    
    Returns:
        The configured root logger
    """
    config = get_config()
    
    # Get or create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))
    
    # Remove any existing handlers
    root_logger.handlers.clear()
    
    # Choose formatter based on configuration
    if config.log_format == "json":
        formatter = StructuredFormatter()
    else:
        formatter = TextFormatter()
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.log_level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if configured)
    if config.log_file:
        log_file_path = Path(config.log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setLevel(getattr(logging, config.log_level))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Log the logging configuration
    root_logger.info(
        "Logging system initialized",
        extra={
            "extra_fields": {
                "log_level": config.log_level,
                "log_format": config.log_format,
                "log_file": config.log_file or "stdout only"
            }
        }
    )
    
    return root_logger


def get_logger(name: str, **context) -> ContextLogger:
    """
    Get a logger with optional context.
    
    This is the recommended way to get a logger in the application.
    It returns a ContextLogger that can include additional context
    in all log messages.
    
    Args:
        name: The logger name (typically __name__)
        **context: Additional context to include in all logs
        
    Returns:
        A ContextLogger instance
        
    Example:
        logger = get_logger(__name__, request_id="abc123")
        logger.info("Processing request")
        # Output includes request_id in all logs
    """
    base_logger = logging.getLogger(name)
    return ContextLogger(base_logger, context)


def log_exception(
    logger: logging.Logger,
    exception: Exception,
    message: str = "An error occurred",
    **extra_context
) -> None:
    """
    Log an exception with full context.
    
    This function provides a consistent way to log exceptions throughout
    the application, including structured error information.
    
    Args:
        logger: The logger to use
        exception: The exception to log
        message: A descriptive message about the error
        **extra_context: Additional context to include in the log
    """
    extra_fields = extra_context.copy()
    
    # Add exception details
    extra_fields["exception_type"] = type(exception).__name__
    extra_fields["exception_message"] = str(exception)
    
    # Add structured details for UATServiceException
    if isinstance(exception, UATServiceException):
        extra_fields.update(exception.to_dict())
    
    logger.error(
        message,
        exc_info=True,
        extra={"extra_fields": extra_fields}
    )


def log_test_step(
    logger: logging.Logger,
    run_id: str,
    scenario_id: str,
    step_index: int,
    action: str,
    status: str,
    duration_ms: int,
    **extra_context
) -> None:
    """
    Log a test step execution with structured data.
    
    This provides consistent logging for test execution steps,
    making it easy to track and analyze test runs.
    
    Args:
        logger: The logger to use
        run_id: The test run ID
        scenario_id: The scenario ID
        step_index: The step index
        action: The action performed
        status: The step status (passed, failed, skipped)
        duration_ms: The step duration in milliseconds
        **extra_context: Additional context to include
    """
    extra_fields = {
        "event_type": "test_step_executed",
        "run_id": run_id,
        "scenario_id": scenario_id,
        "step_index": step_index,
        "action": action,
        "status": status,
        "duration_ms": duration_ms
    }
    extra_fields.update(extra_context)
    
    logger.info(
        f"Test step {step_index}: {action} - {status}",
        extra={"extra_fields": extra_fields}
    )


def log_llm_request(
    logger: logging.Logger,
    model: str,
    prompt_type: str,
    tokens_used: Optional[int] = None,
    duration_ms: Optional[int] = None,
    success: bool = True,
    **extra_context
) -> None:
    """
    Log an LLM API request with structured data.
    
    This provides consistent logging for LLM interactions,
    useful for monitoring API usage and performance.
    
    Args:
        logger: The logger to use
        model: The model used
        prompt_type: The type of prompt (story_parsing, scenario_generation, etc.)
        tokens_used: Number of tokens used (if available)
        duration_ms: Request duration in milliseconds
        success: Whether the request succeeded
        **extra_context: Additional context to include
    """
    extra_fields = {
        "event_type": "llm_request",
        "model": model,
        "prompt_type": prompt_type,
        "success": success
    }
    
    if tokens_used is not None:
        extra_fields["tokens_used"] = tokens_used
    
    if duration_ms is not None:
        extra_fields["duration_ms"] = duration_ms
    
    extra_fields.update(extra_context)
    
    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        f"LLM request: {prompt_type} using {model} - {'success' if success else 'failed'}",
        extra={"extra_fields": extra_fields}
    )


def log_api_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    **extra_context
) -> None:
    """
    Log an API request with structured data.
    
    This provides consistent logging for API requests,
    useful for monitoring and debugging.
    
    Args:
        logger: The logger to use
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **extra_context: Additional context to include
    """
    extra_fields = {
        "event_type": "api_request",
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms
    }
    extra_fields.update(extra_context)
    
    # Choose log level based on status code
    if status_code < 400:
        level = logging.INFO
    elif status_code < 500:
        level = logging.WARNING
    else:
        level = logging.ERROR
    
    logger.log(
        level,
        f"{method} {path} - {status_code}",
        extra={"extra_fields": extra_fields}
    )


# Initialize logging when module is imported
# This ensures logging is set up before any other code runs
try:
    setup_logging()
except Exception as e:
    # Fallback to basic logging if setup fails
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logging.error(f"Failed to set up structured logging: {e}", exc_info=True)
