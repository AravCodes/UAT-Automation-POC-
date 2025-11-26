"""User story and acceptance criteria models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    """Priority levels for acceptance criteria and test scenarios."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class StoryInput(BaseModel):
    """Input model for user story submission."""
    
    text: str = Field(
        ...,
        min_length=10,
        description="User story text in standard format"
    )
    source: str = Field(
        default="manual",
        description="Source of the story (manual, jira, azure_devops)"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata about the story"
    )
    
    @field_validator("text")
    @classmethod
    def validate_text_not_empty(cls, v: str) -> str:
        """Ensure story text is not just whitespace."""
        if not v.strip():
            raise ValueError("Story text cannot be empty or whitespace only")
        return v.strip()
    
    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate source is one of the allowed values."""
        allowed_sources = ["manual", "jira", "azure_devops"]
        if v not in allowed_sources:
            raise ValueError(f"Source must be one of: {', '.join(allowed_sources)}")
        return v


class Ambiguity(BaseModel):
    """Represents an ambiguity or unclear requirement in the story."""
    
    text: str = Field(..., description="Description of the ambiguity")
    location: str = Field(..., description="Where in the story the ambiguity occurs")
    suggestion: Optional[str] = Field(
        None,
        description="Suggested clarification"
    )


class AcceptanceCriterion(BaseModel):
    """Represents a single acceptance criterion for a user story."""
    
    id: str = Field(..., description="Unique identifier for the criterion")
    text: str = Field(
        ...,
        min_length=5,
        description="Acceptance criterion text"
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Priority level of this criterion"
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="IDs of dependent criteria that must be satisfied first"
    )
    
    @field_validator("text")
    @classmethod
    def validate_text_not_empty(cls, v: str) -> str:
        """Ensure criterion text is not just whitespace."""
        if not v.strip():
            raise ValueError("Acceptance criterion text cannot be empty")
        return v.strip()


class ParsedStory(BaseModel):
    """Represents a fully parsed user story with extracted components."""
    
    id: str = Field(..., description="Unique identifier for the story")
    title: str = Field(..., min_length=3, description="Story title")
    role: str = Field(..., description="User role (As a...)")
    feature: str = Field(..., description="Desired feature (I want...)")
    benefit: str = Field(..., description="Expected benefit (So that...)")
    acceptance_criteria: list[AcceptanceCriterion] = Field(
        ...,
        min_length=1,
        description="List of acceptance criteria"
    )
    implicit_requirements: list[str] = Field(
        default_factory=list,
        description="Requirements implied but not explicitly stated"
    )
    ambiguities: list[Ambiguity] = Field(
        default_factory=list,
        description="Identified ambiguities or unclear requirements"
    )
    parsing_method: str = Field(
        ...,
        description="Method used to parse the story (llm_primary, llm_fallback, nlp_legacy)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the story was parsed"
    )
    
    @field_validator("title", "role", "feature", "benefit")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure required fields are not empty or whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()
    
    @field_validator("parsing_method")
    @classmethod
    def validate_parsing_method(cls, v: str) -> str:
        """Validate parsing method is one of the allowed values."""
        allowed_methods = ["llm_primary", "llm_fallback", "nlp_legacy"]
        if v not in allowed_methods:
            raise ValueError(f"Parsing method must be one of: {', '.join(allowed_methods)}")
        return v
    
    @field_validator("acceptance_criteria")
    @classmethod
    def validate_unique_criterion_ids(cls, v: list[AcceptanceCriterion]) -> list[AcceptanceCriterion]:
        """Ensure all acceptance criteria have unique IDs."""
        ids = [criterion.id for criterion in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Acceptance criteria must have unique IDs")
        return v
