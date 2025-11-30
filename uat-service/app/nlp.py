from typing import List, Dict, Optional
import os
import json
import re
from .llm_client import get_llm_client


def parse_story_to_scenarios(title: str, criteria: List[str]) -> List[Dict]:
    """
    Parse user story acceptance criteria into BDD scenarios using LLM.
    Falls back to basic NLP parsing if LLM is unavailable.
    """
    llm = get_llm_client()
    if llm:
        return _parse_with_llm(title, criteria, llm)
    else:
        return _parse_with_fallback(title, criteria)


def _parse_with_llm(title: str, criteria: List[str], llm) -> List[Dict]:
    """Use OpenAI LLM to parse acceptance criteria into structured BDD scenarios."""
    scenarios: List[Dict] = []
    
    # Combine all criteria into a single prompt
    criteria_text = "\n".join([f"- {c}" for c in criteria])
    
    prompt = f"""You are a test automation expert. Parse the following user story acceptance criteria into structured BDD (Given-When-Then) scenarios.

User Story Title: {title}

Acceptance Criteria:
{criteria_text}

For each acceptance criterion, extract:
1. Given steps (preconditions/initial state)
2. When steps (actions/user interactions)
3. Then steps (expected outcomes/assertions)

Return a JSON array where each element represents one scenario with this structure:
{{
  "name": "Scenario description",
  "given": ["Given step 1", "Given step 2"],
  "when": ["When step 1", "When step 2"],
  "then": ["Then step 1", "Then step 2"]
}}

If a criterion doesn't explicitly state Given/When/Then, infer them from the context.
Be specific about UI elements, actions, and expected outcomes.
Return ONLY valid JSON, no additional text."""

    try:
        # Create a more structured prompt that requests specific JSON format
        structured_prompt = f"""Parse the following user story acceptance criteria into BDD scenarios.

User Story: {title}

Acceptance Criteria:
{criteria_text}

Return a JSON object with this exact structure:
{{
  "scenarios": [
    {{
      "name": "Scenario description",
      "given": ["Given step 1"],
      "when": ["When step 1"],
      "then": ["Then step 1"]
    }}
  ]
}}

Extract Given/When/Then steps from each criterion. If not explicitly stated, infer from context."""

        messages = [
            {"role": "system", "content": "You are a test automation expert. Always return valid JSON with a 'scenarios' array."},
            {"role": "user", "content": structured_prompt}
        ]
        
        result_text = llm.chat_completion(
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        if not result_text:
            raise Exception("LLM returned empty response")
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(0)
        
        parsed = json.loads(result_text)
        
        # Handle different response formats
        if isinstance(parsed, dict) and "scenarios" in parsed:
            scenarios = parsed["scenarios"]
        elif isinstance(parsed, list):
            scenarios = parsed
        elif isinstance(parsed, dict) and "scenario" in parsed:
            scenarios = [parsed["scenario"]]
        else:
            # Fallback if structure is unexpected
            scenarios = _parse_with_fallback(title, criteria)
            
    except Exception as e:
        print(f"LLM parsing failed: {e}. Falling back to basic parsing.")
        scenarios = _parse_with_fallback(title, criteria)
    
    # Ensure all scenarios have required fields
    for idx, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            continue
        scenario.setdefault("name", f"Scenario {idx+1}: {title}")
        scenario.setdefault("given", [])
        scenario.setdefault("when", [])
        scenario.setdefault("then", [])
    
    return scenarios if scenarios else _parse_with_fallback(title, criteria)


def _parse_with_fallback(title: str, criteria: List[str]) -> List[Dict]:
    """
    Fallback parsing using basic NLP heuristics when LLM is unavailable.
    """
    scenarios: List[Dict] = []
    
    for idx, crit in enumerate(criteria):
        lines = [l.strip() for l in re.split(r"[\n\r]+", crit) if l.strip()]
        given, when, then = [], [], []
        current = None
        
        for line in lines:
            low = line.lower().strip()
            # Handle "And" steps - they continue the current section
            if low.startswith("and "):
                line = "And " + line[4:].strip() if len(line) > 4 else line
                low = line.lower().strip()
            
            if low.startswith("given"):
                current = "given"
                given.append(line)
            elif low.startswith("when"):
                current = "when"
                when.append(line)
            elif low.startswith("then"):
                current = "then"
                then.append(line)
            elif low.startswith("and"):
                # "And" steps continue the current section
                if current == "given":
                    given.append(line)
                elif current == "when":
                    when.append(line)
                elif current == "then":
                    then.append(line)
                else:
                    # If no current section, treat as Then (most common)
                    current = "then"
                    then.append(line)
            else:
                if current == "given":
                    given.append(line)
                elif current == "when":
                    when.append(line)
                elif current == "then":
                    then.append(line)
                else:
                    # Default to Then if unclear
                    current = "then"
                    then.append(line)
        
        scenarios.append({
            "name": f"Scenario {idx+1}: {title}",
            "given": given or ["Given I am on the homepage"],
            "when": when or ["When I interact with the page"],
            "then": then or ["Then I should see the expected result"],
        })
    
    return scenarios


def map_story_to_dom_elements(story_text: str, page_content: str) -> Dict[str, str]:
    """
    Use LLM to map story text to DOM elements (data-testid attributes).
    This helps identify which UI elements are relevant for the story.
    """
    if not client:
        return {}
    
    prompt = f"""You are analyzing a user story and a web page to identify relevant DOM elements.

User Story:
{story_text}

Page Content (HTML structure):
{page_content[:2000]}  # Limit to avoid token limits

Identify which data-testid attributes or other selectors are relevant for this story.
Return a JSON object mapping story actions to selectors:
{{
  "actions": {{
    "action_description": "selector (prefer data-testid)"
  }}
}}

Return ONLY valid JSON."""

    try:
        messages = [
            {"role": "system", "content": "You are a test automation expert. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        result_text = llm.chat_completion(
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        if not result_text:
            raise Exception("LLM returned empty response")
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(0)
        
        return json.loads(result_text)
    except Exception as e:
        print(f"DOM mapping failed: {e}")
        return {}
