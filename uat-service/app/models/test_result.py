"""Test execution result models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from .test_scenario import TestStep


class StepStatus(str, Enum):
    """Status of a test step execution."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class ScenarioStatus(str, Enum):
    """Status of a test scenario execution."""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    ERROR = "error"


class RunStatus(str, Enum):
    """Status of a complete test run."""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    RUNNING = "running"
    ERROR = "error"


class StepResult(BaseModel):
    """Result of executing a single test step."""
    
    step: TestStep = Field(..., description="The test step that was executed")
    status: StepStatus = Field(..., description="Execution status of the step")
    screenshot_path: Optional[str] = Field(
        None,
        description="Path to screenshot captured during this step"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if step failed"
    )
    dom_snapshot: Optional[str] = Field(
        None,
        description="DOM snapshot at time of failure"
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Duration of step execution in milliseconds"
    )
    console_logs: list[str] = Field(
        default_factory=list,
        description="Console logs captured during step execution"
    )
    network_requests: list[str] = Field(
        default_factory=list,
        description="Network requests made during step execution"
    )
    
    @field_validator("screenshot_path", "dom_snapshot")
    @classmethod
    def validate_path_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure paths are not empty strings."""
        if v is not None and not v.strip():
            return None
        return v


class ScenarioResult(BaseModel):
    """Result of executing a test scenario."""
    
    scenario_id: str = Field(..., description="ID of the executed scenario")
    status: ScenarioStatus = Field(..., description="Overall scenario status")
    step_results: list[StepResult] = Field(
        ...,
        description="Results of individual steps"
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Total duration of scenario execution in milliseconds"
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of times this scenario was retried"
    )
    is_flaky: bool = Field(
        default=False,
        description="Whether this scenario passed after retry (flaky test indicator)"
    )
    error_summary: Optional[str] = Field(
        None,
        description="Summary of errors encountered"
    )
    
    @field_validator("scenario_id")
    @classmethod
    def validate_id_not_empty(cls, v: str) -> str:
        """Ensure scenario ID is not empty."""
        if not v.strip():
            raise ValueError("Scenario ID cannot be empty")
        return v.strip()


class RunDiagnostics(BaseModel):
    """Diagnostic information for a test run."""
    
    total_scenarios: int = Field(..., ge=0, description="Total number of scenarios")
    passed_scenarios: int = Field(..., ge=0, description="Number of passed scenarios")
    failed_scenarios: int = Field(..., ge=0, description="Number of failed scenarios")
    skipped_scenarios: int = Field(
        default=0,
        ge=0,
        description="Number of skipped scenarios"
    )
    total_steps: int = Field(..., ge=0, description="Total number of steps executed")
    passed_steps: int = Field(..., ge=0, description="Number of passed steps")
    failed_steps: int = Field(..., ge=0, description="Number of failed steps")
    flaky_scenarios: list[str] = Field(
        default_factory=list,
        description="IDs of scenarios that were flaky"
    )
    execution_timeline: list[dict] = Field(
        default_factory=list,
        description="Timeline of execution events with timestamps"
    )
    performance_metrics: dict = Field(
        default_factory=dict,
        description="Performance metrics (avg step time, etc.)"
    )
    
    @field_validator("passed_scenarios", "failed_scenarios", "skipped_scenarios")
    @classmethod
    def validate_scenario_counts(cls, v: int, info) -> int:
        """Validate scenario counts are non-negative."""
        if v < 0:
            raise ValueError("Scenario counts cannot be negative")
        return v


class TestRunResult(BaseModel):
    """Complete result of a test run."""
    
    id: str = Field(..., description="Unique identifier for this test run")
    story_id: str = Field(..., description="ID of the story being tested")
    started_at: datetime = Field(..., description="When the test run started")
    completed_at: datetime = Field(..., description="When the test run completed")
    status: RunStatus = Field(..., description="Overall status of the test run")
    scenario_results: list[ScenarioResult] = Field(
        ...,
        description="Results of all executed scenarios"
    )
    diagnostics: RunDiagnostics = Field(
        ...,
        description="Diagnostic information and metrics"
    )
    environment: dict = Field(
        default_factory=dict,
        description="Environment information (browser, OS, etc.)"
    )
    configuration: dict = Field(
        default_factory=dict,
        description="Test configuration used for this run"
    )
    
    @field_validator("id", "story_id")
    @classmethod
    def validate_id_not_empty(cls, v: str) -> str:
        """Ensure IDs are not empty."""
        if not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()
    
    @field_validator("completed_at")
    @classmethod
    def validate_completed_after_started(cls, v: datetime, info) -> datetime:
        """Ensure completed_at is after started_at."""
        if "started_at" in info.data and v < info.data["started_at"]:
            raise ValueError("completed_at must be after started_at")
        return v
