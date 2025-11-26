"""Test scenario and test step models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from .story import Priority


class ScenarioType(str, Enum):
    """Type of test scenario."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    EDGE_CASE = "edge_case"


class ActionType(str, Enum):
    """Types of actions that can be performed in a test step."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    ASSERT = "assert"
    WAIT = "wait"
    HOVER = "hover"
    SCROLL = "scroll"


class TestStep(BaseModel):
    """Represents a single step in a test scenario."""
    
    action: ActionType = Field(..., description="Type of action to perform")
    target: str = Field(..., description="Element description or selector")
    value: Optional[str] = Field(
        None,
        description="Value to input (for type, select actions)"
    )
    expected_outcome: Optional[str] = Field(
        None,
        description="Expected result after this step"
    )
    
    @field_validator("target")
    @classmethod
    def validate_target_not_empty(cls, v: str) -> str:
        """Ensure target is not empty or whitespace."""
        if not v.strip():
            raise ValueError("Target cannot be empty or whitespace only")
        return v.strip()
    
    @field_validator("value")
    @classmethod
    def validate_value_for_action(cls, v: Optional[str], info) -> Optional[str]:
        """Validate that value is provided for actions that require it."""
        if v is not None:
            return v.strip() if v.strip() else None
        return v


class TestScenario(BaseModel):
    """Represents a complete test scenario in Given-When-Then format."""
    
    id: str = Field(..., description="Unique identifier for the scenario")
    criterion_id: str = Field(
        ...,
        description="ID of the acceptance criterion this scenario tests"
    )
    type: ScenarioType = Field(
        ...,
        description="Type of scenario (positive, negative, edge_case)"
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Priority level of this scenario"
    )
    given: list[str] = Field(
        ...,
        min_length=1,
        description="Preconditions (Given statements)"
    )
    when: list[str] = Field(
        ...,
        min_length=1,
        description="Actions (When statements)"
    )
    then: list[str] = Field(
        ...,
        min_length=1,
        description="Expected outcomes (Then statements)"
    )
    test_steps: list[TestStep] = Field(
        ...,
        min_length=1,
        description="Executable test steps"
    )
    
    @field_validator("given", "when", "then")
    @classmethod
    def validate_statements_not_empty(cls, v: list[str]) -> list[str]:
        """Ensure all Given-When-Then statements are not empty."""
        cleaned = [s.strip() for s in v if s.strip()]
        if not cleaned:
            raise ValueError("Given-When-Then statements cannot be empty")
        return cleaned
    
    @field_validator("id", "criterion_id")
    @classmethod
    def validate_id_not_empty(cls, v: str) -> str:
        """Ensure IDs are not empty or whitespace."""
        if not v.strip():
            raise ValueError("ID cannot be empty or whitespace only")
        return v.strip()
