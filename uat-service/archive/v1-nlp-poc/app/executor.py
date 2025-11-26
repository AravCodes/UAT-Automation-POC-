from typing import List, Dict
import asyncio
from functools import partial
from playwright.sync_api import sync_playwright


def _run_scenarios_sync(scenarios: List[Dict], target_url: str, artifacts_dir: str) -> Dict:
    results: List[Dict] = []
    with sync_playwright() as p:
        # browser = p.chromium.launch(headless=False, slow_mo=1000)
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        for i, scenario in enumerate(scenarios):
            # Positive path
            passed_pos = True
            errors_pos: List[str] = []
            try:
                page.goto(f"{target_url}/login")
                page.fill('[data-testid="email-input"]', 'user@example.com')
                page.fill('[data-testid="password-input"]', 'Password123!')
                page.click('[data-testid="login-button"]')
                page.wait_for_url('**/dashboard*')
                page.wait_for_selector('[data-testid="welcome-message"]', timeout=3000)
            except Exception as e:
                passed_pos = False
                errors_pos.append(str(e))
                page.screenshot(path=f"{artifacts_dir}/scenario_{i+1}_positive.png", full_page=True)

            results.append({
                "scenario": {**scenario, "variant": "positive"},
                "passed": passed_pos,
                "errors": errors_pos,
            })

            # Negative path
            passed_neg = True
            errors_neg: List[str] = []
            try:
                page.goto(f"{target_url}/login")
                page.fill('[data-testid="email-input"]', 'user@example.com')
                page.fill('[data-testid="password-input"]', 'WrongPassword!')
                page.click('[data-testid="login-button"]')
                page.wait_for_url('**/login*')
                page.wait_for_selector('[data-testid="login-error"]', timeout=3000)
            except Exception as e:
                passed_neg = False
                errors_neg.append(str(e))
                page.screenshot(path=f"{artifacts_dir}/scenario_{i+1}_negative.png", full_page=True)

            results.append({
                "scenario": {**scenario, "variant": "negative"},
                "passed": passed_neg,
                "errors": errors_neg,
            })

        browser.close()

    return {"results": results}


async def run_scenarios(scenarios: List[Dict], target_url: str, artifacts_dir: str) -> Dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_run_scenarios_sync, scenarios, target_url, artifacts_dir))


