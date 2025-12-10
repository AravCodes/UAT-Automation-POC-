"""
LLM-powered selector suggestion service.

This module uses LLM to analyze page context and suggest alternative
selectors when elements cannot be found using standard strategies.
"""

from typing import Optional
from playwright.async_api import Page
import json

from app.services.llm.groq_client import GroqClient
from app.core.logging import get_logger


logger = get_logger(__name__)


class SelectorSuggester:
    """
    LLM-powered selector suggestion service.
    
    This service captures full page context and uses LLM to suggest
    alternative selectors when element finding fails.
    
    Requirements: 3.5
    """
    
    SELECTOR_SUGGESTION_PROMPT = """You are a test automation expert helping to locate UI elements on a web page.

An element could not be found with the description: "{element_description}"

Here is the page context (HTML structure with interactive elements):

{page_context}

Based on this page structure, suggest alternative ways to describe or locate this element.
Consider:
1. Similar elements that might match the intent
2. Alternative text descriptions
3. Nearby elements that could provide context
4. Form fields or buttons with similar purposes

Provide your suggestions as a JSON object with this structure:
{{
  "selectors": [
    "suggestion 1 - description of element",
    "suggestion 2 - description of element",
    "suggestion 3 - description of element"
  ],
  "reasoning": "Brief explanation of why these alternatives might work"
}}

Limit to 5 suggestions maximum."""

    def __init__(self, groq_client: Optional[GroqClient] = None):
        """
        Initialize the selector suggester.
        
        Args:
            groq_client: Optional GroqClient instance (creates new one if None)
        """
        self.groq_client = groq_client
        self._client_created = False
    
    async def _get_client(self) -> GroqClient:
        """Get or create Groq client."""
        if self.groq_client is None:
            self.groq_client = GroqClient()
            self._client_created = True
        return self.groq_client
    
    async def _cleanup_client(self):
        """Cleanup client if we created it."""
        if self._client_created and self.groq_client:
            await self.groq_client.close()
            self.groq_client = None
            self._client_created = False
    
    async def suggest_selectors(
        self,
        page: Page,
        element_description: str
    ) -> list[str]:
        """
        Suggest alternative selectors using LLM analysis.
        
        Args:
            page: Playwright page object
            element_description: Description of the element that couldn't be found
            
        Returns:
            List of suggested alternative descriptions/selectors
            
        Requirements: 3.5
        """
        try:
            # Capture page context
            page_context = await self._capture_page_context(page)
            
            # Get LLM client
            client = await self._get_client()
            
            # Format prompt
            prompt = self.SELECTOR_SUGGESTION_PROMPT.format(
                element_description=element_description,
                page_context=page_context
            )
            
            # Get suggestions from LLM
            messages = [
                {
                    "role": "system",
                    "content": "You are a test automation expert. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            logger.info(
                "requesting_llm_selector_suggestions",
                extra={
                    "element_description": element_description,
                    "page_url": page.url
                }
            )
            
            result = await client.complete(
                messages=messages,
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            
            # Extract selectors from response
            selectors = result.get("selectors", [])
            reasoning = result.get("reasoning", "")
            
            logger.info(
                "llm_selector_suggestions_received",
                extra={
                    "element_description": element_description,
                    "suggestions_count": len(selectors),
                    "reasoning": reasoning
                }
            )
            
            return selectors[:5]  # Limit to 5 suggestions
            
        except Exception as e:
            logger.error(
                "llm_selector_suggestion_failed",
                extra={
                    "element_description": element_description,
                    "error": str(e)
                }
            )
            return []
        
        finally:
            await self._cleanup_client()
    
    async def _capture_page_context(self, page: Page) -> str:
        """
        Capture relevant page context for LLM analysis.
        
        Extracts interactive elements and their attributes to provide
        context for selector suggestions.
        
        Args:
            page: Playwright page object
            
        Returns:
            String representation of page context
        """
        try:
            # Extract interactive elements with their attributes
            context_data = await page.evaluate("""
                () => {
                    const elements = [];
                    const selectors = [
                        'button',
                        'a[href]',
                        'input',
                        'textarea',
                        'select',
                        '[role="button"]',
                        '[role="link"]',
                        'label'
                    ];
                    
                    // Get all interactive elements
                    const allElements = document.querySelectorAll(selectors.join(','));
                    
                    // Limit to first 50 elements to avoid context overflow
                    const limitedElements = Array.from(allElements).slice(0, 50);
                    
                    limitedElements.forEach((el, index) => {
                        const info = {
                            index: index,
                            tag: el.tagName.toLowerCase(),
                            text: el.innerText?.substring(0, 100) || '',
                            attributes: {}
                        };
                        
                        // Extract relevant attributes
                        const attrs = [
                            'id', 'name', 'class', 'type', 'placeholder',
                            'aria-label', 'title', 'data-testid', 'role', 'for'
                        ];
                        
                        attrs.forEach(attr => {
                            const value = el.getAttribute(attr);
                            if (value) {
                                info.attributes[attr] = value;
                            }
                        });
                        
                        // For inputs, get associated label
                        if (el.tagName.toLowerCase() === 'input' && el.id) {
                            const label = document.querySelector(`label[for="${el.id}"]`);
                            if (label) {
                                info.label = label.innerText?.substring(0, 100);
                            }
                        }
                        
                        // For labels, note what they're for
                        if (el.tagName.toLowerCase() === 'label') {
                            const forAttr = el.getAttribute('for');
                            if (forAttr) {
                                info.for_element = forAttr;
                            }
                        }
                        
                        elements.push(info);
                    });
                    
                    return {
                        url: window.location.href,
                        title: document.title,
                        elements: elements
                    };
                }
            """)
            
            # Format context as readable text
            context_lines = [
                f"Page: {context_data['title']}",
                f"URL: {context_data['url']}",
                "",
                "Interactive Elements:",
                ""
            ]
            
            for elem in context_data['elements']:
                elem_desc = f"[{elem['index']}] <{elem['tag']}>"
                
                # Add attributes
                if elem['attributes']:
                    attrs = []
                    for key, value in elem['attributes'].items():
                        attrs.append(f"{key}='{value}'")
                    elem_desc += " " + " ".join(attrs)
                
                # Add text content
                if elem.get('text'):
                    elem_desc += f" | Text: '{elem['text']}'"
                
                # Add label info
                if elem.get('label'):
                    elem_desc += f" | Label: '{elem['label']}'"
                
                if elem.get('for_element'):
                    elem_desc += f" | For: '{elem['for_element']}'"
                
                context_lines.append(elem_desc)
            
            context = "\n".join(context_lines)
            
            # Limit context size (LLM token limits)
            if len(context) > 8000:
                context = context[:8000] + "\n... (truncated)"
            
            return context
            
        except Exception as e:
            logger.error(
                "page_context_capture_failed",
                extra={
                    "page_url": page.url,
                    "error": str(e)
                }
            )
            return f"Page: {page.url}\n(Context capture failed)"
