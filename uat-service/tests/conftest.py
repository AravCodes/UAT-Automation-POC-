"""
Pytest configuration and shared fixtures.

This module provides shared fixtures and configuration for all tests.
"""

import pytest
import os
import sys
from pathlib import Path

# Add app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Pytest Hooks
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Set test environment
    os.environ["ENVIRONMENT"] = "test"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Disable API docs in tests
    os.environ["ENABLE_API_DOCS"] = "false"
    
    # Set test-specific configuration
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"  # Use different DB for tests


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add marker for tests that require Groq API
        if "groq" in item.name.lower() or "llm" in item.name.lower():
            item.add_marker(pytest.mark.requires_groq)
        
        # Add marker for tests that require sample app
        if "sample_app" in item.name.lower() or "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.requires_sample_app)


# ============================================================================
# Session-scoped Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    import asyncio
    
    # Windows-specific event loop policy
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_artifacts_dir(tmp_path_factory):
    """Create a temporary directory for test artifacts."""
    artifacts_dir = tmp_path_factory.mktemp("test-artifacts")
    return str(artifacts_dir)


# ============================================================================
# Function-scoped Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    from unittest.mock import MagicMock
    
    config = MagicMock()
    config.environment = "test"
    config.groq_api_key = "test_api_key"
    config.model_primary = "llama-3.1-70b-versatile"
    config.model_fallback = "llama-3.1-8b-instant"
    config.llm_timeout = 30
    config.llm_max_retries = 3
    config.concurrency = 2
    config.test_timeout = 30000
    config.headless_mode = True
    config.sample_app_url = "http://localhost:5173"
    config.enable_webhooks = False
    config.enable_api_docs = False
    config.api_port = 8000
    
    return config


@pytest.fixture
def clean_artifacts_dir(tmp_path):
    """Provide a clean artifacts directory for each test."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    return str(artifacts_dir)


# ============================================================================
# Skip Conditions
# ============================================================================

def pytest_runtest_setup(item):
    """Setup hook to skip tests based on conditions."""
    # Skip tests that require Groq API if API key not set
    if item.get_closest_marker("requires_groq"):
        if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "your_api_key_here":
            pytest.skip("Groq API key not configured")
    
    # Skip tests that require sample app if not running
    if item.get_closest_marker("requires_sample_app"):
        sample_app_url = os.getenv("SAMPLE_APP_URL", "http://localhost:5173")
        try:
            import httpx
            response = httpx.get(sample_app_url, timeout=2.0)
            if response.status_code != 200:
                pytest.skip(f"Sample app not accessible at {sample_app_url}")
        except Exception:
            pytest.skip(f"Sample app not running at {sample_app_url}")
