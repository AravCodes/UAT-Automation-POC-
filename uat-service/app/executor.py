from typing import List, Dict, Optional
import asyncio
from functools import partial
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
import re
import os
import json
from .llm_client import get_llm_client


def _map_step_to_action(step: str, page: Page) -> Optional[Dict]:
    """
    Use LLM to map a BDD step to a Playwright action.
    Prioritizes LLM over fallback for better accuracy.
    Returns a dict with action type and selector.
    """
    # Try LLM first if available (better accuracy)
    llm = get_llm_client()
    if llm:
        try:
            # Get page content for context (only if page has content)
            page_content = ""
            try:
                current_url = page.url
                if current_url and current_url != "about:blank":
                    page_content = page.content()[:3000]  # Limit to avoid token limits
            except:
                page_content = ""
            
            prompt = f"""You are a test automation expert. Map the following BDD step to a Playwright action.

BDD Step: {step}

Available Page Content (HTML):
{page_content[:2000] if page_content else "Page not loaded yet"}

Complete list of available data-testid attributes with descriptions:
- store-title: Store header title
- products-title: Products section title
- products-grid: Products container grid
- product-card-{{id}}: Individual product card (use [data-testid^='product-card'] to match any)
- product-title-{{id}}: Product name (use [data-testid^='product-title'] to match any)
- product-price-{{id}}: Product price (use [data-testid^='product-price'] to match any)
- add-to-cart-{{id}}: Add to cart button (use [data-testid^='add-to-cart'] to match any)
- cart-link: Link to cart page in header
- cart-count: Cart item count in header
- cart-title: Cart page title
- cart-container: Cart container
- cart-items-list: List of cart items
- cart-item-{{id}}: Individual cart item (use [data-testid^='cart-item'] to match any)
- cart-item-name-{{id}}: Cart item name (use [data-testid^='cart-item-name'] to match any)
- cart-item-price-{{id}}: Cart item price (use [data-testid^='cart-item-price'] to match any)
- remove-item-{{id}}: Remove item button (use [data-testid^='remove-item'] to match any)
- cart-subtotal: Cart subtotal amount
- cart-tax: Cart tax amount
- cart-total: Cart total amount
- checkout-button: Proceed to checkout button
- checkout-title: Checkout page title
- checkout-form: Checkout form
- shipping-section: Shipping information section
- payment-section: Payment information section
- order-summary: Order summary sidebar
- order-items: List of items in order summary
- full-name-input: Full name input field
- email-input: Email input field
- address-input: Address input field
- city-input: City input field
- zip-input: ZIP code input field
- country-select: Country dropdown
- card-number-input: Card number input
- expiry-input: Expiry date input
- cvv-input: CVV input
- place-order-button: Place order button
- success-page: Success confirmation page
- success-title: Success message title
- success-message: Success message text
- message-box: Success/error message container
- empty-cart: Empty cart message container
- home-link: Link to homepage/continue shopping
- summary-subtotal: Order summary subtotal
- summary-tax: Order summary tax
- summary-total: Order summary total
- order-item-{{id}}: Item in order summary (use [data-testid^='order-item'] to match any)
- order-item-price-{{id}}: Item price in summary (use [data-testid^='order-item-price'] to match any)

Mapping Rules:
1. ALWAYS use data-testid selectors in format: [data-testid='exact-id'] or [data-testid^='prefix'] for patterns
2. For "click" actions, identify the button/link test ID from the step text
3. For "fill" actions, identify the input field test ID and provide a reasonable test value
4. For "assert" actions, identify the element to verify
5. Match step keywords to test IDs (e.g., "Add to Cart" → add-to-cart, "email" → email-input)

Examples:
- "click Add to Cart" → {{"action": "click", "selector": "[data-testid^='add-to-cart']", "timeout": 5000}}
- "fill email" → {{"action": "fill", "selector": "[data-testid='email-input']", "value": "test@example.com", "timeout": 5000}}
- "see products" → {{"action": "assert_visible", "selector": "[data-testid='products-grid']", "timeout": 5000}}
- "navigate to homepage" → {{"action": "navigate", "url": "/", "timeout": 10000}}

Return a JSON object with this structure:
{{
  "action": "navigate|fill|click|wait_for|assert_text|assert_url|assert_visible",
  "selector": "CSS selector using data-testid (e.g., [data-testid='test-id'] or [data-testid^='prefix'] for patterns)",
  "value": "value to fill (if action is fill, provide reasonable test data)",
  "expected": "expected text/url (if action is assert)",
  "timeout": 5000
}}

Action types:
- navigate: Navigate to a URL (use "url" field instead of "selector", e.g., "/", "/cart", "/checkout")
- fill: Fill an input field (provide "value" field with test data)
- click: Click a button/link
- wait_for: Wait for an element to appear
- assert_text: Assert text content matches (provide "expected" field)
- assert_url: Assert URL matches pattern (provide "expected" field like "**/checkout*")
- assert_visible: Assert element is visible

Return ONLY valid JSON."""

            messages = [
                {"role": "system", "content": "You are a test automation expert specializing in Playwright and data-testid selectors. Always return valid JSON with precise selectors matching the step description."},
                {"role": "user", "content": prompt}
            ]
            
            result_text = llm.chat_completion(
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            if not result_text:
                raise Exception("LLM returned empty response")
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(0)
            
            result = json.loads(result_text)
            # Validate the result has required fields
            if "action" in result:
                print(f"LLM mapped step: '{step}' → {result.get('action')} with selector: {result.get('selector', result.get('url', 'N/A'))}")
                return result
            else:
                print(f"LLM returned invalid result (no action field), using fallback")
        except Exception as e:
            print(f"LLM step mapping failed: {e}. Using fallback.")
            # Fall through to fallback
    
    # Fallback when LLM is unavailable or failed
    return _map_step_to_action_fallback(step, page)


def _map_step_to_action_fallback(step: str, page: Page) -> Optional[Dict]:
    """
    Fallback mapping using heuristics when LLM is unavailable.
    Enhanced with better pattern matching.
    """
    step_lower = step.lower().strip()
    
    # Handle "And" steps by removing "and" prefix
    if step_lower.startswith("and "):
        step_lower = step_lower[4:].strip()
    
    # Navigate actions - check first as they're common
    if any(word in step_lower for word in ["navigate", "go to", "visit", "on the", "am on"]):
        if any(word in step_lower for word in ["homepage", "home", "home page"]):
            return {"action": "navigate", "url": "/", "timeout": 10000}
        elif "cart" in step_lower and "page" in step_lower:
            return {"action": "navigate", "url": "/cart", "timeout": 10000}
        elif "checkout" in step_lower and "page" in step_lower:
            return {"action": "navigate", "url": "/checkout", "timeout": 10000}
        elif "cart" in step_lower:
            return {"action": "navigate", "url": "/cart", "timeout": 10000}
        elif "checkout" in step_lower:
            return {"action": "navigate", "url": "/checkout", "timeout": 10000}
    
    # Click actions
    if "click" in step_lower:
        if "add to cart" in step_lower or "add-to-cart" in step_lower:
            # Use first available add-to-cart button
            return {"action": "click", "selector": "[data-testid^='add-to-cart']:first-of-type", "timeout": 5000}
        elif ("checkout" in step_lower or "proceed" in step_lower) and "button" in step_lower:
            return {"action": "click", "selector": "[data-testid='checkout-button']", "timeout": 5000}
        elif "place order" in step_lower or "place-order" in step_lower:
            return {"action": "click", "selector": "[data-testid='place-order-button']", "timeout": 5000}
        elif "remove" in step_lower:
            return {"action": "click", "selector": "[data-testid^='remove-item']:first-of-type", "timeout": 5000}
        elif "cart" in step_lower and "link" in step_lower:
            return {"action": "click", "selector": "[data-testid='cart-link']", "timeout": 5000}
    
    # Fill/Enter actions
    if any(word in step_lower for word in ["enter", "fill", "type", "input", "provide"]):
        if "email" in step_lower:
            test_value = "test@example.com"
            if "valid" in step_lower:
                test_value = "test@example.com"
            return {"action": "fill", "selector": "[data-testid='email-input']", "value": test_value, "timeout": 5000}
        elif "name" in step_lower and ("full" in step_lower or "full-name" in step_lower):
            return {"action": "fill", "selector": "[data-testid='full-name-input']", "value": "Test User", "timeout": 5000}
        elif "address" in step_lower:
            return {"action": "fill", "selector": "[data-testid='address-input']", "value": "123 Test Street", "timeout": 5000}
        elif "city" in step_lower:
            return {"action": "fill", "selector": "[data-testid='city-input']", "value": "Test City", "timeout": 5000}
        elif "zip" in step_lower or "postal" in step_lower:
            return {"action": "fill", "selector": "[data-testid='zip-input']", "value": "12345", "timeout": 5000}
        elif "country" in step_lower:
            return {"action": "fill", "selector": "[data-testid='country-select']", "value": "US", "timeout": 5000}
        elif "card" in step_lower and "number" in step_lower:
            return {"action": "fill", "selector": "[data-testid='card-number-input']", "value": "1234567890123456", "timeout": 5000}
        elif "expiry" in step_lower or "expiration" in step_lower:
            return {"action": "fill", "selector": "[data-testid='expiry-input']", "value": "12/25", "timeout": 5000}
        elif "cvv" in step_lower or "cvc" in step_lower:
            return {"action": "fill", "selector": "[data-testid='cvv-input']", "value": "123", "timeout": 5000}
    
    # Assert/Then actions - check for visibility, text, URL
    if any(phrase in step_lower for phrase in ["should see", "should be", "then", "expect", "verify"]):
        # Product-related assertions
        if "product" in step_lower:
            if "grid" in step_lower:
                return {"action": "assert_visible", "selector": "[data-testid='products-grid']", "timeout": 5000}
            elif "card" in step_lower:
                return {"action": "assert_visible", "selector": "[data-testid^='product-card']", "timeout": 5000}
            else:
                return {"action": "assert_visible", "selector": "[data-testid^='product-card']", "timeout": 5000}
        
        # Cart-related assertions
        elif "cart" in step_lower:
            if "empty" in step_lower or "no items" in step_lower:
                return {"action": "assert_visible", "selector": "[data-testid='empty-cart']", "timeout": 5000}
            elif "item" in step_lower:
                return {"action": "assert_visible", "selector": "[data-testid^='cart-item']", "timeout": 5000}
            else:
                return {"action": "assert_visible", "selector": "[data-testid='cart-container']", "timeout": 5000}
        
        # Success/confirmation assertions
        elif "success" in step_lower or "confirmation" in step_lower or "placed" in step_lower:
            return {"action": "assert_visible", "selector": "[data-testid='success-page']", "timeout": 10000}
        
        # Message assertions
        elif "message" in step_lower:
            if "success" in step_lower or "added" in step_lower:
                return {"action": "assert_visible", "selector": "[data-testid='message-box']", "timeout": 5000}
            else:
                return {"action": "assert_visible", "selector": "[data-testid='message-box']", "timeout": 5000}
        
        # URL/redirect assertions
        elif any(word in step_lower for word in ["redirected", "url", "navigate", "go to"]):
            if "checkout" in step_lower:
                return {"action": "assert_url", "expected": "**/checkout*", "timeout": 5000}
            elif "cart" in step_lower:
                return {"action": "assert_url", "expected": "**/cart*", "timeout": 5000}
            elif "home" in step_lower:
                return {"action": "assert_url", "expected": "**/", "timeout": 5000}
        
        # Count assertions (cart count)
        elif "count" in step_lower and "cart" in step_lower:
            return {"action": "assert_visible", "selector": "[data-testid='cart-count']", "timeout": 5000}
        
        # Generic "see" assertions - try common elements
        elif "see" in step_lower:
            if "button" in step_lower:
                return {"action": "assert_visible", "selector": "button", "timeout": 5000}
            else:
                # Generic visibility check
                return {"action": "wait_for", "selector": "body", "timeout": 3000}
    
    # View actions (similar to navigate but might be about seeing content)
    if "view" in step_lower:
        if "product" in step_lower:
            return {"action": "assert_visible", "selector": "[data-testid='products-grid']", "timeout": 5000}
        elif "cart" in step_lower:
            return {"action": "navigate", "url": "/cart", "timeout": 10000}
    
    # Wait actions
    if "wait" in step_lower:
        return {"action": "wait_for", "selector": "body", "timeout": 3000}
    
    return None


def _execute_action(action: Dict, page: Page, base_url: str) -> tuple:
    """
    Execute a single Playwright action.
    Returns (success, error_message)
    """
    try:
        action_type = action.get("action")
        timeout = action.get("timeout", 5000)
        
        if action_type == "navigate":
            url = action.get("url", "/")
            page.goto(f"{base_url}{url}", timeout=timeout)
            return True, None
        
        elif action_type == "fill":
            selector = action.get("selector")
            value = action.get("value", "")
            # Wait for element to be visible before filling
            page.wait_for_selector(selector, timeout=timeout, state="visible")
            page.fill(selector, value, timeout=timeout)
            return True, None
        
        elif action_type == "click":
            selector = action.get("selector")
            # Wait for element to be visible before clicking
            page.wait_for_selector(selector, timeout=timeout, state="visible")
            page.click(selector, timeout=timeout)
            # Wait a bit after click for page to respond
            page.wait_for_timeout(500)
            return True, None
        
        elif action_type == "wait_for":
            selector = action.get("selector")
            page.wait_for_selector(selector, timeout=timeout)
            return True, None
        
        elif action_type == "assert_text":
            selector = action.get("selector")
            expected = action.get("expected", "")
            actual = page.locator(selector).text_content(timeout=timeout)
            if expected.lower() in actual.lower() if actual else False:
                return True, None
            else:
                return False, f"Expected text '{expected}' not found. Actual: '{actual}'"
        
        elif action_type == "assert_url":
            expected = action.get("expected", "")
            page.wait_for_url(expected, timeout=timeout)
            return True, None
        
        elif action_type == "assert_visible":
            selector = action.get("selector")
            # Use count to verify at least one element is visible
            count = page.locator(selector).count()
            if count > 0:
                page.wait_for_selector(selector, timeout=timeout, state="visible")
                return True, None
            else:
                return False, f"Element with selector '{selector}' not found on page"
        
        else:
            return False, f"Unknown action type: {action_type}"
    
    except PlaywrightTimeoutError as e:
        return False, f"Timeout: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def _run_scenarios_sync(scenarios: List[Dict], target_url: str, artifacts_dir: str) -> Dict:
    """
    Execute BDD scenarios using Playwright with LLM-based step mapping.
    """
    results: List[Dict] = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # Clear localStorage to start fresh
        page.goto(f"{target_url}/")
        page.evaluate("localStorage.clear()")

        for i, scenario in enumerate(scenarios):
            scenario_result = {
                "scenario": scenario.get("name", f"Scenario {i+1}"),
                "steps": [],
                "passed": True,
                "errors": []
            }
            
            try:
                # Execute Given steps
                for given_step in scenario.get("given", []):
                    if not given_step or not given_step.strip():
                        continue
                    action = _map_step_to_action(given_step, page)
                    if action:
                        success, error = _execute_action(action, page, target_url)
                        scenario_result["steps"].append({
                            "step": given_step,
                            "type": "given",
                            "passed": success,
                            "error": error
                        })
                        if not success:
                            scenario_result["passed"] = False
                            scenario_result["errors"].append(f"Given step failed: {error}")
                    else:
                        scenario_result["steps"].append({
                            "step": given_step,
                            "type": "given",
                            "passed": False,
                            "error": "Could not map step to action"
                        })
                        scenario_result["passed"] = False
                        scenario_result["errors"].append(f"Could not map Given step: {given_step}")
                
                # Execute When steps
                for when_step in scenario.get("when", []):
                    if not when_step or not when_step.strip():
                        continue
                    action = _map_step_to_action(when_step, page)
                    if action:
                        success, error = _execute_action(action, page, target_url)
                        scenario_result["steps"].append({
                            "step": when_step,
                            "type": "when",
                            "passed": success,
                            "error": error
                        })
                        if not success:
                            scenario_result["passed"] = False
                            scenario_result["errors"].append(f"When step failed: {error}")
                    else:
                        scenario_result["steps"].append({
                            "step": when_step,
                            "type": "when",
                            "passed": False,
                            "error": "Could not map step to action"
                        })
                        scenario_result["passed"] = False
                        scenario_result["errors"].append(f"Could not map When step: {when_step}")
                
                # Execute Then steps (assertions)
                for then_step in scenario.get("then", []):
                    if not then_step or not then_step.strip():
                        continue
                    action = _map_step_to_action(then_step, page)
                    if action:
                        success, error = _execute_action(action, page, target_url)
                        scenario_result["steps"].append({
                            "step": then_step,
                            "type": "then",
                            "passed": success,
                            "error": error
                        })
                        if not success:
                            scenario_result["passed"] = False
                            scenario_result["errors"].append(f"Then step failed: {error}")
                    else:
                        scenario_result["steps"].append({
                            "step": then_step,
                            "type": "then",
                            "passed": False,
                            "error": "Could not map step to action"
                        })
                        scenario_result["passed"] = False
                        scenario_result["errors"].append(f"Could not map Then step: {then_step}")
                
                # Take screenshot if scenario failed
                if not scenario_result["passed"]:
                    page.screenshot(path=f"{artifacts_dir}/scenario_{i+1}_failed.png", full_page=True)
                else:
                    page.screenshot(path=f"{artifacts_dir}/scenario_{i+1}_passed.png", full_page=True)
            
            except Exception as e:
                scenario_result["passed"] = False
                scenario_result["errors"].append(f"Scenario execution error: {str(e)}")
                page.screenshot(path=f"{artifacts_dir}/scenario_{i+1}_error.png", full_page=True)
            
            results.append(scenario_result)

        browser.close()

    return {"results": results}


async def run_scenarios(scenarios: List[Dict], target_url: str, artifacts_dir: str) -> Dict:
    """
    Async wrapper for scenario execution.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        _run_scenarios_sync,
        scenarios,
        target_url,
        artifacts_dir
    )
