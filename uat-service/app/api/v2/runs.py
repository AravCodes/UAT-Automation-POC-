"""
Test execution API endpoints.

This module provides REST API endpoints for executing test runs,
checking run status, and managing test execution lifecycle.

Requirements: 9.3
"""

import uuid
import asyncio
from datetime import datetime
from typing import Optional
from enum import Enum
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.dependencies import ApiKeyDep, ConfigDep, RequestIdDep
from app.core.logging import get_logger
from app.models.test_result import TestRunResult, RunStatus


logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2", tags=["test-execution"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ExecutionMode(str, Enum):
    """Execution mode for test runs."""
    SYNC = "sync"
    ASYNC = "async"


class RunRequest(BaseModel):
    """Request model for starting a test run."""
    
    target_url: str = Field(
        ...,
        description="URL of the application to test"
    )
    mode: ExecutionMode = Field(
        default=ExecutionMode.ASYNC,
        description="Execution mode (sync or async)"
    )
    webhook_url: Optional[str] = Field(
        None,
        description="Webhook URL to notify on completion (async mode only)"
    )
    concurrency: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="Number of parallel scenarios (overrides config)"
    )
    headless: Optional[bool] = Field(
        None,
        description="Run browser in headless mode (overrides config)"
    )
    timeout: Optional[int] = Field(
        None,
        ge=5000,
        le=300000,
        description="Test timeout in milliseconds (overrides config)"
    )


class RunStartResponse(BaseModel):
    """Response model for starting a test run."""
    
    run_id: str = Field(..., description="Unique identifier for the test run")
    story_id: str = Field(..., description="ID of the story being tested")
    status: str = Field(..., description="Current status of the run")
    mode: ExecutionMode = Field(..., description="Execution mode")
    message: str = Field(..., description="Human-readable message")
    started_at: datetime = Field(..., description="When the run started")
    status_url: str = Field(..., description="URL to check run status")
    result_url: str = Field(..., description="URL to get results (available when complete)")


class RunStatusResponse(BaseModel):
    """Response model for checking run status."""
    
    run_id: str = Field(..., description="Test run ID")
    story_id: str = Field(..., description="Story ID")
    status: RunStatus = Field(..., description="Current run status")
    started_at: datetime = Field(..., description="When the run started")
    completed_at: Optional[datetime] = Field(None, description="When the run completed")
    progress: dict = Field(
        default_factory=dict,
        description="Progress information (scenarios completed, etc.)"
    )
    result_url: Optional[str] = Field(
        None,
        description="URL to get full results (available when complete)"
    )


# ============================================================================
# In-memory storage for run status (temporary until database is implemented)
# ============================================================================

# This will be replaced with database storage in Task 6.1
_active_runs: dict[str, dict] = {}


# ============================================================================
# Background task for async execution
# ============================================================================

async def execute_test_run_async(
    run_id: str,
    story_id: str,
    target_url: str,
    config: dict,
    webhook_url: Optional[str] = None
):
    """
    Execute test run asynchronously in the background.
    
    This function runs the test execution in the background and updates
    the run status. When complete, it optionally sends a webhook notification.
    
    Args:
        run_id: The test run ID
        story_id: The story ID
        target_url: Target application URL
        config: Test configuration
        webhook_url: Optional webhook URL for completion notification
    """
    logger.info(
        "Starting async test execution",
        extra={
            "extra_fields": {
                "run_id": run_id,
                "story_id": story_id,
                "target_url": target_url
            }
        }
    )
    
    try:
        # Update status to running
        _active_runs[run_id]["status"] = RunStatus.RUNNING
        _active_runs[run_id]["progress"] = {
            "total_scenarios": 0,
            "completed_scenarios": 0,
            "passed_scenarios": 0,
            "failed_scenarios": 0
        }
        
        # TODO: Implement actual test execution (Task 8)
        # For now, simulate execution with a delay
        await asyncio.sleep(2)
        
        # Simulate completion
        _active_runs[run_id]["status"] = RunStatus.PASSED
        _active_runs[run_id]["completed_at"] = datetime.utcnow()
        _active_runs[run_id]["progress"] = {
            "total_scenarios": 5,
            "completed_scenarios": 5,
            "passed_scenarios": 5,
            "failed_scenarios": 0
        }
        
        logger.info(
            "Async test execution completed",
            extra={
                "extra_fields": {
                    "run_id": run_id,
                    "story_id": story_id,
                    "status": _active_runs[run_id]["status"]
                }
            }
        )
        
        # Send webhook notification if configured
        if webhook_url:
            # TODO: Implement webhook notification (Task 10.4)
            logger.info(
                "Webhook notification would be sent",
                extra={
                    "extra_fields": {
                        "run_id": run_id,
                        "webhook_url": webhook_url
                    }
                }
            )
        
    except Exception as e:
        logger.error(
            "Async test execution failed",
            extra={
                "extra_fields": {
                    "run_id": run_id,
                    "story_id": story_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        _active_runs[run_id]["status"] = RunStatus.ERROR
        _active_runs[run_id]["completed_at"] = datetime.utcnow()
        _active_runs[run_id]["error"] = str(e)


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/stories/{story_id}/run",
    response_model=RunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute tests for a story",
    description="""
    Start test execution for a user story.
    
    This endpoint:
    1. Parses the story (if not already parsed)
    2. Generates test scenarios
    3. Executes the scenarios against the target application
    4. Returns a run ID for tracking
    
    **Execution Modes:**
    - `async` (default): Returns immediately with run ID. Poll status endpoint for progress.
    - `sync`: Waits for execution to complete before returning results.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Example Request:**
    ```json
    {
        "target_url": "http://localhost:5173",
        "mode": "async",
        "webhook_url": "https://example.com/webhook",
        "concurrency": 3,
        "headless": true
    }
    ```
    """
)
async def start_test_run(
    story_id: str,
    run_request: RunRequest,
    background_tasks: BackgroundTasks,
    api_key: ApiKeyDep,
    config: ConfigDep,
    request_id: RequestIdDep
) -> RunStartResponse:
    """
    Start a test run for a story.
    
    Args:
        story_id: The story ID to test
        run_request: Test run configuration
        background_tasks: FastAPI background tasks
        api_key: Validated API key (injected)
        config: Application configuration (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Run start response with run ID and status URL
        
    Raises:
        HTTPException: If story not found or execution fails to start
    """
    logger.info(
        "Starting test run",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "story_id": story_id,
                "target_url": run_request.target_url,
                "mode": run_request.mode
            }
        }
    )
    
    try:
        # TODO: Verify story exists in database (Task 6.1)
        # For now, we'll proceed with the run
        
        # Generate unique run ID
        run_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        # Build execution config
        execution_config = {
            "target_url": run_request.target_url,
            "concurrency": run_request.concurrency or config.concurrency,
            "headless": run_request.headless if run_request.headless is not None else config.headless_mode,
            "timeout": run_request.timeout or config.test_timeout
        }
        
        # Store run info
        _active_runs[run_id] = {
            "run_id": run_id,
            "story_id": story_id,
            "status": RunStatus.RUNNING if run_request.mode == ExecutionMode.ASYNC else RunStatus.RUNNING,
            "started_at": started_at,
            "completed_at": None,
            "config": execution_config,
            "webhook_url": run_request.webhook_url
        }
        
        if run_request.mode == ExecutionMode.ASYNC:
            # Start async execution in background
            background_tasks.add_task(
                execute_test_run_async,
                run_id=run_id,
                story_id=story_id,
                target_url=run_request.target_url,
                config=execution_config,
                webhook_url=run_request.webhook_url
            )
            
            logger.info(
                "Test run started in async mode",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "run_id": run_id,
                        "story_id": story_id
                    }
                }
            )
            
            return RunStartResponse(
                run_id=run_id,
                story_id=story_id,
                status="running",
                mode=ExecutionMode.ASYNC,
                message="Test run started. Use the status URL to check progress.",
                started_at=started_at,
                status_url=f"/api/v2/runs/{run_id}/status",
                result_url=f"/api/v2/runs/{run_id}"
            )
        else:
            # Sync execution - execute and wait
            # TODO: Implement sync execution (Task 8)
            # For now, simulate with delay
            await asyncio.sleep(1)
            
            _active_runs[run_id]["status"] = RunStatus.PASSED
            _active_runs[run_id]["completed_at"] = datetime.utcnow()
            
            logger.info(
                "Test run completed in sync mode",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "run_id": run_id,
                        "story_id": story_id
                    }
                }
            )
            
            return RunStartResponse(
                run_id=run_id,
                story_id=story_id,
                status="completed",
                mode=ExecutionMode.SYNC,
                message="Test run completed. Use the result URL to get full results.",
                started_at=started_at,
                status_url=f"/api/v2/runs/{run_id}/status",
                result_url=f"/api/v2/runs/{run_id}"
            )
        
    except Exception as e:
        logger.error(
            "Failed to start test run",
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
            detail=f"Failed to start test run: {str(e)}"
        )


@router.get(
    "/runs/{run_id}/status",
    response_model=RunStatusResponse,
    summary="Get test run status",
    description="""
    Check the status of a test run.
    
    Use this endpoint to poll for progress when running tests in async mode.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Status Values:**
    - `running`: Test execution in progress
    - `passed`: All tests passed
    - `failed`: Some tests failed
    - `partial`: Some tests passed, some failed
    - `error`: Execution error occurred
    """
)
async def get_run_status(
    run_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> RunStatusResponse:
    """
    Get the status of a test run.
    
    Args:
        run_id: The test run ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Run status information
        
    Raises:
        HTTPException: If run not found
    """
    logger.info(
        "Getting run status",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "run_id": run_id
            }
        }
    )
    
    try:
        # TODO: Retrieve run status from database (Task 6.1)
        # For now, check in-memory storage
        
        if run_id not in _active_runs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test run with ID {run_id} not found"
            )
        
        run_info = _active_runs[run_id]
        
        result_url = None
        if run_info["status"] in [RunStatus.PASSED, RunStatus.FAILED, RunStatus.PARTIAL, RunStatus.ERROR]:
            result_url = f"/api/v2/runs/{run_id}"
        
        return RunStatusResponse(
            run_id=run_id,
            story_id=run_info["story_id"],
            status=run_info["status"],
            started_at=run_info["started_at"],
            completed_at=run_info.get("completed_at"),
            progress=run_info.get("progress", {}),
            result_url=result_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get run status",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get run status: {str(e)}"
        )


@router.post(
    "/runs/{run_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a running test",
    description="""
    Cancel a test run that is currently in progress.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Note:** Only runs with status `running` can be cancelled.
    """
)
async def cancel_test_run(
    run_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> dict:
    """
    Cancel a running test.
    
    Args:
        run_id: The test run ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Cancellation confirmation
        
    Raises:
        HTTPException: If run not found or cannot be cancelled
    """
    logger.info(
        "Cancelling test run",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "run_id": run_id
            }
        }
    )
    
    try:
        # TODO: Implement run cancellation (Task 8)
        # For now, just update status
        
        if run_id not in _active_runs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test run with ID {run_id} not found"
            )
        
        run_info = _active_runs[run_id]
        
        if run_info["status"] != RunStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel run with status {run_info['status']}"
            )
        
        # Update status
        _active_runs[run_id]["status"] = RunStatus.ERROR
        _active_runs[run_id]["completed_at"] = datetime.utcnow()
        _active_runs[run_id]["error"] = "Cancelled by user"
        
        logger.info(
            "Test run cancelled",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id
                }
            }
        )
        
        return {
            "run_id": run_id,
            "status": "cancelled",
            "message": "Test run cancelled successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to cancel test run",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel test run: {str(e)}"
        )
