"""
Core module for UAT Automation Service V2.

This module contains core functionality including:
- Configuration management
- Exception hierarchy
- Logging setup
- Dependency injection
"""

from .config import Config, get_config, reload_config
from .exceptions import (
    UATServiceException,
    LLMException,
    GroqAPIException,
    RateLimitException,
    LLMTimeoutException,
    LLMResponseValidationException,
    ModelNotAvailableException,
    ParsingException,
    InvalidStoryFormatException,
    ScenarioGenerationException,
    ValidationException,
    ExecutionException,
    BrowserException,
    ElementNotFoundException,
    TimeoutException,
    AssertionFailedException,
    NavigationException,
    TestContextException,
    StorageException,
    DatabaseException,
    CacheException,
    FileStorageException,
    ReportingException,
    ReportGenerationException,
    TemplateException,
    ConfigurationException,
    APIException,
    AuthenticationException,
    AuthorizationException,
    WebhookException,
    IntegrationException,
)
from .logging import (
    setup_logging,
    get_logger,
    log_exception,
    log_test_step,
    log_llm_request,
    log_api_request,
    ContextLogger,
)
from .dependencies import (
    get_app_config,
    verify_api_key,
    optional_api_key,
    get_request_id,
    get_pagination_params,
    ConfigDep,
    ApiKeyDep,
    OptionalApiKeyDep,
    RequestIdDep,
    PaginationDep,
)

__all__ = [
    # Config
    "Config",
    "get_config",
    "reload_config",
    # Exceptions
    "UATServiceException",
    "LLMException",
    "GroqAPIException",
    "RateLimitException",
    "LLMTimeoutException",
    "LLMResponseValidationException",
    "ModelNotAvailableException",
    "ParsingException",
    "InvalidStoryFormatException",
    "ScenarioGenerationException",
    "ValidationException",
    "ExecutionException",
    "BrowserException",
    "ElementNotFoundException",
    "TimeoutException",
    "AssertionFailedException",
    "NavigationException",
    "TestContextException",
    "StorageException",
    "DatabaseException",
    "CacheException",
    "FileStorageException",
    "ReportingException",
    "ReportGenerationException",
    "TemplateException",
    "ConfigurationException",
    "APIException",
    "AuthenticationException",
    "AuthorizationException",
    "WebhookException",
    "IntegrationException",
    # Logging
    "setup_logging",
    "get_logger",
    "log_exception",
    "log_test_step",
    "log_llm_request",
    "log_api_request",
    "ContextLogger",
    # Dependencies
    "get_app_config",
    "verify_api_key",
    "optional_api_key",
    "get_request_id",
    "get_pagination_params",
    "ConfigDep",
    "ApiKeyDep",
    "OptionalApiKeyDep",
    "RequestIdDep",
    "PaginationDep",
]
