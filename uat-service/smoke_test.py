#!/usr/bin/env python3
"""
Smoke test script for UAT automation service.

This script performs basic smoke tests to verify the application is working.
It tests core functionality without requiring extensive mocking or setup.
"""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_imports():
    """Test that all core modules can be imported."""
    print("Testing imports...")
    
    try:
        from app.models.story import StoryInput, ParsedStory
        from app.models.test_scenario import TestScenario, TestStep
        from app.models.test_result import TestRunResult
        from app.services.parser.story_parser import StoryParser
        from app.services.parser.scenario_generator import ScenarioGenerator
        from app.services.llm.groq_client import GroqClient
        from app.core.config import get_config
        from app.core.logging import get_logger
        
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


async def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        from app.core.config import get_config
        
        config = get_config()
        
        print(f"  Environment: {config.environment}")
        print(f"  API Port: {config.api_port}")
        print(f"  Groq API Key: {'Set' if config.groq_api_key and config.groq_api_key != 'your_api_key_here' else 'Not set'}")
        print(f"  Primary Model: {config.model_primary}")
        print(f"  Concurrency: {config.concurrency}")
        
        print("✓ Configuration loaded successfully")
        return True
    except Exception as e:
        print(f"✗ Configuration failed: {e}")
        return False


async def test_models():
    """Test that models can be instantiated."""
    print("\nTesting models...")
    
    try:
        from app.models.story import StoryInput, AcceptanceCriterion, Priority
        from app.models.test_scenario import TestScenario, TestStep, ActionType, ScenarioType
        from datetime import datetime
        
        # Test StoryInput
        story = StoryInput(
            text="As a user, I want to login",
            source="manual",  # Must be: manual, jira, or azure_devops
            metadata={}
        )
        print(f"  ✓ StoryInput created: {story.source}")
        
        # Test TestStep
        step = TestStep(
            action=ActionType.NAVIGATE,
            target="http://example.com",
            value=None,
            expected_outcome="Page loads"
        )
        print(f"  ✓ TestStep created: {step.action}")
        
        # Test TestScenario
        scenario = TestScenario(
            id="test-1",
            criterion_id="ac-1",
            type=ScenarioType.POSITIVE,
            priority=Priority.HIGH,
            given=["I am on the page"],
            when=["I click button"],
            then=["Something happens"],
            test_steps=[step]
        )
        print(f"  ✓ TestScenario created: {scenario.type}")
        
        print("✓ All models working")
        return True
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_story_parser_init():
    """Test that StoryParser can be initialized."""
    print("\nTesting StoryParser initialization...")
    
    try:
        from app.services.parser.story_parser import StoryParser
        from unittest.mock import AsyncMock
        
        # Test with mock client (no API call)
        mock_client = AsyncMock()
        parser = StoryParser(groq_client=mock_client)
        
        print("  ✓ StoryParser initialized with mock client")
        
        # Test without client (will create real one)
        parser2 = StoryParser()
        print("  ✓ StoryParser initialized without client")
        
        print("✓ StoryParser initialization successful")
        return True
    except Exception as e:
        print(f"✗ StoryParser initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_scenario_generator_init():
    """Test that ScenarioGenerator can be initialized."""
    print("\nTesting ScenarioGenerator initialization...")
    
    try:
        from app.services.parser.scenario_generator import ScenarioGenerator
        from unittest.mock import AsyncMock
        
        # Test with mock client
        mock_client = AsyncMock()
        generator = ScenarioGenerator(groq_client=mock_client)
        
        print("  ✓ ScenarioGenerator initialized with mock client")
        
        # Test without client
        generator2 = ScenarioGenerator()
        print("  ✓ ScenarioGenerator initialized without client")
        
        print("✓ ScenarioGenerator initialization successful")
        return True
    except Exception as e:
        print(f"✗ ScenarioGenerator initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_startup():
    """Test that FastAPI app can be created."""
    print("\nTesting API startup...")
    
    try:
        from app.main import app
        
        print(f"  App title: {app.title}")
        print(f"  App version: {app.version}")
        print(f"  Routes: {len(app.routes)}")
        
        print("✓ API app created successfully")
        return True
    except Exception as e:
        print(f"✗ API startup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all smoke tests."""
    print("="*80)
    print("UAT Automation Service - Smoke Tests")
    print("="*80)
    print()
    
    results = []
    
    # Run tests
    results.append(("Imports", await test_imports()))
    results.append(("Configuration", await test_config()))
    results.append(("Models", await test_models()))
    results.append(("StoryParser", await test_story_parser_init()))
    results.append(("ScenarioGenerator", await test_scenario_generator_init()))
    results.append(("API Startup", await test_api_startup()))
    
    # Summary
    print()
    print("="*80)
    print("Smoke Test Summary")
    print("="*80)
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print()
        print("✓ All smoke tests passed!")
        print()
        print("Next steps:")
        print("  1. Run integration tests: python -m pytest tests/integration/ -v")
        print("  2. Start sample app: cd ../sample-app && npm run dev")
        print("  3. Run e2e tests: python -m pytest tests/e2e/ -v")
        return 0
    else:
        print()
        print("✗ Some smoke tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
