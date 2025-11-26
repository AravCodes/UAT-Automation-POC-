"""
Structured prompt templates for LLM interactions.

This module provides prompt templates for story parsing, scenario generation,
and element selector suggestions. All prompts include JSON schema definitions
to ensure consistent, structured outputs from the LLM.

Requirements: 1.4
"""

from typing import Final


# JSON Schema for story parsing response
STORY_PARSING_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Concise title for the user story"
        },
        "role": {
            "type": "string",
            "description": "User role from 'As a...' part"
        },
        "feature": {
            "type": "string",
            "description": "Desired feature from 'I want...' part"
        },
        "benefit": {
            "type": "string",
            "description": "Expected benefit from 'So that...' part"
        },
        "acceptance_criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"]
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["id", "text", "priority"]
            },
            "minItems": 1
        },
        "implicit_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Requirements implied but not explicitly stated"
        },
        "ambiguities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "location": {"type": "string"},
                    "suggestion": {"type": "string"}
                },
                "required": ["text", "location"]
            }
        }
    },
    "required": ["title", "role", "feature", "benefit", "acceptance_criteria"]
}


# Story parsing prompt template
STORY_PARSING_PROMPT: Final[str] = """You are a QA expert analyzing user stories for test automation.

Parse the following user story and extract structured information. Identify the role, feature, benefit, and all acceptance criteria. Also identify any implicit requirements (things that are implied but not explicitly stated) and ambiguities (unclear or vague requirements).

User Story:
{story_text}

Instructions:
1. Extract the role from "As a..." part
2. Extract the feature from "I want..." part
3. Extract the benefit from "So that..." part
4. Identify all acceptance criteria (look for Given-When-Then, bullet points, or numbered lists)
5. Generate unique IDs for each criterion (e.g., "AC-1", "AC-2")
6. Assign priority levels based on business impact:
   - critical: Core functionality, system-breaking if missing
   - high: Important features, significant user impact
   - medium: Standard features, moderate impact
   - low: Nice-to-have features, minimal impact
7. Identify dependencies between criteria (if criterion B requires criterion A to be satisfied first)
8. List implicit requirements (e.g., security, performance, accessibility)
9. Flag any ambiguities or unclear requirements with suggestions for clarification

Return your response as JSON matching this schema:
{schema}

Example response format:
{{
  "title": "User Login Authentication",
  "role": "registered user",
  "feature": "log in to my account using email and password",
  "benefit": "I can access my personalized dashboard and saved preferences",
  "acceptance_criteria": [
    {{
      "id": "AC-1",
      "text": "WHEN user enters valid email and password THEN system SHALL authenticate and redirect to dashboard",
      "priority": "critical",
      "dependencies": []
    }},
    {{
      "id": "AC-2",
      "text": "WHEN user enters invalid credentials THEN system SHALL display error message",
      "priority": "high",
      "dependencies": ["AC-1"]
    }}
  ],
  "implicit_requirements": [
    "Password must be encrypted in transit and at rest",
    "System must implement rate limiting to prevent brute force attacks",
    "Login page must be accessible (WCAG 2.1 AA compliant)"
  ],
  "ambiguities": [
    {{
      "text": "Password requirements not specified",
      "location": "Acceptance criteria",
      "suggestion": "Specify minimum length, character requirements, and complexity rules"
    }}
  ]
}}
"""


# JSON Schema for scenario generation response
SCENARIO_GENERATION_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "criterion_id": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["positive", "negative", "edge_case"]
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"]
                    },
                    "given": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1
                    },
                    "when": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1
                    },
                    "then": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1
                    },
                    "test_steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["navigate", "click", "type", "select", "assert", "wait", "hover", "scroll"]
                                },
                                "target": {"type": "string"},
                                "value": {"type": "string"},
                                "expected_outcome": {"type": "string"}
                            },
                            "required": ["action", "target"]
                        },
                        "minItems": 1
                    }
                },
                "required": ["id", "criterion_id", "type", "priority", "given", "when", "then", "test_steps"]
            },
            "minItems": 1
        }
    },
    "required": ["scenarios"]
}


# Scenario generation prompt template
SCENARIO_GENERATION_PROMPT: Final[str] = """You are a QA expert generating comprehensive test scenarios for user acceptance testing.

Generate detailed BDD (Behavior-Driven Development) test scenarios for the following acceptance criteria. For each criterion, create scenarios covering positive flows, negative flows, and edge cases.

Acceptance Criteria:
{criteria}

Instructions:
1. For each acceptance criterion, generate at least 3 scenarios:
   - Positive flow: Happy path where everything works as expected
   - Negative flow: Error cases, validation failures, invalid inputs
   - Edge case: Boundary conditions, unusual but valid scenarios

2. Each scenario must include:
   - Unique ID (e.g., "SCEN-1", "SCEN-2")
   - Reference to the criterion ID it tests
   - Type: positive, negative, or edge_case
   - Priority: inherited from criterion or adjusted based on scenario importance
   - Given: Preconditions (initial state, setup)
   - When: Actions performed by user or system
   - Then: Expected outcomes and assertions
   - Test steps: Executable steps with actions, targets, values, and expected outcomes

3. Test step actions:
   - navigate: Go to a URL or page
   - click: Click a button, link, or element
   - type: Enter text into an input field
   - select: Choose an option from dropdown
   - assert: Verify expected state or content
   - wait: Wait for element or condition
   - hover: Hover over an element
   - scroll: Scroll to an element or position

4. For test step targets, use descriptive element names (e.g., "login button", "email input field", "error message")

5. Consider:
   - Data validation (format, length, required fields)
   - Error handling (network errors, timeouts, server errors)
   - UI state changes (loading states, disabled buttons, visibility)
   - Navigation flows (redirects, back button, breadcrumbs)
   - Accessibility (keyboard navigation, screen reader support)

Return your response as JSON matching this schema:
{schema}

Example response format:
{{
  "scenarios": [
    {{
      "id": "SCEN-1",
      "criterion_id": "AC-1",
      "type": "positive",
      "priority": "critical",
      "given": [
        "User is on the login page",
        "User has a valid registered account"
      ],
      "when": [
        "User enters valid email address",
        "User enters correct password",
        "User clicks the login button"
      ],
      "then": [
        "System authenticates the user",
        "User is redirected to the dashboard",
        "Welcome message is displayed with user's name"
      ],
      "test_steps": [
        {{
          "action": "navigate",
          "target": "login page",
          "value": null,
          "expected_outcome": "Login form is visible"
        }},
        {{
          "action": "type",
          "target": "email input field",
          "value": "user@example.com",
          "expected_outcome": "Email is entered"
        }},
        {{
          "action": "type",
          "target": "password input field",
          "value": "ValidPass123!",
          "expected_outcome": "Password is entered"
        }},
        {{
          "action": "click",
          "target": "login button",
          "value": null,
          "expected_outcome": "Login request is submitted"
        }},
        {{
          "action": "wait",
          "target": "dashboard page",
          "value": null,
          "expected_outcome": "Dashboard loads successfully"
        }},
        {{
          "action": "assert",
          "target": "welcome message",
          "value": null,
          "expected_outcome": "Welcome message contains user's name"
        }}
      ]
    }},
    {{
      "id": "SCEN-2",
      "criterion_id": "AC-1",
      "type": "negative",
      "priority": "high",
      "given": [
        "User is on the login page"
      ],
      "when": [
        "User enters invalid email format",
        "User clicks the login button"
      ],
      "then": [
        "System displays email validation error",
        "Login button remains disabled or shows error",
        "User remains on login page"
      ],
      "test_steps": [
        {{
          "action": "navigate",
          "target": "login page",
          "value": null,
          "expected_outcome": "Login form is visible"
        }},
        {{
          "action": "type",
          "target": "email input field",
          "value": "invalid-email",
          "expected_outcome": "Invalid email is entered"
        }},
        {{
          "action": "click",
          "target": "login button",
          "value": null,
          "expected_outcome": "Validation is triggered"
        }},
        {{
          "action": "assert",
          "target": "email error message",
          "value": null,
          "expected_outcome": "Error message displays 'Please enter a valid email address'"
        }},
        {{
          "action": "assert",
          "target": "current page",
          "value": null,
          "expected_outcome": "User remains on login page"
        }}
      ]
    }}
  ]
}}
"""


# JSON Schema for selector suggestions response
SELECTOR_SUGGESTION_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "selectors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "strategy": {"type": "string"},
                    "confidence": {"type": "string"},
                    "reasoning": {"type": "string"}
                },
                "required": ["selector", "strategy", "confidence"]
            },
            "minItems": 1
        },
        "analysis": {
            "type": "string",
            "description": "Overall analysis of why the element might not be found"
        }
    },
    "required": ["selectors"]
}


# Selector suggestion prompt template
SELECTOR_SUGGESTION_PROMPT: Final[str] = """You are a test automation expert helping to locate UI elements on a web page.

The test is trying to find an element but failed. Analyze the page context and suggest alternative selectors.

Element Description: {element_description}

Page Context (HTML snippet):
{page_context}

Instructions:
1. Analyze the page HTML to understand the structure
2. Suggest alternative selectors that might locate the desired element
3. Consider multiple strategies:
   - data-testid attributes
   - aria-label attributes
   - label associations (for inputs)
   - placeholder text
   - visible text content
   - semantic roles (button, link, heading, etc.)
   - CSS selectors (class, id)
   - XPath expressions

4. For each suggestion, provide:
   - selector: The actual selector string
   - strategy: The strategy used (testid, aria, text, role, css, xpath)
   - confidence: high, medium, or low
   - reasoning: Why this selector might work

5. Order suggestions by confidence (highest first)

6. Provide an overall analysis of why the original element might not be found

Return your response as JSON matching this schema:
{schema}

Example response format:
{{
  "selectors": [
    {{
      "selector": "[data-testid='submit-button']",
      "strategy": "testid",
      "confidence": "high",
      "reasoning": "Found a button with data-testid attribute matching the description"
    }},
    {{
      "selector": "button[aria-label='Submit form']",
      "strategy": "aria",
      "confidence": "high",
      "reasoning": "Button has aria-label that matches the element description"
    }},
    {{
      "selector": "button:has-text('Submit')",
      "strategy": "text",
      "confidence": "medium",
      "reasoning": "Button contains text 'Submit' which partially matches description"
    }},
    {{
      "selector": "form button[type='submit']",
      "strategy": "css",
      "confidence": "medium",
      "reasoning": "Submit button within form element"
    }}
  ],
  "analysis": "The element might not be found because it could be dynamically loaded, hidden by CSS, or the description doesn't match the actual element attributes. The page contains a submit button with multiple possible selectors."
}}
"""


def get_story_parsing_prompt(story_text: str) -> str:
    """
    Get the story parsing prompt with the story text filled in.
    
    Args:
        story_text: The user story text to parse
    
    Returns:
        str: Formatted prompt ready for LLM
    """
    import json
    schema_str = json.dumps(STORY_PARSING_SCHEMA, indent=2)
    return STORY_PARSING_PROMPT.format(
        story_text=story_text,
        schema=schema_str
    )


def get_scenario_generation_prompt(acceptance_criteria: list[str]) -> str:
    """
    Get the scenario generation prompt with criteria filled in.
    
    Args:
        acceptance_criteria: List of acceptance criteria texts
    
    Returns:
        str: Formatted prompt ready for LLM
    """
    import json
    
    # Format criteria as numbered list
    criteria_text = "\n".join([
        f"{i+1}. {criterion}"
        for i, criterion in enumerate(acceptance_criteria)
    ])
    
    schema_str = json.dumps(SCENARIO_GENERATION_SCHEMA, indent=2)
    return SCENARIO_GENERATION_PROMPT.format(
        criteria=criteria_text,
        schema=schema_str
    )


def get_selector_suggestion_prompt(
    element_description: str,
    page_context: str
) -> str:
    """
    Get the selector suggestion prompt with element and context filled in.
    
    Args:
        element_description: Description of the element to find
        page_context: HTML or DOM context of the page
    
    Returns:
        str: Formatted prompt ready for LLM
    """
    import json
    
    # Limit page context to avoid token limits
    max_context_length = 5000
    if len(page_context) > max_context_length:
        page_context = page_context[:max_context_length] + "\n... (truncated)"
    
    schema_str = json.dumps(SELECTOR_SUGGESTION_SCHEMA, indent=2)
    return SELECTOR_SUGGESTION_PROMPT.format(
        element_description=element_description,
        page_context=page_context,
        schema=schema_str
    )


# Export all templates and schemas
__all__ = [
    "STORY_PARSING_SCHEMA",
    "STORY_PARSING_PROMPT",
    "SCENARIO_GENERATION_SCHEMA",
    "SCENARIO_GENERATION_PROMPT",
    "SELECTOR_SUGGESTION_SCHEMA",
    "SELECTOR_SUGGESTION_PROMPT",
    "get_story_parsing_prompt",
    "get_scenario_generation_prompt",
    "get_selector_suggestion_prompt",
]
