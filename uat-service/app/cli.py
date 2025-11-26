"""
CLI support for UAT Automation Service.

This module provides command-line interface support for running the UAT service
with environment overrides and legacy mode support.

Requirements: 7.6, 8.6
"""

import argparse
import sys
import os
from typing import Optional
import uvicorn
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for UAT service configuration.
    
    Returns:
        Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="UAT Automation Service - LLM-Powered Test Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start service with default configuration
  python -m app.cli

  # Override concurrency and headless mode
  python -m app.cli --concurrency 5 --headless false

  # Run in legacy mode (V1 NLP)
  python -m app.cli --legacy

  # Override multiple settings
  python -m app.cli --port 9000 --log-level DEBUG --concurrency 3

  # Production mode
  python -m app.cli --environment production --headless true --debug false

Environment Variables:
  All configuration can also be set via environment variables.
  CLI arguments take precedence over environment variables.
  See .env.example for complete list of environment variables.
        """
    )
    
    # Server Configuration
    server_group = parser.add_argument_group("Server Configuration")
    server_group.add_argument(
        "--host",
        type=str,
        help="API host (default: 0.0.0.0)"
    )
    server_group.add_argument(
        "--port",
        type=int,
        help="API port (default: 8000)"
    )
    server_group.add_argument(
        "--reload",
        action="store_true",
        help="Enable hot reload for development"
    )
    
    # LLM Configuration
    llm_group = parser.add_argument_group("LLM Configuration")
    llm_group.add_argument(
        "--groq-api-key",
        type=str,
        help="Groq API key (overrides GROQ_API_KEY env var)"
    )
    llm_group.add_argument(
        "--model-primary",
        type=str,
        choices=["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        help="Primary LLM model"
    )
    llm_group.add_argument(
        "--model-fallback",
        type=str,
        choices=["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        help="Fallback LLM model"
    )
    
    # Test Execution Configuration
    exec_group = parser.add_argument_group("Test Execution Configuration")
    exec_group.add_argument(
        "--concurrency",
        type=int,
        choices=range(1, 11),
        metavar="[1-10]",
        help="Number of parallel test scenarios (1-10)"
    )
    exec_group.add_argument(
        "--test-timeout",
        type=int,
        help="Test step timeout in milliseconds"
    )
    exec_group.add_argument(
        "--headless",
        type=str,
        choices=["true", "false"],
        help="Run browser in headless mode"
    )
    exec_group.add_argument(
        "--slow-mo",
        type=int,
        help="Browser slow motion delay for debugging (milliseconds)"
    )
    exec_group.add_argument(
        "--retry-attempts",
        type=int,
        choices=range(0, 6),
        metavar="[0-5]",
        help="Number of retry attempts for failed tests (0-5)"
    )
    
    # Sample Application Configuration
    app_group = parser.add_argument_group("Sample Application Configuration")
    app_group.add_argument(
        "--sample-app-url",
        type=str,
        help="Sample application URL for testing"
    )
    
    # Database Configuration
    db_group = parser.add_argument_group("Database Configuration")
    db_group.add_argument(
        "--database-url",
        type=str,
        help="Database connection URL"
    )
    
    # Cache Configuration
    cache_group = parser.add_argument_group("Cache Configuration")
    cache_group.add_argument(
        "--redis-url",
        type=str,
        help="Redis URL for caching"
    )
    cache_group.add_argument(
        "--enable-cache",
        type=str,
        choices=["true", "false"],
        help="Enable caching"
    )
    
    # Logging Configuration
    log_group = parser.add_argument_group("Logging Configuration")
    log_group.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level"
    )
    log_group.add_argument(
        "--log-format",
        type=str,
        choices=["json", "text"],
        help="Log format"
    )
    
    # Environment Configuration
    env_group = parser.add_argument_group("Environment Configuration")
    env_group.add_argument(
        "--environment",
        type=str,
        choices=["development", "staging", "production"],
        help="Environment"
    )
    env_group.add_argument(
        "--debug",
        type=str,
        choices=["true", "false"],
        help="Enable debug mode"
    )
    
    # Legacy Mode
    legacy_group = parser.add_argument_group("Legacy Mode")
    legacy_group.add_argument(
        "--legacy",
        action="store_true",
        help="Run in legacy mode (V1 NLP-based implementation)"
    )
    
    # Version
    parser.add_argument(
        "--version",
        action="version",
        version="UAT Automation Service v2.0.0"
    )
    
    return parser.parse_args()


def apply_cli_overrides(args: argparse.Namespace) -> None:
    """
    Apply CLI argument overrides to environment variables.
    
    CLI arguments take precedence over existing environment variables.
    
    Args:
        args: Parsed command-line arguments
    """
    # Server Configuration
    if args.host:
        os.environ["API_HOST"] = args.host
    if args.port:
        os.environ["API_PORT"] = str(args.port)
    
    # LLM Configuration
    if args.groq_api_key:
        os.environ["GROQ_API_KEY"] = args.groq_api_key
    if args.model_primary:
        os.environ["MODEL_PRIMARY"] = args.model_primary
    if args.model_fallback:
        os.environ["MODEL_FALLBACK"] = args.model_fallback
    
    # Test Execution Configuration
    if args.concurrency:
        os.environ["CONCURRENCY"] = str(args.concurrency)
    if args.test_timeout:
        os.environ["TEST_TIMEOUT"] = str(args.test_timeout)
    if args.headless:
        os.environ["HEADLESS_MODE"] = args.headless
    if args.slow_mo is not None:
        os.environ["SLOW_MO"] = str(args.slow_mo)
    if args.retry_attempts is not None:
        os.environ["RETRY_ATTEMPTS"] = str(args.retry_attempts)
    
    # Sample Application Configuration
    if args.sample_app_url:
        os.environ["SAMPLE_APP_URL"] = args.sample_app_url
    
    # Database Configuration
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    
    # Cache Configuration
    if args.redis_url:
        os.environ["REDIS_URL"] = args.redis_url
    if args.enable_cache:
        os.environ["ENABLE_CACHE"] = args.enable_cache
    
    # Logging Configuration
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level
    if args.log_format:
        os.environ["LOG_FORMAT"] = args.log_format
    
    # Environment Configuration
    if args.environment:
        os.environ["ENVIRONMENT"] = args.environment
    if args.debug:
        os.environ["DEBUG"] = args.debug
    
    # Legacy Mode
    if args.legacy:
        os.environ["ENABLE_LEGACY_MODE"] = "true"
        print("=" * 70)
        print("LEGACY MODE ENABLED")
        print("=" * 70)
        print("Running V1 NLP-based implementation from archive/v1-nlp-poc/")
        print("This mode uses rule-based NLP parsing instead of LLM.")
        print("For comparison and backward compatibility testing only.")
        print("=" * 70)
        print()


def run_legacy_mode() -> None:
    """
    Run the legacy V1 NLP-based implementation.
    
    This loads the archived V1 code for backward compatibility testing.
    """
    # Check if legacy code exists
    legacy_path = Path("archive/v1-nlp-poc")
    if not legacy_path.exists():
        print("ERROR: Legacy code not found at archive/v1-nlp-poc/")
        print("The V1 NLP-based implementation has not been archived yet.")
        sys.exit(1)
    
    # Add legacy path to Python path
    sys.path.insert(0, str(legacy_path))
    
    try:
        # Import and run legacy main
        from app.main import app as legacy_app
        
        print("Starting legacy V1 service...")
        uvicorn.run(
            legacy_app,
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "info").lower()
        )
    except ImportError as e:
        print(f"ERROR: Failed to import legacy code: {e}")
        print("The legacy code structure may have changed.")
        sys.exit(1)


def main() -> None:
    """
    Main entry point for CLI.
    
    Parses arguments, applies overrides, and starts the service.
    """
    # Parse command-line arguments
    args = parse_args()
    
    # Apply CLI overrides to environment variables
    apply_cli_overrides(args)
    
    # Check if running in legacy mode
    if args.legacy:
        run_legacy_mode()
        return
    
    # Import main app (after environment overrides are applied)
    from app.main import app
    from app.core.config import get_config
    from app.core.logging import get_logger
    
    # Get configuration
    config = get_config()
    logger = get_logger(__name__)
    
    # Log startup information
    logger.info(
        "Starting UAT Automation Service",
        extra={
            "extra_fields": {
                "version": "2.0.0",
                "environment": config.environment,
                "host": config.api_host,
                "port": config.api_port,
                "concurrency": config.concurrency,
                "headless": config.headless_mode,
                "log_level": config.log_level
            }
        }
    )
    
    # Print startup banner
    print("=" * 70)
    print("UAT Automation Service v2.0.0")
    print("=" * 70)
    print(f"Environment:  {config.environment}")
    print(f"API Endpoint: http://{config.api_host}:{config.api_port}")
    print(f"API Docs:     http://{config.api_host}:{config.api_port}/docs")
    print(f"Concurrency:  {config.concurrency} parallel scenarios")
    print(f"Headless:     {config.headless_mode}")
    print(f"Log Level:    {config.log_level}")
    print("=" * 70)
    print()
    
    # Start the service
    uvicorn.run(
        "app.main:app",
        host=config.api_host,
        port=config.api_port,
        reload=args.reload,
        log_level=config.log_level.lower()
    )


if __name__ == "__main__":
    main()
