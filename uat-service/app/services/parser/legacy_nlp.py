"""
Legacy NLP-based story parser (fallback).

This module provides a fallback parser using basic NLP heuristics
when LLM-based parsing fails. It's adapted from the V1 POC code
and provides degraded functionality with warnings.
"""

import re

from app.models.story import (
    ParsedStory,
    AcceptanceCriterion,
    Ambiguity,
    Priority,
)
from app.core.exceptions import ParsingException
from app.core.logging import get_logger


logger = get_logger(__name__)


class LegacyNLPParser:
    """
    Legacy NLP-based parser using heuristics.
    
    This parser uses simple pattern matching and heuristics to extract
    story components. It provides basic functionality as a fallback
    when LLM parsing is unavailable.
    
    Limitations:
    - Cannot detect implicit requirements
    - Cannot identify ambiguities
    - Limited understanding of complex story formats
    - No priority assignment logic
    - No dependency detection
    
    Requirements: 1.3, 7.6
    """
    
    def __init__(self):
        """Initialize the legacy NLP parser."""
        logger.warning(
            "legacy_nlp_parser_initialized",
            extra={
                "warning": "Using degraded functionality - LLM parsing unavailable"
            }
        )
    
    async def parse(self, story_text: str) -> ParsedStory:
        """
        Parse user story using NLP heuristics.
        
        This method implements the same interface as the LLM parser
        but uses simple pattern matching instead of AI.
        
        Args:
            story_text: The user story text to parse
        
        Returns:
            ParsedStory: Parsed story with parsing_method set to nlp_legacy
            
        Raises:
            ParsingException: If parsing fails
        
        Requirements: 1.3, 7.6
        """
        logger.info(
            "legacy_nlp_parsing_started",
            extra={
                "text_length": len(story_text),
            }
        )
        
        try:
            # Extract title (first line or generate from story)
            title = self._extract_title(story_text)
            
            # Extract role, feature, benefit using patterns
            role = self._extract_role(story_text)
            feature = self._extract_feature(story_text)
            benefit = self._extract_benefit(story_text)
            
            # Extract acceptance criteria
            acceptance_criteria = self._extract_acceptance_criteria(story_text)
            
            # Create ambiguity warning about degraded functionality
            ambiguities = [
                Ambiguity(
                    text="Story parsed using legacy NLP parser with limited capabilities",
                    location="Overall",
                    suggestion="Re-run with LLM parsing when available for better accuracy"
                )
            ]
            
            parsed_story = ParsedStory(
                id="",  # Will be set by caller
                title=title,
                role=role,
                feature=feature,
                benefit=benefit,
                acceptance_criteria=acceptance_criteria,
                implicit_requirements=[],  # Legacy parser cannot detect these
                ambiguities=ambiguities,
                parsing_method="nlp_legacy",
            )
            
            logger.info(
                "legacy_nlp_parsing_completed",
                extra={
                    "criteria_count": len(acceptance_criteria),
                }
            )
            
            return parsed_story
            
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
    
    def _extract_title(self, story_text: str) -> str:
        """
        Extract or generate story title.
        
        Args:
            story_text: The story text
        
        Returns:
            str: Extracted or generated title
        """
        # Try to find a title pattern (e.g., "Title:", "Story:", or first line)
        lines = [line.strip() for line in story_text.split('\n') if line.strip()]
        
        if not lines:
            return "Untitled Story"
        
        first_line = lines[0]
        
        # Check if first line looks like a title
        if len(first_line) < 100 and not first_line.lower().startswith(('as a', 'given', 'when', 'then')):
            # Remove common title prefixes
            title = re.sub(r'^(title|story|user story):\s*', '', first_line, flags=re.IGNORECASE)
            return title.strip()
        
        # Generate title from role and feature
        role = self._extract_role(story_text)
        feature = self._extract_feature(story_text)
        
        if role and feature:
            # Create a concise title
            feature_words = feature.split()[:5]  # First 5 words
            return f"{role.title()} - {' '.join(feature_words)}"
        
        return "User Story"
    
    def _extract_role(self, story_text: str) -> str:
        """
        Extract user role from story.
        
        Looks for "As a [role]" pattern.
        
        Args:
            story_text: The story text
        
        Returns:
            str: Extracted role or default
        """
        # Pattern: "As a [role]"
        pattern = r'[Aa]s\s+(?:a|an)\s+([^,\n]+?)(?:,|\s+I\s+want)'
        match = re.search(pattern, story_text)
        
        if match:
            role = match.group(1).strip()
            return role
        
        logger.debug("legacy_nlp_role_not_found_using_default")
        return "user"
    
    def _extract_feature(self, story_text: str) -> str:
        """
        Extract desired feature from story.
        
        Looks for "I want [feature]" pattern.
        
        Args:
            story_text: The story text
        
        Returns:
            str: Extracted feature or default
        """
        # Pattern: "I want [feature]"
        pattern = r'I\s+want\s+(?:to\s+)?([^,\n]+?)(?:,|\s+so\s+that)'
        match = re.search(pattern, story_text, flags=re.IGNORECASE)
        
        if match:
            feature = match.group(1).strip()
            return feature
        
        logger.debug("legacy_nlp_feature_not_found_using_default")
        return "perform an action"
    
    def _extract_benefit(self, story_text: str) -> str:
        """
        Extract expected benefit from story.
        
        Looks for "so that [benefit]" pattern.
        
        Args:
            story_text: The story text
        
        Returns:
            str: Extracted benefit or default
        """
        # Pattern: "so that [benefit]"
        pattern = r'[Ss]o\s+that\s+([^\n]+?)(?:\n|$)'
        match = re.search(pattern, story_text)
        
        if match:
            benefit = match.group(1).strip()
            # Remove trailing punctuation
            benefit = re.sub(r'[.!]+$', '', benefit)
            return benefit
        
        logger.debug("legacy_nlp_benefit_not_found_using_default")
        return "achieve my goal"
    
    def _extract_acceptance_criteria(self, story_text: str) -> list[AcceptanceCriterion]:
        """
        Extract acceptance criteria from story.
        
        Looks for:
        - Numbered lists (1., 2., etc.)
        - Bullet points (-, *, •)
        - Given-When-Then blocks
        - "Acceptance Criteria:" section
        
        Args:
            story_text: The story text
        
        Returns:
            list[AcceptanceCriterion]: Extracted criteria
        """
        criteria = []
        
        # Try to find "Acceptance Criteria" section
        ac_pattern = r'[Aa]cceptance\s+[Cc]riteria:?\s*\n(.*?)(?:\n\n|\Z)'
        ac_match = re.search(ac_pattern, story_text, flags=re.DOTALL)
        
        if ac_match:
            ac_text = ac_match.group(1)
        else:
            # Use entire text after the user story line
            # Find where the story ends (after "so that" clause)
            story_end = re.search(r'[Ss]o\s+that\s+[^\n]+', story_text)
            if story_end:
                ac_text = story_text[story_end.end():]
            else:
                ac_text = story_text
        
        # Extract numbered items (1., 2., etc.)
        numbered_pattern = r'^\s*(\d+)\.\s+(.+?)(?=^\s*\d+\.|$)'
        numbered_matches = re.finditer(numbered_pattern, ac_text, flags=re.MULTILINE | re.DOTALL)
        
        for match in numbered_matches:
            criterion_text = match.group(2).strip()
            criterion_text = re.sub(r'\s+', ' ', criterion_text)  # Normalize whitespace
            
            if len(criterion_text) > 5:  # Ignore very short criteria
                criteria.append(
                    AcceptanceCriterion(
                        id=f"AC-{len(criteria) + 1}",
                        text=criterion_text,
                        priority=Priority.MEDIUM,  # Default priority
                        dependencies=[],
                    )
                )
        
        # If no numbered items, try bullet points
        if not criteria:
            bullet_pattern = r'^\s*[-*•]\s+(.+?)(?=^\s*[-*•]|$)'
            bullet_matches = re.finditer(bullet_pattern, ac_text, flags=re.MULTILINE | re.DOTALL)
            
            for match in bullet_matches:
                criterion_text = match.group(1).strip()
                criterion_text = re.sub(r'\s+', ' ', criterion_text)
                
                if len(criterion_text) > 5:
                    criteria.append(
                        AcceptanceCriterion(
                            id=f"AC-{len(criteria) + 1}",
                            text=criterion_text,
                            priority=Priority.MEDIUM,
                            dependencies=[],
                        )
                    )
        
        # If still no criteria, try to find Given-When-Then blocks
        if not criteria:
            gwt_pattern = r'(Given[^.]+\.?\s*When[^.]+\.?\s*Then[^.]+\.?)'
            gwt_matches = re.finditer(gwt_pattern, ac_text, flags=re.IGNORECASE | re.DOTALL)
            
            for match in gwt_matches:
                criterion_text = match.group(1).strip()
                criterion_text = re.sub(r'\s+', ' ', criterion_text)
                
                if len(criterion_text) > 10:
                    criteria.append(
                        AcceptanceCriterion(
                            id=f"AC-{len(criteria) + 1}",
                            text=criterion_text,
                            priority=Priority.MEDIUM,
                            dependencies=[],
                        )
                    )
        
        # If still no criteria found, create a default one
        if not criteria:
            logger.warning(
                "legacy_nlp_no_criteria_found_creating_default",
                extra={
                    "text_length": len(story_text),
                }
            )
            
            criteria.append(
                AcceptanceCriterion(
                    id="AC-1",
                    text="System should implement the described functionality",
                    priority=Priority.MEDIUM,
                    dependencies=[],
                )
            )
        
        logger.debug(
            "legacy_nlp_criteria_extracted",
            extra={
                "criteria_count": len(criteria),
            }
        )
        
        return criteria
