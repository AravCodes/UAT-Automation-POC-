"""
Redis caching layer for performance optimization.

This module provides caching functionality for DOM analysis results and LLM
responses to improve performance and reduce API calls. It uses Redis as the
caching backend with configurable TTL values.
"""

import json
import hashlib
from typing import Optional, Any
from datetime import timedelta

try:
    import redis
    from redis import Redis, ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None
    ConnectionPool = None

from app.core.config import get_config
from app.core.exceptions import CacheException
from app.core.logging import get_logger


logger = get_logger(__name__)


class CacheManager:
    """
    Manages caching operations using Redis.
    
    Provides caching for:
    - DOM analysis results (semantic DOM trees)
    - LLM responses (story parsing, scenario generation)
    - Element finder results
    
    Cache keys are generated using content hashing to ensure uniqueness.
    """
    
    def __init__(self):
        """Initialize cache manager with Redis connection."""
        self.config = get_config()
        self.redis_client: Optional[Redis] = None
        self._initialized = False
        
        if not REDIS_AVAILABLE:
            logger.warning(
                "Redis library not installed. Caching will be disabled. "
                "Install with: pip install redis"
            )
            return
        
        if not self.config.enable_cache:
            logger.info("Caching is disabled in configuration")
            return
        
        self._initialize_redis()
    
    def _initialize_redis(self) -> None:
        """
        Initialize Redis connection.
        
        Raises:
            CacheException: If Redis connection fails
        """
        try:
            # Parse Redis URL
            redis_url = self.config.redis_url
            
            # Create connection pool
            pool = ConnectionPool.from_url(
                redis_url,
                db=self.config.redis_db,
                decode_responses=True,
                max_connections=10
            )
            
            # Create Redis client
            self.redis_client = Redis(connection_pool=pool)
            
            # Test connection
            self.redis_client.ping()
            
            self._initialized = True
            logger.info(f"Redis cache initialized: {redis_url}")
        
        except Exception as e:
            logger.warning(
                f"Failed to initialize Redis cache: {e}. "
                "Caching will be disabled."
            )
            self.redis_client = None
            self._initialized = False
    
    def is_available(self) -> bool:
        """
        Check if caching is available.
        
        Returns:
            bool: True if Redis is connected and caching is enabled
        """
        return self._initialized and self.redis_client is not None
    
    # ========================================================================
    # Key Generation
    # ========================================================================
    
    def _generate_key(self, prefix: str, content: str) -> str:
        """
        Generate a cache key from content using SHA256 hash.
        
        Args:
            prefix: Key prefix (e.g., "dom", "llm", "element")
            content: Content to hash
            
        Returns:
            str: Cache key in format "prefix:hash"
        """
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        return f"{prefix}:{content_hash}"
    
    # ========================================================================
    # Generic Cache Operations
    # ========================================================================
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Any: Cached value or None if not found
        """
        if not self.is_available():
            return None
        
        try:
            value = self.redis_client.get(key)
            
            if value is None:
                logger.debug(f"Cache miss: {key}")
                return None
            
            logger.debug(f"Cache hit: {key}")
            return json.loads(value)
        
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set a value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds (None = no expiration)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            
            if ttl:
                self.redis_client.setex(key, ttl, serialized)
            else:
                self.redis_client.set(key, serialized)
            
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True
        
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            self.redis_client.delete(key)
            logger.debug(f"Cache delete: {key}")
            return True
        
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if key exists, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            return self.redis_client.exists(key) > 0
        
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    # ========================================================================
    # DOM Analysis Caching
    # ========================================================================
    
    def get_dom_analysis(self, page_url: str, page_html: str) -> Optional[dict]:
        """
        Get cached DOM analysis result.
        
        Args:
            page_url: URL of the page
            page_html: HTML content of the page
            
        Returns:
            dict: Cached DOM analysis or None if not found
        """
        cache_key = self._generate_key("dom", f"{page_url}:{page_html}")
        return self.get(cache_key)
    
    def set_dom_analysis(
        self,
        page_url: str,
        page_html: str,
        analysis: dict
    ) -> bool:
        """
        Cache DOM analysis result.
        
        Args:
            page_url: URL of the page
            page_html: HTML content of the page
            analysis: DOM analysis result to cache
            
        Returns:
            bool: True if successful, False otherwise
        """
        cache_key = self._generate_key("dom", f"{page_url}:{page_html}")
        ttl = self.config.cache_dom_ttl
        return self.set(cache_key, analysis, ttl)
    
    # ========================================================================
    # LLM Response Caching
    # ========================================================================
    
    def get_llm_response(
        self,
        prompt: str,
        model: str,
        operation: str = "general"
    ) -> Optional[dict]:
        """
        Get cached LLM response.
        
        Args:
            prompt: LLM prompt
            model: Model name used
            operation: Operation type (e.g., "parse_story", "generate_scenarios")
            
        Returns:
            dict: Cached LLM response or None if not found
        """
        cache_key = self._generate_key(
            f"llm:{operation}:{model}",
            prompt
        )
        return self.get(cache_key)
    
    def set_llm_response(
        self,
        prompt: str,
        model: str,
        response: dict,
        operation: str = "general"
    ) -> bool:
        """
        Cache LLM response.
        
        Args:
            prompt: LLM prompt
            model: Model name used
            response: LLM response to cache
            operation: Operation type (e.g., "parse_story", "generate_scenarios")
            
        Returns:
            bool: True if successful, False otherwise
        """
        cache_key = self._generate_key(
            f"llm:{operation}:{model}",
            prompt
        )
        ttl = self.config.cache_llm_ttl
        return self.set(cache_key, response, ttl)
    
    # ========================================================================
    # Element Finder Caching
    # ========================================================================
    
    def get_element_selector(
        self,
        page_url: str,
        element_description: str
    ) -> Optional[str]:
        """
        Get cached element selector.
        
        Args:
            page_url: URL of the page
            element_description: Description of the element to find
            
        Returns:
            str: Cached selector or None if not found
        """
        cache_key = self._generate_key(
            "element",
            f"{page_url}:{element_description}"
        )
        return self.get(cache_key)
    
    def set_element_selector(
        self,
        page_url: str,
        element_description: str,
        selector: str
    ) -> bool:
        """
        Cache element selector.
        
        Args:
            page_url: URL of the page
            element_description: Description of the element
            selector: Selector that successfully found the element
            
        Returns:
            bool: True if successful, False otherwise
        """
        cache_key = self._generate_key(
            "element",
            f"{page_url}:{element_description}"
        )
        # Use DOM TTL for element selectors
        ttl = self.config.cache_dom_ttl
        return self.set(cache_key, selector, ttl)
    
    # ========================================================================
    # Bulk Operations
    # ========================================================================
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all cache keys matching a pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "dom:*", "llm:parse_story:*")
            
        Returns:
            int: Number of keys deleted
        """
        if not self.is_available():
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            
            if not keys:
                return 0
            
            deleted = self.redis_client.delete(*keys)
            logger.info(f"Cleared {deleted} cache keys matching pattern: {pattern}")
            return deleted
        
        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """
        Clear all cache entries.
        
        WARNING: This will clear the entire Redis database!
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            self.redis_client.flushdb()
            logger.warning("Cleared all cache entries")
            return True
        
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
            return False
    
    # ========================================================================
    # Statistics and Monitoring
    # ========================================================================
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            dict: Cache statistics including key counts, memory usage, etc.
        """
        if not self.is_available():
            return {
                "available": False,
                "reason": "Redis not connected or caching disabled"
            }
        
        try:
            info = self.redis_client.info()
            
            # Count keys by prefix
            dom_keys = len(self.redis_client.keys("dom:*"))
            llm_keys = len(self.redis_client.keys("llm:*"))
            element_keys = len(self.redis_client.keys("element:*"))
            
            return {
                "available": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_mb": info.get("used_memory", 0) / (1024 * 1024),
                "total_keys": self.redis_client.dbsize(),
                "dom_keys": dom_keys,
                "llm_keys": llm_keys,
                "element_keys": element_keys,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
        
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "available": False,
                "error": str(e)
            }
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        if total == 0:
            return 0.0
        return (hits / total) * 100
    
    # ========================================================================
    # Context Manager Support
    # ========================================================================
    
    def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# ============================================================================
# Global Cache Manager Instance
# ============================================================================

_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """
    Get the global cache manager instance.
    
    Returns:
        CacheManager: Global cache manager
    """
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = CacheManager()
    
    return _cache_manager


# ============================================================================
# Decorator for Caching Function Results
# ============================================================================

def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_func: Optional[callable] = None
):
    """
    Decorator for caching function results.
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        key_func: Optional function to generate cache key from args
        
    Example:
        @cached(prefix="story_parse", ttl=3600)
        def parse_story(story_text: str) -> dict:
            # Expensive parsing operation
            return result
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()
            
            if not cache.is_available():
                return func(*args, **kwargs)
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use function name and args
                key_content = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                cache_key = cache._generate_key(prefix, key_content)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator
