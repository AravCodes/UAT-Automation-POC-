from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import uuid
import os
import sys
import asyncio
import json
from .nlp import parse_story_to_scenarios
from .executor import run_scenarios
from .reporting import score_and_summarize, write_json_report, write_html_report

# Import v2 API routers
from .api.v2 import stories, runs, reports, webhooks
from .api.middleware import setup_middleware
from .core.config import get_config
from .core.logging import get_logger

logger = get_logger(__name__)
config = get_config()

app = FastAPI(
    title="UAT Automation Service",
    description="UAT Automation Service with LLM-powered test generation (v1 POC + v2 API)",
    version="2.0.0",
    docs_url="/docs" if config.enable_api_docs else None,
    redoc_url="/redoc" if config.enable_api_docs else None
)

# Set up middleware for v2 API
setup_middleware(app)

# Ensure artifacts directory exists before mounting
os.makedirs("artifacts", exist_ok=True)
app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")
templates = Jinja2Templates(directory="app/templates")

# Windows fix: allow asyncio to spawn subprocesses (Playwright) on Windows
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        # Best-effort; if unavailable, continue with default policy
        pass

# Include v2 API routers
app.include_router(stories.router, tags=["v2-stories"])
app.include_router(runs.router, tags=["v2-execution"])
app.include_router(reports.router, tags=["v2-reports"])
app.include_router(webhooks.router, tags=["v2-webhooks"])

logger.info(
    "UAT Automation Service started",
    extra={
        "extra_fields": {
            "version": "2.0.0",
            "environment": config.environment,
            "api_docs": f"http://localhost:{config.api_port}/docs" if config.enable_api_docs else "disabled"
        }
    }
)

# ============================================================================
# V1 POC Endpoints (Legacy - for backward compatibility)
# ============================================================================


class AcceptanceCriterion(BaseModel):
    text: str


class StoryRequest(BaseModel):
    title: str
    description: Optional[str] = None
    acceptance_criteria: List[AcceptanceCriterion]
    targetUrl: str = Field(alias="target_url")


class RunResponse(BaseModel):
    run_id: str
    score: float
    status: Literal["pass", "partial", "fail"]
    details: dict


@app.post("/stories:run", response_model=RunResponse)
async def run_story(story: StoryRequest):
    run_id = str(uuid.uuid4())
    artifacts_dir = os.path.join("artifacts", run_id)
    os.makedirs(artifacts_dir, exist_ok=True)

    scenarios = parse_story_to_scenarios(story.title, [c.text for c in story.acceptance_criteria])
    execution_result = await run_scenarios(scenarios, story.targetUrl, artifacts_dir)
    summary = score_and_summarize(execution_result)
    write_json_report(summary, artifacts_dir)
    write_html_report(summary, artifacts_dir)

    return RunResponse(run_id=run_id, score=summary["score"], status=summary["status"], details={
        **summary,
        "artifacts_dir": f"/artifacts/{run_id}",
        "report_html": f"/artifacts/{run_id}/report.html",
        "report_json": f"/artifacts/{run_id}/report.json",
    })


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html.j2", {"request": request, "default_target": os.getenv("SAMPLE_APP_URL", "http://localhost:5173")})


@app.get("/api/sample-stories")
async def get_sample_stories():
    """
    Serve sample user stories from fixtures.
    
    Returns:
        JSON response with sample stories for all modules
    """
    try:
        fixture_path = os.path.join("fixtures", "sample-stories.json")
        
        # Check if fixture file exists
        if not os.path.exists(fixture_path):
            logger.warning(f"Sample stories fixture not found at {fixture_path}")
            return JSONResponse(
                content={"stories": []},
                status_code=200
            )
        
        # Load and return sample stories
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        logger.info(f"Loaded {len(data.get('stories', []))} sample stories")
        return JSONResponse(content=data, status_code=200)
        
    except Exception as e:
        logger.error(f"Failed to load sample stories: {str(e)}", exc_info=True)
        return JSONResponse(
            content={"stories": [], "error": str(e)},
            status_code=500
        )


@app.post("/run")
async def run_from_form(
    request: Request,
    title: str = Form(...),
    acceptance_criteria: str = Form(...),
    target_url: str = Form(...),
):
    criteria = [c.strip() for c in acceptance_criteria.split("\n\n") if c.strip()]
    story = StoryRequest(title=title, description=None, acceptance_criteria=[{"text": c} for c in criteria], target_url=target_url)  # type: ignore[arg-type]
    result = await run_story(story)  # reuse logic

    # If the client explicitly asks for JSON, return a JSON payload
    accept_header = request.headers.get("accept", "")
    report_url = result.details.get("report_html", "/")

    if "application/json" in accept_header.lower():
        return JSONResponse(
            content={
                "run_id": result.run_id,
                "score": result.score,
                "status": result.status,
                "report_html": report_url,
                "report_json": result.details.get("report_json"),
                "artifacts_dir": result.details.get("artifacts_dir"),
            },
            status_code=200,
        )

    # Default browser behavior: redirect to the HTML report
    return RedirectResponse(url=report_url, status_code=303)


# ============================================================================
# System Endpoints
# ============================================================================

@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "environment": config.environment
    }


@app.get("/version", tags=["system"])
async def get_version():
    """Get API version information."""
    return {
        "version": "2.0.0",
        "api_version": "v2",
        "environment": config.environment,
        "features": {
            "v1_poc": True,
            "v2_api": True,
            "llm_integration": True,
            "webhooks": config.enable_webhooks,
            "api_docs": config.enable_api_docs
        }
    }

