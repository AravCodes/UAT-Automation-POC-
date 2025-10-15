
# Automated UAT from User Stories – POC

## Purpose
Turn business user stories into executable UAT checks. This POC ingests acceptance criteria, converts them into BDD-like scenarios, runs the flow against a sample web app via Playwright, and produces business-friendly HTML/JSON reports mapped to the story.

## What this includes
- sample-app/: Minimal login app (Express + static HTML) used as the UAT target.
- uat-service/: FastAPI backend with:
  - Story form UI (manual ingestion)
  - Heuristic NLP → BDD scenario parsing
  - Playwright executor (positive + negative login paths)
  - Report generation (HTML + JSON) under artifacts/
- .github/workflows/ci.yml: Basic CI to install dependencies and validate environment.

## Primary Use Cases
- Validate a login user story (happy path + invalid password).
- Demonstrate the flow: Story → Scenarios → DOM actions → Assertions → Report.
- Foundation for future integrations (Jira, embeddings, multi-module UAT).

## Tech Stack
- Backend: FastAPI (Python 3.11), Jinja2, Playwright (Chromium)
- Sample App: Node.js (Express), static HTML with data-testid locators

## Local Setup (Windows PowerShell)
1) Start sample app (http://localhost:5173):
```powershell
cd sample-app
npm i
npm run dev
```

2) Start UAT service (http://localhost:8000):
```powershell
cd ..\uat-service
pip install poetry
poetry install
poetry run playwright install chromium
poetry run uvicorn app.main:app --reload --port 8000
```

3) Run a story (via UI):
- Open http://localhost:8000/
- Title: Login as a user
- Acceptance Criteria (scenarios separated by a blank line):
  Given I am on the login page
  When I enter a valid email and password and click Login
  Then I should be redirected to the dashboard and see a welcome message

  When I enter incorrect credentials, I see an error message
- Target URL: http://localhost:5173
- Submit → Redirects to /artifacts/<runId>/report.html

4) Run via API (optional):
POST http://localhost:8000/stories:run
```json
{
  "title": "Login as a user",
  "description": "User can log in and see dashboard",
  "acceptance_criteria": [
    { "text": "Given I am on the login page\nWhen I enter a valid email and password and click Login\nThen I should be redirected to the dashboard and see a welcome message" },
    { "text": "When I enter incorrect credentials, I see an error message" }
  ],
  "target_url": "http://localhost:5173"
}
```

## Notes and Extensibility
- Validates positive and negative login paths.
- Reports saved at uat-service/artifacts/<runId>/
- Set default target via SAMPLE_APP_URL for the form.
- Next: Jira CSV import; embeddings-based semantic matching; richer DOM mapping.
