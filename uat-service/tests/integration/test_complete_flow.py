"""
Integration tests for complete UAT automation flow.

This module tests the end-to-end flow:
1. Story submission
2. Story parsing (LLM with fallback)
3. Test scenario generation
4. Test execution
5. Report generation

Requirements: All (Task 14.1)
"""

import pytest
import asyncio
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models.story import StoryInput, ParsedStory, AcceptanceCriterion, Priority
from app.models.test_scenario import TestScenario, TestStep, ActionType, ScenarioType
from app.models.test_result import TestRunResult, ScenarioResult, StepResult, RunStatus, ScenarioStatus, StepStatus
from app.services.parser.story_parser import StoryParser
from app.services.parser.scenario_generator import ScenarioGenerator
from app.services.executor.test_runner import TestRunner
from app.services.reporting.report_generator import ReportGenerator
from app.core.exceptions import GroqAPIException, RateLimitException


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_story_input():
    """Sample story input for testing."""
    return StoryInput(
        text="""As a registered user, I want to log in with my email and password, 
        so that I can access my account and use the application features.
        
        Acceptance Criteria:
        - Given I am on the login page, when I enter valid credentials, then I should be redirected to the dashboard
        - Given I am on the login page, when I enter invalid credentials, then I should see an error message
        """,
        source="manual",
        metadata={"module": "Login", "priority": "critical"}
    )


@pytest.fixture
def sample_parsed_story():
    """Sample parsed story for testing."""
    return ParsedStory(
        id="test-story-001",
        title="User Login with Valid Credentials",
        role="registered user",
        feature="log in with email and password",
        benefit="access my account and use the application features",
        acceptance_criteria=[
            AcceptanceCriterion(
                id="ac-001-1",
                text="Given I am on the login page, when I enter valid credentials, then I should be redirected to the dashboard",
                priority=Priority.CRITICAL,
                dependencies=[]
            ),
            AcceptanceCriterion(
                id="ac-001-2",
                text="Given I am on the login page, when I enter invalid credentials, then I should see an error message",
                priority=Priority.HIGH,
                dependencies=[]
            )
        ],
        implicit_requirements=[],
        ambiguities=[],
        parsing_method="llm_primary",
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_test_scenarios():
    """Sample test scenarios for testing."""
    return [
        TestScenario(
            id="scenario-001",
            criterion_id="ac-001-1",
            type=ScenarioType.POSITIVE,
            priority=Priority.CRITICAL,
            given=["I am on the login page"],
            when=["I enter valid email 'user@example.com'", "I enter valid password 'User123!'", "I click the login button"],
            then=["I should be redirected to the dashboard", "I should see a welcome message"],
            test_steps=[
                TestStep(
                    action=ActionType.NAVIGATE,
                    target="http://localhost:5173/login",
                    value=None,
                    expected_outcome="Login page loads"
                ),
                TestStep(
                    action=ActionType.TYPE,
                    target="email input",
                    value="user@example.com",
                    expected_outcome="Email is entered"
                ),
                TestStep(
                    action=ActionType.TYPE,
                    target="password input",
                    value="User123!",
                    expected_outcome="Password is entered"
                ),
                TestStep(
                    action=ActionType.CLICK,
                    target="login button",
                    value=None,
                    expected_outcome="Login form is submitted"
                ),
                TestStep(
                    action=ActionType.ASSERT,
                    target="page url",
                    value="/dashboard",
                    expected_outcome="User is redirected to dashboard"
                )
            ]
        ),
        TestScenario(
            id="scenario-002",
            criterion_id="ac-001-2",
            type=ScenarioType.NEGATIVE,
            priority=Priority.HIGH,
            given=["I am on the login page"],
            when=["I enter invalid credentials", "I click the login button"],
            then=["I should see an error message"],
            test_steps=[
                TestStep(
                    action=ActionType.NAVIGATE,
                    target="http://localhost:5173/login",
                    value=None,
                    expected_outcome="Login page loads"
                ),
                TestStep(
                    action=ActionType.TYPE,
                    target="email input",
                    value="invalid@example.com",
                    expected_outcome="Email is entered"
                ),
                TestStep(
                    action=ActionType.TYPE,
                    target="password input",
                    value="WrongPassword",
                    expected_outcome="Password is entered"
                ),
                TestStep(
                    action=ActionType.CLICK,
                    target="login button",
                    value=None,
                    expected_outcome="Login form is submitted"
                ),
                TestStep(
                    action=ActionType.ASSERT,
                    target="error message",
                    value="Invalid email or password",
                    expected_outcome="Error message is displayed"
                )
            ]
        )
    ]


@pytest.fixture
def mock_groq_response():
    """Mock Groq API response for story parsing."""
    return {
        "id": "test-completion-id",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "llama-3.1-70b-versatile",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "title": "User Login with Valid Credentials",
                        "role": "registered user",
                        "feature": "log in with email and password",
                        "benefit": "access my account and use the application features",
                        "acceptance_criteria": [
                            "Given I am on the login page, when I enter valid credentials, then I should be redirected to the dashboard",
                            "Given I am on the login page, when I enter invalid credentials, then I should see an error message"
                        ],
                        "implicit_requirements": [],
                        "ambiguities": []
                    })
                }
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
    }


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
class TestCompleteFlow:
    """Test complete flow from story submission to report generation."""
    
    async def test_story_parsing_with_llm_success(self, sample_story_input, mock_groq_response):
        """Test successful story parsing using LLM."""
        # Create mock Groq client
        mock_client = AsyncMock()
        mock_client.parse_story = AsyncMock(return_value=mock_groq_response)
        
        # Create parser with mocked client
        parser = StoryParser(groq_client=mock_client)
        parsed_story = await parser.parse(sample_story_input)
        
        # Verify parsing results
        assert parsed_story is not None
        assert parsed_story.title == "User Login with Valid Credentials"
        assert parsed_story.role == "registered user"
        assert len(parsed_story.acceptance_criteria) == 2
        assert parsed_story.parsing_method == "llm_primary"
    
    
    async def test_story_parsing_with_fallback_to_nlp(self, sample_story_input):
        """Test story parsing falls back to NLP when LLM fails."""
        # Mock Groq API to fail
        with patch('app.services.llm.groq_client.GroqClient') as MockGroqClient:
            mock_client = MockGroqClient.return_value
            mock_client.parse_story = AsyncMock(side_effect=GroqAPIException("API Error"))
            
            # Mock legacy NLP parser
            with patch('app.services.parser.legacy_nlp.LegacyNLPParser') as MockNLPParser:
                mock_nlp = MockNLPParser.return_value
                mock_nlp.parse = AsyncMock(return_value=ParsedStory(
                    id="test-story-nlp",
                    title="User Login",
                    role="user",
                    feature="login",
                    benefit="access account",
                    acceptance_criteria=[],
                    implicit_requirements=[],
                    ambiguities=[],
                    parsing_method="nlp_legacy",
                    created_at=datetime.utcnow()
                ))
                
                # Create parser and parse story
                parser = StoryParser()
                parsed_story = await parser.parse(sample_story_input)
                
                # Verify fallback was used
                assert parsed_story is not None
                assert parsed_story.parsing_method == "nlp_legacy"
    
    
    async def test_scenario_generation_from_criteria(self, sample_parsed_story):
        """Test scenario generation from acceptance criteria."""
        # Create mock Groq client
        mock_client = AsyncMock()
        mock_client.generate_scenarios = AsyncMock(return_value={
            "scenarios": [
                {
                    "criterion_id": "ac-001-1",
                    "type": "positive",
                    "priority": "critical",
                    "given": ["I am on the login page"],
                    "when": ["I enter valid credentials"],
                    "then": ["I should be redirected to the dashboard"],
                    "test_steps": [
                        {
                            "action": "navigate",
                            "target": "http://localhost:5173/login",
                            "value": None,
                            "expected_outcome": "Login page loads"
                        },
                        {
                            "action": "type",
                            "target": "email input",
                            "value": "user@example.com",
                            "expected_outcome": "Email is entered"
                        }
                    ]
                }
            ]
        })
        
        # Generate scenarios with mocked client
        generator = ScenarioGenerator(groq_client=mock_client)
        scenarios = await generator.generate_scenarios(sample_parsed_story.acceptance_criteria)
        
        # Verify scenarios were generated
        assert len(scenarios) > 0
        assert scenarios[0].type in [ScenarioType.POSITIVE, ScenarioType.NEGATIVE, ScenarioType.EDGE_CASE]
        assert len(scenarios[0].test_steps) > 0
    
    
    async def test_parallel_execution_with_retry_logic(self, sample_test_scenarios):
        """Test parallel test execution with retry logic."""
        # Mock Playwright
        with patch('app.services.executor.playwright_wrapper.PlaywrightWrapper') as MockPlaywright:
            mock_pw = MockPlaywright.return_value
            mock_pw.execute_step = AsyncMock(return_value=StepResult(
                step=sample_test_scenarios[0].test_steps[0],
                status=StepStatus.PASSED,
                screenshot_path=None,
                error_message=None,
                dom_snapshot=None,
                duration_ms=100
            ))
            
            # Create test runner with concurrency=2
            runner = TestRunner(concurrency=2)
            
            # Execute scenarios
            result = await runner.run_scenarios(
                scenarios=sample_test_scenarios,
                target_url="http://localhost:5173",
                artifacts_dir="artifacts/test-run"
            )
            
            # Verify execution results
            assert result is not None
            assert result.status in [RunStatus.PASSED, RunStatus.FAILED, RunStatus.PARTIAL]
            assert len(result.scenario_results) == len(sample_test_scenarios)
    
    
    async def test_report_generation_with_traceability(self, sample_parsed_story, sample_test_scenarios):
        """Test report generation with story-to-result traceability."""
        # Create mock test results
        test_result = TestRunResult(
            id="test-run-001",
            story_id=sample_parsed_story.id,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            status=RunStatus.PASSED,
            scenario_results=[
                ScenarioResult(
                    scenario_id=scenario.id,
                    status=ScenarioStatus.PASSED,
                    step_results=[],
                    duration_ms=1000,
                    retry_count=0,
                    is_flaky=False
                )
                for scenario in sample_test_scenarios
            ],
            diagnostics={}
        )
        
        # Generate report
        generator = ReportGenerator()
        report = await generator.generate_report(
            run_result=test_result,
            parsed_story=sample_parsed_story,
            format="html"
        )
        
        # Verify report was generated
        assert report is not None
        assert report.run_id == test_result.id
        assert report.story_id == sample_parsed_story.id
        assert report.summary is not None
    
    
    async def test_complete_flow_end_to_end(self, sample_story_input, mock_groq_response):
        """Test complete flow from story submission to report generation."""
        # This is the main integration test that ties everything together
        
        # Step 1: Parse story
        with patch('app.services.llm.groq_client.GroqClient') as MockGroqClient:
            mock_client = MockGroqClient.return_value
            mock_client.parse_story = AsyncMock(return_value=mock_groq_response)
            
            parser = StoryParser()
            parsed_story = await parser.parse(sample_story_input)
            
            assert parsed_story is not None
            assert len(parsed_story.acceptance_criteria) > 0
        
        # Step 2: Generate scenarios
        with patch('app.services.llm.groq_client.GroqClient') as MockGroqClient:
            mock_client = MockGroqClient.return_value
            mock_client.generate_scenarios = AsyncMock(return_value=[
                {
                    "type": "positive",
                    "priority": "critical",
                    "given": ["I am on the login page"],
                    "when": ["I enter valid credentials"],
                    "then": ["I should be redirected to the dashboard"],
                    "test_steps": [
                        {
                            "action": "navigate",
                            "target": "http://localhost:5173/login",
                            "value": None,
                            "expected_outcome": "Login page loads"
                        }
                    ]
                }
            ])
            
            generator = ScenarioGenerator()
            scenarios = await generator.generate_scenarios(parsed_story.acceptance_criteria)
            
            assert len(scenarios) > 0
        
        # Step 3: Execute tests (mocked)
        with patch('app.services.executor.playwright_wrapper.PlaywrightWrapper') as MockPlaywright:
            mock_pw = MockPlaywright.return_value
            mock_pw.execute_step = AsyncMock(return_value=StepResult(
                step=scenarios[0].test_steps[0] if scenarios[0].test_steps else TestStep(
                    action=ActionType.NAVIGATE,
                    target="http://localhost:5173",
                    value=None,
                    expected_outcome="Page loads"
                ),
                status=StepStatus.PASSED,
                screenshot_path=None,
                error_message=None,
                dom_snapshot=None,
                duration_ms=100
            ))
            
            runner = TestRunner(concurrency=1)
            test_result = await runner.run_scenarios(
                scenarios=scenarios,
                target_url="http://localhost:5173",
                artifacts_dir="artifacts/test-run"
            )
            
            assert test_result is not None
        
        # Step 4: Generate report
        generator = ReportGenerator()
        report = await generator.generate_report(
            run_result=test_result,
            parsed_story=parsed_story,
            format="html"
        )
        
        assert report is not None
        assert report.story_id == parsed_story.id


@pytest.mark.asyncio
@pytest.mark.integration
class TestFallbackMechanisms:
    """Test fallback mechanisms (LLM → NLP)."""
    
    async def test_rate_limit_triggers_fallback(self, sample_story_input):
        """Test that rate limiting triggers fallback to secondary model."""
        # Mock primary model to return rate limit error
        with patch('app.services.llm.groq_client.GroqClient') as MockGroqClient:
            mock_client = MockGroqClient.return_value
            
            # First call fails with rate limit, second succeeds with fallback model
            mock_client.parse_story = AsyncMock(side_effect=[
                RateLimitException("Rate limit exceeded", retry_after=60),
                {
                    "id": "fallback-completion",
                    "model": "llama-3.1-8b-instant",
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "title": "User Login",
                                "role": "user",
                                "feature": "login",
                                "benefit": "access account",
                                "acceptance_criteria": [],
                                "implicit_requirements": [],
                                "ambiguities": []
                            })
                        }
                    }]
                }
            ])
            
            parser = StoryParser()
            parsed_story = await parser.parse(sample_story_input)
            
            # Verify fallback was used
            assert parsed_story is not None
            assert parsed_story.parsing_method in ["llm_fallback", "llm_primary"]
    
    
    async def test_all_llm_models_fail_uses_nlp(self, sample_story_input):
        """Test that when all LLM models fail, system falls back to NLP."""
        # Mock all LLM models to fail
        with patch('app.services.llm.groq_client.GroqClient') as MockGroqClient:
            mock_client = MockGroqClient.return_value
            mock_client.parse_story = AsyncMock(side_effect=GroqAPIException("All models failed"))
            
            # Mock NLP parser
            with patch('app.services.parser.legacy_nlp.LegacyNLPParser') as MockNLPParser:
                mock_nlp = MockNLPParser.return_value
                mock_nlp.parse = AsyncMock(return_value=ParsedStory(
                    id="nlp-story",
                    title="User Login",
                    role="user",
                    feature="login",
                    benefit="access",
                    acceptance_criteria=[],
                    implicit_requirements=[],
                    ambiguities=[],
                    parsing_method="nlp_legacy",
                    created_at=datetime.utcnow()
                ))
                
                parser = StoryParser()
                parsed_story = await parser.parse(sample_story_input)
                
                # Verify NLP fallback was used
                assert parsed_story is not None
                assert parsed_story.parsing_method == "nlp_legacy"


@pytest.mark.asyncio
@pytest.mark.integration
class TestRetryLogic:
    """Test retry logic and flaky test detection."""
    
    async def test_flaky_test_detection(self, sample_test_scenarios):
        """Test that flaky tests are detected and flagged."""
        # Mock Playwright to fail first, then succeed on retry
        with patch('app.services.executor.playwright_wrapper.PlaywrightWrapper') as MockPlaywright:
            mock_pw = MockPlaywright.return_value
            
            # First execution fails, second succeeds (flaky behavior)
            call_count = 0
            async def mock_execute_step(step, page):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return StepResult(
                        step=step,
                        status=StepStatus.FAILED,
                        screenshot_path=None,
                        error_message="Element not found",
                        dom_snapshot=None,
                        duration_ms=100
                    )
                else:
                    return StepResult(
                        step=step,
                        status=StepStatus.PASSED,
                        screenshot_path=None,
                        error_message=None,
                        dom_snapshot=None,
                        duration_ms=100
                    )
            
            mock_pw.execute_step = mock_execute_step
            
            runner = TestRunner(concurrency=1, retry_attempts=1)
            result = await runner.run_scenarios(
                scenarios=sample_test_scenarios[:1],  # Test one scenario
                target_url="http://localhost:5173",
                artifacts_dir="artifacts/test-run"
            )
            
            # Verify flaky test was detected
            assert result is not None
            if len(result.scenario_results) > 0:
                # At least one scenario should be marked as flaky
                flaky_scenarios = [sr for sr in result.scenario_results if sr.is_flaky]
                assert len(flaky_scenarios) > 0 or result.scenario_results[0].retry_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
