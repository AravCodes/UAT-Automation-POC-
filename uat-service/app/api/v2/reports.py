"""
Report retrieval API endpoints.

This module provides REST API endpoints for retrieving test run results,
reports, and analytics with pagination and filtering support.

Requirements: 9.4, 9.5
"""

from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.dependencies import ApiKeyDep, PaginationDep, RequestIdDep
from app.core.logging import get_logger
from app.models.test_result import TestRunResult, RunStatus


logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2", tags=["reports"])


# ============================================================================
# Response Models
# ============================================================================

class RunSummary(BaseModel):
    """Summary information for a test run."""
    
    run_id: str = Field(..., description="Test run ID")
    story_id: str = Field(..., description="Story ID")
    status: RunStatus = Field(..., description="Run status")
    started_at: datetime = Field(..., description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    total_scenarios: int = Field(..., description="Total number of scenarios")
    passed_scenarios: int = Field(..., description="Number of passed scenarios")
    failed_scenarios: int = Field(..., description="Number of failed scenarios")
    pass_rate: float = Field(..., description="Pass rate percentage")


class RunListResponse(BaseModel):
    """Response model for listing test runs."""
    
    runs: list[RunSummary] = Field(..., description="List of test runs")
    total: int = Field(..., description="Total number of runs")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")


class RunDetailResponse(BaseModel):
    """Response model for detailed test run results."""
    
    run: TestRunResult = Field(..., description="Complete test run result")
    report_urls: dict[str, str] = Field(
        ...,
        description="URLs for different report formats"
    )


class ReportFormat(str):
    """Available report formats."""
    HTML = "html"
    JSON = "json"
    PDF = "pdf"


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/runs",
    response_model=RunListResponse,
    summary="List test runs",
    description="""
    Retrieve a paginated list of test runs with filtering support.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Query Parameters:**
    - `skip`: Number of items to skip (default: 0)
    - `limit`: Maximum number of items to return (default: 100, max: 1000)
    - `story_id`: Filter by story ID
    - `status`: Filter by run status (passed, failed, partial, running, error)
    - `from_date`: Filter runs started after this date (ISO 8601 format)
    - `to_date`: Filter runs started before this date (ISO 8601 format)
    
    **Example:**
    ```
    GET /api/v2/runs?story_id=abc123&status=passed&limit=50
    ```
    """
)
async def list_runs(
    api_key: ApiKeyDep,
    pagination: PaginationDep,
    request_id: RequestIdDep,
    story_id: Optional[str] = Query(None, description="Filter by story ID"),
    status: Optional[RunStatus] = Query(None, description="Filter by run status"),
    from_date: Optional[datetime] = Query(None, description="Filter runs after this date"),
    to_date: Optional[datetime] = Query(None, description="Filter runs before this date")
) -> RunListResponse:
    """
    List test runs with pagination and filtering.
    
    Args:
        api_key: Validated API key (injected)
        pagination: Pagination parameters (injected)
        request_id: Request ID for tracing (injected)
        story_id: Optional filter by story ID
        status: Optional filter by run status
        from_date: Optional filter by start date (after)
        to_date: Optional filter by start date (before)
        
    Returns:
        Paginated list of test runs
        
    Raises:
        HTTPException: If retrieval fails
    """
    logger.info(
        "Listing test runs",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "skip": pagination["skip"],
                "limit": pagination["limit"],
                "story_id": story_id,
                "status": status,
                "from_date": from_date,
                "to_date": to_date
            }
        }
    )
    
    try:
        # TODO: Retrieve runs from database (Task 6.1)
        # For now, return empty list
        # In the full implementation, this would:
        # 1. Query database with filters and pagination
        # 2. Return list of RunSummary objects
        # 3. Calculate pass rates and other metrics
        
        runs: list[RunSummary] = []
        total = 0
        
        logger.info(
            "Test runs retrieved successfully",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "count": len(runs),
                    "total": total
                }
            }
        )
        
        return RunListResponse(
            runs=runs,
            total=total,
            skip=pagination["skip"],
            limit=pagination["limit"]
        )
        
    except Exception as e:
        logger.error(
            "Failed to list test runs",
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
            detail=f"Failed to list test runs: {str(e)}"
        )


@router.get(
    "/runs/{run_id}",
    response_model=RunDetailResponse,
    summary="Get test run results",
    description="""
    Retrieve detailed results for a specific test run.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    Returns complete test run results including:
    - All scenario results
    - Step-by-step execution details
    - Screenshots and diagnostics
    - Performance metrics
    - Traceability to acceptance criteria
    
    Use the `report_urls` in the response to download formatted reports
    in HTML, JSON, or PDF format.
    """
)
async def get_run_results(
    run_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> RunDetailResponse:
    """
    Get detailed results for a test run.
    
    Args:
        run_id: The test run ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Detailed test run results
        
    Raises:
        HTTPException: If run not found or retrieval fails
    """
    logger.info(
        "Getting test run results",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "run_id": run_id
            }
        }
    )
    
    try:
        # TODO: Retrieve run results from database (Task 6.1)
        # For now, return 404
        # In the full implementation, this would:
        # 1. Query database for run by ID
        # 2. Return TestRunResult object if found
        # 3. Include URLs for different report formats
        # 4. Raise 404 if not found
        
        logger.warning(
            "Test run not found",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id
                }
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run with ID {run_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get test run results",
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
            detail=f"Failed to get test run results: {str(e)}"
        )


@router.get(
    "/runs/{run_id}/report",
    summary="Download test report",
    description="""
    Download a formatted test report in the specified format.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Query Parameters:**
    - `format`: Report format (html, json, pdf) - default: html
    
    **Formats:**
    - `html`: Business-friendly HTML report with charts and visualizations
    - `json`: Machine-readable JSON format for integrations
    - `pdf`: Printable PDF report (if enabled in configuration)
    
    **Example:**
    ```
    GET /api/v2/runs/{run_id}/report?format=html
    ```
    """
)
async def download_report(
    run_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep,
    format: Literal["html", "json", "pdf"] = Query(
        "html",
        description="Report format"
    )
) -> FileResponse:
    """
    Download a formatted test report.
    
    Args:
        run_id: The test run ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        format: Report format (html, json, pdf)
        
    Returns:
        Report file
        
    Raises:
        HTTPException: If run not found or report generation fails
    """
    logger.info(
        "Downloading test report",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "run_id": run_id,
                "format": format
            }
        }
    )
    
    try:
        # TODO: Generate and return report (Task 9)
        # For now, return 404
        # In the full implementation, this would:
        # 1. Retrieve run results from database
        # 2. Generate report in requested format
        # 3. Return file response with appropriate content type
        # 4. Set proper filename and headers
        
        if format == "pdf":
            # Check if PDF reports are enabled
            # TODO: Check config.enable_pdf_reports
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF reports are not enabled. Set ENABLE_PDF_REPORTS=true in configuration."
            )
        
        logger.warning(
            "Test run not found for report generation",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id,
                    "format": format
                }
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run with ID {run_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to download report",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id,
                    "format": format,
                    "error": str(e)
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download report: {str(e)}"
        )


@router.get(
    "/runs/{run_id}/artifacts",
    summary="List test artifacts",
    description="""
    List all artifacts (screenshots, logs, etc.) for a test run.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    Returns a list of artifact URLs that can be downloaded individually.
    """
)
async def list_artifacts(
    run_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> dict:
    """
    List artifacts for a test run.
    
    Args:
        run_id: The test run ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        List of artifact URLs
        
    Raises:
        HTTPException: If run not found
    """
    logger.info(
        "Listing test artifacts",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "run_id": run_id
            }
        }
    )
    
    try:
        # TODO: List artifacts from storage (Task 6.2)
        # For now, return empty list
        # In the full implementation, this would:
        # 1. Query file storage for artifacts by run_id
        # 2. Return list of artifact metadata with download URLs
        # 3. Group by type (screenshots, logs, network traces, etc.)
        
        artifacts = {
            "run_id": run_id,
            "screenshots": [],
            "logs": [],
            "network_traces": [],
            "dom_snapshots": [],
            "total_count": 0,
            "total_size_bytes": 0
        }
        
        logger.info(
            "Test artifacts listed successfully",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id,
                    "artifact_count": artifacts["total_count"]
                }
            }
        )
        
        return artifacts
        
    except Exception as e:
        logger.error(
            "Failed to list artifacts",
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
            detail=f"Failed to list artifacts: {str(e)}"
        )


@router.get(
    "/runs/{run_id}/analytics",
    summary="Get test run analytics",
    description="""
    Get analytics and insights for a test run.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    Returns:
    - Pass/fail trends
    - Flaky test detection
    - Performance metrics
    - Coverage analysis
    - Comparison with previous runs
    """
)
async def get_run_analytics(
    run_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> dict:
    """
    Get analytics for a test run.
    
    Args:
        run_id: The test run ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Returns:
        Analytics data
        
    Raises:
        HTTPException: If run not found or analytics generation fails
    """
    logger.info(
        "Getting test run analytics",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "run_id": run_id
            }
        }
    )
    
    try:
        # TODO: Generate analytics (Task 9.3)
        # For now, return basic structure
        # In the full implementation, this would:
        # 1. Retrieve run results and historical data
        # 2. Calculate trends and metrics
        # 3. Detect flaky tests
        # 4. Compare with previous runs
        # 5. Generate insights and recommendations
        
        analytics = {
            "run_id": run_id,
            "summary": {
                "pass_rate": 0.0,
                "avg_duration_ms": 0,
                "total_scenarios": 0,
                "flaky_scenarios": 0
            },
            "trends": {
                "pass_rate_trend": [],
                "duration_trend": [],
                "flakiness_trend": []
            },
            "flaky_tests": [],
            "performance": {
                "avg_step_duration_ms": 0,
                "slowest_scenarios": [],
                "fastest_scenarios": []
            },
            "coverage": {
                "criteria_covered": 0,
                "criteria_total": 0,
                "coverage_percentage": 0.0
            },
            "comparison": {
                "previous_run_id": None,
                "pass_rate_change": 0.0,
                "duration_change_ms": 0,
                "new_failures": [],
                "new_passes": []
            }
        }
        
        logger.info(
            "Test run analytics generated successfully",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id
                }
            }
        )
        
        return analytics
        
    except Exception as e:
        logger.error(
            "Failed to get analytics",
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
            detail=f"Failed to get analytics: {str(e)}"
        )


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a test run",
    description="""
    Delete a test run and all associated artifacts.
    
    **Authentication:** Requires valid API key via X-API-Key header.
    
    **Warning:** This operation is irreversible and will delete all test results,
    screenshots, logs, and other artifacts associated with this run.
    """
)
async def delete_run(
    run_id: str,
    api_key: ApiKeyDep,
    request_id: RequestIdDep
) -> None:
    """
    Delete a test run.
    
    Args:
        run_id: The test run ID
        api_key: Validated API key (injected)
        request_id: Request ID for tracing (injected)
        
    Raises:
        HTTPException: If run not found or deletion fails
    """
    logger.info(
        "Deleting test run",
        extra={
            "extra_fields": {
                "request_id": request_id,
                "run_id": run_id
            }
        }
    )
    
    try:
        # TODO: Delete run from database and artifacts (Task 6.1, 6.2)
        # For now, return 404
        # In the full implementation, this would:
        # 1. Check if run exists
        # 2. Delete all artifacts from file storage
        # 3. Delete run results from database
        # 4. Return 204 No Content
        
        logger.warning(
            "Test run not found for deletion",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "run_id": run_id
                }
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run with ID {run_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete test run",
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
            detail=f"Failed to delete test run: {str(e)}"
        )
