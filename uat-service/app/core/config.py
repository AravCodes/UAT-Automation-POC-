"""
Configuration management system with Pydantic.

This module provides environment variable validation and configuration management
for the UAT automation service. It implements fail-fast validation for required
configuration and provides sensible defaults for optional settings.

Requirements: 8.1, 8.2, 8.3, 8.5
"""

import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Determine the .env file path relative to this module
# This ensures the .env file is found regardless of where the script is run from
_current_dir = Path(__file__).parent.parent.parent  # Go up to uat-service directory
_env_file_path = _current_dir / ".env"


class Config(BaseSettings):
    """
    Main configuration class for UAT automation service.
    
    Loads configuration from environment variables with validation.
    Implements fail-fast validation for required settings.
    """
    
    model_config = SettingsConfigDict(
        env_file=str(_env_file_path),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ============================================================================
    # LLM Configuration (Required)
    # ============================================================================
    
    groq_api_key: str = Field(
        ...,
        description="Groq API key for LLM integration (required)"
    )
    
    model_primary: str = Field(
        default="llama-3.1-70b-versatile",
        description="Primary LLM model for story parsing and scenario generation"
    )
    
    model_fallback: str = Field(
        default="llama-3.1-8b-instant",
        description="Fallback LLM model when primary fails or is rate-limited"
    )
    
    llm_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="LLM request timeout in seconds"
    )
    
    llm_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for LLM API calls"
    )
    
    enable_legacy_nlp_fallback: bool = Field(
        default=True,
        description="Enable legacy NLP fallback when LLM unavailable"
    )
    
    # ============================================================================
    # Test Execution Configuration
    # ============================================================================
    
    concurrency: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of parallel test scenarios to execute"
    )
    
    test_timeout: int = Field(
        default=30000,
        ge=5000,
        le=300000,
        description="Test step timeout in milliseconds"
    )
    
    retry_attempts: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Number of retry attempts for failed tests"
    )
    
    retry_delay: int = Field(
        default=2000,
        ge=0,
        le=10000,
        description="Delay before retry in milliseconds"
    )
    
    headless_mode: bool = Field(
        default=True,
        description="Run browser in headless mode"
    )
    
    slow_mo: int = Field(
        default=0,
        ge=0,
        le=5000,
        description="Browser slow motion delay for debugging (milliseconds)"
    )
    
    screenshot_on_failure: bool = Field(
        default=True,
        description="Capture screenshot on test failure"
    )
    
    screenshot_on_step: bool = Field(
        default=False,
        description="Capture screenshot on every test step"
    )
    
    capture_console_logs: bool = Field(
        default=True,
        description="Capture console logs during test execution"
    )
    
    capture_network: bool = Field(
        default=True,
        description="Capture network requests during test execution"
    )
    
    # ============================================================================
    # Element Finding Configuration
    # ============================================================================
    
    fuzzy_match_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Fuzzy matching similarity threshold"
    )
    
    enable_llm_selector_suggestions: bool = Field(
        default=True,
        description="Enable LLM-powered selector suggestions"
    )
    
    element_wait_timeout: int = Field(
        default=10000,
        ge=1000,
        le=60000,
        description="Maximum wait time for element to appear (milliseconds)"
    )
    
    element_poll_interval: int = Field(
        default=100,
        ge=50,
        le=1000,
        description="Polling interval for element checks (milliseconds)"
    )
    
    # ============================================================================
    # Sample Application Configuration
    # ============================================================================
    
    sample_app_url: str = Field(
        default="http://localhost:5173",
        description="Sample application URL for testing"
    )
    
    sample_app_api_url: str = Field(
        default="http://localhost:3000",
        description="Sample app backend URL"
    )
    
    # ============================================================================
    # Database Configuration
    # ============================================================================
    
    database_url: str = Field(
        default="sqlite:///./uat_service.db",
        description="Database connection URL"
    )
    
    database_echo: bool = Field(
        default=False,
        description="Enable database query logging"
    )
    
    database_pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Database connection pool size (PostgreSQL only)"
    )
    
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Database connection pool max overflow (PostgreSQL only)"
    )
    
    # ============================================================================
    # Cache Configuration (Redis)
    # ============================================================================
    
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis URL for caching"
    )
    
    redis_db: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Redis database number"
    )
    
    cache_dom_ttl: int = Field(
        default=3600,
        ge=60,
        description="Cache TTL for DOM analysis (seconds)"
    )
    
    cache_llm_ttl: int = Field(
        default=86400,
        ge=60,
        description="Cache TTL for LLM responses (seconds)"
    )
    
    enable_cache: bool = Field(
        default=True,
        description="Enable caching"
    )
    
    # ============================================================================
    # API Configuration
    # ============================================================================
    
    api_host: str = Field(
        default="0.0.0.0",
        description="API host"
    )
    
    api_port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="API port"
    )
    
    api_key_header: str = Field(
        default="X-API-Key",
        description="API key header name"
    )
    
    api_keys: str = Field(
        default="",
        description="API keys for authentication (comma-separated)"
    )
    
    enable_cors: bool = Field(
        default=True,
        description="Enable CORS"
    )
    
    cors_origins: str = Field(
        default="*",
        description="CORS allowed origins (comma-separated)"
    )
    
    enable_api_docs: bool = Field(
        default=True,
        description="Enable API documentation at /docs"
    )
    
    # ============================================================================
    # Webhook Configuration
    # ============================================================================
    
    enable_webhooks: bool = Field(
        default=True,
        description="Enable webhook notifications"
    )
    
    webhook_timeout: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Webhook timeout in seconds"
    )
    
    webhook_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Webhook retry attempts"
    )
    
    # ============================================================================
    # Reporting Configuration
    # ============================================================================
    
    default_report_format: Literal["html", "json", "pdf"] = Field(
        default="html",
        description="Default report format"
    )
    
    enable_pdf_reports: bool = Field(
        default=False,
        description="Enable PDF report generation"
    )
    
    report_retention_days: int = Field(
        default=30,
        ge=0,
        description="Report retention days (0 = keep forever)"
    )
    
    artifacts_dir: str = Field(
        default="./artifacts",
        description="Artifacts directory"
    )
    
    max_artifact_size_mb: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum artifact size in MB"
    )
    
    # ============================================================================
    # Logging Configuration
    # ============================================================================
    
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Log level"
    )
    
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log format"
    )
    
    log_file: str = Field(
        default="",
        description="Log file path (empty = stdout only)"
    )
    
    log_requests: bool = Field(
        default=True,
        description="Enable request/response logging"
    )
    
    # ============================================================================
    # Performance Configuration
    # ============================================================================
    
    enable_metrics: bool = Field(
        default=True,
        description="Enable performance metrics collection"
    )
    
    metrics_interval: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Metrics export interval in seconds"
    )
    
    enable_tracing: bool = Field(
        default=False,
        description="Enable distributed tracing"
    )
    
    tracing_url: str = Field(
        default="",
        description="Tracing service URL (Jaeger, Zipkin, etc.)"
    )
    
    # ============================================================================
    # Feature Flags
    # ============================================================================
    
    enable_experimental_features: bool = Field(
        default=False,
        description="Enable experimental features"
    )
    
    enable_flaky_test_detection: bool = Field(
        default=True,
        description="Enable flaky test detection"
    )
    
    enable_analytics: bool = Field(
        default=True,
        description="Enable analytics and trend analysis"
    )
    
    enable_multi_tenant: bool = Field(
        default=False,
        description="Enable multi-tenant support"
    )
    
    # ============================================================================
    # Development Configuration
    # ============================================================================
    
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Environment"
    )
    
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    hot_reload: bool = Field(
        default=True,
        description="Enable hot reload"
    )
    
    enable_profiling: bool = Field(
        default=False,
        description="Enable profiling"
    )
    
    # ============================================================================
    # Integration Configuration
    # ============================================================================
    
    jira_url: str = Field(
        default="",
        description="Jira URL"
    )
    
    jira_username: str = Field(
        default="",
        description="Jira username"
    )
    
    jira_api_token: str = Field(
        default="",
        description="Jira API token"
    )
    
    enable_jira_integration: bool = Field(
        default=False,
        description="Enable Jira integration"
    )
    
    azure_devops_org: str = Field(
        default="",
        description="Azure DevOps organization"
    )
    
    azure_devops_project: str = Field(
        default="",
        description="Azure DevOps project"
    )
    
    azure_devops_pat: str = Field(
        default="",
        description="Azure DevOps personal access token"
    )
    
    enable_azure_devops_integration: bool = Field(
        default=False,
        description="Enable Azure DevOps integration"
    )
    
    slack_webhook_url: str = Field(
        default="",
        description="Slack webhook URL"
    )
    
    enable_slack_notifications: bool = Field(
        default=False,
        description="Enable Slack notifications"
    )
    
    # ============================================================================
    # Security Configuration
    # ============================================================================
    
    enable_rate_limiting: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    
    rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Rate limit: requests per minute"
    )
    
    enable_request_validation: bool = Field(
        default=True,
        description="Enable request validation"
    )
    
    max_request_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum request body size in MB"
    )
    
    enable_audit_log: bool = Field(
        default=True,
        description="Enable audit logging"
    )
    
    # ============================================================================
    # Validators
    # ============================================================================
    
    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_api_key(cls, v: str) -> str:
        """
        Validate that GROQ_API_KEY is set and not a placeholder.
        Implements fail-fast validation for required configuration.
        """
        if not v or v.strip() == "":
            raise ValueError(
                "GROQ_API_KEY is required. "
                "Get your free API key from: https://console.groq.com/keys"
            )
        
        if v == "your_api_key_here":
            raise ValueError(
                "GROQ_API_KEY must be set to a valid API key. "
                "Replace 'your_api_key_here' with your actual Groq API key."
            )
        
        return v.strip()
    
    @field_validator("model_primary", "model_fallback")
    @classmethod
    def validate_model_names(cls, v: str) -> str:
        """Validate that model names are not empty."""
        if not v or v.strip() == "":
            raise ValueError("Model name cannot be empty")
        return v.strip()
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v or v.strip() == "":
            raise ValueError("DATABASE_URL cannot be empty")
        
        v = v.strip()
        
        # Basic validation for supported database types
        if not (v.startswith("sqlite://") or v.startswith("postgresql://")):
            raise ValueError(
                "DATABASE_URL must start with 'sqlite://' or 'postgresql://'"
            )
        
        return v
    
    @field_validator("sample_app_url", "sample_app_api_url")
    @classmethod
    def validate_urls(cls, v: str) -> str:
        """Validate URL format."""
        if not v or v.strip() == "":
            raise ValueError("URL cannot be empty")
        
        v = v.strip()
        
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with 'http://' or 'https://'")
        
        return v
    
    @model_validator(mode="after")
    def validate_configuration(self) -> "Config":
        """
        Perform cross-field validation and consistency checks.
        Implements fail-fast validation for configuration consistency.
        """
        # Validate concurrency is reasonable for the system
        if self.concurrency > 10:
            raise ValueError(
                f"CONCURRENCY={self.concurrency} is too high. "
                "Maximum recommended value is 10 for system stability."
            )
        
        # Validate timeout values are reasonable
        if self.test_timeout < 5000:
            raise ValueError(
                f"TEST_TIMEOUT={self.test_timeout}ms is too low. "
                "Minimum recommended value is 5000ms (5 seconds)."
            )
        
        # Validate retry configuration
        if self.retry_attempts > 0 and self.retry_delay == 0:
            raise ValueError(
                "RETRY_DELAY must be greater than 0 when RETRY_ATTEMPTS > 0"
            )
        
        # Validate Jira integration configuration
        if self.enable_jira_integration:
            if not self.jira_url or not self.jira_username or not self.jira_api_token:
                raise ValueError(
                    "JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN are required "
                    "when ENABLE_JIRA_INTEGRATION=true"
                )
        
        # Validate Azure DevOps integration configuration
        if self.enable_azure_devops_integration:
            if not self.azure_devops_org or not self.azure_devops_project or not self.azure_devops_pat:
                raise ValueError(
                    "AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, and AZURE_DEVOPS_PAT "
                    "are required when ENABLE_AZURE_DEVOPS_INTEGRATION=true"
                )
        
        # Validate Slack integration configuration
        if self.enable_slack_notifications:
            if not self.slack_webhook_url:
                raise ValueError(
                    "SLACK_WEBHOOK_URL is required when ENABLE_SLACK_NOTIFICATIONS=true"
                )
        
        # Validate tracing configuration
        if self.enable_tracing:
            if not self.tracing_url:
                raise ValueError(
                    "TRACING_URL is required when ENABLE_TRACING=true"
                )
        
        return self
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def get_api_keys_list(self) -> list[str]:
        """Parse comma-separated API keys into a list."""
        if not self.api_keys:
            return []
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]
    
    def get_cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment == "staging"


# Global configuration instance
# This will be initialized when the module is imported
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    This function implements lazy initialization and caching of the configuration.
    The configuration is loaded once and reused across the application.
    
    Returns:
        Config: The global configuration instance
        
    Raises:
        ValueError: If configuration validation fails (fail-fast behavior)
    """
    global _config
    
    if _config is None:
        _config = Config()
    
    return _config


def reload_config() -> Config:
    """
    Reload the configuration from environment variables.
    
    This is useful for testing or when configuration needs to be refreshed.
    
    Returns:
        Config: The newly loaded configuration instance
        
    Raises:
        ValueError: If configuration validation fails (fail-fast behavior)
    """
    global _config
    _config = Config()
    return _config
