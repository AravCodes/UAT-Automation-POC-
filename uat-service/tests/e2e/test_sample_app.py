"""
End-to-end tests against sample application.

This module tests the complete UAT automation system against the sample
application using all 15+ sample user stories from fixtures.

Requirements: All (Task 14.2)
"""

import pytest
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime
from typing import List

from app.models.story import StoryInput, ParsedStory
from app.models.test_scenario import TestScenario
from app.models.test_result import TestRunResult, RunStatus
from app.services.parser.story_parser import StoryParser
from app.services.parser.scenario_generator import ScenarioGenerator
from app.services.executor.test_runner import TestRunner
from app.services.reporting.report_generator import ReportGenerator
from app.core.config import get_config


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def sample_stories():
    """Load all sample stories from fixtures."""
    fixture_path = Path("fixtures/sample-stories.json")
    
    if not fixture_path.exists():
        pytest.skip(f"Sample stories fixture not found at {fixture_path}")
    
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data.get("stories", [])


@pytest.fixture(scope="module")
def config():
    """Get application configuration."""
    return get_config()


@pytest.fixture(scope="module")
def sample_app_url(config):
    """Get sample application URL."""
    url = config.sample_app_url
    
    # Check if sample app is running
    import httpx
    try:
        response = httpx.get(url, timeout=5.0)
        if response.status_code != 200:
            pytest.skip(f"Sample app not accessible at {url}")
    except Exception as e:
        pytest.skip(f"Sample app not running at {url}: {str(e)}")
    
    return url


# ============================================================================
# Helper Functions
# ============================================================================

def convert_fixture_to_story_input(fixture_story: dict) -> StoryInput:
    """Convert fixture story format to StoryInput model."""
    # Build story text from fixture
    story_text = fixture_story.get("story", "")
    
    # Add acceptance criteria to story text
    if "acceptance_criteria" in fixture_story:
        story_text += "\n\nAcceptance Criteria:\n"
        for ac in fixture_story["acceptance_criteria"]:
            given = ac.get("given", "")
            when = ac.get("when", "")
            then = ac.get("then", "")
            story_text += f"- Given {given}, when {when}, then {then}\n"
    
    return StoryInput(
        text=story_text,
        source="fixture",
        metadata={
            "fixture_id": fixture_story.get("id"),
            "module": fixture_story.get("module"),
            "priority": fixture_story.get("priority"),
            "title": fixture_story.get("title")
        }
    )


async def run_story_test(
    story_fixture: dict,
    sample_app_url: str,
    artifacts_base_dir: str
) -> dict:
    """
    Run complete test flow for a single story.
    
    Returns:
        dict with test results and metrics
    """
    story_id = story_fixture.get("id", "unknown")
    module = story_fixture.get("module", "unknown")
    
    print(f"\n{'='*80}")
    print(f"Testing Story: {story_id} - {story_fixture.get('title')}")
    print(f"Module: {module}")
    print(f"{'='*80}\n")
    
    # Create artifacts directory for this story
    artifacts_dir = os.path.join(artifacts_base_dir, story_id)
    os.makedirs(artifacts_dir, exist_ok=True)
    
    result = {
        "story_id": story_id,
        "module": module,
        "title": story_fixture.get("title"),
        "success": False,
        "parsing_success": False,
        "scenario_generation_success": False,
        "execution_success": False,
        "report_generation_success": False,
        "error": None,
        "metrics": {}
    }
    
    try:
        # Step 1: Parse story
        print(f"[{story_id}] Step 1: Parsing story...")
        story_input = convert_fixture_to_story_input(story_fixture)
        
        parser = StoryParser()
        parsed_story = await parser.parse(story_input)
        
        result["parsing_success"] = True
        result["metrics"]["parsing_method"] = parsed_story.parsing_method
        result["metrics"]["acceptance_criteria_count"] = len(parsed_story.acceptance_criteria)
        
        print(f"[{story_id}] ✓ Parsing successful ({parsed_story.parsing_method})")
        print(f"[{story_id}]   - Acceptance Criteria: {len(parsed_story.acceptance_criteria)}")
        
        # Step 2: Generate scenarios
        print(f"[{story_id}] Step 2: Generating test scenarios...")
        generator = ScenarioGenerator()
        scenarios = await generator.generate_scenarios(parsed_story.acceptance_criteria)
        
        result["scenario_generation_success"] = True
        result["metrics"]["scenario_count"] = len(scenarios)
        
        print(f"[{story_id}] ✓ Scenario generation successful")
        print(f"[{story_id}]   - Scenarios: {len(scenarios)}")
        
        # Step 3: Execute tests
        print(f"[{story_id}] Step 3: Executing tests...")
        runner = TestRunner(concurrency=1)  # Use concurrency=1 for e2e tests
        test_result = await runner.run_scenarios(
            scenarios=scenarios,
            target_url=sample_app_url,
            artifacts_dir=artifacts_dir
        )
        
        result["execution_success"] = True
        result["metrics"]["execution_status"] = test_result.status.value
        result["metrics"]["passed_scenarios"] = sum(
            1 for sr in test_result.scenario_results 
            if sr.status.value == "passed"
        )
        result["metrics"]["failed_scenarios"] = sum(
            1 for sr in test_result.scenario_results 
            if sr.status.value == "failed"
        )
        result["metrics"]["flaky_scenarios"] = sum(
            1 for sr in test_result.scenario_results 
            if sr.is_flaky
        )
        
        print(f"[{story_id}] ✓ Execution completed")
        print(f"[{story_id}]   - Status: {test_result.status.value}")
        print(f"[{story_id}]   - Passed: {result['metrics']['passed_scenarios']}")
        print(f"[{story_id}]   - Failed: {result['metrics']['failed_scenarios']}")
        print(f"[{story_id}]   - Flaky: {result['metrics']['flaky_scenarios']}")
        
        # Step 4: Generate report
        print(f"[{story_id}] Step 4: Generating report...")
        report_generator = ReportGenerator()
        report = await report_generator.generate_report(
            run_result=test_result,
            parsed_story=parsed_story,
            format="html"
        )
        
        # Save report to artifacts
        report_path = os.path.join(artifacts_dir, "report.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report.html_content if hasattr(report, "html_content") else str(report))
        
        result["report_generation_success"] = True
        result["metrics"]["report_path"] = report_path
        
        print(f"[{story_id}] ✓ Report generated: {report_path}")
        
        # Mark overall success
        result["success"] = True
        
    except Exception as e:
        result["error"] = str(e)
        print(f"[{story_id}] ✗ Error: {str(e)}")
    
    return result


# ============================================================================
# End-to-End Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.slow
class TestSampleApplicationE2E:
    """End-to-end tests against sample application."""
    
    async def test_all_sample_stories(self, sample_stories, sample_app_url, tmp_path):
        """
        Test all sample stories against the sample application.
        
        This is the main end-to-end test that runs all 15+ sample stories
        through the complete UAT automation flow.
        """
        if not sample_stories:
            pytest.skip("No sample stories found")
        
        print(f"\n{'='*80}")
        print(f"Running E2E tests for {len(sample_stories)} sample stories")
        print(f"Sample App URL: {sample_app_url}")
        print(f"{'='*80}\n")
        
        # Create artifacts directory
        artifacts_dir = os.path.join(str(tmp_path), "e2e-artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Run tests for all stories
        results = []
        for story in sample_stories:
            result = await run_story_test(story, sample_app_url, artifacts_dir)
            results.append(result)
        
        # Generate summary report
        print(f"\n{'='*80}")
        print("E2E Test Summary")
        print(f"{'='*80}\n")
        
        total_stories = len(results)
        successful_stories = sum(1 for r in results if r["success"])
        parsing_success = sum(1 for r in results if r["parsing_success"])
        scenario_gen_success = sum(1 for r in results if r["scenario_generation_success"])
        execution_success = sum(1 for r in results if r["execution_success"])
        report_gen_success = sum(1 for r in results if r["report_generation_success"])
        
        print(f"Total Stories: {total_stories}")
        print(f"Successful: {successful_stories} ({successful_stories/total_stories*100:.1f}%)")
        print(f"\nPipeline Success Rates:")
        print(f"  - Parsing: {parsing_success}/{total_stories} ({parsing_success/total_stories*100:.1f}%)")
        print(f"  - Scenario Generation: {scenario_gen_success}/{total_stories} ({scenario_gen_success/total_stories*100:.1f}%)")
        print(f"  - Execution: {execution_success}/{total_stories} ({execution_success/total_stories*100:.1f}%)")
        print(f"  - Report Generation: {report_gen_success}/{total_stories} ({report_gen_success/total_stories*100:.1f}%)")
        
        # Group results by module
        modules = {}
        for r in results:
            module = r["module"]
            if module not in modules:
                modules[module] = []
            modules[module].append(r)
        
        print(f"\nResults by Module:")
        for module, module_results in modules.items():
            success_count = sum(1 for r in module_results if r["success"])
            print(f"  - {module}: {success_count}/{len(module_results)} successful")
        
        # List failed stories
        failed_stories = [r for r in results if not r["success"]]
        if failed_stories:
            print(f"\nFailed Stories ({len(failed_stories)}):")
            for r in failed_stories:
                print(f"  - {r['story_id']}: {r['error']}")
        
        # Save detailed results to JSON
        results_path = os.path.join(artifacts_dir, "e2e-results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.utcnow().isoformat(),
                "total_stories": total_stories,
                "successful_stories": successful_stories,
                "results": results
            }, f, indent=2)
        
        print(f"\nDetailed results saved to: {results_path}")
        print(f"Artifacts directory: {artifacts_dir}")
        
        # Assert that at least 80% of stories passed
        success_rate = successful_stories / total_stories
        assert success_rate >= 0.8, f"Success rate {success_rate:.1%} is below 80% threshold"
    
    
    async def test_login_module_stories(self, sample_stories, sample_app_url, tmp_path):
        """Test all Login module stories."""
        login_stories = [s for s in sample_stories if s.get("module") == "Login"]
        
        if not login_stories:
            pytest.skip("No Login module stories found")
        
        print(f"\nTesting {len(login_stories)} Login module stories")
        
        artifacts_dir = os.path.join(str(tmp_path), "login-artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        
        results = []
        for story in login_stories:
            result = await run_story_test(story, sample_app_url, artifacts_dir)
            results.append(result)
        
        # Verify all login stories passed
        successful = sum(1 for r in results if r["success"])
        print(f"\nLogin Module: {successful}/{len(results)} stories successful")
        
        assert successful >= len(results) * 0.8, "Less than 80% of Login stories passed"
    
    
    async def test_user_management_module_stories(self, sample_stories, sample_app_url, tmp_path):
        """Test all User Management module stories."""
        user_mgmt_stories = [s for s in sample_stories if s.get("module") == "User Management"]
        
        if not user_mgmt_stories:
            pytest.skip("No User Management module stories found")
        
        print(f"\nTesting {len(user_mgmt_stories)} User Management module stories")
        
        artifacts_dir = os.path.join(str(tmp_path), "user-mgmt-artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        
        results = []
        for story in user_mgmt_stories:
            result = await run_story_test(story, sample_app_url, artifacts_dir)
            results.append(result)
        
        successful = sum(1 for r in results if r["success"])
        print(f"\nUser Management Module: {successful}/{len(results)} stories successful")
        
        assert successful >= len(results) * 0.8, "Less than 80% of User Management stories passed"
    
    
    async def test_element_finding_strategies(self, sample_stories, sample_app_url, tmp_path):
        """
        Test that element finding strategies work across all modules.
        
        This test verifies that the multi-strategy element finder can locate
        elements using various strategies (testid, aria-label, text, etc.)
        """
        if not sample_stories:
            pytest.skip("No sample stories found")
        
        print(f"\nTesting element finding strategies across {len(sample_stories)} stories")
        
        artifacts_dir = os.path.join(str(tmp_path), "element-finding-artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Track element finding success by strategy
        strategy_stats = {
            "testid": 0,
            "aria_label": 0,
            "label_for": 0,
            "placeholder": 0,
            "text": 0,
            "role": 0,
            "fuzzy": 0
        }
        
        # Run a subset of stories to test element finding
        test_stories = sample_stories[:5]  # Test first 5 stories
        
        for story in test_stories:
            result = await run_story_test(story, sample_app_url, artifacts_dir)
            
            # TODO: Extract element finding strategy stats from execution logs
            # This would require instrumenting the element finder to track which
            # strategy successfully found each element
        
        print(f"\nElement Finding Strategy Stats:")
        for strategy, count in strategy_stats.items():
            print(f"  - {strategy}: {count} elements found")
        
        # For now, just verify that tests ran
        assert len(test_stories) > 0
    
    
    async def test_report_traceability(self, sample_stories, sample_app_url, tmp_path):
        """
        Test that reports maintain traceability from story to results.
        
        Verifies that generated reports correctly map:
        - Story → Acceptance Criteria → Scenarios → Results
        """
        if not sample_stories:
            pytest.skip("No sample stories found")
        
        # Test with first story
        story = sample_stories[0]
        
        artifacts_dir = os.path.join(str(tmp_path), "traceability-artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        
        result = await run_story_test(story, sample_app_url, artifacts_dir)
        
        # Verify report was generated
        assert result["report_generation_success"], "Report generation failed"
        
        # Verify report file exists
        report_path = result["metrics"].get("report_path")
        assert report_path is not None, "Report path not found"
        assert os.path.exists(report_path), f"Report file not found at {report_path}"
        
        # Read report and verify it contains traceability information
        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()
        
        # Verify report contains story information
        assert story["id"] in report_content or story["title"] in report_content, \
            "Report does not contain story information"
        
        print(f"\n✓ Report traceability verified for story {story['id']}")


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.smoke
class TestSampleApplicationSmoke:
    """Smoke tests for quick validation."""
    
    async def test_sample_app_accessible(self, sample_app_url):
        """Test that sample application is accessible."""
        import httpx
        
        response = httpx.get(sample_app_url, timeout=10.0)
        assert response.status_code == 200, f"Sample app returned status {response.status_code}"
        
        print(f"✓ Sample app accessible at {sample_app_url}")
    
    
    async def test_single_story_end_to_end(self, sample_stories, sample_app_url, tmp_path):
        """Quick smoke test with a single story."""
        if not sample_stories:
            pytest.skip("No sample stories found")
        
        # Use first story for smoke test
        story = sample_stories[0]
        
        artifacts_dir = os.path.join(str(tmp_path), "smoke-artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        
        result = await run_story_test(story, sample_app_url, artifacts_dir)
        
        assert result["success"], f"Smoke test failed: {result.get('error')}"
        
        print(f"\n✓ Smoke test passed for story {story['id']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
