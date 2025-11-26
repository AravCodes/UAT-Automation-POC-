"""
Semantic DOM analyzer for building intelligent DOM trees.

This module analyzes web pages to build semantic DOM trees that capture
element roles, labels, relationships, and interactive elements. This enables
intelligent element discovery without requiring explicit test IDs.

Requirements: 3.1, 3.6
"""

from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from playwright.async_api import Page, Locator, ElementHandle
import json


class ElementRole(str, Enum):
    """Semantic roles for DOM elements."""
    BUTTON = "button"
    LINK = "link"
    INPUT = "input"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FORM = "form"
    HEADING = "heading"
    IMAGE = "image"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    NAVIGATION = "navigation"
    ARTICLE = "article"
    SECTION = "section"
    DIALOG = "dialog"
    ALERT = "alert"
    UNKNOWN = "unknown"


@dataclass
class ElementAttributes:
    """Attributes extracted from a DOM element."""
    id: Optional[str] = None
    name: Optional[str] = None
    class_list: list[str] = field(default_factory=list)
    data_testid: Optional[str] = None
    aria_label: Optional[str] = None
    aria_labelledby: Optional[str] = None
    aria_describedby: Optional[str] = None
    placeholder: Optional[str] = None
    title: Optional[str] = None
    alt: Optional[str] = None
    type: Optional[str] = None
    role: Optional[str] = None
    href: Optional[str] = None
    value: Optional[str] = None
    for_attribute: Optional[str] = None  # for label elements
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            k: v for k, v in self.__dict__.items() 
            if v is not None and (not isinstance(v, list) or v)
        }


@dataclass
class SemanticElement:
    """Represents a semantic element in the DOM tree."""
    tag_name: str
    role: ElementRole
    attributes: ElementAttributes
    text_content: str
    inner_text: str
    is_visible: bool
    is_interactive: bool
    bounding_box: Optional[dict[str, float]] = None
    parent_id: Optional[str] = None
    children_ids: list[str] = field(default_factory=list)
    label_text: Optional[str] = None  # Associated label text
    form_id: Optional[str] = None  # Parent form ID if applicable
    
    def __post_init__(self):
        """Generate unique ID for this element."""
        self.element_id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate a unique identifier for this element."""
        parts = [self.tag_name]
        
        if self.attributes.id:
            parts.append(f"id={self.attributes.id}")
        elif self.attributes.data_testid:
            parts.append(f"testid={self.attributes.data_testid}")
        elif self.attributes.name:
            parts.append(f"name={self.attributes.name}")
        elif self.label_text:
            parts.append(f"label={self.label_text[:20]}")
        elif self.inner_text:
            parts.append(f"text={self.inner_text[:20]}")
        
        return "_".join(parts).replace(" ", "_")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "element_id": self.element_id,
            "tag_name": self.tag_name,
            "role": self.role.value,
            "attributes": self.attributes.to_dict(),
            "text_content": self.text_content[:100] if self.text_content else "",
            "inner_text": self.inner_text[:100] if self.inner_text else "",
            "is_visible": self.is_visible,
            "is_interactive": self.is_interactive,
            "bounding_box": self.bounding_box,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "label_text": self.label_text,
            "form_id": self.form_id
        }


@dataclass
class FormStructure:
    """Represents a form and its fields."""
    form_id: str
    action: Optional[str]
    method: Optional[str]
    fields: list[SemanticElement] = field(default_factory=list)
    submit_buttons: list[SemanticElement] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "form_id": self.form_id,
            "action": self.action,
            "method": self.method,
            "fields": [f.to_dict() for f in self.fields],
            "submit_buttons": [b.to_dict() for b in self.submit_buttons]
        }


@dataclass
class InteractiveElement:
    """Represents an interactive element (button, link, input, etc.)."""
    element: SemanticElement
    purpose: str  # Inferred purpose based on context
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "element": self.element.to_dict(),
            "purpose": self.purpose
        }


@dataclass
class SemanticDOM:
    """Complete semantic representation of a page's DOM."""
    url: str
    title: str
    elements: dict[str, SemanticElement] = field(default_factory=dict)
    forms: list[FormStructure] = field(default_factory=list)
    interactive_elements: list[InteractiveElement] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "elements": {k: v.to_dict() for k, v in self.elements.items()},
            "forms": [f.to_dict() for f in self.forms],
            "interactive_elements": [ie.to_dict() for ie in self.interactive_elements]
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class DOMAnalyzer:
    """
    Analyzes web pages to build semantic DOM trees.
    
    This analyzer extracts semantic information from DOM elements including
    roles, labels, relationships, and interactive elements. It enables
    intelligent element discovery without requiring explicit test IDs.
    """
    
    # Interactive element selectors
    INTERACTIVE_SELECTORS = [
        "button",
        "a[href]",
        "input",
        "textarea",
        "select",
        "[role='button']",
        "[role='link']",
        "[role='textbox']",
        "[role='checkbox']",
        "[role='radio']",
        "[onclick]",
        "[tabindex]"
    ]
    
    # Form field selectors
    FORM_FIELD_SELECTORS = [
        "input:not([type='hidden'])",
        "textarea",
        "select"
    ]
    
    async def analyze_page(self, page: Page) -> SemanticDOM:
        """
        Build semantic representation of page structure.
        
        Args:
            page: Playwright page object
            
        Returns:
            SemanticDOM object containing analyzed page structure
            
        Requirements: 3.1
        """
        url = page.url
        title = await page.title()
        
        semantic_dom = SemanticDOM(url=url, title=title)
        
        # Analyze all interactive elements
        await self._analyze_interactive_elements(page, semantic_dom)
        
        # Extract forms and their structures
        await self._extract_forms(page, semantic_dom)
        
        # Build element relationships
        self._build_relationships(semantic_dom)
        
        return semantic_dom
    
    async def _analyze_interactive_elements(
        self, 
        page: Page, 
        semantic_dom: SemanticDOM
    ) -> None:
        """
        Identify and analyze all interactive elements on the page.
        
        Requirements: 3.6
        """
        for selector in self.INTERACTIVE_SELECTORS:
            try:
                elements = await page.locator(selector).all()
                
                for element in elements:
                    semantic_element = await self._create_semantic_element(element)
                    
                    if semantic_element and semantic_element.is_visible:
                        semantic_dom.elements[semantic_element.element_id] = semantic_element
                        
                        # Determine purpose and add to interactive elements
                        purpose = await self._infer_element_purpose(element, semantic_element)
                        interactive_elem = InteractiveElement(
                            element=semantic_element,
                            purpose=purpose
                        )
                        semantic_dom.interactive_elements.append(interactive_elem)
                        
            except Exception:
                # Continue if selector fails
                continue
    
    async def _create_semantic_element(
        self, 
        element: Locator
    ) -> Optional[SemanticElement]:
        """
        Create a semantic element from a Playwright locator.
        
        Args:
            element: Playwright locator
            
        Returns:
            SemanticElement or None if element cannot be analyzed
        """
        try:
            # Get basic element info
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            is_visible = await element.is_visible()
            
            # Extract attributes
            attributes = await self._extract_attributes(element)
            
            # Get text content
            text_content = await element.text_content() or ""
            inner_text = await element.inner_text() or ""
            
            # Get bounding box if visible
            bounding_box = None
            if is_visible:
                try:
                    box = await element.bounding_box()
                    bounding_box = box if box else None
                except Exception:
                    pass
            
            # Determine semantic role
            role = self._determine_role(tag_name, attributes)
            
            # Check if interactive
            is_interactive = self._is_interactive(tag_name, attributes)
            
            # Get associated label
            label_text = await self._get_label_text(element, attributes)
            
            semantic_element = SemanticElement(
                tag_name=tag_name,
                role=role,
                attributes=attributes,
                text_content=text_content.strip(),
                inner_text=inner_text.strip(),
                is_visible=is_visible,
                is_interactive=is_interactive,
                bounding_box=bounding_box,
                label_text=label_text
            )
            
            return semantic_element
            
        except Exception:
            return None
    
    async def _extract_attributes(self, element: Locator) -> ElementAttributes:
        """Extract relevant attributes from an element."""
        attrs = ElementAttributes()
        
        try:
            # Use JavaScript to extract all relevant attributes at once
            attr_data = await element.evaluate("""
                el => ({
                    id: el.id || null,
                    name: el.name || null,
                    classList: Array.from(el.classList),
                    dataTestId: el.getAttribute('data-testid') || null,
                    ariaLabel: el.getAttribute('aria-label') || null,
                    ariaLabelledby: el.getAttribute('aria-labelledby') || null,
                    ariaDescribedby: el.getAttribute('aria-describedby') || null,
                    placeholder: el.placeholder || null,
                    title: el.title || null,
                    alt: el.alt || null,
                    type: el.type || null,
                    role: el.getAttribute('role') || null,
                    href: el.href || null,
                    value: el.value || null,
                    forAttr: el.getAttribute('for') || null
                })
            """)
            
            attrs.id = attr_data.get("id")
            attrs.name = attr_data.get("name")
            attrs.class_list = attr_data.get("classList", [])
            attrs.data_testid = attr_data.get("dataTestId")
            attrs.aria_label = attr_data.get("ariaLabel")
            attrs.aria_labelledby = attr_data.get("ariaLabelledby")
            attrs.aria_describedby = attr_data.get("ariaDescribedby")
            attrs.placeholder = attr_data.get("placeholder")
            attrs.title = attr_data.get("title")
            attrs.alt = attr_data.get("alt")
            attrs.type = attr_data.get("type")
            attrs.role = attr_data.get("role")
            attrs.href = attr_data.get("href")
            attrs.value = attr_data.get("value")
            attrs.for_attribute = attr_data.get("forAttr")
            
        except Exception:
            pass
        
        return attrs
    
    def _determine_role(
        self, 
        tag_name: str, 
        attributes: ElementAttributes
    ) -> ElementRole:
        """Determine the semantic role of an element."""
        # Check explicit ARIA role first
        if attributes.role:
            role_map = {
                "button": ElementRole.BUTTON,
                "link": ElementRole.LINK,
                "textbox": ElementRole.INPUT,
                "checkbox": ElementRole.CHECKBOX,
                "radio": ElementRole.RADIO,
                "navigation": ElementRole.NAVIGATION,
                "dialog": ElementRole.DIALOG,
                "alert": ElementRole.ALERT,
                "heading": ElementRole.HEADING,
                "img": ElementRole.IMAGE,
                "list": ElementRole.LIST,
                "listitem": ElementRole.LIST_ITEM,
                "table": ElementRole.TABLE,
                "article": ElementRole.ARTICLE,
                "section": ElementRole.SECTION
            }
            if attributes.role in role_map:
                return role_map[attributes.role]
        
        # Determine by tag name and type
        if tag_name == "button":
            return ElementRole.BUTTON
        elif tag_name == "a":
            return ElementRole.LINK
        elif tag_name == "input":
            input_type = attributes.type or "text"
            if input_type in ["checkbox"]:
                return ElementRole.CHECKBOX
            elif input_type in ["radio"]:
                return ElementRole.RADIO
            else:
                return ElementRole.INPUT
        elif tag_name == "textarea":
            return ElementRole.TEXTAREA
        elif tag_name == "select":
            return ElementRole.SELECT
        elif tag_name == "form":
            return ElementRole.FORM
        elif tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            return ElementRole.HEADING
        elif tag_name == "img":
            return ElementRole.IMAGE
        elif tag_name in ["ul", "ol"]:
            return ElementRole.LIST
        elif tag_name == "li":
            return ElementRole.LIST_ITEM
        elif tag_name == "table":
            return ElementRole.TABLE
        elif tag_name == "nav":
            return ElementRole.NAVIGATION
        elif tag_name == "article":
            return ElementRole.ARTICLE
        elif tag_name == "section":
            return ElementRole.SECTION
        
        return ElementRole.UNKNOWN
    
    def _is_interactive(
        self, 
        tag_name: str, 
        attributes: ElementAttributes
    ) -> bool:
        """Determine if an element is interactive."""
        interactive_tags = ["button", "a", "input", "textarea", "select"]
        interactive_roles = ["button", "link", "textbox", "checkbox", "radio"]
        
        if tag_name in interactive_tags:
            return True
        
        if attributes.role in interactive_roles:
            return True
        
        # Elements with click handlers or tabindex are interactive
        if attributes.role == "button" or "btn" in " ".join(attributes.class_list).lower():
            return True
        
        return False
    
    async def _get_label_text(
        self, 
        element: Locator, 
        attributes: ElementAttributes
    ) -> Optional[str]:
        """Get the label text associated with an element."""
        try:
            # Try aria-label first
            if attributes.aria_label:
                return attributes.aria_label
            
            # Try aria-labelledby
            if attributes.aria_labelledby:
                label_elem = await element.page.locator(
                    f"#{attributes.aria_labelledby}"
                ).first
                if label_elem:
                    return await label_elem.inner_text()
            
            # Try associated label element
            if attributes.id:
                label_elem = await element.page.locator(
                    f"label[for='{attributes.id}']"
                ).first
                if label_elem:
                    return await label_elem.inner_text()
            
            # Try parent label
            parent_label = await element.locator("xpath=ancestor::label").first
            if parent_label:
                return await parent_label.inner_text()
            
        except Exception:
            pass
        
        return None
    
    async def _infer_element_purpose(
        self, 
        element: Locator, 
        semantic_element: SemanticElement
    ) -> str:
        """Infer the purpose of an interactive element based on context."""
        # Use label, text, or attributes to infer purpose
        text_indicators = []
        
        if semantic_element.label_text:
            text_indicators.append(semantic_element.label_text.lower())
        
        if semantic_element.inner_text:
            text_indicators.append(semantic_element.inner_text.lower())
        
        if semantic_element.attributes.placeholder:
            text_indicators.append(semantic_element.attributes.placeholder.lower())
        
        if semantic_element.attributes.title:
            text_indicators.append(semantic_element.attributes.title.lower())
        
        if semantic_element.attributes.name:
            text_indicators.append(semantic_element.attributes.name.lower())
        
        combined_text = " ".join(text_indicators)
        
        # Infer purpose from text
        if any(word in combined_text for word in ["submit", "save", "create", "add"]):
            return "submit_action"
        elif any(word in combined_text for word in ["cancel", "close", "dismiss"]):
            return "cancel_action"
        elif any(word in combined_text for word in ["delete", "remove"]):
            return "delete_action"
        elif any(word in combined_text for word in ["edit", "update", "modify"]):
            return "edit_action"
        elif any(word in combined_text for word in ["search", "find"]):
            return "search_action"
        elif any(word in combined_text for word in ["login", "sign in", "log in"]):
            return "login_action"
        elif any(word in combined_text for word in ["logout", "sign out", "log out"]):
            return "logout_action"
        elif any(word in combined_text for word in ["email", "e-mail"]):
            return "email_input"
        elif any(word in combined_text for word in ["password", "pwd"]):
            return "password_input"
        elif any(word in combined_text for word in ["username", "user name"]):
            return "username_input"
        elif any(word in combined_text for word in ["name"]):
            return "name_input"
        elif semantic_element.role == ElementRole.LINK:
            return "navigation"
        elif semantic_element.role in [ElementRole.INPUT, ElementRole.TEXTAREA]:
            return "data_input"
        elif semantic_element.role == ElementRole.SELECT:
            return "selection"
        elif semantic_element.role == ElementRole.CHECKBOX:
            return "toggle"
        
        return "unknown"
    
    async def _extract_forms(self, page: Page, semantic_dom: SemanticDOM) -> None:
        """
        Extract form structures and their fields.
        
        Requirements: 3.1
        """
        try:
            forms = await page.locator("form").all()
            
            for form in forms:
                form_element = await self._create_semantic_element(form)
                if not form_element:
                    continue
                
                # Get form action and method
                action = await form.get_attribute("action")
                method = await form.get_attribute("method")
                
                form_structure = FormStructure(
                    form_id=form_element.element_id,
                    action=action,
                    method=method
                )
                
                # Find all form fields
                for field_selector in self.FORM_FIELD_SELECTORS:
                    fields = await form.locator(field_selector).all()
                    
                    for field in fields:
                        field_element = await self._create_semantic_element(field)
                        if field_element:
                            field_element.form_id = form_element.element_id
                            form_structure.fields.append(field_element)
                            semantic_dom.elements[field_element.element_id] = field_element
                
                # Find submit buttons
                submit_buttons = await form.locator(
                    "button[type='submit'], input[type='submit'], button:not([type])"
                ).all()
                
                for button in submit_buttons:
                    button_element = await self._create_semantic_element(button)
                    if button_element:
                        button_element.form_id = form_element.element_id
                        form_structure.submit_buttons.append(button_element)
                        semantic_dom.elements[button_element.element_id] = button_element
                
                semantic_dom.forms.append(form_structure)
                semantic_dom.elements[form_element.element_id] = form_element
                
        except Exception:
            pass
    
    def _build_relationships(self, semantic_dom: SemanticDOM) -> None:
        """
        Build parent-child relationships between elements.
        
        This is a simplified version - in a full implementation,
        we would traverse the actual DOM tree to build accurate relationships.
        """
        # Group elements by form
        for form in semantic_dom.forms:
            form_elem = semantic_dom.elements.get(form.form_id)
            if form_elem:
                for field in form.fields:
                    field.parent_id = form.form_id
                    form_elem.children_ids.append(field.element_id)
                
                for button in form.submit_buttons:
                    button.parent_id = form.form_id
                    form_elem.children_ids.append(button.element_id)
    
    def extract_forms(self, dom: SemanticDOM) -> list[FormStructure]:
        """
        Identify forms and their fields from semantic DOM.
        
        Args:
            dom: Semantic DOM structure
            
        Returns:
            List of form structures
        """
        return dom.forms
    
    def find_interactive_elements(
        self, 
        dom: SemanticDOM
    ) -> list[InteractiveElement]:
        """
        Locate buttons, links, inputs from semantic DOM.
        
        Args:
            dom: Semantic DOM structure
            
        Returns:
            List of interactive elements
        """
        return dom.interactive_elements
