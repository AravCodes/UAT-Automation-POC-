from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
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
from dotenv import load_dotenv
from .nlp import parse_story_to_scenarios
from .executor import run_scenarios
from .reporting import score_and_summarize, write_json_report, write_html_report
from .excel_parser import parse_excel_file

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="UAT Automation Service (POC)")
# Ensure artifacts directory exists before mounting
os.makedirs("artifacts", exist_ok=True)
app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")

# Mount static files for Excel template
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
try:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
except Exception:
    pass  # Static directory might not exist yet

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


@app.post("/upload-excel")
async def upload_excel(
    request: Request,
    file: UploadFile = File(...),
    target_url: str = Form(...),
):
    """Upload and parse Excel file with user stories, then run all stories."""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Parse Excel file
        stories = parse_excel_file(file_content)
        
        if not stories:
            raise HTTPException(status_code=400, detail="No stories found in Excel file")
        
        # Run all stories and collect results
        results = []
        for story_data in stories:
            try:
                story = StoryRequest(
                    title=story_data["title"],
                    description=story_data.get("description"),
                    acceptance_criteria=[{"text": c} for c in story_data.get("acceptance_criteria", [])],
                    target_url=target_url
                )
                result = await run_story(story)
                results.append({
                    "test_id": story_data.get("test_id", "N/A"),
                    "title": story_data["title"],
                    "run_id": result.run_id,
                    "score": result.score,
                    "status": result.status,
                    "report_url": result.details.get("report_html", "/")
                })
            except Exception as e:
                results.append({
                    "test_id": story_data.get("test_id", "N/A"),
                    "title": story_data["title"],
                    "error": str(e)
                })
        
        # Create a summary page
        return templates.TemplateResponse("excel_results.html.j2", {
            "request": request,
            "results": results,
            "total_stories": len(stories),
            "successful": len([r for r in results if "error" not in r])
        })
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Excel file: {str(e)}")

