"""
Tests for Groq API client.

This module contains tests for the GroqClient implementation,
including retry logic, fallback support, and JSON validation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.llm.groq_client import GroqClient, ModelType
from app.core.exceptions import (
    GroqAPIException,
    RateLimitException,
    LLMTimeoutException,
    LLMResponseValidationException,
)


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = MagicMock()
    config.groq_api_key = "test_api_key"
    config.model_primary = "llama-3.1-70b-versatile"
    config.model_fallback = "llama-3.1-8b-instant"
    config.llm_timeout = 30
    config.llm_max_retries = 3
    return config


@pytest.fixture
def groq_client(mock_config):
    """Create a GroqClient instance for testing."""
    with patch("app.services.llm.groq_client.get_config", return_value=mock_config):
        client = GroqClient(api_key="test_api_key")
        yield client


@pytest.mark.asyncio
async def test_groq_client_initialization(groq_client):
    """Test that GroqClient initializes correctly."""
    assert groq_client.api_key == "test_api_key"
    assert groq_client.model_primary == "llama-3.1-70b-versatile"
    assert groq_client.model_fallback == "llama-3.1-8b-instant"
    assert groq_client.timeout == 30
    assert groq_client.max_retries == 3


@pytest.mark.asyncio
async def test_successful_request(groq_client):
    """Test successful API request."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test_id",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "llama-3.1-70b-versatile",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"result": "success"}'
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    }
    
    with patch.object(groq_client.client, "post", return_value=mock_response):
        result = await groq_client._make_request(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": "test"}]
        )
        
        assert result["id"] == "test_id"
        assert result["model"] == "llama-3.1-70b-versatile"


@pytest.mark.asyncio
async def test_rate_limit_exception(groq_client):
    """Test that rate limit errors are handled correctly."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"retry-after": "60"}
    
    with patch.object(groq_client.client, "post", return_value=mock_response):
        with pytest.raises(RateLimitException) as exc_info:
            await groq_client._make_request(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": "test"}]
            )
        
        assert exc_info.value.retry_after == 60


@pytest.mark.asyncio
async def test_timeout_exception(groq_client):
    """Test that timeout errors are handled correctly."""
    with patch.object(groq_client.client, "post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(LLMTimeoutException):
            await groq_client._make_request(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": "test"}]
            )


@pytest.mark.asyncio
async def test_retry_logic(groq_client):
    """Test exponential backoff retry logic."""
    # First two calls fail, third succeeds
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    mock_response_fail.text = "Internal Server Error"
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {
        "id": "test_id",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "llama-3.1-70b-versatile",
        "choices": [{"message": {"role": "assistant", "content": "success"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    }
    
    with patch.object(groq_client.client, "post", side_effect=[
        mock_response_fail,
        mock_response_fail,
        mock_response_success
    ]):
        with patch("asyncio.sleep"):  # Mock sleep to speed up test
            result = await groq_client._make_request_with_retry(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": "test"}]
            )
            
            assert result["id"] == "test_id"


@pytest.mark.asyncio
async def test_json_validation(groq_client):
    """Test JSON response validation."""
    # Valid JSON
    valid_json = '{"key": "value"}'
    result = await groq_client._validate_json_response(valid_json)
    assert result == {"key": "value"}
    
    # Invalid JSON
    invalid_json = '{invalid json}'
    with pytest.raises(LLMResponseValidationException):
        await groq_client._validate_json_response(invalid_json)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
