"""
Common Crawl CDX API Client

Queries the Common Crawl CDX index to discover Greenhouse and Lever job board URLs.
"""

import re
from dataclasses import dataclass
from typing import Iterator

import httpx

from shared.utils.logging import get_logger

logger = get_logger(__name__)

# Common Crawl CDX API endpoint
# Use the latest available index
CDX_API_BASE = "https://index.commoncrawl.org/CC-MAIN-2024-51-index"

# URL patterns to search for
GREENHOUSE_PATTERNS = [
    "boards.greenhouse.io/*",
    "boards-api.greenhouse.io/v1/boards/*",
]
LEVER_PATTERN = "jobs.lever.co/*"

# Token extraction regexes
GREENHOUSE_BOARD_REGEX = re.compile(r"boards\.greenhouse\.io/([a-zA-Z0-9_-]+)")
GREENHOUSE_API_REGEX = re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-zA-Z0-9_-]+)")
LEVER_REGEX = re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_-]+)")


@dataclass
class DiscoveredSource:
    """A discovered company source from CDX."""
    source_type: str  # 'greenhouse' or 'lever'
    source_key: str   # The board token or site identifier
    url: str          # The original URL found


class CDXClient:
    """Client for querying Common Crawl CDX API."""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._seen_keys: set[tuple[str, str]] = set()
    
    def _query_cdx(
        self,
        url_pattern: str,
        page: int = 0,
        page_size: int = 1000,
    ) -> list[dict]:
        """
        Query CDX API for a URL pattern.
        
        Args:
            url_pattern: URL pattern with wildcards (e.g., "boards.greenhouse.io/*")
            page: Page number (0-indexed)
            page_size: Results per page
            
        Returns:
            List of CDX records
        """
        params = {
            "url": url_pattern,
            "output": "json",
            "page": page,
            "pageSize": page_size,
            "fl": "url,timestamp,status",
            "filter": "status:200",  # Only successful fetches
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(CDX_API_BASE, params=params)
                response.raise_for_status()
                
                # CDX returns newline-delimited JSON
                lines = response.text.strip().split("\n")
                if not lines or lines[0] == "":
                    return []
                
                # First line might be header, skip if it doesn't look like JSON
                results = []
                for line in lines:
                    if line.startswith("{"):
                        import json
                        results.append(json.loads(line))
                
                return results
                
        except httpx.HTTPError as e:
            logger.error("CDX query failed", pattern=url_pattern, error=str(e))
            return []
    
    def _extract_greenhouse_token(self, url: str) -> str | None:
        """Extract board token from Greenhouse URL."""
        # Try API URL first
        match = GREENHOUSE_API_REGEX.search(url)
        if match:
            return match.group(1)
        
        # Try board URL
        match = GREENHOUSE_BOARD_REGEX.search(url)
        if match:
            token = match.group(1)
            # Filter out non-company paths
            if token not in ("embed", "careers", "jobs", "static", "assets"):
                return token
        
        return None
    
    def _extract_lever_token(self, url: str) -> str | None:
        """Extract site identifier from Lever URL."""
        match = LEVER_REGEX.search(url)
        if match:
            token = match.group(1)
            # Filter out non-company paths
            if token not in ("embed", "static", "assets", "api"):
                return token
        return None
    
    def discover_greenhouse(self, limit: int | None = None) -> Iterator[DiscoveredSource]:
        """
        Discover Greenhouse board tokens from CDX.
        
        Args:
            limit: Maximum number of unique sources to return
            
        Yields:
            DiscoveredSource objects
        """
        count = 0
        
        for pattern in GREENHOUSE_PATTERNS:
            page = 0
            
            while True:
                if limit and count >= limit:
                    return
                
                logger.info("Querying CDX for Greenhouse", pattern=pattern, page=page)
                records = self._query_cdx(pattern, page=page)
                
                if not records:
                    break
                
                for record in records:
                    if limit and count >= limit:
                        return
                    
                    url = record.get("url", "")
                    token = self._extract_greenhouse_token(url)
                    
                    if token:
                        key = ("greenhouse", token)
                        if key not in self._seen_keys:
                            self._seen_keys.add(key)
                            count += 1
                            yield DiscoveredSource(
                                source_type="greenhouse",
                                source_key=token,
                                url=url,
                            )
                
                page += 1
    
    def discover_lever(self, limit: int | None = None) -> Iterator[DiscoveredSource]:
        """
        Discover Lever site identifiers from CDX.
        
        Args:
            limit: Maximum number of unique sources to return
            
        Yields:
            DiscoveredSource objects
        """
        count = 0
        page = 0
        
        while True:
            if limit and count >= limit:
                return
            
            logger.info("Querying CDX for Lever", page=page)
            records = self._query_cdx(LEVER_PATTERN, page=page)
            
            if not records:
                break
            
            for record in records:
                if limit and count >= limit:
                    return
                
                url = record.get("url", "")
                token = self._extract_lever_token(url)
                
                if token:
                    key = ("lever", token)
                    if key not in self._seen_keys:
                        self._seen_keys.add(key)
                        count += 1
                        yield DiscoveredSource(
                            source_type="lever",
                            source_key=token,
                            url=url,
                        )
            
            page += 1
    
    def discover_all(self, limit: int | None = None) -> Iterator[DiscoveredSource]:
        """
        Discover sources from both Greenhouse and Lever.
        
        Args:
            limit: Maximum total unique sources to return
            
        Yields:
            DiscoveredSource objects
        """
        count = 0
        
        # Alternate between sources for balanced discovery
        greenhouse_gen = self.discover_greenhouse()
        lever_gen = self.discover_lever()
        
        greenhouse_done = False
        lever_done = False
        
        while not (greenhouse_done and lever_done):
            if limit and count >= limit:
                return
            
            # Get from Greenhouse
            if not greenhouse_done:
                try:
                    source = next(greenhouse_gen)
                    count += 1
                    yield source
                except StopIteration:
                    greenhouse_done = True
            
            if limit and count >= limit:
                return
            
            # Get from Lever
            if not lever_done:
                try:
                    source = next(lever_gen)
                    count += 1
                    yield source
                except StopIteration:
                    lever_done = True
