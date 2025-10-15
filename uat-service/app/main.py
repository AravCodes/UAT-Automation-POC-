from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import uuid
import os
import sys
import asyncio
from .nlp import parse_story_to_scenarios
from .executor import run_scenarios
from .reporting import score_and_summarize, write_json_report, write_html_report

app = FastAPI(title="UAT Automation Service (POC)")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return RedirectResponse(url=result.details.get("report_html", "/"), status_code=303)

