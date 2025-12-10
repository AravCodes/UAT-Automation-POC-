"""
API middleware for authentication, CORS, logging, and request validation.

This module provides middleware components for the FastAPI application
including API key authentication, CORS configuration, request/response logging,
and request validation.

"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_config
from app.core.logging import get_logger


logger = get_logger(__name__)


# ============================================================================
# Request ID Middleware
# ============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to each request.
    
    The request ID is used for tracing and correlating logs across
    the request lifecycle.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add request ID to request state and response headers.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response with X-Request-ID header
        """
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Store in request state for access in route handlers
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


# ============================================================================
# Request Logging Middleware
# ============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all incoming requests and outgoing responses.
    
    Logs include:
    - Request method, path, query parameters
    - Response status code
    - Request duration
    - Client IP address
    - User agent
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log request and response details.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response
        """
        config = get_config()
        
        # Skip logging if disabled
        if not config.log_requests:
            return await call_next(request)
        
        # Get request ID
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Record start time
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            "Incoming request",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent")
                }
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms
                    }
                }
            )
            
            # Add duration header
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log error
            logger.error(
                "Request failed",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": duration_ms,
                        "error": str(e)
                    }
                },
                exc_info=True
            )
            
            # Re-raise to let FastAPI handle it
            raise


# ============================================================================
# Rate Limiting Middleware
# ============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to implement rate limiting.
    
    Uses a simple in-memory token bucket algorithm.
    For production, this should be replaced with Redis-based rate limiting.
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            app: The FastAPI application
            requests_per_minute: Maximum requests per minute per client
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.buckets: dict[str, dict] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check rate limit before processing request.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response or 429 Too Many Requests
        """
        config = get_config()
        
        # Skip rate limiting if disabled
        if not config.enable_rate_limiting:
            return await call_next(request)
        
        # Get client identifier (IP address or API key)
        client_id = request.client.host if request.client else "unknown"
        api_key = request.headers.get("X-API-Key")
        if api_key:
            client_id = f"api_key:{api_key[:8]}"
        
        # Get or create bucket for client
        now = time.time()
        if client_id not in self.buckets:
            self.buckets[client_id] = {
                "tokens": config.rate_limit_per_minute,
                "last_update": now
            }
        
        bucket = self.buckets[client_id]
        
        # Refill tokens based on time elapsed
        time_elapsed = now - bucket["last_update"]
        tokens_to_add = time_elapsed * (config.rate_limit_per_minute / 60.0)
        bucket["tokens"] = min(
            config.rate_limit_per_minute,
            bucket["tokens"] + tokens_to_add
        )
        bucket["last_update"] = now
        
        # Check if request can proceed
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(config.rate_limit_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(int(bucket["tokens"]))
            response.headers["X-RateLimit-Reset"] = str(int(now + 60))
            
            return response
        else:
            # Rate limit exceeded
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "extra_fields": {
                        "client_id": client_id,
                        "path": request.url.path
                    }
                }
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": 60
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(config.rate_limit_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + 60))
                }
            )


# ============================================================================
# Request Size Validation Middleware
# ============================================================================

class RequestSizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate request body size.
    
    Prevents large payloads from consuming excessive memory or bandwidth.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check request size before processing.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response or 413 Payload Too Large
        """
        config = get_config()
        
        # Skip validation if disabled
        if not config.enable_request_validation:
            return await call_next(request)
        
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            max_size = config.max_request_size_mb * 1024 * 1024  # Convert MB to bytes
            
            if content_length > max_size:
                logger.warning(
                    "Request too large",
                    extra={
                        "extra_fields": {
                            "content_length": content_length,
                            "max_size": max_size,
                            "path": request.url.path
                        }
                    }
                )
                
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "detail": f"Request body too large. Maximum size is {config.max_request_size_mb}MB.",
                        "max_size_mb": config.max_request_size_mb,
                        "received_size_mb": round(content_length / (1024 * 1024), 2)
                    }
                )
        
        return await call_next(request)


# ============================================================================
# Security Headers Middleware
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Adds headers like:
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Strict-Transport-Security (for HTTPS)
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to response.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response with security headers
        """
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Add HSTS header for HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


# ============================================================================
# Error Handler Middleware
# ============================================================================

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to catch and format unhandled exceptions.
    
    Ensures all errors are returned in a consistent JSON format.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Catch and format exceptions.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response or formatted error response
        """
        try:
            return await call_next(request)
        except Exception as e:
            # Get request ID for tracing
            request_id = getattr(request.state, "request_id", "unknown")
            
            # Log error
            logger.error(
                "Unhandled exception",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(e)
                    }
                },
                exc_info=True
            )
            
            # Return formatted error response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                    "error_type": type(e).__name__
                }
            )


# ============================================================================
# Helper Functions
# ============================================================================

def setup_middleware(app):
    """
    Set up all middleware for the FastAPI application.
    
    Middleware is applied in the order added, so the order matters:
    1. Error handler (outermost - catches all errors)
    2. Request ID (early - needed for logging)
    3. Request logging
    4. Security headers
    5. Rate limiting
    6. Request size validation
    7. CORS (if enabled)
    
    Args:
        app: The FastAPI application
    """
    config = get_config()
    
    # Add CORS middleware if enabled
    if config.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.get_cors_origins_list(),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "X-Response-Time", "X-RateLimit-*"]
        )
    
    # Add custom middleware (in reverse order of execution)
    app.add_middleware(RequestSizeMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=config.rate_limit_per_minute)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)
    
    logger.info(
        "Middleware configured",
        extra={
            "extra_fields": {
                "cors_enabled": config.enable_cors,
                "rate_limiting_enabled": config.enable_rate_limiting,
                "request_logging_enabled": config.log_requests
            }
        }
    )
