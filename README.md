# Automated UAT from User Stories – POC

## Purpose
Turn business user stories into executable UAT checks using LLM and NLP. This POC ingests acceptance criteria, converts them into BDD-like scenarios using OpenAI GPT, maps steps to DOM actions intelligently, runs the flow against a sample e-commerce web app via Playwright, and produces business-friendly HTML/JSON reports mapped to the story.

## What this includes
- **sample-app/**: E-commerce web app (Express + static HTML) with product listing, shopping cart, and checkout flows. All UI elements have `data-testid` attributes for reliable test automation.
- **uat-service/**: FastAPI backend with:
  - Story form UI (manual ingestion)
  - **LLM-based NLP** → BDD scenario parsing using OpenAI GPT-4o-mini
  - **Intelligent step mapping** → DOM action mapping using LLM
  - Playwright executor (supports e-commerce flows)
  - Report generation (HTML + JSON) under artifacts/
- **USER_STORIES.md**: Complete user stories for the e-commerce app with test IDs

## Primary Use Cases
- Validate e-commerce user stories (browse products, add to cart, checkout)
- Demonstrate the flow: Story → LLM Parsing → Scenarios → LLM Step Mapping → DOM actions → Assertions → Report
- Foundation for future integrations (Jira, embeddings, multi-module UAT)

## Tech Stack
- **Backend**: FastAPI (Python 3.11), OpenAI API, Jinja2, Playwright (Chromium)
- **Sample App**: Node.js (Express), static HTML with comprehensive `data-testid` locators
- **AI/NLP**: OpenAI GPT-4o-mini for story parsing and step-to-action mapping

## Prerequisites
- Node.js and npm
- Python 3.11+
- Poetry (Python package manager)
- OpenAI API key (set as environment variable `OPENAI_API_KEY`)

## Local Setup (Windows PowerShell)

### 1) Set up OpenAI API Key
```powershell
$env:OPENAI_API_KEY = "your-api-key-here"
```

Or create a `.env` file in `uat-service/`:
```
OPENAI_API_KEY=your-api-key-here
```

### 2) Start sample e-commerce app (http://localhost:5173):
```powershell
cd sample-app
npm i
npm run dev
```

### 3) Start UAT service (http://localhost:8000):
```powershell
cd ..\uat-service
pip install poetry
poetry install
poetry run playwright install chromium
poetry run uvicorn app.main:app --reload --port 8000
```

### 4) Run a story (via UI):
- Open http://localhost:8000/
- **Title**: Browse Products
- **Acceptance Criteria** (scenarios separated by a blank line):
  ```
  Given I am on the homepage
  When I view the products section
  Then I should see a grid of products with images, names, prices, and descriptions
  And each product should have an "Add to Cart" button
  ```
- **Target URL**: http://localhost:5173
- Submit → Redirects to /artifacts/<runId>/report.html

### 5) Run via API (optional):
POST http://localhost:8000/stories:run
```json
{
  "title": "Add Product to Cart",
  "description": "User can add products to shopping cart",
  "acceptance_criteria": [
    {
      "text": "Given I am on the homepage viewing products\nWhen I click the \"Add to Cart\" button for a product\nThen the product should be added to my cart\nAnd I should see a success message confirming the item was added\nAnd the cart count in the header should increase by 1"
    }
  ],
  "target_url": "http://localhost:5173"
}
```

## User Stories

See `USER_STORIES.md` for complete documentation of all user stories with test IDs:
- STORY-001: Browse Products
- STORY-002: Add Product to Cart
- STORY-003: View Shopping Cart
- STORY-004: Remove Item from Cart
- STORY-005: Proceed to Checkout
- STORY-006: Complete Checkout
- STORY-007: Empty Cart Handling
- STORY-008: Cart Persistence
- STORY-009: Order Summary Accuracy
- STORY-010: Form Validation

## How It Works

1. **Story Ingestion**: User provides story title and acceptance criteria via UI or API
2. **LLM Parsing**: OpenAI GPT-4o-mini parses acceptance criteria into structured BDD scenarios (Given/When/Then)
3. **Step Mapping**: For each step, LLM maps the natural language to Playwright actions (navigate, click, fill, assert)
4. **Execution**: Playwright executes the mapped actions against the e-commerce app
5. **Reporting**: Results are aggregated, scored, and presented in HTML/JSON reports

## Notes and Extensibility
- Uses LLM for intelligent parsing and mapping (falls back to heuristics if API key not set)
- All UI elements use `data-testid` attributes for reliable test automation
- Reports saved at `uat-service/artifacts/<runId>/`
- Set default target via `SAMPLE_APP_URL` environment variable
- Next: Jira CSV import; embeddings-based semantic matching; richer DOM mapping; multi-browser support

## E-Commerce App Features
- **Homepage**: Product grid with 6 sample products
- **Shopping Cart**: View, manage, and remove cart items
- **Checkout**: Complete order with shipping and payment information
- **Cart Persistence**: Uses localStorage to maintain cart across page navigation
