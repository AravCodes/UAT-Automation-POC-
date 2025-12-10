"""
Story management API endpoints.

This module provides REST API endpoints for managing user stories,
including creation, retrieval, updating, and deletion.
"""

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.core.dependencies import ApiKeyDep, ConfigDep, PaginationDep, RequestIdDep
from app.core.logging import get_logger
from app.models.story import StoryInput, ParsedStory


logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/stories", tags=["stories"])


# ============================================================================
# Response Models
# ============================================================================

class StoryCreateResponse(BaseModel):
    """Response model for story creation."""
    
    id: str = Field(..., description="Unique identifier for the created story")
    status: str = Field(..., description="Status of the creation operation")
    message: str = Field(..., description="Human-readable message")
    created_at: datetime = Field(..., description="Timestamp of creation")


class StoryListResponse(BaseModel):
    """Response model for listing stories."""
    
    stories: list[ParsedStory] = Field(..., description="List of stories")
    total: int = Field(..., description="Total number of stories")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")


class StoryDetailResponse(BaseModel):
    """Response model for story details."""
    
    story: ParsedStory = Field(..., description="Story details")


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=StoryCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user story",
    description="""
    Submit a new user story for parsing and test scenario generation.
    
    The story will be parsed using LLM (with fallback to legacy NLP if needed)
    to extract structured information including acceptance criteria.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Example Request:**
    ```json
    {
        "text": "As a user, I want to login with email and password, so that I can access my account",
        "source": "manual",
        "metadata": {
            "project": "sample-app",
            "module": "authentication"
        }
    }
    ```
    """
)
async def create_story(
    story_input: StoryInput,
    api_key: ApiKeyDep,
    config: ConfigDep,
    request_id: RequestIdDep
) -> StoryCreateResponse:
    """
    Create a new user story.
    
    This endpoint accepts a user story in text format and:
    1. Generates a unique ID for the story
    2. Validates the input
    3. Returns the story ID for subsequent operations (parsing, execution)
    
    The actual parsing happens asynchronously when the story is executed.
    
    Args:
        story_input: The user story input
        api_key: Validated API key (injected)
        config: Application configuration (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Story creation response with ID and status
        
    Raises:
        HTTPException: If validation fails or story creation fails
    """
    logger.info(
        "Creating new story",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "source": story_input.source,
                "text_length": len(story_input.text)
            }
        }
    )
    
    try:
        # Generate unique ID for the story
        story_id = str(uuid.uuid4())
        
        # TODO: Store story in database (Task 6.1)
        # For now, we just generate an ID and return success
        # In the full implementation, this would:
        # 1. Store the raw story input in the database
        # 2. Optionally trigger async parsing
        # 3. Return the story ID for tracking
        
        logger.info(
            "Story created successfully",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "story_id": story_id
                }
            }
        )
        
        return StoryCreateResponse(
            id=story_id,
            status="created",
            message="Story created successfully. Use the story ID to execute tests.",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(
            "Failed to create story",
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
            detail=f"Failed to create story: {str(e)}"
        )


@router.get(
    "",
    response_model=StoryListResponse,
    summary="List user stories",
    description="""
    Retrieve a paginated list of user stories.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Query Parameters:**
    - `skip`: Number of items to skip (default: 0)
    - `limit`: Maximum number of items to return (default: 100, max: 1000)
    - `source`: Filter by story source (manual, jira, azure_devops)
    - `parsing_method`: Filter by parsing method (llm_primary, llm_fallback, nlp_legacy)
    """
)
async def list_stories(
    api_key: ApiKeyDep,
    pagination: PaginationDep,
    request_id: RequestIdDep,
    source: Optional[str] = Query(None, description="Filter by story source"),
    parsing_method: Optional[str] = Query(None, description="Filter by parsing method")
) -> StoryListResponse:
    """
    List user stories with pagination and filtering.
    
    Args:
        api_key: Validated API key (injected)
        pagination: Pagination parameters (injected)
        request_id: Request ID for tracing (injected)
        source: Optional filter by story source
        parsing_method: Optional filter by parsing method
        
    Returns:
        Paginated list of stories
        
    Raises:
        HTTPException: If retrieval fails
    """
    logger.info(
        "Listing stories",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "skip": pagination["skip"],
                "limit": pagination["limit"],
                "source": source,
                "parsing_method": parsing_method
            }
        }
    )
    
    try:
        # TODO: Retrieve stories from database (Task 6.1)
        # For now, return empty list
        # In the full implementation, this would:
        # 1. Query database with filters and pagination
        # 2. Return list of ParsedStory objects
        
        stories: list[ParsedStory] = []
        total = 0
        
        logger.info(
            "Stories retrieved successfully",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "count": len(stories),
                    "total": total
                }
            }
        )
        
        return StoryListResponse(
            stories=stories,
            total=total,
            skip=pagination["skip"],
            limit=pagination["limit"]
        )
        
    except Exception as e:
        logger.error(
            "Failed to list stories",
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
            detail=f"Failed to list stories: {str(e)}"
        )


@router.get(
    "/{story_id}",
    response_model=StoryDetailResponse,
    summary="Get story details",
    description="""
    Retrieve detailed information about a specific user story.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    Returns the parsed story with all acceptance criteria, implicit requirements,
    and identified ambiguities.
    """
)
async def get_story(
    story_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> StoryDetailResponse:
    """
    Get details of a specific story.
    
    Args:
        story_id: The story ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Story details
        
    Raises:
        HTTPException: If story not found or retrieval fails
    """
    logger.info(
        "Getting story details",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "story_id": story_id
            }
        }
    )
    
    try:
        # TODO: Retrieve story from database (Task 6.1)
        # For now, return 404
        # In the full implementation, this would:
        # 1. Query database for story by ID
        # 2. Return ParsedStory object if found
        # 3. Raise 404 if not found
        
        logger.warning(
            "Story not found",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "story_id": story_id
                }
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story with ID {story_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get story",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "story_id": story_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get story: {str(e)}"
        )


@router.delete(
    "/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a story",
    description="""
    Delete a user story and all associated test runs and results.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Warning:** This operation is irreversible and will delete all test runs
    and results associated with this story.
    """
)
async def delete_story(
    story_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> None:
    """
    Delete a story.
    
    Args:
        story_id: The story ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Raises:
        HTTPException: If story not found or deletion fails
    """
    logger.info(
        "Deleting story",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "story_id": story_id
            }
        }
    )
    
    try:
        # TODO: Delete story from database (Task 6.1)
        # For now, return 404
        # In the full implementation, this would:
        # 1. Check if story exists
        # 2. Delete all associated test runs and results
        # 3. Delete the story
        # 4. Return 204 No Content
        
        logger.warning(
            "Story not found for deletion",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "story_id": story_id
                }
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story with ID {story_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete story",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "story_id": story_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete story: {str(e)}"
        )
