"""
Distributed Rate Limiter

Redis-based rate limiting for API calls across multiple workers.
Implements a semaphore pattern for global concurrency control.
"""

import time
from contextlib import contextmanager
from uuid import uuid4

import redis

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Lazy Redis client
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


# Rate limit configurations per host
RATE_LIMITS = {
    "greenhouse": {
        "key": "ratelimit:greenhouse",
        "max_concurrent": 5,
        "timeout": 60,  # seconds
    },
    "lever": {
        "key": "ratelimit:lever",
        "max_concurrent": 5,
        "timeout": 60,
    },
    "openai": {
        "key": "ratelimit:openai",
        "max_concurrent": 10,  # Allow more concurrent, rely on token limits
        "timeout": 120,
        "tokens_per_minute": 200_000,
        "token_key": "ratelimit:openai:tokens",
    },
}


@contextmanager
def rate_limit(host: str, wait: bool = True, max_wait: float = 60.0):
    """
    Distributed rate limiter using Redis semaphore.
    
    Args:
        host: One of 'greenhouse', 'lever', 'openai'
        wait: If True, block until slot available. If False, raise if full.
        max_wait: Maximum seconds to wait for a slot
        
    Yields:
        None when slot acquired
        
    Raises:
        RuntimeError: If wait=False and no slots available
        TimeoutError: If wait exceeds max_wait
    """
    config = RATE_LIMITS.get(host)
    if not config:
        # No rate limiting for unknown hosts
        yield
        return
    
    r = get_redis()
    key = config["key"]
    max_concurrent = config["max_concurrent"]
    timeout = config["timeout"]
    
    token = str(uuid4())
    start_time = time.time()
    acquired = False
    
    try:
        while not acquired:
            # Clean up expired tokens
            r.zremrangebyscore(key, 0, time.time() - timeout)
            
            # Check current count
            current = r.zcard(key)
            
            if current < max_concurrent:
                # Try to acquire slot
                r.zadd(key, {token: time.time()})
                acquired = True
                logger.debug(
                    "Rate limit slot acquired",
                    host=host,
                    concurrent=current + 1,
                    max=max_concurrent,
                )
            elif not wait:
                raise RuntimeError(f"Rate limit full for {host}: {current}/{max_concurrent}")
            else:
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise TimeoutError(f"Rate limit wait exceeded {max_wait}s for {host}")
                
                # Wait and retry
                time.sleep(0.2)
        
        yield
        
    finally:
        if acquired:
            r.zrem(key, token)
            logger.debug("Rate limit slot released", host=host)


class TokenBucketLimiter:
    """
    Token bucket rate limiter for API token limits.
    
    Tracks tokens consumed per minute across all workers.
    """
    
    def __init__(self, host: str = "openai"):
        config = RATE_LIMITS.get(host, {})
        self.redis_key = config.get("token_key", f"ratelimit:{host}:tokens")
        self.tokens_per_minute = config.get("tokens_per_minute", 200_000)
        self.window_seconds = 60
    
    def consume(self, tokens: int, wait: bool = True, max_wait: float = 120.0) -> bool:
        """
        Consume tokens if available.
        
        Args:
            tokens: Number of tokens to consume
            wait: Block until tokens available
            max_wait: Maximum wait time
            
        Returns:
            True if tokens consumed, False if not available (when wait=False)
        """
        r = get_redis()
        start_time = time.time()
        
        while True:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Remove old entries
            r.zremrangebyscore(self.redis_key, 0, window_start)
            
            # Calculate current usage
            entries = r.zrangebyscore(self.redis_key, window_start, now, withscores=True)
            current_tokens = sum(int(e[0]) for e in entries)
            
            if current_tokens + tokens <= self.tokens_per_minute:
                # Add tokens consumed
                r.zadd(self.redis_key, {str(tokens): now})
                r.expire(self.redis_key, self.window_seconds * 2)
                
                logger.debug(
                    "Tokens consumed",
                    tokens=tokens,
                    current=current_tokens + tokens,
                    limit=self.tokens_per_minute,
                )
                return True
            
            if not wait:
                return False
            
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                raise TimeoutError(f"Token wait exceeded {max_wait}s")
            
            # Wait for tokens to be available
            tokens_needed = current_tokens + tokens - self.tokens_per_minute
            wait_time = min(5.0, tokens_needed / (self.tokens_per_minute / 60))
            logger.debug(
                "Waiting for tokens",
                needed=tokens_needed,
                wait_estimate=wait_time,
            )
            time.sleep(max(1.0, wait_time))


# Pre-created limiters
openai_token_limiter = TokenBucketLimiter("openai")


def consume_tokens(tokens: int, wait: bool = True) -> bool:
    """Convenience function to consume OpenAI tokens."""
    return openai_token_limiter.consume(tokens, wait=wait)
