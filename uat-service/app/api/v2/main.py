"""
FastAPI application setup for API v2.

This module configures the FastAPI application with all v2 endpoints,
middleware, OpenAPI documentation, and application lifecycle hooks.

Requirements: 9.1
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.config import get_config
from app.core.logging import get_logger
from app.api.middleware import setup_middleware
from app.api.v2 import stories, runs, reports, webhooks


logger = get_logger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    config = get_config()
    
    # Create FastAPI app with custom configuration
    app = FastAPI(
        title="UAT Automation Service API",
        description="""
        # UAT Automation Service API v2
        
        Advanced UAT automation platform powered by LLMs for intelligent test generation and execution.
        
        ## Features
        
        - **Story Management**: Submit and manage user stories
        - **Test Execution**: Execute automated tests against web applications
        - **Reporting**: Comprehensive test reports with analytics
        - **Webhooks**: Real-time notifications for test events
        - **Authentication**: API key-based authentication
        
        ## Getting Started
        
        1. **Get an API Key**: Contact your administrator for an API key
        2. **Submit a Story**: POST to `/api/v2/stories` with your user story
        3. **Execute Tests**: POST to `/api/v2/stories/{story_id}/run` with target URL
        4. **Get Results**: GET `/api/v2/runs/{run_id}` to retrieve test results
        
        ## Authentication
        
        All API endpoints require authentication via API key.
        Include your API key in the `X-API-Key` header:
        
        ```
        X-API-Key: your-api-key-here
        ```
        
        ## Rate Limiting
        
        API requests are rate limited to prevent abuse.
        Rate limit information is included in response headers:
        
        - `X-RateLimit-Limit`: Maximum requests per minute
        - `X-RateLimit-Remaining`: Remaining requests in current window
        - `X-RateLimit-Reset`: Unix timestamp when limit resets
        
        ## Webhooks
        
        Configure webhooks to receive real-time notifications when:
        - Test runs complete
        - Test runs fail
        - Stories are created or parsed
        
        See the `/api/v2/webhooks` endpoints for webhook management.
        
        ## Support
        
        For support, please contact your system administrator or refer to the
        documentation at your deployment's `/docs` endpoint.
        """,
        version="2.0.0",
        docs_url="/docs" if config.enable_api_docs else None,
        redoc_url="/redoc" if config.enable_api_docs else None,
        openapi_url="/openapi.json" if config.enable_api_docs else None,
        contact={
            "name": "UAT Automation Team",
            "email": "support@example.com"
        },
        license_info={
            "name": "Proprietary",
        }
    )
    
    # Set up middleware
    setup_middleware(app)
    
    # Include routers
    app.include_router(stories.router)
    app.include_router(runs.router)
    app.include_router(reports.router)
    app.include_router(webhooks.router)
    
    # Add startup event
    @app.on_event("startup")
    async def startup_event():
        """Application startup tasks."""
        logger.info(
            "Starting UAT Automation Service API v2",
            extra={
                "extra_fields": {
                    "version": "2.0.0",
                    "environment": config.environment,
                    "api_docs_enabled": config.enable_api_docs
                }
            }
        )
    
    # Add shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown tasks."""
        logger.info("Shutting down UAT Automation Service API v2")
    
    # Customize OpenAPI schema
    def custom_openapi():
        """
        Customize OpenAPI schema with additional information.
        
        Returns:
            Customized OpenAPI schema
        """
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            contact=app.contact,
            license_info=app.license_info
        )
        
        # Add security scheme for API key authentication
        openapi_schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for authentication. Contact your administrator to obtain an API key."
            }
        }
        
        # Apply security globally
        openapi_schema["security"] = [{"ApiKeyAuth": []}]
        
        # Add tags with descriptions
        openapi_schema["tags"] = [
            {
                "name": "stories",
                "description": "User story management operations. Submit, retrieve, and manage user stories."
            },
            {
                "name": "test-execution",
                "description": "Test execution operations. Start test runs, check status, and cancel running tests."
            },
            {
                "name": "reports",
                "description": "Report and analytics operations. Retrieve test results, download reports, and view analytics."
            },
            {
                "name": "webhooks",
                "description": "Webhook management operations. Configure webhooks to receive real-time notifications."
            }
        ]
        
        # Add servers
        openapi_schema["servers"] = [
            {
                "url": f"http://localhost:{config.api_port}",
                "description": "Local development server"
            },
            {
                "url": "https://api.example.com",
                "description": "Production server (update with your actual URL)"
            }
        ]
        
        # Add examples for common responses
        openapi_schema["components"]["examples"] = {
            "StoryExample": {
                "summary": "Example user story",
                "value": {
                    "text": "As a user, I want to login with email and password, so that I can access my account",
                    "source": "manual",
                    "metadata": {
                        "project": "sample-app",
                        "module": "authentication"
                    }
                }
            },
            "RunRequestExample": {
                "summary": "Example test run request",
                "value": {
                    "target_url": "http://localhost:5173",
                    "mode": "async",
                    "webhook_url": "https://example.com/webhook",
                    "concurrency": 3,
                    "headless": True
                }
            },
            "WebhookExample": {
                "summary": "Example webhook configuration",
                "value": {
                    "url": "https://example.com/webhooks/uat",
                    "events": ["run.completed", "run.failed"],
                    "description": "Notify CI/CD pipeline",
                    "secret": "your-secret-key-here",
                    "active": True
                }
            }
        }
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    # Add health check endpoint
    @app.get(
        "/health",
        tags=["system"],
        summary="Health check",
        description="Check if the API is running and healthy",
        response_model=dict
    )
    async def health_check():
        """
        Health check endpoint.
        
        Returns:
            Health status information
        """
        return {
            "status": "healthy",
            "version": "2.0.0",
            "environment": config.environment
        }
    
    # Add version endpoint
    @app.get(
        "/version",
        tags=["system"],
        summary="Get API version",
        description="Get the current API version and build information",
        response_model=dict
    )
    async def get_version():
        """
        Get API version information.
        
        Returns:
            Version information
        """
        return {
            "version": "2.0.0",
            "api_version": "v2",
            "build_date": "2024-01-01",
            "environment": config.environment
        }
    
    logger.info(
        "FastAPI application created",
        extra={
            "extra_fields": {
                "docs_url": app.docs_url,
                "redoc_url": app.redoc_url,
                "openapi_url": app.openapi_url
            }
        }
    )
    
    return app


# Create the application instance
app = create_app()
