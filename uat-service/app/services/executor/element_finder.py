"""
Multi-strategy element finder for intelligent element discovery.

This module implements a sophisticated element finding system that uses
multiple strategies to locate elements without requiring explicit test IDs.
It includes fuzzy matching and context-aware disambiguation.

Requirements: 3.2, 3.3, 3.4
"""

from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum
from playwright.async_api import Page, Locator
import re
from difflib import SequenceMatcher

from app.core.exceptions import ElementNotFoundException


class FindStrategy(str, Enum):
    """Element finding strategies in priority order."""
    DATA_TESTID = "data-testid"
    ARIA_LABEL = "aria-label"
    LABEL_FOR = "label-for"
    PLACEHOLDER = "placeholder"
    TEXT_CONTENT = "text-content"
    ROLE = "role"
    FUZZY_MATCH = "fuzzy-match"


@dataclass
class ElementContext:
    """Context information for element finding."""
    parent_text: Optional[str] = None
    sibling_texts: list[str] = None
    form_context: Optional[str] = None
    section_heading: Optional[str] = None
    
    def __post_init__(self):
        if self.sibling_texts is None:
            self.sibling_texts = []


@dataclass
class ElementMatch:
    """Represents a matched element with confidence score."""
    locator: Locator
    strategy: FindStrategy
    confidence: float  # 0.0 to 1.0
    description: str
    
    def __lt__(self, other):
        """Compare matches by confidence for sorting."""
        return self.confidence < other.confidence


class ElementFinder:
    """
    Multi-strategy element finder with fuzzy matching.
    
    This finder uses a chain of strategies to locate elements:
    1. data-testid (exact match)
    2. aria-label (exact match)
    3. label-for relationship (exact match)
    4. placeholder text (exact match)
    5. text content (exact match)
    6. semantic role (exact match)
    7. fuzzy matching (80% similarity threshold)
    
    Requirements: 3.2, 3.3, 3.4
    """
    
    FUZZY_THRESHOLD = 0.80  # 80% similarity threshold
    MAX_MATCHES = 5  # Maximum number of fuzzy matches to consider
    
    def __init__(self):
        """Initialize the element finder."""
        self.strategies_tried: list[str] = []
    
    async def find_element(
        self,
        page: Page,
        description: str,
        context: Optional[ElementContext] = None
    ) -> Locator:
        """
        Find element using multi-strategy approach.
        
        Args:
            page: Playwright page object
            description: Element description (e.g., "email input", "submit button")
            context: Optional context information for disambiguation
            
        Returns:
            Playwright Locator for the found element
            
        Raises:
            ElementNotFoundException: If element cannot be found with any strategy
            
        Requirements: 3.2
        """
        self.strategies_tried = []
        context = context or ElementContext()
        
        # Try exact match strategies first
        exact_match = await self._try_exact_match(page, description)
        if exact_match:
            return exact_match
        
        # Try fuzzy matching
        fuzzy_matches = await self._try_fuzzy_match(page, description)
        if fuzzy_matches:
            # If multiple matches, use context for disambiguation
            if len(fuzzy_matches) > 1:
                best_match = await self._disambiguate_matches(
                    page, fuzzy_matches, context
                )
                if best_match:
                    return best_match.locator
            
            # Return the best match
            return fuzzy_matches[0].locator
        
        # Element not found with any strategy
        raise ElementNotFoundException(
            f"Could not find element: {description}",
            element_description=description,
            page_url=page.url,
            strategies_tried=self.strategies_tried
        )
    
    async def _try_exact_match(
        self,
        page: Page,
        description: str
    ) -> Optional[Locator]:
        """
        Try exact matching strategies.
        
        Requirements: 3.2
        """
        # Strategy 1: data-testid
        locator = await self._find_by_testid(page, description)
        if locator:
            return locator
        
        # Strategy 2: aria-label
        locator = await self._find_by_aria_label(page, description)
        if locator:
            return locator
        
        # Strategy 3: label-for relationship
        locator = await self._find_by_label(page, description)
        if locator:
            return locator
        
        # Strategy 4: placeholder
        locator = await self._find_by_placeholder(page, description)
        if locator:
            return locator
        
        # Strategy 5: text content
        locator = await self._find_by_text(page, description)
        if locator:
            return locator
        
        # Strategy 6: semantic role
        locator = await self._find_by_role(page, description)
        if locator:
            return locator
        
        return None
    
    async def _find_by_testid(
        self,
        page: Page,
        description: str
    ) -> Optional[Locator]:
        """Find element by data-testid attribute."""
        self.strategies_tried.append(FindStrategy.DATA_TESTID.value)
        
        # Try exact testid match
        testid = self._normalize_for_testid(description)
        locator = page.locator(f"[data-testid='{testid}']")
        
        try:
            if await locator.count() > 0:
                return locator.first
        except Exception:
            pass
        
        # Try common variations
        variations = [
            description.lower().replace(" ", "-"),
            description.lower().replace(" ", "_"),
            description.lower().replace(" ", ""),
        ]
        
        for variation in variations:
            locator = page.locator(f"[data-testid='{variation}']")
            try:
                if await locator.count() > 0:
                    return locator.first
            except Exception:
                pass
        
        return None
    
    async def _find_by_aria_label(
        self,
        page: Page,
        description: str
    ) -> Optional[Locator]:
        """Find element by aria-label attribute."""
        self.strategies_tried.append(FindStrategy.ARIA_LABEL.value)
        
        # Try exact match
        locator = page.locator(f"[aria-label='{description}']")
        try:
            if await locator.count() > 0:
                return locator.first
        except Exception:
            pass
        
        # Try case-insensitive match
        try:
            all_elements = await page.locator("[aria-label]").all()
            for elem in all_elements:
                aria_label = await elem.get_attribute("aria-label")
                if aria_label and aria_label.lower() == description.lower():
                    return elem
        except Exception:
            pass
        
        return None
    
    async def _find_by_label(
        self,
        page: Page,
        description: str
    ) -> Optional[Locator]:
        """Find element by associated label text."""
        self.strategies_tried.append(FindStrategy.LABEL_FOR.value)
        
        try:
            # Find label with matching text
            labels = await page.locator("label").all()
            
            for label in labels:
                label_text = await label.inner_text()
                if label_text and self._text_matches(label_text, description):
                    # Get the associated input
                    for_attr = await label.get_attribute("for")
                    
                    if for_attr:
                        # Label has 'for' attribute
                        input_elem = page.locator(f"#{for_attr}")
                        if await input_elem.count() > 0:
                            return input_elem.first
                    else:
                        # Label wraps the input
                        input_elem = label.locator("input, textarea, select").first
                        if await input_elem.count() > 0:
                            return input_elem
        except Exception:
            pass
        
        return None
    
    async def _find_by_placeholder(
        self,
        page: Page,
        description: str
    ) -> Optional[Locator]:
        """Find element by placeholder text."""
        self.strategies_tried.append(FindStrategy.PLACEHOLDER.value)
        
        # Try exact match
        locator = page.locator(f"[placeholder='{description}']")
        try:
            if await locator.count() > 0:
                return locator.first
        except Exception:
            pass
        
        # Try case-insensitive match
        try:
            all_elements = await page.locator("[placeholder]").all()
            for elem in all_elements:
                placeholder = await elem.get_attribute("placeholder")
                if placeholder and self._text_matches(placeholder, description):
                    return elem
        except Exception:
            pass
        
        return None
    
    async def _find_by_text(
        self,
        page: Page,
        description: str
    ) -> Optional[Locator]:
        """Find element by text content."""
        self.strategies_tried.append(FindStrategy.TEXT_CONTENT.value)
        
        # Try exact text match
        locator = page.get_by_text(description, exact=True)
        try:
            if await locator.count() > 0:
                return locator.first
        except Exception:
            pass
        
        # Try case-insensitive match
        locator = page.get_by_text(re.compile(re.escape(description), re.IGNORECASE))
        try:
            if await locator.count() > 0:
                return locator.first
        except Exception:
            pass
        
        return None
    
    async def _find_by_role(
        self,
        page: Page,
        description: str
    ) -> Optional[Locator]:
        """Find element by semantic role and name."""
        self.strategies_tried.append(FindStrategy.ROLE.value)
        
        # Extract role and name from description
        role_mapping = {
            "button": ["button", "submit", "click"],
            "textbox": ["input", "field", "textbox", "text"],
            "link": ["link"],
            "checkbox": ["checkbox", "check"],
            "radio": ["radio"],
            "combobox": ["select", "dropdown", "combobox"],
        }
        
        for role, keywords in role_mapping.items():
            if any(keyword in description.lower() for keyword in keywords):
                try:
                    # Try to find by role with name
                    locator = page.get_by_role(role, name=re.compile(re.escape(description), re.IGNORECASE))
                    if await locator.count() > 0:
                        return locator.first
                    
                    # Try just by role if description seems to be just the role
                    if description.lower() in keywords:
                        locator = page.get_by_role(role)
                        if await locator.count() == 1:
                            return locator.first
                except Exception:
                    pass
        
        return None
    
    async def _try_fuzzy_match(
        self,
        page: Page,
        description: str
    ) -> list[ElementMatch]:
        """
        Try fuzzy matching with similarity threshold.
        
        Requirements: 3.3
        """
        self.strategies_tried.append(FindStrategy.FUZZY_MATCH.value)
        
        matches: list[ElementMatch] = []
        
        # Get all interactive elements
        interactive_selectors = [
            "button",
            "a",
            "input",
            "textarea",
            "select",
            "[role='button']",
            "[role='link']",
        ]
        
        for selector in interactive_selectors:
            try:
                elements = await page.locator(selector).all()
                
                for elem in elements:
                    # Get all text sources for this element
                    text_sources = await self._get_element_text_sources(elem)
                    
                    # Calculate similarity for each text source
                    for source_text, source_type in text_sources:
                        similarity = self._calculate_similarity(description, source_text)
                        
                        if similarity >= self.FUZZY_THRESHOLD:
                            match = ElementMatch(
                                locator=elem,
                                strategy=FindStrategy.FUZZY_MATCH,
                                confidence=similarity,
                                description=f"{source_type}: {source_text}"
                            )
                            matches.append(match)
            except Exception:
                continue
        
        # Sort by confidence (highest first) and return top matches
        matches.sort(reverse=True)
        return matches[:self.MAX_MATCHES]
    
    async def _get_element_text_sources(
        self,
        element: Locator
    ) -> list[tuple[str, str]]:
        """Get all text sources from an element for fuzzy matching."""
        sources: list[tuple[str, str]] = []
        
        try:
            # Inner text
            inner_text = await element.inner_text()
            if inner_text and inner_text.strip():
                sources.append((inner_text.strip(), "text"))
            
            # Aria-label
            aria_label = await element.get_attribute("aria-label")
            if aria_label:
                sources.append((aria_label, "aria-label"))
            
            # Placeholder
            placeholder = await element.get_attribute("placeholder")
            if placeholder:
                sources.append((placeholder, "placeholder"))
            
            # Title
            title = await element.get_attribute("title")
            if title:
                sources.append((title, "title"))
            
            # Name attribute
            name = await element.get_attribute("name")
            if name:
                # Convert name to readable text (e.g., "user_email" -> "user email")
                readable_name = name.replace("_", " ").replace("-", " ")
                sources.append((readable_name, "name"))
            
            # Associated label
            elem_id = await element.get_attribute("id")
            if elem_id:
                try:
                    label = await element.page.locator(f"label[for='{elem_id}']").first
                    if label:
                        label_text = await label.inner_text()
                        if label_text:
                            sources.append((label_text.strip(), "label"))
                except Exception:
                    pass
        except Exception:
            pass
        
        return sources
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two strings.
        
        Uses SequenceMatcher for fuzzy string matching.
        
        Requirements: 3.3
        """
        # Normalize texts
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        # Exact match
        if t1 == t2:
            return 1.0
        
        # Check if one contains the other
        if t1 in t2 or t2 in t1:
            return 0.95
        
        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, t1, t2).ratio()
    
    async def _disambiguate_matches(
        self,
        page: Page,
        matches: list[ElementMatch],
        context: ElementContext
    ) -> Optional[ElementMatch]:
        """
        Use context to disambiguate multiple matches.
        
        Requirements: 3.4
        """
        if not matches:
            return None
        
        if len(matches) == 1:
            return matches[0]
        
        # Score each match based on context
        scored_matches: list[tuple[ElementMatch, float]] = []
        
        for match in matches:
            context_score = 0.0
            
            try:
                # Check parent context
                if context.parent_text:
                    parent = await match.locator.locator("xpath=..").first
                    if parent:
                        parent_text = await parent.inner_text()
                        if parent_text and context.parent_text.lower() in parent_text.lower():
                            context_score += 0.3
                
                # Check sibling context
                if context.sibling_texts:
                    for sibling_text in context.sibling_texts:
                        # Check if any sibling contains the expected text
                        siblings = await match.locator.locator("xpath=..//*").all()
                        for sibling in siblings:
                            sib_text = await sibling.inner_text()
                            if sib_text and sibling_text.lower() in sib_text.lower():
                                context_score += 0.2
                                break
                
                # Check form context
                if context.form_context:
                    form = await match.locator.locator("xpath=ancestor::form").first
                    if form:
                        form_text = await form.inner_text()
                        if form_text and context.form_context.lower() in form_text.lower():
                            context_score += 0.3
                
                # Check section heading context
                if context.section_heading:
                    # Look for nearest heading
                    headings = await page.locator("h1, h2, h3, h4, h5, h6").all()
                    for heading in headings:
                        heading_text = await heading.inner_text()
                        if heading_text and context.section_heading.lower() in heading_text.lower():
                            # Check if match is after this heading
                            heading_box = await heading.bounding_box()
                            match_box = await match.locator.bounding_box()
                            
                            if heading_box and match_box and match_box["y"] > heading_box["y"]:
                                context_score += 0.2
                                break
            except Exception:
                pass
            
            # Combine original confidence with context score
            total_score = match.confidence + context_score
            scored_matches.append((match, total_score))
        
        # Sort by total score and return best match
        scored_matches.sort(key=lambda x: x[1], reverse=True)
        return scored_matches[0][0]
    
    def _text_matches(self, text1: str, text2: str) -> bool:
        """Check if two texts match (case-insensitive, trimmed)."""
        return text1.strip().lower() == text2.strip().lower()
    
    def _normalize_for_testid(self, text: str) -> str:
        """Normalize text for data-testid format."""
        # Convert to lowercase and replace spaces with hyphens
        normalized = text.lower().strip()
        normalized = re.sub(r'[^a-z0-9]+', '-', normalized)
        normalized = normalized.strip('-')
        return normalized
    
    async def suggest_alternatives(
        self,
        page: Page,
        failed_description: str,
        use_llm: bool = True
    ) -> list[str]:
        """
        Suggest alternative selectors when element not found.
        
        Uses LLM to analyze page context and suggest alternatives.
        Falls back to basic similarity matching if LLM is unavailable.
        
        Args:
            page: Playwright page object
            failed_description: The description that failed to find an element
            use_llm: Whether to use LLM for suggestions (default: True)
            
        Returns:
            List of alternative selector suggestions
            
        Requirements: 3.5
        """
        suggestions: list[str] = []
        
        # Try LLM-powered suggestions first
        if use_llm:
            try:
                from app.services.executor.selector_suggester import SelectorSuggester
                
                suggester = SelectorSuggester()
                llm_suggestions = await suggester.suggest_selectors(
                    page=page,
                    element_description=failed_description
                )
                
                if llm_suggestions:
                    return llm_suggestions
            except Exception as e:
                # Fall back to basic suggestions if LLM fails
                pass
        
        # Fallback: Basic similarity-based suggestions
        try:
            # Get all interactive elements and their descriptions
            interactive_selectors = ["button", "a", "input", "textarea", "select"]
            
            for selector in interactive_selectors:
                elements = await page.locator(selector).all()
                
                for elem in elements[:10]:  # Limit to first 10 of each type
                    text_sources = await self._get_element_text_sources(elem)
                    
                    for source_text, source_type in text_sources:
                        # Calculate similarity
                        similarity = self._calculate_similarity(failed_description, source_text)
                        
                        if similarity >= 0.5:  # Lower threshold for suggestions
                            suggestions.append(
                                f"{source_text} (similarity: {similarity:.2f}, type: {source_type})"
                            )
        except Exception:
            pass
        
        # Sort by similarity (extracted from string) and return top 5
        suggestions.sort(reverse=True)
        return suggestions[:5]
