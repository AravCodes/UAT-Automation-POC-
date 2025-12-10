"""
Groq API client with retry logic and fallback model support.

This module provides a robust client for interacting with Groq's LLM API,
implementing exponential backoff retry logic, primary/fallback model support,
and JSON schema validation for LLM responses.

"""

import asyncio
import json
import time
from typing import Any, Optional
from enum import Enum

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_config
from app.core.exceptions import (
    GroqAPIException,
    RateLimitException,
    LLMTimeoutException,
    LLMResponseValidationException,
    ModelNotAvailableException,
)
from app.core.logging import get_logger


logger = get_logger(__name__)


class ModelType(str, Enum):
    """Enum for model types."""
    PRIMARY = "primary"
    FALLBACK = "fallback"


class GroqResponse(BaseModel):
    """Pydantic model for Groq API response."""
    id: str
    object: str
    created: int
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int]


class GroqClient:
    """
    Groq API client with retry logic and fallback model support.
    
    This client implements:
    - Primary and fallback model support (llama-3.1-70b-versatile → llama-3.1-8b-instant)
    - Exponential backoff retry logic (1s, 2s, 4s delays)
    - JSON schema validation for LLM responses
    - Rate limit handling
    - Comprehensive error handling and logging
    
    Requirements: 1.1, 1.2, 1.4, 1.5, 1.6
    """
    
    GROQ_API_BASE_URL = "https://api.groq.com/openai/v1"
    RETRY_DELAYS = [1, 2, 4]  # Exponential backoff delays in seconds
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Groq API client.
        
        Args:
            api_key: Groq API key (if None, loads from config)
        """
        self.config = get_config()
        self.api_key = api_key or self.config.groq_api_key
        self.model_primary = self.config.model_primary
        self.model_fallback = self.config.model_fallback
        self.timeout = self.config.llm_timeout
        self.max_retries = self.config.llm_max_retries
        
        # HTTP client with timeout configuration
        self.client = httpx.AsyncClient(
            base_url=self.GROQ_API_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(self.timeout),
        )
        
        logger.info(
            "groq_client_initialized",
            extra={
                "model_primary": self.model_primary,
                "model_fallback": self.model_fallback,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
            }
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    
    async def _make_request(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Make a request to the Groq API.
        
        Args:
            model: Model name to use
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response
            response_format: Response format specification (e.g., {"type": "json_object"})
        
        Returns:
            dict: Raw API response
            
        Raises:
            GroqAPIException: If API request fails
            LLMTimeoutException: If request times out
            RateLimitException: If rate limit is exceeded
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        if response_format:
            payload["response_format"] = response_format
        
        try:
            logger.debug(
                "groq_api_request",
                extra={
                    "model": model,
                    "messages_count": len(messages),
                    "temperature": temperature,
                }
            )
            
            response = await self.client.post(
                "/chat/completions",
                json=payload,
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("retry-after", 60))
                logger.warning(
                    "groq_rate_limit_exceeded",
                    extra={
                        "model": model,
                        "retry_after": retry_after,
                    }
                )
                raise RateLimitException(
                    f"Rate limit exceeded for model {model}",
                    retry_after=retry_after,
                    details={"model": model}
                )
            
            # Handle other HTTP errors
            if response.status_code != 200:
                error_body = response.text
                logger.error(
                    "groq_api_error",
                    extra={
                        "model": model,
                        "status_code": response.status_code,
                        "error_body": error_body,
                    }
                )
                raise GroqAPIException(
                    f"Groq API request failed with status {response.status_code}",
                    status_code=response.status_code,
                    response_body=error_body,
                )
            
            response_data = response.json()
            
            logger.debug(
                "groq_api_response",
                extra={
                    "model": model,
                    "usage": response_data.get("usage", {}),
                }
            )
            
            return response_data
            
        except httpx.TimeoutException as e:
            logger.error(
                "groq_api_timeout",
                extra={
                    "model": model,
                    "timeout": self.timeout,
                }
            )
            raise LLMTimeoutException(
                f"Groq API request timed out after {self.timeout}s",
                timeout_seconds=self.timeout,
                original_exception=e,
            )
        
        except httpx.HTTPError as e:
            logger.error(
                "groq_api_http_error",
                extra={
                    "model": model,
                    "error": str(e),
                }
            )
            raise GroqAPIException(
                f"HTTP error during Groq API request: {str(e)}",
                original_exception=e,
            )

    
    async def _make_request_with_retry(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Make a request with exponential backoff retry logic.
        
        Implements retry logic with delays: 1s, 2s, 4s
        
        Args:
            model: Model name to use
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            response_format: Response format specification
        
        Returns:
            dict: API response
            
        Raises:
            GroqAPIException: If all retries fail
            RateLimitException: If rate limit is exceeded
        
        Requirements: 1.6
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await self._make_request(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
            
            except RateLimitException:
                # Don't retry on rate limit, let it bubble up for queue handling
                raise
            
            except (GroqAPIException, LLMTimeoutException) as e:
                last_exception = e
                
                # Don't retry on last attempt
                if attempt == self.max_retries - 1:
                    break
                
                # Calculate delay with exponential backoff
                delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                
                logger.warning(
                    "groq_api_retry",
                    extra={
                        "model": model,
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries,
                        "delay_seconds": delay,
                        "error": str(e),
                    }
                )
                
                await asyncio.sleep(delay)
        
        # All retries failed
        logger.error(
            "groq_api_all_retries_failed",
            extra={
                "model": model,
                "max_retries": self.max_retries,
                "last_error": str(last_exception),
            }
        )
        
        raise last_exception

    
    async def _extract_content(self, response: dict[str, Any]) -> str:
        """
        Extract content from Groq API response.
        
        Args:
            response: Raw API response
        
        Returns:
            str: Extracted content
            
        Raises:
            GroqAPIException: If response format is invalid
        """
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error(
                "groq_response_parse_error",
                extra={
                    "response": response,
                    "error": str(e),
                }
            )
            raise GroqAPIException(
                "Failed to extract content from Groq API response",
                response_body=json.dumps(response),
                original_exception=e,
            )
    
    async def _validate_json_response(
        self,
        content: str,
        expected_schema: Optional[type[BaseModel]] = None,
    ) -> dict[str, Any]:
        """
        Validate and parse JSON response from LLM.
        
        Args:
            content: Raw content string from LLM
            expected_schema: Optional Pydantic model for validation
        
        Returns:
            dict: Parsed and validated JSON
            
        Raises:
            LLMResponseValidationException: If JSON is invalid or doesn't match schema
        
        Requirements: 1.4, 1.5
        """
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(
                "llm_json_parse_error",
                extra={
                    "content": content[:500],  # Log first 500 chars
                    "error": str(e),
                }
            )
            raise LLMResponseValidationException(
                "LLM response is not valid JSON",
                response=content,
                original_exception=e,
            )
        
        # Validate against schema if provided
        if expected_schema:
            try:
                validated = expected_schema(**data)
                return validated.model_dump()
            except ValidationError as e:
                logger.error(
                    "llm_schema_validation_error",
                    extra={
                        "data": data,
                        "schema": expected_schema.__name__,
                        "errors": e.errors(),
                    }
                )
                raise LLMResponseValidationException(
                    f"LLM response doesn't match expected schema: {expected_schema.__name__}",
                    response=content,
                    validation_errors=e.errors(),
                    original_exception=e,
                )
        
        return data

    
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, str]] = None,
        use_fallback: bool = False,
        expected_schema: Optional[type[BaseModel]] = None,
    ) -> dict[str, Any]:
        """
        Complete a chat conversation with automatic fallback support.
        
        This is the main entry point for LLM interactions. It automatically
        handles primary/fallback model switching and JSON validation.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response
            response_format: Response format (e.g., {"type": "json_object"})
            use_fallback: If True, use fallback model directly
            expected_schema: Optional Pydantic model for response validation
        
        Returns:
            dict: Parsed and validated response
            
        Raises:
            GroqAPIException: If request fails
            LLMResponseValidationException: If response validation fails
            ModelNotAvailableException: If both models fail
        
        Requirements: 1.1, 1.2, 1.4, 1.5
        """
        model = self.model_fallback if use_fallback else self.model_primary
        model_type = ModelType.FALLBACK if use_fallback else ModelType.PRIMARY
        
        start_time = time.time()
        
        try:
            logger.info(
                "llm_request_started",
                extra={
                    "model": model,
                    "model_type": model_type.value,
                    "messages_count": len(messages),
                }
            )
            
            # Make request with retry logic
            response = await self._make_request_with_retry(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            
            # Extract content
            content = await self._extract_content(response)
            
            # Parse and validate JSON if response format is JSON
            if response_format and response_format.get("type") == "json_object":
                result = await self._validate_json_response(content, expected_schema)
            else:
                result = {"content": content}
            
            duration = time.time() - start_time
            
            logger.info(
                "llm_request_completed",
                extra={
                    "model": model,
                    "model_type": model_type.value,
                    "duration_seconds": round(duration, 2),
                    "usage": response.get("usage", {}),
                }
            )
            
            return result
            
        except (GroqAPIException, LLMTimeoutException, LLMResponseValidationException) as e:
            duration = time.time() - start_time
            
            logger.error(
                "llm_request_failed",
                extra={
                    "model": model,
                    "model_type": model_type.value,
                    "duration_seconds": round(duration, 2),
                    "error": str(e),
                }
            )
            
            # If primary model failed and we haven't tried fallback yet, try fallback
            if model_type == ModelType.PRIMARY and not use_fallback:
                logger.warning(
                    "llm_falling_back_to_secondary",
                    extra={
                        "primary_model": self.model_primary,
                        "fallback_model": self.model_fallback,
                        "reason": str(e),
                    }
                )
                
                try:
                    return await self.complete(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                        use_fallback=True,
                        expected_schema=expected_schema,
                    )
                except Exception as fallback_error:
                    logger.error(
                        "llm_fallback_also_failed",
                        extra={
                            "fallback_model": self.model_fallback,
                            "error": str(fallback_error),
                        }
                    )
                    raise ModelNotAvailableException(
                        f"Both primary ({self.model_primary}) and fallback ({self.model_fallback}) models failed",
                        details={
                            "primary_error": str(e),
                            "fallback_error": str(fallback_error),
                        }
                    )
            
            # Re-raise if we're already using fallback or it's a rate limit error
            raise

    
    async def parse_story(
        self,
        story_text: str,
        prompt_template: str,
        expected_schema: Optional[type[BaseModel]] = None,
    ) -> dict[str, Any]:
        """
        Parse a user story using LLM with structured output.
        
        This is a convenience method for story parsing that ensures
        JSON output and schema validation.
        
        Args:
            story_text: The user story text to parse
            prompt_template: The prompt template with {story_text} placeholder
            expected_schema: Pydantic model for response validation
        
        Returns:
            dict: Parsed story data
            
        Raises:
            GroqAPIException: If request fails
            LLMResponseValidationException: If response validation fails
        
        Requirements: 1.4, 1.5
        """
        prompt = prompt_template.format(story_text=story_text)
        
        messages = [
            {
                "role": "system",
                "content": "You are a QA expert analyzing user stories for test automation. Always respond with valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        return await self.complete(
            messages=messages,
            temperature=0.3,  # Lower temperature for more consistent parsing
            response_format={"type": "json_object"},
            expected_schema=expected_schema,
        )
    
    async def generate_scenarios(
        self,
        acceptance_criteria: list[str],
        prompt_template: str,
        expected_schema: Optional[type[BaseModel]] = None,
    ) -> dict[str, Any]:
        """
        Generate test scenarios from acceptance criteria using LLM.
        
        This is a convenience method for scenario generation that ensures
        JSON output and schema validation.
        
        Args:
            acceptance_criteria: List of acceptance criteria
            prompt_template: The prompt template with {criteria} placeholder
            expected_schema: Pydantic model for response validation
        
        Returns:
            dict: Generated scenarios data
            
        Raises:
            GroqAPIException: If request fails
            LLMResponseValidationException: If response validation fails
        
        Requirements: 1.4, 1.5
        """
        criteria_text = "\n".join([f"{i+1}. {c}" for i, c in enumerate(acceptance_criteria)])
        prompt = prompt_template.format(criteria=criteria_text)
        
        messages = [
            {
                "role": "system",
                "content": "You are a QA expert generating comprehensive test scenarios. Always respond with valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        return await self.complete(
            messages=messages,
            temperature=0.5,  # Moderate temperature for creative scenario generation
            response_format={"type": "json_object"},
            expected_schema=expected_schema,
        )
    
    async def suggest_selectors(
        self,
        element_description: str,
        page_context: str,
        prompt_template: str,
    ) -> list[str]:
        """
        Suggest alternative selectors when element is not found.
        
        This method uses LLM to analyze page context and suggest
        alternative ways to locate an element.
        
        Args:
            element_description: Description of the element to find
            page_context: HTML or DOM context of the page
            prompt_template: The prompt template with placeholders
        
        Returns:
            list[str]: List of suggested selectors
            
        Raises:
            GroqAPIException: If request fails
        
        Requirements: 3.5
        """
        prompt = prompt_template.format(
            element_description=element_description,
            page_context=page_context[:5000]  # Limit context size
        )
        
        messages = [
            {
                "role": "system",
                "content": "You are a test automation expert helping to locate UI elements. Always respond with valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        result = await self.complete(
            messages=messages,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        
        # Extract selectors from response
        return result.get("selectors", [])
