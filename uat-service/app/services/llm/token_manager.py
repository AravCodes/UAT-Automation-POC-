"""
Token bucket rate limiting for LLM API requests.

This module implements a token bucket algorithm to manage rate limits for
Groq API requests. It queues requests when approaching rate limits and
ensures smooth request flow without hitting API rate limits.

"""

import asyncio
import time
from typing import Optional
from dataclasses import dataclass, field
from collections import deque

from app.core.config import get_config
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    
    requests_per_minute: int = 60
    """Maximum requests per minute"""
    
    burst_size: int = 10
    """Maximum burst size (tokens in bucket)"""
    
    refill_rate: float = field(init=False)
    """Token refill rate per second"""
    
    def __post_init__(self):
        """Calculate refill rate based on requests per minute."""
        self.refill_rate = self.requests_per_minute / 60.0


@dataclass
class RequestMetrics:
    """Metrics for tracking request patterns."""
    
    total_requests: int = 0
    """Total number of requests made"""
    
    queued_requests: int = 0
    """Number of requests that were queued"""
    
    total_wait_time: float = 0.0
    """Total time spent waiting in queue (seconds)"""
    
    max_wait_time: float = 0.0
    """Maximum wait time for a single request (seconds)"""
    
    rate_limit_hits: int = 0
    """Number of times rate limit was hit"""
    
    def record_request(self, wait_time: float, was_queued: bool):
        """Record metrics for a request."""
        self.total_requests += 1
        if was_queued:
            self.queued_requests += 1
            self.total_wait_time += wait_time
            self.max_wait_time = max(self.max_wait_time, wait_time)
    
    def record_rate_limit_hit(self):
        """Record a rate limit hit."""
        self.rate_limit_hits += 1
    
    def get_average_wait_time(self) -> float:
        """Calculate average wait time for queued requests."""
        if self.queued_requests == 0:
            return 0.0
        return self.total_wait_time / self.queued_requests


class TokenBucket:
    """
    Token bucket implementation for rate limiting.
    
    The token bucket algorithm allows for burst traffic while maintaining
    an average rate limit. Tokens are added to the bucket at a constant rate,
    and each request consumes one token. If no tokens are available, the
    request must wait.
    
    This implementation is thread-safe and async-compatible.
    """
    
    def __init__(self, config: RateLimitConfig):
        """
        Initialize the token bucket.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.tokens = float(config.burst_size)
        self.max_tokens = float(config.burst_size)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        
        logger.info(
            "token_bucket_initialized",
            extra={
                "requests_per_minute": config.requests_per_minute,
                "burst_size": config.burst_size,
                "refill_rate": config.refill_rate,
            }
        )
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time and refill rate
        tokens_to_add = elapsed * self.config.refill_rate
        self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
        self.last_refill = now
        
        logger.debug(
            "token_bucket_refilled",
            extra={
                "elapsed_seconds": round(elapsed, 2),
                "tokens_added": round(tokens_to_add, 2),
                "current_tokens": round(self.tokens, 2),
            }
        )
    
    async def acquire(self, tokens: float = 1.0) -> float:
        """
        Acquire tokens from the bucket, waiting if necessary.
        
        This method will wait until enough tokens are available.
        It returns the time spent waiting.
        
        Args:
            tokens: Number of tokens to acquire (default: 1.0)
        
        Returns:
            float: Time spent waiting in seconds
        """
        start_time = time.monotonic()
        
        async with self._lock:
            self._refill()
            
            # If we have enough tokens, consume them immediately
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    "tokens_acquired_immediately",
                    extra={
                        "tokens_requested": tokens,
                        "tokens_remaining": round(self.tokens, 2),
                    }
                )
                return 0.0
            
            # Calculate wait time needed
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.config.refill_rate
            
            logger.debug(
                "tokens_insufficient_waiting",
                extra={
                    "tokens_requested": tokens,
                    "tokens_available": round(self.tokens, 2),
                    "tokens_needed": round(tokens_needed, 2),
                    "wait_time_seconds": round(wait_time, 2),
                }
            )
        
        # Wait outside the lock to allow other operations
        await asyncio.sleep(wait_time)
        
        # Acquire the lock again and consume tokens
        async with self._lock:
            self._refill()
            self.tokens -= tokens
            
            actual_wait_time = time.monotonic() - start_time
            
            logger.debug(
                "tokens_acquired_after_wait",
                extra={
                    "tokens_requested": tokens,
                    "tokens_remaining": round(self.tokens, 2),
                    "wait_time_seconds": round(actual_wait_time, 2),
                }
            )
            
            return actual_wait_time
    
    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        Try to acquire tokens without waiting.
        
        Args:
            tokens: Number of tokens to acquire (default: 1.0)
        
        Returns:
            bool: True if tokens were acquired, False otherwise
        """
        async with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    "tokens_acquired_non_blocking",
                    extra={
                        "tokens_requested": tokens,
                        "tokens_remaining": round(self.tokens, 2),
                    }
                )
                return True
            
            logger.debug(
                "tokens_unavailable_non_blocking",
                extra={
                    "tokens_requested": tokens,
                    "tokens_available": round(self.tokens, 2),
                }
            )
            return False
    
    async def get_available_tokens(self) -> float:
        """
        Get the current number of available tokens.
        
        Returns:
            float: Number of available tokens
        """
        async with self._lock:
            self._refill()
            return self.tokens
    
    async def get_wait_time(self, tokens: float = 1.0) -> float:
        """
        Calculate wait time needed to acquire tokens.
        
        Args:
            tokens: Number of tokens needed
        
        Returns:
            float: Wait time in seconds (0 if tokens available)
        """
        async with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                return 0.0
            
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.config.refill_rate


class TokenManager:
    """
    Token manager for LLM API rate limiting.
    
    This class manages rate limiting for LLM API requests using a token bucket
    algorithm. It queues requests when approaching rate limits and provides
    metrics for monitoring request patterns.
    
    The manager supports different rate limits for different models and
    tracks metrics for performance monitoring.
    
    Requirements: 1.7
    """
    
    def __init__(
        self,
        requests_per_minute: Optional[int] = None,
        burst_size: Optional[int] = None,
    ):
        """
        Initialize the token manager.
        
        Args:
            requests_per_minute: Maximum requests per minute (default: from config)
            burst_size: Maximum burst size (default: 10)
        """
        config = get_config()
        
        # Use provided values or defaults
        rpm = requests_per_minute or config.rate_limit_per_minute
        burst = burst_size or 10
        
        # Create rate limit configuration
        self.rate_config = RateLimitConfig(
            requests_per_minute=rpm,
            burst_size=burst,
        )
        
        # Create token bucket
        self.bucket = TokenBucket(self.rate_config)
        
        # Request queue for tracking pending requests
        self.request_queue: deque = deque()
        
        # Metrics tracking
        self.metrics = RequestMetrics()
        
        # Lock for queue operations
        self._queue_lock = asyncio.Lock()
        
        logger.info(
            "token_manager_initialized",
            extra={
                "requests_per_minute": rpm,
                "burst_size": burst,
            }
        )
    
    async def acquire_token(self, request_id: Optional[str] = None) -> float:
        """
        Acquire a token for making an LLM API request.
        
        This method will wait if necessary until a token is available.
        It tracks metrics and logs queue information.
        
        Args:
            request_id: Optional request identifier for logging
        
        Returns:
            float: Time spent waiting in seconds
        """
        start_time = time.monotonic()
        request_id = request_id or f"req_{int(time.time() * 1000)}"
        
        # Add to queue
        async with self._queue_lock:
            self.request_queue.append(request_id)
            queue_position = len(self.request_queue)
        
        logger.debug(
            "request_queued",
            extra={
                "request_id": request_id,
                "queue_position": queue_position,
                "queue_size": queue_position,
            }
        )
        
        # Try to acquire token
        wait_time = await self.bucket.acquire(1.0)
        
        # Remove from queue
        async with self._queue_lock:
            if request_id in self.request_queue:
                self.request_queue.remove(request_id)
        
        # Record metrics
        was_queued = wait_time > 0
        self.metrics.record_request(wait_time, was_queued)
        
        if was_queued:
            logger.info(
                "request_dequeued_after_wait",
                extra={
                    "request_id": request_id,
                    "wait_time_seconds": round(wait_time, 2),
                    "queue_size": len(self.request_queue),
                }
            )
        else:
            logger.debug(
                "request_processed_immediately",
                extra={
                    "request_id": request_id,
                    "queue_size": len(self.request_queue),
                }
            )
        
        return wait_time
    
    async def try_acquire_token(self, request_id: Optional[str] = None) -> bool:
        """
        Try to acquire a token without waiting.
        
        Args:
            request_id: Optional request identifier for logging
        
        Returns:
            bool: True if token was acquired, False otherwise
        """
        request_id = request_id or f"req_{int(time.time() * 1000)}"
        
        acquired = await self.bucket.try_acquire(1.0)
        
        if acquired:
            self.metrics.record_request(0.0, False)
            logger.debug(
                "token_acquired_non_blocking",
                extra={"request_id": request_id}
            )
        else:
            logger.debug(
                "token_unavailable_non_blocking",
                extra={"request_id": request_id}
            )
        
        return acquired
    
    async def get_queue_size(self) -> int:
        """
        Get the current size of the request queue.
        
        Returns:
            int: Number of requests waiting in queue
        """
        async with self._queue_lock:
            return len(self.request_queue)
    
    async def get_available_tokens(self) -> float:
        """
        Get the current number of available tokens.
        
        Returns:
            float: Number of available tokens
        """
        return await self.bucket.get_available_tokens()
    
    async def get_estimated_wait_time(self) -> float:
        """
        Get estimated wait time for the next request.
        
        Returns:
            float: Estimated wait time in seconds
        """
        return await self.bucket.get_wait_time(1.0)
    
    def get_metrics(self) -> RequestMetrics:
        """
        Get current metrics.
        
        Returns:
            RequestMetrics: Current metrics snapshot
        """
        return self.metrics
    
    def reset_metrics(self):
        """Reset metrics counters."""
        self.metrics = RequestMetrics()
        logger.info("token_manager_metrics_reset")
    
    async def is_approaching_limit(self, threshold: float = 0.2) -> bool:
        """
        Check if we're approaching the rate limit.
        
        Args:
            threshold: Threshold as fraction of max tokens (default: 0.2 = 20%)
        
        Returns:
            bool: True if available tokens are below threshold
        """
        available = await self.get_available_tokens()
        max_tokens = self.bucket.max_tokens
        
        is_low = available < (max_tokens * threshold)
        
        if is_low:
            logger.warning(
                "approaching_rate_limit",
                extra={
                    "available_tokens": round(available, 2),
                    "max_tokens": max_tokens,
                    "threshold": threshold,
                    "utilization": round((1 - available / max_tokens) * 100, 1),
                }
            )
        
        return is_low
    
    async def wait_for_capacity(self, min_tokens: float = 1.0):
        """
        Wait until at least min_tokens are available.
        
        This is useful for batch operations that need multiple tokens.
        
        Args:
            min_tokens: Minimum tokens to wait for
        """
        wait_time = await self.bucket.get_wait_time(min_tokens)
        
        if wait_time > 0:
            logger.info(
                "waiting_for_capacity",
                extra={
                    "min_tokens": min_tokens,
                    "wait_time_seconds": round(wait_time, 2),
                }
            )
            await asyncio.sleep(wait_time)


# Global token manager instance
_token_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """
    Get the global token manager instance.
    
    This function implements lazy initialization and caching of the token manager.
    The manager is created once and reused across the application.
    
    Returns:
        TokenManager: The global token manager instance
    """
    global _token_manager
    
    if _token_manager is None:
        _token_manager = TokenManager()
    
    return _token_manager


def create_token_manager(
    requests_per_minute: Optional[int] = None,
    burst_size: Optional[int] = None,
) -> TokenManager:
    """
    Create a new token manager instance.
    
    This is useful for testing or when you need multiple managers
    with different configurations.
    
    Args:
        requests_per_minute: Maximum requests per minute
        burst_size: Maximum burst size
    
    Returns:
        TokenManager: A new token manager instance
    """
    return TokenManager(
        requests_per_minute=requests_per_minute,
        burst_size=burst_size,
    )
