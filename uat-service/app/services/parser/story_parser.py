"""
Main story parser with LLM integration.

This module provides the primary story parsing functionality using LLM
with automatic fallback to legacy NLP parser when LLM fails.

Requirements: 2.1, 2.5
"""

import uuid
from typing import Optional
from datetime import datetime

from app.models.story import (
    StoryInput,
    ParsedStory,
    AcceptanceCriterion,
    Ambiguity,
    Priority,
)
from app.services.llm.groq_client import GroqClient
from app.services.llm.prompt_templates import get_story_parsing_prompt
from app.core.exceptions import (
    ParsingException,
    InvalidStoryFormatException,
    LLMException,
    ModelNotAvailableException,
)
from app.core.logging import get_logger


logger = get_logger(__name__)


class ValidationResult:
    """Result of story completeness validation."""
    
    def __init__(
        self,
        is_complete: bool,
        missing_fields: list[str],
        warnings: list[str]
    ):
        self.is_complete = is_complete
        self.missing_fields = missing_fields
        self.warnings = warnings


class StoryParser:
    """
    Main story parser with LLM integration and fallback support.
    
    This parser orchestrates story parsing using LLM with automatic
    fallback to legacy NLP parser when LLM fails. It extracts user
    stories, acceptance criteria, implicit requirements, and flags
    ambiguities.
    
    Requirements: 2.1, 2.5
    """
    
    def __init__(self, groq_client: Optional[GroqClient] = None):
        """
        Initialize the story parser.
        
        Args:
            groq_client: Optional GroqClient instance (creates new if None)
        """
        self.groq_client = groq_client
        self._owns_client = groq_client is None
        
        logger.info("story_parser_initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self._owns_client:
            self.groq_client = GroqClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._owns_client and self.groq_client:
            await self.groq_client.close()
    
    async def parse(self, story_input: StoryInput) -> ParsedStory:
        """
        Main parsing entry point with fallback handling.
        
        This method attempts to parse the story using LLM first,
        then falls back to legacy NLP parser if LLM fails.
        
        Args:
            story_input: The user story input to parse
        
        Returns:
            ParsedStory: Fully parsed story with all components
            
        Raises:
            ParsingException: If all parsing methods fail
            InvalidStoryFormatException: If story format is invalid
        
        Requirements: 2.1, 2.5
        """
        logger.info(
            "story_parsing_started",
            extra={
                "source": story_input.source,
                "text_length": len(story_input.text),
            }
        )
        
        # Try LLM-based parsing first
        try:
            parsed_story = await self._parse_with_llm(story_input.text)
            
            # Add metadata from input
            parsed_story.id = str(uuid.uuid4())
            parsed_story.created_at = datetime.utcnow()
            
            logger.info(
                "story_parsing_completed",
                extra={
                    "story_id": parsed_story.id,
                    "parsing_method": parsed_story.parsing_method,
                    "criteria_count": len(parsed_story.acceptance_criteria),
                    "ambiguities_count": len(parsed_story.ambiguities),
                }
            )
            
            return parsed_story
            
        except ModelNotAvailableException as e:
            # Both LLM models failed, try legacy NLP fallback
            logger.warning(
                "llm_parsing_failed_trying_legacy",
                extra={
                    "error": str(e),
                }
            )
            
            try:
                parsed_story = await self._parse_with_legacy_nlp(story_input.text)
                
                # Add metadata from input
                parsed_story.id = str(uuid.uuid4())
                parsed_story.created_at = datetime.utcnow()
                
                logger.info(
                    "story_parsing_completed_with_legacy",
                    extra={
                        "story_id": parsed_story.id,
                        "parsing_method": parsed_story.parsing_method,
                        "criteria_count": len(parsed_story.acceptance_criteria),
                    }
                )
                
                return parsed_story
                
            except Exception as legacy_error:
                logger.error(
                    "all_parsing_methods_failed",
                    extra={
                        "llm_error": str(e),
                        "legacy_error": str(legacy_error),
                    }
                )
                
                raise ParsingException(
                    "Failed to parse story with all available methods",
                    details={
                        "llm_error": str(e),
                        "legacy_error": str(legacy_error),
                    }
                )
        
        except LLMException as e:
            # LLM error but not complete failure, try legacy
            logger.warning(
                "llm_parsing_error_trying_legacy",
                extra={
                    "error": str(e),
                }
            )
            
            try:
                parsed_story = await self._parse_with_legacy_nlp(story_input.text)
                parsed_story.id = str(uuid.uuid4())
                parsed_story.created_at = datetime.utcnow()
                
                logger.info(
                    "story_parsing_completed_with_legacy_after_llm_error",
                    extra={
                        "story_id": parsed_story.id,
                        "parsing_method": parsed_story.parsing_method,
                    }
                )
                
                return parsed_story
                
            except Exception as legacy_error:
                logger.error(
                    "all_parsing_methods_failed_after_llm_error",
                    extra={
                        "llm_error": str(e),
                        "legacy_error": str(legacy_error),
                    }
                )
                
                raise ParsingException(
                    "Failed to parse story with all available methods",
                    details={
                        "llm_error": str(e),
                        "legacy_error": str(legacy_error),
                    }
                )
    
    async def _parse_with_llm(self, story_text: str) -> ParsedStory:
        """
        Parse user story using LLM (primary method).
        
        This method uses Groq's LLM API to intelligently parse the story,
        extracting all components including implicit requirements and
        ambiguities.
        
        Args:
            story_text: The user story text to parse
        
        Returns:
            ParsedStory: Parsed story with parsing_method set to llm_primary or llm_fallback
            
        Raises:
            LLMException: If LLM parsing fails
            InvalidStoryFormatException: If parsed data is invalid
        
        Requirements: 2.1, 2.5
        """
        logger.debug(
            "llm_parsing_started",
            extra={
                "text_length": len(story_text),
            }
        )
        
        # Get the prompt template
        prompt = get_story_parsing_prompt(story_text)
        
        # Call LLM
        try:
            response = await self.groq_client.parse_story(
                story_text=story_text,
                prompt_template=prompt,
            )
            
            # Determine which model was used
            parsing_method = "llm_primary"  # Default assumption
            
            # Extract and validate components
            title = response.get("title", "").strip()
            role = response.get("role", "").strip()
            feature = response.get("feature", "").strip()
            benefit = response.get("benefit", "").strip()
            
            if not all([title, role, feature, benefit]):
                missing = []
                if not title:
                    missing.append("title")
                if not role:
                    missing.append("role")
                if not feature:
                    missing.append("feature")
                if not benefit:
                    missing.append("benefit")
                
                raise InvalidStoryFormatException(
                    "LLM failed to extract required story components",
                    story_text=story_text,
                    missing_fields=missing,
                )
            
            # Parse acceptance criteria
            criteria_data = response.get("acceptance_criteria", [])
            if not criteria_data:
                raise InvalidStoryFormatException(
                    "No acceptance criteria found in story",
                    story_text=story_text,
                    missing_fields=["acceptance_criteria"],
                )
            
            acceptance_criteria = []
            for idx, criterion_data in enumerate(criteria_data):
                criterion = AcceptanceCriterion(
                    id=criterion_data.get("id", f"AC-{idx+1}"),
                    text=criterion_data.get("text", ""),
                    priority=Priority(criterion_data.get("priority", "medium")),
                    dependencies=criterion_data.get("dependencies", []),
                )
                acceptance_criteria.append(criterion)
            
            # Parse implicit requirements
            implicit_requirements = response.get("implicit_requirements", [])
            
            # Parse ambiguities
            ambiguities_data = response.get("ambiguities", [])
            ambiguities = []
            for amb_data in ambiguities_data:
                ambiguity = Ambiguity(
                    text=amb_data.get("text", ""),
                    location=amb_data.get("location", ""),
                    suggestion=amb_data.get("suggestion"),
                )
                ambiguities.append(ambiguity)
            
            # Create ParsedStory
            parsed_story = ParsedStory(
                id="",  # Will be set by caller
                title=title,
                role=role,
                feature=feature,
                benefit=benefit,
                acceptance_criteria=acceptance_criteria,
                implicit_requirements=implicit_requirements,
                ambiguities=ambiguities,
                parsing_method=parsing_method,
            )
            
            logger.debug(
                "llm_parsing_completed",
                extra={
                    "criteria_count": len(acceptance_criteria),
                    "implicit_requirements_count": len(implicit_requirements),
                    "ambiguities_count": len(ambiguities),
                }
            )
            
            return parsed_story
            
        except LLMException:
            # Re-raise LLM exceptions to trigger fallback
            raise
        
        except Exception as e:
            logger.error(
                "llm_parsing_unexpected_error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            
            raise ParsingException(
                f"Unexpected error during LLM parsing: {str(e)}",
                original_exception=e,
            )
    
    async def _parse_with_legacy_nlp(self, story_text: str) -> ParsedStory:
        """
        Parse user story using legacy NLP parser (fallback method).
        
        This method uses the archived NLP-based parser as a fallback
        when LLM parsing fails. It provides degraded functionality
        with a warning.
        
        Args:
            story_text: The user story text to parse
        
        Returns:
            ParsedStory: Parsed story with parsing_method set to nlp_legacy
            
        Raises:
            ParsingException: If NLP parsing fails
        
        Requirements: 1.3, 7.6
        """
        logger.warning(
            "using_legacy_nlp_parser",
            extra={
                "text_length": len(story_text),
            }
        )
        
        # Import legacy parser (lazy import to avoid loading if not needed)
        try:
            from app.services.parser.legacy_nlp import LegacyNLPParser
            
            parser = LegacyNLPParser()
            parsed_story = await parser.parse(story_text)
            
            logger.info(
                "legacy_nlp_parsing_completed",
                extra={
                    "criteria_count": len(parsed_story.acceptance_criteria),
                }
            )
            
            return parsed_story
            
        except ImportError as e:
            logger.error(
                "legacy_nlp_parser_not_available",
                extra={
                    "error": str(e),
                }
            )
            
            raise ParsingException(
                "Legacy NLP parser is not available",
                details={"error": str(e)},
                original_exception=e,
            )
        
        except Exception as e:
            logger.error(
                "legacy_nlp_parsing_failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            
            raise ParsingException(
                f"Legacy NLP parsing failed: {str(e)}",
                original_exception=e,
            )
    
    def validate_completeness(self, story: ParsedStory) -> ValidationResult:
        """
        Check if story has sufficient detail for testing.
        
        This method validates that the parsed story contains all
        necessary information for test generation and execution.
        
        Args:
            story: The parsed story to validate
        
        Returns:
            ValidationResult: Validation result with missing fields and warnings
        
        Requirements: 2.5
        """
        missing_fields = []
        warnings = []
        
        # Check required fields
        if not story.title or len(story.title) < 3:
            missing_fields.append("title")
        
        if not story.role:
            missing_fields.append("role")
        
        if not story.feature:
            missing_fields.append("feature")
        
        if not story.benefit:
            missing_fields.append("benefit")
        
        if not story.acceptance_criteria:
            missing_fields.append("acceptance_criteria")
        
        # Check for warnings
        if len(story.acceptance_criteria) < 2:
            warnings.append("Story has only one acceptance criterion - consider adding more for comprehensive testing")
        
        if story.ambiguities:
            warnings.append(f"Story has {len(story.ambiguities)} ambiguities that should be clarified")
        
        if not story.implicit_requirements:
            warnings.append("No implicit requirements identified - consider security, performance, accessibility")
        
        # Check acceptance criteria quality
        for criterion in story.acceptance_criteria:
            if len(criterion.text) < 10:
                warnings.append(f"Acceptance criterion '{criterion.id}' is very short and may lack detail")
        
        is_complete = len(missing_fields) == 0
        
        logger.debug(
            "story_validation_completed",
            extra={
                "story_id": story.id,
                "is_complete": is_complete,
                "missing_fields": missing_fields,
                "warnings_count": len(warnings),
            }
        )
        
        return ValidationResult(
            is_complete=is_complete,
            missing_fields=missing_fields,
            warnings=warnings,
        )
