# AI-Powered UAT Automation – POC Plan

## Goal
Build a minimal, end-to-end proof of concept that:
- Ingests user stories (manual input for MVP) module-by-module (e.g., Login).
- Parses acceptance criteria into BDD-style Given–When–Then scenarios using an LLM with spaCy fallback.
- Executes tests against a simple sample web app (Login module) using Playwright.
- Compares expected behavior vs actual app behavior and produces a %-score with diagnostics.
- Displays a small report page summarizing story → criteria → execution results.

## Scope (POC)
- One target module: Login (email + password, basic validations, success redirect).
- One sample web app hosted locally (Node/Express + simple frontend, or Next.js). 
- Manual story input via a form or JSON file; optional CSV import.
- Playwright-based headless test execution (Chromium only for POC).
- Minimal reporting: in-memory store + JSON + HTML page with screenshots.

## Non-Goals (for POC)
- Multi-tenant SaaS, RBAC, SSO, org management.
- Full Jira/Azure DevOps integration (will simulate via CSV/JSON import).
- Email verification in real inbox; we’ll stub/mock the email outcome.
- Cross-browser/device matrix; we’ll stick to Chromium.

## Architecture (POC)
- Web UI (React + Vite or Next.js):
  - Story input form
  - Test run trigger
  - Results dashboard
- Backend API (FastAPI or Node/Express):
  - Endpoints: /stories, /run, /results, /artifacts
  - Orchestrates: NLP→BDD, DOM mapping, Playwright execution, scoring
- NLP Service (local module):
  - LLM (OpenAI GPT-4o initially) with deterministic prompts
  - spaCy + regex fallback for basic Given/When/Then extraction
- Executor (Playwright):
  - Launch browser, navigate, perform steps using DOM-mapping heuristics
  - Capture screenshots, console logs
- Storage (for POC):
  - In-memory or lightweight SQLite/Supabase (optional)
  - Artifacts in ./artifacts/<runId>/

## Data Flow
1) User provides story + acceptance criteria in UI.
2) Backend calls NLP → BDD scenarios.
3) Backend compiles executable steps (Playwright) with DOM mapping.
4) Executor runs steps on target app URL.
5) Comparator scores each criterion (Pass/Fail/Partial) and aggregates.
6) UI fetches and displays results + screenshots.

## DOM Mapping Heuristics (POC)
- Prefer stable selectors if available: [data-testid], [name], [id].
- Fallback ranking:
  1. Exact text match for buttons/links/labels.
  2. Label-for association to inputs.
  3. Placeholder/title/aria-label similarity.
  4. Semantic role (role="button"/"textbox").
- Similarity scoring using cosine similarity over embeddings for text labels.

## Scoring Logic
- Each acceptance criterion yields one or more verifications (assertions).
- Pass = all assertions true; Partial = some true; Fail = none true.
- Story score = (passed_criteria / total_criteria) × 100.
- Include reasons for failures and screenshot references.

## Tech Stack
- Frontend: Next.js (React, TypeScript), Tailwind (optional)
- Backend: FastAPI (Python 3.11) or Node/Express (TypeScript). POC will use FastAPI for tight NLP integration.
- NLP: OpenAI GPT-4o via openai SDK, spaCy (en_core_web_sm)
- Testing: Playwright (Python) for simplicity with FastAPI, or Playwright (Node). We will use Playwright (Python) for co-location with NLP.
- Storage: In-memory + filesystem; optional SQLite via SQLModel for runs and results.

## Deliverables (POC)
- Sample Login App (Minimal):
  - Routes: /login (email, password), /dashboard
  - Behavior: on correct creds → redirect /dashboard; otherwise error message
- UAT Automation Service:
  - API endpoints to ingest stories and run tests
  - NLP→BDD transformation module
  - Executor with DOM mapping
  - Report generator (JSON + simple HTML)
- Plan + README + setup scripts

## Milestones & Steps
1. Sample App
   - Create minimal Next.js app with /login and /dashboard
   - Add stable selectors (data-testid) to key elements
   - Implement simple auth logic in-memory
2. Backend API (FastAPI)
   - Scaffold FastAPI project with endpoints
   - Define schemas: Story, Criterion, Scenario, Step, RunResult
3. NLP→BDD
   - Implement prompt for Given/When/Then extraction
   - spaCy fallback for basic patterns
4. Executor (Playwright)
   - Implement DOM mapping helpers
   - Implement step runners: navigate, fill, click, expect text/url
5. Scoring + Reporting
   - Aggregate criterion pass/fail
   - Save screenshots and JSON report
   - Simple HTML dashboard page
6. Wire & Demo
   - Connect sample app URL
   - Run story for Login module
   - Present results in UI

## Example User Story (POC)
As a User, I should be able to log in with email and password so that I can access my dashboard.

Acceptance Criteria:
- Given I am on the login page
- When I enter a valid email and password and click Login
- Then I should be redirected to the dashboard and see a welcome message
- When I enter incorrect credentials, I see an error message

## Risks & Mitigations
- LLM variability → use deterministic prompts + schema validation.
- Flaky selectors → add data-testid, build robust heuristics.
- Test environment instability → run locally with seeded state.

## Next Steps
- Scaffold repositories: `sample-app/` and `uat-service/`
- Implement Login sample app
- Implement FastAPI backend with NLP→BDD and Playwright executor
- Run first story end-to-end and iterate
