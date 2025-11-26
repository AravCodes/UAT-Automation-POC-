"""
FastAPI dependency injection setup.

This module provides dependency injection functions for FastAPI endpoints,
enabling clean separation of concerns and testability.

Requirements: 9.1
"""

from typing import Annotated, Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import Config, get_config
from .logging import get_logger
from .exceptions import AuthenticationException


logger = get_logger(__name__)


# ============================================================================
# Configuration Dependencies
# ============================================================================

def get_app_config() -> Config:
    """
    Get the application configuration.
    
    This dependency provides access to the global configuration
    throughout the application.
    
    Returns:
        The application configuration instance
        
    Example:
        @app.get("/health")
        async def health_check(config: Config = Depends(get_app_config)):
            return {"status": "healthy", "environment": config.environment}
    """
    return get_config()


# Type alias for configuration dependency
ConfigDep = Annotated[Config, Depends(get_app_config)]


# ============================================================================
# Authentication Dependencies
# ============================================================================

async def verify_api_key(
    x_api_key: Annotated[Optional[str], Header()] = None,
    config: Config = Depends(get_app_config)
) -> str:
    """
    Verify API key authentication.
    
    This dependency checks if the provided API key is valid.
    If no API keys are configured, authentication is bypassed.
    
    Args:
        x_api_key: The API key from the request header
        config: The application configuration
        
    Returns:
        The validated API key
        
    Raises:
        HTTPException: If authentication fails
        
    Example:
        @app.post("/api/v2/stories")
        async def create_story(
            story: StoryInput,
            api_key: str = Depends(verify_api_key)
        ):
            # API key is validated before this code runs
            pass
    """
    # Get configured API keys
    api_keys = config.get_api_keys_list()
    
    # If no API keys are configured, bypass authentication
    if not api_keys:
        logger.warning(
            "API key authentication bypassed - no API keys configured",
            extra={"extra_fields": {"security_warning": True}}
        )
        return "bypass"
    
    # Check if API key is provided
    if not x_api_key:
        logger.warning(
            "API request without API key",
            extra={"extra_fields": {"auth_failure": "missing_key"}}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide via X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # Validate API key
    if x_api_key not in api_keys:
        logger.warning(
            "API request with invalid API key",
            extra={"extra_fields": {"auth_failure": "invalid_key"}}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    logger.debug(
        "API key validated successfully",
        extra={"extra_fields": {"auth_success": True}}
    )
    
    return x_api_key


# Type alias for API key dependency
ApiKeyDep = Annotated[str, Depends(verify_api_key)]


async def optional_api_key(
    x_api_key: Annotated[Optional[str], Header()] = None,
    config: Config = Depends(get_app_config)
) -> Optional[str]:
    """
    Optional API key authentication.
    
    This dependency checks for an API key but doesn't require it.
    Useful for endpoints that have different behavior for authenticated users.
    
    Args:
        x_api_key: The API key from the request header
        config: The application configuration
        
    Returns:
        The API key if valid, None otherwise
    """
    api_keys = config.get_api_keys_list()
    
    if not api_keys or not x_api_key:
        return None
    
    if x_api_key in api_keys:
        return x_api_key
    
    return None


# Type alias for optional API key dependency
OptionalApiKeyDep = Annotated[Optional[str], Depends(optional_api_key)]


# ============================================================================
# Database Dependencies
# ============================================================================

# Note: These will be implemented when the database layer is created
# For now, we provide placeholder functions

def get_db_session():
    """
    Get a database session.
    
    This dependency provides a database session for the request.
    The session is automatically closed after the request completes.
    
    Yields:
        A database session
        
    Example:
        @app.get("/api/v2/stories")
        async def list_stories(db: Session = Depends(get_db_session)):
            stories = db.query(Story).all()
            return stories
    """
    # TODO: Implement when database layer is created (Task 6.1)
    # This is a placeholder that will be replaced with actual implementation
    raise NotImplementedError("Database session dependency not yet implemented")


# Type alias for database session dependency
DbSessionDep = Annotated[Session, Depends(get_db_session)]


# ============================================================================
# Service Dependencies
# ============================================================================

# Note: These will be implemented as services are created
# For now, we provide placeholder functions

def get_llm_service():
    """
    Get the LLM service instance.
    
    This dependency provides access to the LLM service for story parsing
    and scenario generation.
    
    Returns:
        The LLM service instance
        
    Example:
        @app.post("/api/v2/parse")
        async def parse_story(
            story: StoryInput,
            llm_service = Depends(get_llm_service)
        ):
            parsed = await llm_service.parse_story(story.text)
            return parsed
    """
    # TODO: Implement when LLM service is created (Task 4)
    raise NotImplementedError("LLM service dependency not yet implemented")


def get_story_parser():
    """
    Get the story parser service instance.
    
    This dependency provides access to the story parser service.
    
    Returns:
        The story parser service instance
    """
    # TODO: Implement when story parser is created (Task 5)
    raise NotImplementedError("Story parser dependency not yet implemented")


def get_test_runner():
    """
    Get the test runner service instance.
    
    This dependency provides access to the test execution engine.
    
    Returns:
        The test runner service instance
    """
    # TODO: Implement when test runner is created (Task 8)
    raise NotImplementedError("Test runner dependency not yet implemented")


def get_report_generator():
    """
    Get the report generator service instance.
    
    This dependency provides access to the reporting service.
    
    Returns:
        The report generator service instance
    """
    # TODO: Implement when report generator is created (Task 9)
    raise NotImplementedError("Report generator dependency not yet implemented")


# ============================================================================
# Cache Dependencies
# ============================================================================

def get_cache_client():
    """
    Get the cache client instance.
    
    This dependency provides access to the Redis cache client.
    
    Returns:
        The cache client instance
        
    Example:
        @app.get("/api/v2/cached-data")
        async def get_cached_data(cache = Depends(get_cache_client)):
            data = await cache.get("my_key")
            return data
    """
    # TODO: Implement when cache layer is created (Task 6.3)
    raise NotImplementedError("Cache client dependency not yet implemented")


# ============================================================================
# Request Context Dependencies
# ============================================================================

async def get_request_id(
    x_request_id: Annotated[Optional[str], Header()] = None
) -> str:
    """
    Get or generate a request ID.
    
    This dependency ensures every request has a unique ID for tracing.
    If the client provides an X-Request-ID header, it's used; otherwise,
    a new UUID is generated.
    
    Args:
        x_request_id: Optional request ID from header
        
    Returns:
        The request ID
        
    Example:
        @app.get("/api/v2/data")
        async def get_data(request_id: str = Depends(get_request_id)):
            logger = get_logger(__name__, request_id=request_id)
            logger.info("Processing request")
            return {"data": "..."}
    """
    import uuid
    
    if x_request_id:
        return x_request_id
    
    return str(uuid.uuid4())


# Type alias for request ID dependency
RequestIdDep = Annotated[str, Depends(get_request_id)]


# ============================================================================
# Pagination Dependencies
# ============================================================================

async def get_pagination_params(
    skip: int = 0,
    limit: int = 100
) -> dict[str, int]:
    """
    Get pagination parameters.
    
    This dependency provides standardized pagination parameters
    with validation.
    
    Args:
        skip: Number of items to skip (offset)
        limit: Maximum number of items to return
        
    Returns:
        Dictionary with skip and limit values
        
    Raises:
        HTTPException: If parameters are invalid
        
    Example:
        @app.get("/api/v2/items")
        async def list_items(
            pagination: dict = Depends(get_pagination_params)
        ):
            items = get_items(
                skip=pagination["skip"],
                limit=pagination["limit"]
            )
            return items
    """
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="skip must be >= 0"
        )
    
    if limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be >= 1"
        )
    
    if limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be <= 1000"
        )
    
    return {"skip": skip, "limit": limit}


# Type alias for pagination dependency
PaginationDep = Annotated[dict[str, int], Depends(get_pagination_params)]


# ============================================================================
# Utility Functions
# ============================================================================

def create_service_dependencies():
    """
    Create and initialize all service dependencies.
    
    This function is called during application startup to initialize
    all services that will be injected via dependencies.
    
    This is a placeholder that will be implemented as services are created.
    """
    # TODO: Implement service initialization
    # This will create singleton instances of services that are shared
    # across all requests
    pass


def cleanup_service_dependencies():
    """
    Clean up service dependencies.
    
    This function is called during application shutdown to properly
    clean up resources (close connections, etc.).
    
    This is a placeholder that will be implemented as services are created.
    """
    # TODO: Implement service cleanup
    # This will close database connections, cache connections, etc.
    pass
