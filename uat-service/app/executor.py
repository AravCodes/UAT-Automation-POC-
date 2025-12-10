from typing import List, Dict
import asyncio
from functools import partial
from playwright.sync_api import sync_playwright


def _run_scenarios_sync(scenarios: List[Dict], target_url: str, artifacts_dir: str) -> Dict:
    """Execute basic login positive/negative scenarios against the target app.

    Assumes the app has:
      - Login page at f"{target_url}/login"
      - Email input:  "#email"            (adjust in code if different)
      - Password input: "#password"       (adjust in code if different)
      - Login button: "button[type='submit']" (adjust if different)
      - Successful login redirects to URL containing "/dashboard"
      - Failed login shows an error containing text "Invalid"
    """
    results: List[Dict] = []
    with sync_playwright() as p:
        # Visible browser with slow motion so you can watch the steps
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        context = browser.new_context()
        page = context.new_page()

        for i, scenario in enumerate(scenarios):
            # Positive path: valid credentials should reach dashboard
            passed_pos = True
            errors_pos: List[str] = []
            try:
                page.goto(f"{target_url}/login", wait_until="networkidle")
                page.fill("#email", "user@example.com")
                page.fill("#password", "Password123!")
                page.click("button[type='submit']")
                page.wait_for_url("**/dashboard*", timeout=10000)
                page.wait_for_timeout(1000)
            except Exception as e:
                passed_pos = False
                errors_pos.append(str(e))
                try:
                    page.screenshot(
                        path=f"{artifacts_dir}/scenario_{i+1}_positive_error.png",
                        full_page=True,
                    )
                except Exception:
                    pass

            results.append(
                {
                    "scenario": {**scenario, "variant": "positive"},
                    "passed": passed_pos,
                    "errors": errors_pos,
                }
            )

            # Negative path: wrong password should keep user on login with error
            passed_neg = True
            errors_neg: List[str] = []
            try:
                page.goto(f"{target_url}/login", wait_until="networkidle")
                page.fill("#email", "user@example.com")
                page.fill("#password", "WrongPassword!")
                page.click("button[type='submit']")
                page.wait_for_url("**/login*", timeout=10000)
                page.wait_for_selector("text=Invalid", timeout=5000)
                page.wait_for_timeout(1000)
            except Exception as e:
                passed_neg = False
                errors_neg.append(str(e))
                try:
                    page.screenshot(
                        path=f"{artifacts_dir}/scenario_{i+1}_negative_error.png",
                        full_page=True,
                    )
                except Exception:
                    pass

            results.append(
                {
                    "scenario": {**scenario, "variant": "negative"},
                    "passed": passed_neg,
                    "errors": errors_neg,
                }
            )

        browser.close()

    return {"results": results}


async def run_scenarios(scenarios: List[Dict], target_url: str, artifacts_dir: str) -> Dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(_run_scenarios_sync, scenarios, target_url, artifacts_dir)
    )


