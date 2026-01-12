"""
Greenhouse and Lever Scrapers

Implements job scrapers for Greenhouse and Lever APIs.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from workers.scraper_worker.http_client import fetch_sync
from shared.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RawJob:
    """A raw job posting from a source API."""
    source_type: str
    source_key: str
    source_job_id: str
    url: str
    payload: dict[str, Any]
    fetched_at: datetime


class GreenhouseScraper:
    """Scraper for Greenhouse job boards API."""
    
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
    
    def __init__(self, source_key: str):
        self.source_key = source_key
        self.source_type = "greenhouse"
    
    def list_jobs(self) -> Iterator[RawJob]:
        """
        Fetch all jobs from a Greenhouse board.
        
        Greenhouse returns all jobs in a single response (no pagination).
        
        Yields:
            RawJob objects for each job posting
        """
        url = f"{self.BASE_URL}/{self.source_key}/jobs"
        params = {"content": "true"}  # Include full job content
        
        logger.info("Fetching Greenhouse jobs", source_key=self.source_key)
        
        try:
            response = fetch_sync(url, params=params)
            
            if response.status_code == 404:
                logger.warning("Greenhouse board not found", source_key=self.source_key)
                return
            
            response.raise_for_status()
            data = response.json()
            
            jobs = data.get("jobs", [])
            fetched_at = datetime.now(timezone.utc)
            
            logger.info(
                "Fetched Greenhouse jobs",
                source_key=self.source_key,
                count=len(jobs),
            )
            
            for job in jobs:
                job_id = str(job.get("id", ""))
                if not job_id:
                    continue
                
                # Build the public URL
                absolute_url = job.get("absolute_url", "")
                
                yield RawJob(
                    source_type=self.source_type,
                    source_key=self.source_key,
                    source_job_id=job_id,
                    url=absolute_url,
                    payload=job,
                    fetched_at=fetched_at,
                )
                
        except Exception as e:
            logger.error(
                "Failed to fetch Greenhouse jobs",
                source_key=self.source_key,
                error=str(e),
            )
            raise
    
    def validate(self) -> bool:
        """
        Validate that this source returns a valid job list.
        
        Returns:
            True if valid (HTTP 200 and parseable), False otherwise
        """
        url = f"{self.BASE_URL}/{self.source_key}/jobs"
        
        try:
            response = fetch_sync(url, timeout=15.0)
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            # Must have 'jobs' key (even if empty)
            return "jobs" in data
            
        except Exception as e:
            logger.debug(
                "Validation failed",
                source_key=self.source_key,
                error=str(e),
            )
            return False


class LeverScraper:
    """Scraper for Lever job postings API."""
    
    BASE_URL = "https://api.lever.co/v0/postings"
    PAGE_SIZE = 100
    
    def __init__(self, source_key: str):
        self.source_key = source_key
        self.source_type = "lever"
    
    def list_jobs(self) -> Iterator[RawJob]:
        """
        Fetch all jobs from a Lever site.
        
        Lever uses pagination with skip/limit.
        
        Yields:
            RawJob objects for each job posting
        """
        url = f"{self.BASE_URL}/{self.source_key}"
        skip = 0
        total_fetched = 0
        fetched_at = datetime.now(timezone.utc)
        
        logger.info("Fetching Lever jobs", source_key=self.source_key)
        
        while True:
            params = {
                "mode": "json",
                "skip": skip,
                "limit": self.PAGE_SIZE,
            }
            
            try:
                response = fetch_sync(url, params=params)
                
                if response.status_code == 404:
                    logger.warning("Lever site not found", source_key=self.source_key)
                    return
                
                response.raise_for_status()
                jobs = response.json()
                
                # Lever returns array directly
                if not isinstance(jobs, list):
                    logger.warning(
                        "Unexpected Lever response",
                        source_key=self.source_key,
                        response_type=type(jobs).__name__,
                    )
                    return
                
                if not jobs:
                    # No more jobs
                    break
                
                for job in jobs:
                    job_id = str(job.get("id", ""))
                    if not job_id:
                        continue
                    
                    # Build the public URL
                    hosted_url = job.get("hostedUrl", "")
                    
                    yield RawJob(
                        source_type=self.source_type,
                        source_key=self.source_key,
                        source_job_id=job_id,
                        url=hosted_url,
                        payload=job,
                        fetched_at=fetched_at,
                    )
                    total_fetched += 1
                
                # Continue pagination
                skip += self.PAGE_SIZE
                
                # Safety limit
                if skip > 10000:
                    logger.warning(
                        "Lever pagination limit reached",
                        source_key=self.source_key,
                        total=total_fetched,
                    )
                    break
                    
            except Exception as e:
                logger.error(
                    "Failed to fetch Lever jobs",
                    source_key=self.source_key,
                    skip=skip,
                    error=str(e),
                )
                raise
        
        logger.info(
            "Fetched Lever jobs",
            source_key=self.source_key,
            count=total_fetched,
        )
    
    def validate(self) -> bool:
        """
        Validate that this source returns a valid job list.
        
        Returns:
            True if valid (HTTP 200 and parseable array), False otherwise
        """
        url = f"{self.BASE_URL}/{self.source_key}"
        params = {"mode": "json", "limit": 1}
        
        try:
            response = fetch_sync(url, params=params, timeout=15.0)
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            # Must be a list (even if empty)
            return isinstance(data, list)
            
        except Exception as e:
            logger.debug(
                "Validation failed",
                source_key=self.source_key,
                error=str(e),
            )
            return False


def get_scraper(source_type: str, source_key: str) -> GreenhouseScraper | LeverScraper:
    """
    Factory function to get the appropriate scraper.
    
    Args:
        source_type: 'greenhouse' or 'lever'
        source_key: Board token or site identifier
        
    Returns:
        Scraper instance
    """
    if source_type == "greenhouse":
        return GreenhouseScraper(source_key)
    elif source_type == "lever":
        return LeverScraper(source_key)
    else:
        raise ValueError(f"Unknown source type: {source_type}")
