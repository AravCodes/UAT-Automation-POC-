"""
Report generation service with multiple format support.

This module provides comprehensive report generation for test runs,
including HTML, JSON, and PDF formats. Reports include story-to-result
traceability, executive summaries, and detailed diagnostics.
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.story import ParsedStory
from app.models.test_scenario import TestScenario
from app.models.test_result import TestRunResult, ScenarioResult
from app.core.logging import get_logger
from app.core.exceptions import ReportGenerationException


logger = get_logger(__name__)


class ReportFormat(str, Enum):
    """Supported report formats."""
    HTML = "html"
    JSON = "json"
    PDF = "pdf"


class ExecutiveSummary:
    """Executive summary with key metrics and insights."""
    
    def __init__(
        self,
        total_scenarios: int,
        passed_scenarios: int,
        failed_scenarios: int,
        skipped_scenarios: int,
        pass_percentage: float,
        total_duration_ms: int,
        flaky_test_count: int,
        critical_failures: list[str],
        recommendations: list[str]
    ):
        self.total_scenarios = total_scenarios
        self.passed_scenarios = passed_scenarios
        self.failed_scenarios = failed_scenarios
        self.skipped_scenarios = skipped_scenarios
        self.pass_percentage = pass_percentage
        self.total_duration_ms = total_duration_ms
        self.flaky_test_count = flaky_test_count
        self.critical_failures = critical_failures
        self.recommendations = recommendations
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_scenarios": self.total_scenarios,
            "passed_scenarios": self.passed_scenarios,
            "failed_scenarios": self.failed_scenarios,
            "skipped_scenarios": self.skipped_scenarios,
            "pass_percentage": round(self.pass_percentage, 2),
            "total_duration_seconds": round(self.total_duration_ms / 1000, 2),
            "flaky_test_count": self.flaky_test_count,
            "critical_failures": self.critical_failures,
            "recommendations": self.recommendations
        }


class StoryResultMapping:
    """Maps test results back to user stories and acceptance criteria."""
    
    def __init__(
        self,
        story: ParsedStory,
        criteria_results: dict[str, dict],
        overall_status: str
    ):
        self.story = story
        self.criteria_results = criteria_results
        self.overall_status = overall_status
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "story": {
                "id": self.story.id,
                "title": self.story.title,
                "role": self.story.role,
                "feature": self.story.feature,
                "benefit": self.story.benefit
            },
            "criteria_results": self.criteria_results,
            "overall_status": self.overall_status
        }


class Report:
    """Complete test report with all sections."""
    
    def __init__(
        self,
        run_id: str,
        story_id: str,
        generated_at: datetime,
        executive_summary: ExecutiveSummary,
        story_mapping: StoryResultMapping,
        scenario_results: list[ScenarioResult],
        diagnostics: dict,
        format: ReportFormat,
        content: str
    ):
        self.run_id = run_id
        self.story_id = story_id
        self.generated_at = generated_at
        self.executive_summary = executive_summary
        self.story_mapping = story_mapping
        self.scenario_results = scenario_results
        self.diagnostics = diagnostics
        self.format = format
        self.content = content
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "story_id": self.story_id,
            "generated_at": self.generated_at.isoformat(),
            "executive_summary": self.executive_summary.to_dict(),
            "story_mapping": self.story_mapping.to_dict(),
            "scenario_results": [
                {
                    "scenario_id": sr.scenario_id,
                    "status": sr.status.value,
                    "duration_ms": sr.duration_ms,
                    "retry_count": sr.retry_count,
                    "is_flaky": sr.is_flaky,
                    "error_summary": sr.error_summary,
                    "step_count": len(sr.step_results),
                    "failed_steps": [
                        {
                            "action": step.step.action.value,
                            "target": step.step.target,
                            "error": step.error_message,
                            "screenshot": step.screenshot_path
                        }
                        for step in sr.step_results
                        if step.error_message
                    ]
                }
                for sr in self.scenario_results
            ],
            "diagnostics": self.diagnostics,
            "format": self.format.value
        }


class ReportGenerator:
    """
    Generates comprehensive test reports in multiple formats.
    
    This service creates business-friendly reports that map test results
    back to user stories and acceptance criteria, providing traceability
    and actionable insights.
    """
    
    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize report generator.
        
        Args:
            template_dir: Directory containing Jinja2 templates
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = template_dir
        self.jinja_env = None
        
        # Initialize Jinja2 environment if templates exist
        if template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True
            )
            # Add custom filters
            self.jinja_env.filters['format_duration'] = self._format_duration
            self.jinja_env.filters['format_timestamp'] = self._format_timestamp
    
    async def generate_report(
        self,
        run_result: TestRunResult,
        story: ParsedStory,
        scenarios: list[TestScenario],
        format: ReportFormat = ReportFormat.HTML
    ) -> Report:
        """
        Generate comprehensive test report.
        
        Args:
            run_result: Test run results
            story: Parsed user story
            scenarios: Test scenarios that were executed
            format: Desired report format
            
        Returns:
            Report: Generated report
            
        Raises:
            ReportGenerationException: If report generation fails
        """
        try:
            logger.info(
                "generating_report",
                extra={
                    "run_id": run_result.id,
                    "story_id": run_result.story_id,
                    "format": format.value
                }
            )
            
            # Create executive summary
            executive_summary = self.create_executive_summary(run_result)
            
            # Map results to stories
            story_mapping = self.map_results_to_stories(
                run_result,
                story,
                scenarios
            )
            
            # Generate content based on format
            if format == ReportFormat.JSON:
                content = self._generate_json_report(
                    run_result,
                    executive_summary,
                    story_mapping
                )
            elif format == ReportFormat.HTML:
                content = self._generate_html_report(
                    run_result,
                    story,
                    executive_summary,
                    story_mapping
                )
            elif format == ReportFormat.PDF:
                # PDF generation would use a library like weasyprint
                # For now, generate HTML and note it needs conversion
                html_content = self._generate_html_report(
                    run_result,
                    story,
                    executive_summary,
                    story_mapping
                )
                content = f"<!-- PDF generation requires weasyprint -->\n{html_content}"
            else:
                raise ReportGenerationException(f"Unsupported format: {format}")
            
            report = Report(
                run_id=run_result.id,
                story_id=run_result.story_id,
                generated_at=datetime.utcnow(),
                executive_summary=executive_summary,
                story_mapping=story_mapping,
                scenario_results=run_result.scenario_results,
                diagnostics=run_result.diagnostics.model_dump(),
                format=format,
                content=content
            )
            
            logger.info(
                "report_generated",
                extra={
                    "run_id": run_result.id,
                    "format": format.value,
                    "content_length": len(content)
                }
            )
            
            return report
            
        except Exception as e:
            logger.error(
                "report_generation_failed",
                extra={"run_id": run_result.id, "error": str(e)},
                exc_info=True
            )
            raise ReportGenerationException(f"Failed to generate report: {e}") from e
    
    def create_executive_summary(
        self,
        run_result: TestRunResult
    ) -> ExecutiveSummary:
        """
        Create business-friendly executive summary.
        
        Args:
            run_result: Test run results
            
        Returns:
            ExecutiveSummary: Summary with key metrics
        """
        diagnostics = run_result.diagnostics
        
        # Calculate pass percentage
        total = diagnostics.total_scenarios
        passed = diagnostics.passed_scenarios
        pass_percentage = (passed / total * 100) if total > 0 else 0
        
        # Calculate total duration
        total_duration = sum(
            sr.duration_ms for sr in run_result.scenario_results
        )
        
        # Identify critical failures
        critical_failures = []
        for sr in run_result.scenario_results:
            if sr.status.value in ["failed", "error"]:
                # Find first failed step
                for step_result in sr.step_results:
                    if step_result.error_message:
                        critical_failures.append(
                            f"Scenario {sr.scenario_id}: {step_result.error_message[:100]}"
                        )
                        break
        
        # Generate recommendations
        recommendations = self._generate_recommendations(run_result)
        
        return ExecutiveSummary(
            total_scenarios=diagnostics.total_scenarios,
            passed_scenarios=diagnostics.passed_scenarios,
            failed_scenarios=diagnostics.failed_scenarios,
            skipped_scenarios=diagnostics.skipped_scenarios,
            pass_percentage=pass_percentage,
            total_duration_ms=total_duration,
            flaky_test_count=len(diagnostics.flaky_scenarios),
            critical_failures=critical_failures[:5],  # Top 5
            recommendations=recommendations
        )
    
    def map_results_to_stories(
        self,
        run_result: TestRunResult,
        story: ParsedStory,
        scenarios: list[TestScenario]
    ) -> StoryResultMapping:
        """
        Create traceability matrix mapping results to stories.
        
        Args:
            run_result: Test run results
            story: Parsed user story
            scenarios: Test scenarios
            
        Returns:
            StoryResultMapping: Mapping of story to results
        """
        # Group scenarios by acceptance criterion
        criteria_results = {}
        
        for criterion in story.acceptance_criteria:
            criterion_scenarios = [
                s for s in scenarios if s.criterion_id == criterion.id
            ]
            
            # Find results for these scenarios
            scenario_results = []
            for scenario in criterion_scenarios:
                result = next(
                    (sr for sr in run_result.scenario_results if sr.scenario_id == scenario.id),
                    None
                )
                if result:
                    scenario_results.append({
                        "scenario": scenario,
                        "result": result
                    })
            
            # Determine criterion status
            if not scenario_results:
                status = "not_tested"
            elif all(sr["result"].status.value == "passed" for sr in scenario_results):
                status = "passed"
            elif any(sr["result"].status.value == "failed" for sr in scenario_results):
                status = "failed"
            else:
                status = "partial"
            
            criteria_results[criterion.id] = {
                "criterion": criterion,
                "status": status,
                "scenarios": scenario_results
            }
        
        # Determine overall story status
        if not criteria_results:
            overall_status = "not_tested"
        elif all(cr["status"] == "passed" for cr in criteria_results.values()):
            overall_status = "passed"
        elif any(cr["status"] == "failed" for cr in criteria_results.values()):
            overall_status = "failed"
        else:
            overall_status = "partial"
        
        return StoryResultMapping(
            story=story,
            criteria_results=criteria_results,
            overall_status=overall_status
        )
    
    def _generate_json_report(
        self,
        run_result: TestRunResult,
        executive_summary: ExecutiveSummary,
        story_mapping: StoryResultMapping
    ) -> str:
        """Generate JSON format report."""
        report_data = {
            "run_id": run_result.id,
            "story_id": run_result.story_id,
            "generated_at": datetime.utcnow().isoformat(),
            "status": run_result.status.value,
            "started_at": run_result.started_at.isoformat(),
            "completed_at": run_result.completed_at.isoformat(),
            "executive_summary": executive_summary.to_dict(),
            "story_mapping": story_mapping.to_dict(),
            "scenario_results": [
                {
                    "scenario_id": sr.scenario_id,
                    "status": sr.status.value,
                    "duration_ms": sr.duration_ms,
                    "retry_count": sr.retry_count,
                    "is_flaky": sr.is_flaky,
                    "error_summary": sr.error_summary,
                    "steps": [
                        {
                            "action": step.step.action.value,
                            "target": step.step.target,
                            "value": step.step.value,
                            "status": step.status.value,
                            "duration_ms": step.duration_ms,
                            "error_message": step.error_message,
                            "screenshot_path": step.screenshot_path
                        }
                        for step in sr.step_results
                    ]
                }
                for sr in run_result.scenario_results
            ],
            "diagnostics": run_result.diagnostics.model_dump(),
            "environment": run_result.environment,
            "configuration": run_result.configuration
        }
        
        return json.dumps(report_data, indent=2)
    
    def _generate_html_report(
        self,
        run_result: TestRunResult,
        story: ParsedStory,
        executive_summary: ExecutiveSummary,
        story_mapping: StoryResultMapping
    ) -> str:
        """Generate HTML format report using Jinja2 templates."""
        if not self.jinja_env:
            # Fallback to basic HTML if templates not available
            return self._generate_basic_html(
                run_result,
                story,
                executive_summary,
                story_mapping
            )
        
        try:
            template = self.jinja_env.get_template("report.html")
            return template.render(
                run_result=run_result,
                story=story,
                executive_summary=executive_summary,
                story_mapping=story_mapping,
                generated_at=datetime.utcnow()
            )
        except Exception as e:
            logger.warning(
                "template_rendering_failed",
                extra={"error": str(e)},
                exc_info=True
            )
            # Fallback to basic HTML
            return self._generate_basic_html(
                run_result,
                story,
                executive_summary,
                story_mapping
            )
    
    def _generate_basic_html(
        self,
        run_result: TestRunResult,
        story: ParsedStory,
        executive_summary: ExecutiveSummary,
        story_mapping: StoryResultMapping
    ) -> str:
        """Generate basic HTML report without templates."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Report - {story.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .partial {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>Test Report: {story.title}</h1>
    <div class="summary">
        <h2>Executive Summary</h2>
        <p><strong>Status:</strong> <span class="{run_result.status.value}">{run_result.status.value.upper()}</span></p>
        <p><strong>Pass Rate:</strong> {executive_summary.pass_percentage:.1f}%</p>
        <p><strong>Total Scenarios:</strong> {executive_summary.total_scenarios}</p>
        <p><strong>Passed:</strong> {executive_summary.passed_scenarios}</p>
        <p><strong>Failed:</strong> {executive_summary.failed_scenarios}</p>
        <p><strong>Duration:</strong> {executive_summary.total_duration_ms / 1000:.2f}s</p>
    </div>
    
    <h2>Story Details</h2>
    <p><strong>Role:</strong> {story.role}</p>
    <p><strong>Feature:</strong> {story.feature}</p>
    <p><strong>Benefit:</strong> {story.benefit}</p>
    
    <h2>Test Results</h2>
    <table>
        <tr>
            <th>Scenario ID</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Retries</th>
        </tr>
"""
        
        for sr in run_result.scenario_results:
            html += f"""
        <tr>
            <td>{sr.scenario_id}</td>
            <td class="{sr.status.value}">{sr.status.value.upper()}</td>
            <td>{sr.duration_ms / 1000:.2f}s</td>
            <td>{sr.retry_count}</td>
        </tr>
"""
        
        html += """
    </table>
</body>
</html>
"""
        return html
    
    def _generate_recommendations(
        self,
        run_result: TestRunResult
    ) -> list[str]:
        """Generate actionable recommendations based on results."""
        recommendations = []
        
        diagnostics = run_result.diagnostics
        
        # Check pass rate
        if diagnostics.total_scenarios > 0:
            pass_rate = diagnostics.passed_scenarios / diagnostics.total_scenarios
            if pass_rate < 0.7:
                recommendations.append(
                    "Pass rate is below 70%. Review failed scenarios and address critical issues."
                )
        
        # Check for flaky tests
        if diagnostics.flaky_scenarios:
            recommendations.append(
                f"Found {len(diagnostics.flaky_scenarios)} flaky test(s). "
                "Investigate timing issues or unstable elements."
            )
        
        # Check for slow tests
        avg_duration = (
            sum(sr.duration_ms for sr in run_result.scenario_results) /
            len(run_result.scenario_results)
            if run_result.scenario_results else 0
        )
        if avg_duration > 30000:  # 30 seconds
            recommendations.append(
                "Average scenario duration exceeds 30s. Consider optimizing wait times."
            )
        
        # Check for repeated failures
        failed_actions = {}
        for sr in run_result.scenario_results:
            if sr.status.value == "failed":
                for step in sr.step_results:
                    if step.error_message:
                        action = step.step.action.value
                        failed_actions[action] = failed_actions.get(action, 0) + 1
        
        if failed_actions:
            most_failed = max(failed_actions.items(), key=lambda x: x[1])
            if most_failed[1] > 2:
                recommendations.append(
                    f"Action '{most_failed[0]}' failed {most_failed[1]} times. "
                    "Review element selectors or page stability."
                )
        
        if not recommendations:
            recommendations.append("All tests passed successfully. Great work!")
        
        return recommendations
    
    @staticmethod
    def _format_duration(milliseconds: int) -> str:
        """Format duration in milliseconds to human-readable string."""
        if milliseconds < 1000:
            return f"{milliseconds}ms"
        elif milliseconds < 60000:
            return f"{milliseconds / 1000:.1f}s"
        else:
            minutes = milliseconds // 60000
            seconds = (milliseconds % 60000) / 1000
            return f"{minutes}m {seconds:.0f}s"
    
    @staticmethod
    def _format_timestamp(dt: datetime) -> str:
        """Format datetime to human-readable string."""
        return dt.strftime("%Y-%m-%d %H:%M:%S")
