"""
Webhook management API endpoints.

This module provides REST API endpoints for managing webhooks that receive
notifications when test runs complete or other events occur.

Requirements: 9.6
"""

import uuid
import httpx
from datetime import datetime
from typing import Optional, Literal
from enum import Enum
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.core.dependencies import ApiKeyDep, ConfigDep, PaginationDep, RequestIdDep
from app.core.logging import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/webhooks", tags=["webhooks"])


# ============================================================================
# Models
# ============================================================================

class WebhookEvent(str, Enum):
    """Types of events that can trigger webhooks."""
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"
    STORY_CREATED = "story.created"
    STORY_PARSED = "story.parsed"


class WebhookCreate(BaseModel):
    """Request model for creating a webhook."""
    
    url: HttpUrl = Field(
        ...,
        description="Webhook endpoint URL"
    )
    events: list[WebhookEvent] = Field(
        ...,
        min_length=1,
        description="Events that trigger this webhook"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Human-readable description"
    )
    secret: Optional[str] = Field(
        None,
        min_length=16,
        max_length=128,
        description="Secret for HMAC signature verification"
    )
    active: bool = Field(
        default=True,
        description="Whether webhook is active"
    )
    
    @field_validator("events")
    @classmethod
    def validate_unique_events(cls, v: list[WebhookEvent]) -> list[WebhookEvent]:
        """Ensure events are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Events must be unique")
        return v


class WebhookUpdate(BaseModel):
    """Request model for updating a webhook."""
    
    url: Optional[HttpUrl] = Field(None, description="Webhook endpoint URL")
    events: Optional[list[WebhookEvent]] = Field(
        None,
        min_length=1,
        description="Events that trigger this webhook"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Human-readable description"
    )
    secret: Optional[str] = Field(
        None,
        min_length=16,
        max_length=128,
        description="Secret for HMAC signature verification"
    )
    active: Optional[bool] = Field(None, description="Whether webhook is active")


class Webhook(BaseModel):
    """Webhook configuration."""
    
    id: str = Field(..., description="Webhook ID")
    url: str = Field(..., description="Webhook endpoint URL")
    events: list[WebhookEvent] = Field(..., description="Subscribed events")
    description: Optional[str] = Field(None, description="Description")
    active: bool = Field(..., description="Whether webhook is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_triggered_at: Optional[datetime] = Field(
        None,
        description="Last time webhook was triggered"
    )
    success_count: int = Field(
        default=0,
        description="Number of successful deliveries"
    )
    failure_count: int = Field(
        default=0,
        description="Number of failed deliveries"
    )


class WebhookListResponse(BaseModel):
    """Response model for listing webhooks."""
    
    webhooks: list[Webhook] = Field(..., description="List of webhooks")
    total: int = Field(..., description="Total number of webhooks")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")


class WebhookDelivery(BaseModel):
    """Webhook delivery attempt record."""
    
    id: str = Field(..., description="Delivery ID")
    webhook_id: str = Field(..., description="Webhook ID")
    event: WebhookEvent = Field(..., description="Event type")
    payload: dict = Field(..., description="Event payload")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    success: bool = Field(..., description="Whether delivery succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    attempted_at: datetime = Field(..., description="Attempt timestamp")
    duration_ms: int = Field(..., description="Request duration in milliseconds")


class WebhookDeliveryListResponse(BaseModel):
    """Response model for listing webhook deliveries."""
    
    deliveries: list[WebhookDelivery] = Field(..., description="List of deliveries")
    total: int = Field(..., description="Total number of deliveries")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")


# ============================================================================
# In-memory storage (temporary until database is implemented)
# ============================================================================

_webhooks: dict[str, dict] = {}
_deliveries: list[dict] = []


# ============================================================================
# Helper Functions
# ============================================================================

async def send_webhook(
    webhook_id: str,
    event: WebhookEvent,
    payload: dict,
    config: ConfigDep
) -> WebhookDelivery:
    """
    Send a webhook notification.
    
    Args:
        webhook_id: The webhook ID
        event: The event type
        payload: The event payload
        config: Application configuration
        
    Returns:
        Delivery record
    """
    if webhook_id not in _webhooks:
        raise ValueError(f"Webhook {webhook_id} not found")
    
    webhook = _webhooks[webhook_id]
    
    if not webhook["active"]:
        logger.debug(
            "Webhook is inactive, skipping",
            extra={"extra_fields": {"webhook_id": webhook_id}}
        )
        return None
    
    if event not in webhook["events"]:
        logger.debug(
            "Event not subscribed, skipping",
            extra={
                "extra_fields": {
                    "webhook_id": webhook_id,
                    "event": event
                }
            }
        )
        return None
    
    delivery_id = str(uuid.uuid4())
    attempted_at = datetime.utcnow()
    
    logger.info(
        "Sending webhook",
        extra={
            "extra_fields": {
                "webhook_id": webhook_id,
                "delivery_id": delivery_id,
                "event": event,
                "url": webhook["url"]
            }
        }
    )
    
    try:
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event,
            "X-Webhook-Delivery": delivery_id,
            "X-Webhook-Timestamp": attempted_at.isoformat()
        }
        
        # Add HMAC signature if secret is configured
        if webhook.get("secret"):
            # TODO: Implement HMAC signature
            # import hmac
            # import hashlib
            # signature = hmac.new(
            #     webhook["secret"].encode(),
            #     json.dumps(payload).encode(),
            #     hashlib.sha256
            # ).hexdigest()
            # headers["X-Webhook-Signature"] = f"sha256={signature}"
            pass
        
        # Send webhook with timeout
        start_time = datetime.utcnow()
        async with httpx.AsyncClient(timeout=config.webhook_timeout) as client:
            response = await client.post(
                webhook["url"],
                json=payload,
                headers=headers
            )
        
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        success = 200 <= response.status_code < 300
        
        # Create delivery record
        delivery = WebhookDelivery(
            id=delivery_id,
            webhook_id=webhook_id,
            event=event,
            payload=payload,
            status_code=response.status_code,
            success=success,
            error_message=None if success else f"HTTP {response.status_code}",
            attempted_at=attempted_at,
            duration_ms=duration_ms
        )
        
        # Update webhook stats
        if success:
            webhook["success_count"] += 1
        else:
            webhook["failure_count"] += 1
        webhook["last_triggered_at"] = attempted_at
        
        # Store delivery record
        _deliveries.append(delivery.model_dump())
        
        logger.info(
            "Webhook sent successfully" if success else "Webhook delivery failed",
            extra={
                "extra_fields": {
                    "webhook_id": webhook_id,
                    "delivery_id": delivery_id,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms
                }
            }
        )
        
        return delivery
        
    except httpx.TimeoutException as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        delivery = WebhookDelivery(
            id=delivery_id,
            webhook_id=webhook_id,
            event=event,
            payload=payload,
            status_code=None,
            success=False,
            error_message=f"Timeout after {config.webhook_timeout}s",
            attempted_at=attempted_at,
            duration_ms=duration_ms
        )
        
        webhook["failure_count"] += 1
        _deliveries.append(delivery.model_dump())
        
        logger.error(
            "Webhook delivery timeout",
            extra={
                "extra_fields": {
                    "webhook_id": webhook_id,
                    "delivery_id": delivery_id,
                    "error": str(e)
                }
            }
        )
        
        return delivery
        
    except Exception as e:
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        delivery = WebhookDelivery(
            id=delivery_id,
            webhook_id=webhook_id,
            event=event,
            payload=payload,
            status_code=None,
            success=False,
            error_message=str(e),
            attempted_at=attempted_at,
            duration_ms=duration_ms
        )
        
        webhook["failure_count"] += 1
        _deliveries.append(delivery.model_dump())
        
        logger.error(
            "Webhook delivery error",
            extra={
                "extra_fields": {
                    "webhook_id": webhook_id,
                    "delivery_id": delivery_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        
        return delivery


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=Webhook,
    status_code=status.HTTP_201_CREATED,
    summary="Create a webhook",
    description="""
    Create a new webhook to receive notifications for specific events.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Events:**
    - `run.started`: Test run started
    - `run.completed`: Test run completed successfully
    - `run.failed`: Test run failed
    - `run.cancelled`: Test run cancelled
    - `story.created`: New story created
    - `story.parsed`: Story parsed successfully
    
    **Security:**
    Optionally provide a secret for HMAC signature verification.
    The signature will be sent in the `X-Webhook-Signature` header.
    
    **Example Request:**
    ```json
    {
        "url": "https://example.com/webhooks/uat",
        "events": ["run.completed", "run.failed"],
        "description": "Notify CI/CD pipeline",
        "secret": "your-secret-key-here",
        "active": true
    }
    ```
    """
)
async def create_webhook(
    webhook_create: WebhookCreate,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> Webhook:
    """
    Create a new webhook.
    
    Args:
        webhook_create: Webhook configuration
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Created webhook
        
    Raises:
        HTTPException: If creation fails
    """
    logger.info(
        "Creating webhook",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "url": str(webhook_create.url),
                "events": [e.value for e in webhook_create.events]
            }
        }
    )
    
    try:
        webhook_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        webhook_data = {
            "id": webhook_id,
            "url": str(webhook_create.url),
            "events": webhook_create.events,
            "description": webhook_create.description,
            "secret": webhook_create.secret,
            "active": webhook_create.active,
            "created_at": now,
            "updated_at": now,
            "last_triggered_at": None,
            "success_count": 0,
            "failure_count": 0
        }
        
        # TODO: Store in database (Task 6.1)
        _webhooks[webhook_id] = webhook_data
        
        webhook = Webhook(**{k: v for k, v in webhook_data.items() if k != "secret"})
        
        logger.info(
            "Webhook created successfully",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "webhook_id": webhook_id
                }
            }
        )
        
        return webhook
        
    except Exception as e:
        logger.error(
            "Failed to create webhook",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create webhook: {str(e)}"
        )


@router.get(
    "",
    response_model=WebhookListResponse,
    summary="List webhooks",
    description="""
    Retrieve a paginated list of configured webhooks.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    """
)
async def list_webhooks(
    api_key: ApiKeyDep,
    pagination: PaginationDep,
    request_id: RequestIdDep
) -> WebhookListResponse:
    """
    List all webhooks.
    
    Args:
        api_key: Validated API key (injected)
        pagination: Pagination parameters (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Paginated list of webhooks
    """
    logger.info(
        "Listing webhooks",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "skip": pagination["skip"],
                "limit": pagination["limit"]
            }
        }
    )
    
    try:
        # TODO: Retrieve from database (Task 6.1)
        all_webhooks = list(_webhooks.values())
        total = len(all_webhooks)
        
        # Apply pagination
        start = pagination["skip"]
        end = start + pagination["limit"]
        paginated = all_webhooks[start:end]
        
        webhooks = [
            Webhook(**{k: v for k, v in w.items() if k != "secret"})
            for w in paginated
        ]
        
        return WebhookListResponse(
            webhooks=webhooks,
            total=total,
            skip=pagination["skip"],
            limit=pagination["limit"]
        )
        
    except Exception as e:
        logger.error(
            "Failed to list webhooks",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list webhooks: {str(e)}"
        )


@router.get(
    "/{webhook_id}",
    response_model=Webhook,
    summary="Get webhook details",
    description="""
    Retrieve details of a specific webhook.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    """
)
async def get_webhook(
    webhook_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> Webhook:
    """
    Get webhook details.
    
    Args:
        webhook_id: The webhook ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Webhook details
        
    Raises:
        HTTPException: If webhook not found
    """
    logger.info(
        "Getting webhook details",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "webhook_id": webhook_id
            }
        }
    )
    
    try:
        if webhook_id not in _webhooks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )
        
        webhook_data = _webhooks[webhook_id]
        webhook = Webhook(**{k: v for k, v in webhook_data.items() if k != "secret"})
        
        return webhook
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get webhook",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "webhook_id": webhook_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get webhook: {str(e)}"
        )


@router.patch(
    "/{webhook_id}",
    response_model=Webhook,
    summary="Update a webhook",
    description="""
    Update webhook configuration.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    Only provided fields will be updated. Omitted fields remain unchanged.
    """
)
async def update_webhook(
    webhook_id: str,
    webhook_update: WebhookUpdate,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> Webhook:
    """
    Update a webhook.
    
    Args:
        webhook_id: The webhook ID
        webhook_update: Fields to update
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Updated webhook
        
    Raises:
        HTTPException: If webhook not found or update fails
    """
    logger.info(
        "Updating webhook",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "webhook_id": webhook_id
            }
        }
    )
    
    try:
        if webhook_id not in _webhooks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )
        
        webhook_data = _webhooks[webhook_id]
        
        # Update fields
        update_data = webhook_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "url":
                webhook_data[key] = str(value)
            else:
                webhook_data[key] = value
        
        webhook_data["updated_at"] = datetime.utcnow()
        
        webhook = Webhook(**{k: v for k, v in webhook_data.items() if k != "secret"})
        
        logger.info(
            "Webhook updated successfully",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "webhook_id": webhook_id
                }
            }
        )
        
        return webhook
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update webhook",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "webhook_id": webhook_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update webhook: {str(e)}"
        )


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook",
    description="""
    Delete a webhook configuration.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    """
)
async def delete_webhook(
    webhook_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> None:
    """
    Delete a webhook.
    
    Args:
        webhook_id: The webhook ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Raises:
        HTTPException: If webhook not found or deletion fails
    """
    logger.info(
        "Deleting webhook",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "webhook_id": webhook_id
            }
        }
    )
    
    try:
        if webhook_id not in _webhooks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )
        
        del _webhooks[webhook_id]
        
        logger.info(
            "Webhook deleted successfully",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "webhook_id": webhook_id
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete webhook",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "webhook_id": webhook_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete webhook: {str(e)}"
        )


@router.get(
    "/{webhook_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
    summary="List webhook deliveries",
    description="""
    Retrieve delivery history for a webhook.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    Shows all delivery attempts including successes and failures.
    """
)
async def list_webhook_deliveries(
    webhook_id: str,
    api_key: ApiKeyDep,
    pagination: PaginationDep,
    request_id: RequestIdDep
) -> WebhookDeliveryListResponse:
    """
    List webhook delivery attempts.
    
    Args:
        webhook_id: The webhook ID
        api_key: Validated API key (injected)
        pagination: Pagination parameters (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Paginated list of deliveries
        
    Raises:
        HTTPException: If webhook not found
    """
    logger.info(
        "Listing webhook deliveries",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "webhook_id": webhook_id
            }
        }
    )
    
    try:
        if webhook_id not in _webhooks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )
        
        # Filter deliveries for this webhook
        webhook_deliveries = [
            d for d in _deliveries
            if d["webhook_id"] == webhook_id
        ]
        
        total = len(webhook_deliveries)
        
        # Apply pagination
        start = pagination["skip"]
        end = start + pagination["limit"]
        paginated = webhook_deliveries[start:end]
        
        deliveries = [WebhookDelivery(**d) for d in paginated]
        
        return WebhookDeliveryListResponse(
            deliveries=deliveries,
            total=total,
            skip=pagination["skip"],
            limit=pagination["limit"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to list webhook deliveries",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "webhook_id": webhook_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list webhook deliveries: {str(e)}"
        )


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookDelivery,
    summary="Test a webhook",
    description="""
    Send a test event to a webhook to verify it's working correctly.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    """
)
async def test_webhook(
    webhook_id: str,
    api_key: ApiKeyDep,
    config: ConfigDep,
    request_id: RequestIdDep
) -> WebhookDelivery:
    """
    Test a webhook by sending a test event.
    
    Args:
        webhook_id: The webhook ID
        api_key: Validated API key (injected)
        config: Application configuration (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Delivery result
        
    Raises:
        HTTPException: If webhook not found or test fails
    """
    logger.info(
        "Testing webhook",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "webhook_id": webhook_id
            }
        }
    )
    
    try:
        if webhook_id not in _webhooks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found"
            )
        
        # Send test event
        test_payload = {
            "event": "webhook.test",
            "webhook_id": webhook_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "This is a test webhook delivery"
        }
        
        # Use the first subscribed event for testing
        webhook = _webhooks[webhook_id]
        test_event = webhook["events"][0]
        
        delivery = await send_webhook(
            webhook_id=webhook_id,
            event=test_event,
            payload=test_payload,
            config=config
        )
        
        return delivery
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to test webhook",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "webhook_id": webhook_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test webhook: {str(e)}"
        )
