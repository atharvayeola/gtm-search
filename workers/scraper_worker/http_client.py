"""
Rate-Limited HTTP Client

Provides a rate-limited HTTP client with per-host concurrency limits
and exponential backoff retry logic.
"""

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

import httpx

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Per-host concurrency limits
HOST_LIMITS = {
    "boards-api.greenhouse.io": 5,
    "api.lever.co": 5,
}
DEFAULT_LIMIT = 5

# Retry configuration
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
BACKOFF_SCHEDULE = [2, 4, 8, 16, 32]  # seconds
MAX_RETRIES = 5


class RateLimiter:
    """Per-host rate limiter using semaphores."""
    
    def __init__(self):
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()
    
    async def get_semaphore(self, host: str) -> asyncio.Semaphore:
        """Get or create a semaphore for a host."""
        async with self._lock:
            if host not in self._semaphores:
                limit = HOST_LIMITS.get(host, DEFAULT_LIMIT)
                self._semaphores[host] = asyncio.Semaphore(limit)
                logger.debug("Created semaphore", host=host, limit=limit)
            return self._semaphores[host]
    
    @asynccontextmanager
    async def acquire(self, host: str):
        """Acquire rate limit slot for a host."""
        sem = await self.get_semaphore(host)
        async with sem:
            yield


# Global rate limiter instance
_rate_limiter = RateLimiter()


async def fetch_with_retry(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """
    Fetch a URL with rate limiting and retry logic.
    
    Args:
        url: URL to fetch
        method: HTTP method
        headers: Request headers
        params: Query parameters
        timeout: Request timeout in seconds
        
    Returns:
        httpx.Response object
        
    Raises:
        httpx.HTTPError: If all retries fail
    """
    # Extract host for rate limiting
    parsed = httpx.URL(url)
    host = parsed.host or "unknown"
    
    last_error: Exception | None = None
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with _rate_limiter.acquire(host):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                    )
                    
                    # Check if we need to retry
                    if response.status_code in RETRY_STATUS_CODES:
                        if attempt < MAX_RETRIES:
                            backoff = BACKOFF_SCHEDULE[attempt]
                            logger.warning(
                                "Retrying request",
                                url=url,
                                status=response.status_code,
                                attempt=attempt + 1,
                                backoff=backoff,
                            )
                            await asyncio.sleep(backoff)
                            continue
                    
                    return response
                    
        except httpx.HTTPError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                backoff = BACKOFF_SCHEDULE[attempt]
                logger.warning(
                    "Request failed, retrying",
                    url=url,
                    error=str(e),
                    attempt=attempt + 1,
                    backoff=backoff,
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "Request failed after all retries",
                    url=url,
                    error=str(e),
                )
                raise
    
    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in fetch_with_retry")


def fetch_sync(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """
    Synchronous version of fetch with retry (no rate limiting).
    
    For use in Celery tasks that run synchronously.
    """
    last_error: Exception | None = None
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                )
                
                if response.status_code in RETRY_STATUS_CODES:
                    if attempt < MAX_RETRIES:
                        backoff = BACKOFF_SCHEDULE[attempt]
                        logger.warning(
                            "Retrying request",
                            url=url,
                            status=response.status_code,
                            attempt=attempt + 1,
                            backoff=backoff,
                        )
                        import time
                        time.sleep(backoff)
                        continue
                
                return response
                
        except httpx.HTTPError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                backoff = BACKOFF_SCHEDULE[attempt]
                logger.warning(
                    "Request failed, retrying",
                    url=url,
                    error=str(e),
                    attempt=attempt + 1,
                    backoff=backoff,
                )
                import time
                time.sleep(backoff)
            else:
                logger.error(
                    "Request failed after all retries",
                    url=url,
                    error=str(e),
                )
                raise
    
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in fetch_sync")
