"""
LLM service layer for UAT automation.

This package provides LLM integration with Groq API, including:
- Groq API client with retry logic and fallback support
- Token bucket rate limiting
- Structured prompt templates
- Fallback handler orchestration

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
"""

from app.services.llm.groq_client import GroqClient, ModelType
from app.services.llm.token_manager import (
    TokenManager,
    TokenBucket,
    RateLimitConfig,
    RequestMetrics,
    get_token_manager,
    create_token_manager,
)
from app.services.llm.prompt_templates import (
    STORY_PARSING_SCHEMA,
    STORY_PARSING_PROMPT,
    SCENARIO_GENERATION_SCHEMA,
    SCENARIO_GENERATION_PROMPT,
    SELECTOR_SUGGESTION_SCHEMA,
    SELECTOR_SUGGESTION_PROMPT,
    get_story_parsing_prompt,
    get_scenario_generation_prompt,
    get_selector_suggestion_prompt,
)
from app.services.llm.fallback_handler import (
    FallbackHandler,
    FallbackLevel,
    FallbackResult,
    DegradationWarning,
    DegradationSeverity,
    get_fallback_handler,
    create_fallback_handler,
)

__all__ = [
    # Groq Client
    "GroqClient",
    "ModelType",
    # Token Manager
    "TokenManager",
    "TokenBucket",
    "RateLimitConfig",
    "RequestMetrics",
    "get_token_manager",
    "create_token_manager",
    # Prompt Templates
    "STORY_PARSING_SCHEMA",
    "STORY_PARSING_PROMPT",
    "SCENARIO_GENERATION_SCHEMA",
    "SCENARIO_GENERATION_PROMPT",
    "SELECTOR_SUGGESTION_SCHEMA",
    "SELECTOR_SUGGESTION_PROMPT",
    "get_story_parsing_prompt",
    "get_scenario_generation_prompt",
    "get_selector_suggestion_prompt",
    # Fallback Handler
    "FallbackHandler",
    "FallbackLevel",
    "FallbackResult",
    "DegradationWarning",
    "DegradationSeverity",
    "get_fallback_handler",
    "create_fallback_handler",
]
