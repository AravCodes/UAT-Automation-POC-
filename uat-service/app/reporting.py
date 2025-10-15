from typing import Dict, List
import json
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape


def score_and_summarize(execution_result: Dict) -> Dict:
    results: List[Dict] = execution_result.get("results", [])
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    score = (passed / total * 100.0) if total else 0.0

    if passed == total and total > 0:
        status = "pass"
    elif passed == 0:
        status = "fail"
    else:
        status = "partial"

    return {
        "score": round(score, 2),
        "status": status,
        "total_scenarios": total,
        "passed": passed,
        "failed": total - passed,
        "results": results,
    }


def write_json_report(summary: Dict, artifacts_dir: str) -> str:
    os.makedirs(artifacts_dir, exist_ok=True)
    json_path = os.path.join(artifacts_dir, "report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return json_path


def write_html_report(summary: Dict, artifacts_dir: str) -> str:
    os.makedirs(artifacts_dir, exist_ok=True)
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    html = template.render(summary=summary)
    html_path = os.path.join(artifacts_dir, "report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


