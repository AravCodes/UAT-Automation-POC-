"""
Fallback handler for LLM service orchestration.

This module manages the fallback chain for story parsing and scenario generation:
LLM (primary) → LLM (fallback) → NLP (legacy) → Manual mode

It provides graceful degradation with warnings about reduced functionality
at each fallback level.
"""

from typing import Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from app.core.logging import get_logger
from app.core.exceptions import (
    GroqAPIException,
    RateLimitException,
    LLMTimeoutException,
    LLMResponseValidationException,
    ModelNotAvailableException,
)


logger = get_logger(__name__)


class FallbackLevel(str, Enum):
    """Levels in the fallback chain."""
    LLM_PRIMARY = "llm_primary"
    LLM_FALLBACK = "llm_fallback"
    NLP_LEGACY = "nlp_legacy"
    MANUAL = "manual"


class DegradationSeverity(str, Enum):
    """Severity levels for degraded functionality warnings."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DegradationWarning:
    """Warning about degraded functionality at a fallback level."""
    
    level: FallbackLevel
    severity: DegradationSeverity
    message: str
    limitations: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert warning to dictionary."""
        return {
            "level": self.level.value,
            "severity": self.severity.value,
            "message": self.message,
            "limitations": self.limitations,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class FallbackResult:
    """Result from fallback handler execution."""
    
    success: bool
    level_used: FallbackLevel
    result: Any
    warnings: list[DegradationWarning] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "level_used": self.level_used.value,
            "result": self.result,
            "warnings": [w.to_dict() for w in self.warnings],
            "attempts": self.attempts,
            "total_duration_seconds": self.total_duration_seconds,
        }


class FallbackHandler:
    """
    Orchestrates fallback chain for LLM operations.
    
    This handler manages the fallback sequence:
    1. LLM Primary (llama-3.1-70b-versatile) - Full functionality
    2. LLM Fallback (llama-3.1-8b-instant) - Slightly reduced quality
    3. NLP Legacy (spaCy-based) - Limited functionality, rule-based
    4. Manual Mode - Returns error, requires human intervention
    
    At each level, appropriate warnings are generated about degraded functionality.
    
    Requirements: 1.3
    """
    
    def __init__(
        self,
        enable_llm_primary: bool = True,
        enable_llm_fallback: bool = True,
        enable_nlp_legacy: bool = True,
    ):
        """
        Initialize the fallback handler.
        
        Args:
            enable_llm_primary: Enable primary LLM model
            enable_llm_fallback: Enable fallback LLM model
            enable_nlp_legacy: Enable legacy NLP parser
        """
        self.enable_llm_primary = enable_llm_primary
        self.enable_llm_fallback = enable_llm_fallback
        self.enable_nlp_legacy = enable_nlp_legacy
        
        logger.info(
            "fallback_handler_initialized",
            extra={
                "llm_primary_enabled": enable_llm_primary,
                "llm_fallback_enabled": enable_llm_fallback,
                "nlp_legacy_enabled": enable_nlp_legacy,
            }
        )
    
    def _create_degradation_warning(
        self,
        level: FallbackLevel,
        reason: str,
    ) -> DegradationWarning:
        """
        Create a degradation warning for a fallback level.
        
        Args:
            level: The fallback level being used
            reason: Reason for falling back to this level
        
        Returns:
            DegradationWarning: Warning with appropriate severity and limitations
        """
        warnings_config = {
            FallbackLevel.LLM_PRIMARY: {
                "severity": DegradationSeverity.INFO,
                "message": "Using primary LLM model (full functionality)",
                "limitations": [],
            },
            FallbackLevel.LLM_FALLBACK: {
                "severity": DegradationSeverity.WARNING,
                "message": f"Primary LLM unavailable ({reason}), using fallback model",
                "limitations": [
                    "Slightly reduced parsing accuracy",
                    "May miss some implicit requirements",
                    "Edge case detection may be less comprehensive",
                ],
            },
            FallbackLevel.NLP_LEGACY: {
                "severity": DegradationSeverity.ERROR,
                "message": f"Both LLM models unavailable ({reason}), using legacy NLP parser",
                "limitations": [
                    "Rule-based parsing only (no AI reasoning)",
                    "Cannot detect implicit requirements",
                    "Cannot identify ambiguities",
                    "Limited scenario generation (templates only)",
                    "No context-aware analysis",
                    "Reduced accuracy for complex stories",
                ],
            },
            FallbackLevel.MANUAL: {
                "severity": DegradationSeverity.CRITICAL,
                "message": f"All automated parsing methods failed ({reason})",
                "limitations": [
                    "Manual intervention required",
                    "Cannot proceed with automated testing",
                    "Human must parse story and create scenarios",
                ],
            },
        }
        
        config = warnings_config[level]
        return DegradationWarning(
            level=level,
            severity=config["severity"],
            message=config["message"],
            limitations=config["limitations"],
        )
    
    async def execute_with_fallback(
        self,
        operation_name: str,
        llm_primary_fn: Optional[Callable] = None,
        llm_fallback_fn: Optional[Callable] = None,
        nlp_legacy_fn: Optional[Callable] = None,
        **kwargs,
    ) -> FallbackResult:
        """
        Execute an operation with automatic fallback handling.
        
        This method tries each level in sequence until one succeeds or all fail.
        It tracks attempts, warnings, and timing information.
        
        Args:
            operation_name: Name of the operation (for logging)
            llm_primary_fn: Function to call for primary LLM
            llm_fallback_fn: Function to call for fallback LLM
            nlp_legacy_fn: Function to call for legacy NLP
            **kwargs: Arguments to pass to the functions
        
        Returns:
            FallbackResult: Result with success status, data, and warnings
        
        Requirements: 1.3
        """
        import time
        
        start_time = time.time()
        attempts = []
        warnings = []
        
        logger.info(
            "fallback_execution_started",
            extra={
                "operation": operation_name,
                "kwargs_keys": list(kwargs.keys()),
            }
        )
        
        # Level 1: Try primary LLM
        if self.enable_llm_primary and llm_primary_fn:
            try:
                logger.debug(
                    "attempting_llm_primary",
                    extra={"operation": operation_name}
                )
                
                attempt_start = time.time()
                result = await llm_primary_fn(**kwargs)
                attempt_duration = time.time() - attempt_start
                
                attempts.append({
                    "level": FallbackLevel.LLM_PRIMARY.value,
                    "success": True,
                    "duration_seconds": round(attempt_duration, 2),
                })
                
                warning = self._create_degradation_warning(
                    FallbackLevel.LLM_PRIMARY,
                    "N/A"
                )
                warnings.append(warning)
                
                total_duration = time.time() - start_time
                
                logger.info(
                    "fallback_execution_succeeded",
                    extra={
                        "operation": operation_name,
                        "level": FallbackLevel.LLM_PRIMARY.value,
                        "duration_seconds": round(total_duration, 2),
                    }
                )
                
                return FallbackResult(
                    success=True,
                    level_used=FallbackLevel.LLM_PRIMARY,
                    result=result,
                    warnings=warnings,
                    attempts=attempts,
                    total_duration_seconds=round(total_duration, 2),
                )
                
            except RateLimitException as e:
                attempt_duration = time.time() - start_time
                attempts.append({
                    "level": FallbackLevel.LLM_PRIMARY.value,
                    "success": False,
                    "error": "Rate limit exceeded",
                    "duration_seconds": round(attempt_duration, 2),
                })
                
                logger.warning(
                    "llm_primary_rate_limited",
                    extra={
                        "operation": operation_name,
                        "error": str(e),
                    }
                )
                
                # For rate limits, we should wait and not immediately fallback
                # But for now, we'll continue to fallback
                
            except (GroqAPIException, LLMTimeoutException, LLMResponseValidationException, ModelNotAvailableException) as e:
                attempt_duration = time.time() - start_time
                attempts.append({
                    "level": FallbackLevel.LLM_PRIMARY.value,
                    "success": False,
                    "error": str(e),
                    "duration_seconds": round(attempt_duration, 2),
                })
                
                logger.warning(
                    "llm_primary_failed",
                    extra={
                        "operation": operation_name,
                        "error": str(e),
                    }
                )
        
        # Level 2: Try fallback LLM
        if self.enable_llm_fallback and llm_fallback_fn:
            try:
                logger.debug(
                    "attempting_llm_fallback",
                    extra={"operation": operation_name}
                )
                
                attempt_start = time.time()
                result = await llm_fallback_fn(**kwargs)
                attempt_duration = time.time() - attempt_start
                
                attempts.append({
                    "level": FallbackLevel.LLM_FALLBACK.value,
                    "success": True,
                    "duration_seconds": round(attempt_duration, 2),
                })
                
                # Get reason from last attempt
                last_error = attempts[-2].get("error", "Unknown error") if len(attempts) > 1 else "Primary unavailable"
                
                warning = self._create_degradation_warning(
                    FallbackLevel.LLM_FALLBACK,
                    last_error
                )
                warnings.append(warning)
                
                total_duration = time.time() - start_time
                
                logger.info(
                    "fallback_execution_succeeded",
                    extra={
                        "operation": operation_name,
                        "level": FallbackLevel.LLM_FALLBACK.value,
                        "duration_seconds": round(total_duration, 2),
                    }
                )
                
                return FallbackResult(
                    success=True,
                    level_used=FallbackLevel.LLM_FALLBACK,
                    result=result,
                    warnings=warnings,
                    attempts=attempts,
                    total_duration_seconds=round(total_duration, 2),
                )
                
            except (GroqAPIException, LLMTimeoutException, LLMResponseValidationException, ModelNotAvailableException) as e:
                attempt_duration = time.time() - start_time
                attempts.append({
                    "level": FallbackLevel.LLM_FALLBACK.value,
                    "success": False,
                    "error": str(e),
                    "duration_seconds": round(attempt_duration, 2),
                })
                
                logger.warning(
                    "llm_fallback_failed",
                    extra={
                        "operation": operation_name,
                        "error": str(e),
                    }
                )
        
        # Level 3: Try legacy NLP
        if self.enable_nlp_legacy and nlp_legacy_fn:
            try:
                logger.debug(
                    "attempting_nlp_legacy",
                    extra={"operation": operation_name}
                )
                
                attempt_start = time.time()
                result = await nlp_legacy_fn(**kwargs)
                attempt_duration = time.time() - attempt_start
                
                attempts.append({
                    "level": FallbackLevel.NLP_LEGACY.value,
                    "success": True,
                    "duration_seconds": round(attempt_duration, 2),
                })
                
                # Get reason from last attempt
                last_error = attempts[-2].get("error", "Unknown error") if len(attempts) > 1 else "LLM unavailable"
                
                warning = self._create_degradation_warning(
                    FallbackLevel.NLP_LEGACY,
                    last_error
                )
                warnings.append(warning)
                
                total_duration = time.time() - start_time
                
                logger.warning(
                    "fallback_execution_degraded",
                    extra={
                        "operation": operation_name,
                        "level": FallbackLevel.NLP_LEGACY.value,
                        "duration_seconds": round(total_duration, 2),
                        "limitations": warning.limitations,
                    }
                )
                
                return FallbackResult(
                    success=True,
                    level_used=FallbackLevel.NLP_LEGACY,
                    result=result,
                    warnings=warnings,
                    attempts=attempts,
                    total_duration_seconds=round(total_duration, 2),
                )
                
            except Exception as e:
                attempt_duration = time.time() - start_time
                attempts.append({
                    "level": FallbackLevel.NLP_LEGACY.value,
                    "success": False,
                    "error": str(e),
                    "duration_seconds": round(attempt_duration, 2),
                })
                
                logger.error(
                    "nlp_legacy_failed",
                    extra={
                        "operation": operation_name,
                        "error": str(e),
                    }
                )
        
        # Level 4: All methods failed - manual intervention required
        total_duration = time.time() - start_time
        
        last_error = attempts[-1].get("error", "Unknown error") if attempts else "No methods available"
        
        warning = self._create_degradation_warning(
            FallbackLevel.MANUAL,
            last_error
        )
        warnings.append(warning)
        
        logger.error(
            "fallback_execution_failed",
            extra={
                "operation": operation_name,
                "attempts_count": len(attempts),
                "duration_seconds": round(total_duration, 2),
            }
        )
        
        return FallbackResult(
            success=False,
            level_used=FallbackLevel.MANUAL,
            result=None,
            warnings=warnings,
            attempts=attempts,
            total_duration_seconds=round(total_duration, 2),
        )
    
    def get_fallback_status(self) -> dict:
        """
        Get current status of fallback levels.
        
        Returns:
            dict: Status of each fallback level
        """
        return {
            "llm_primary": {
                "enabled": self.enable_llm_primary,
                "level": FallbackLevel.LLM_PRIMARY.value,
            },
            "llm_fallback": {
                "enabled": self.enable_llm_fallback,
                "level": FallbackLevel.LLM_FALLBACK.value,
            },
            "nlp_legacy": {
                "enabled": self.enable_nlp_legacy,
                "level": FallbackLevel.NLP_LEGACY.value,
            },
        }


# Global fallback handler instance
_fallback_handler: Optional[FallbackHandler] = None


def get_fallback_handler() -> FallbackHandler:
    """
    Get the global fallback handler instance.
    
    This function implements lazy initialization and caching of the handler.
    
    Returns:
        FallbackHandler: The global fallback handler instance
    """
    global _fallback_handler
    
    if _fallback_handler is None:
        _fallback_handler = FallbackHandler()
    
    return _fallback_handler


def create_fallback_handler(
    enable_llm_primary: bool = True,
    enable_llm_fallback: bool = True,
    enable_nlp_legacy: bool = True,
) -> FallbackHandler:
    """
    Create a new fallback handler instance.
    
    This is useful for testing or when you need custom configurations.
    
    Args:
        enable_llm_primary: Enable primary LLM model
        enable_llm_fallback: Enable fallback LLM model
        enable_nlp_legacy: Enable legacy NLP parser
    
    Returns:
        FallbackHandler: A new fallback handler instance
    """
    return FallbackHandler(
        enable_llm_primary=enable_llm_primary,
        enable_llm_fallback=enable_llm_fallback,
        enable_nlp_legacy=enable_nlp_legacy,
    )


__all__ = [
    "FallbackLevel",
    "DegradationSeverity",
    "DegradationWarning",
    "FallbackResult",
    "FallbackHandler",
    "get_fallback_handler",
    "create_fallback_handler",
]
