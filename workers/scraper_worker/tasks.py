"""
Scraper Worker Tasks

Celery tasks for fetching job postings from Greenhouse and Lever APIs.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

from shared.utils.celery_app import celery_app
from shared.utils.logging import bind_task_context, get_logger
from shared.db.session import get_db
from shared.models import CompanySource, JobRaw

logger = get_logger("scraper_worker")


@celery_app.task(
    bind=True,
    name="workers.scraper_worker.tasks.scrape_source",
    autoretry_for=(Exception,),
    retry_backoff=2,
    retry_backoff_max=32,
    max_retries=5,
)
def scrape_source(self, company_source_id: str):
    """
    Scrape all job postings from a company source.
    
    For Greenhouse: GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
    For Lever: Paginate GET api.lever.co/v0/postings/{site}?mode=json
    
    Stores raw payloads to MinIO and creates job_raw entries.
    
    Args:
        company_source_id: UUID of the company_source to scrape
    """
    bind_task_context(
        self.request.id,
        "scrape_source",
        company_source_id=company_source_id,
    )
    logger.info("Starting source scrape", company_source_id=company_source_id)
    
    from workers.scraper_worker.scrapers import get_scraper
    from workers.scraper_worker.storage import get_storage_client
    
    storage = get_storage_client()
    
    with get_db() as db:
        # Fetch the source
        source = db.execute(
            select(CompanySource).where(CompanySource.id == company_source_id)
        ).scalar_one_or_none()
        
        if not source:
            logger.error("Source not found", company_source_id=company_source_id)
            return {"status": "error", "reason": "not_found"}
        
        if source.status != "valid":
            logger.warning(
                "Skipping invalid source",
                company_source_id=company_source_id,
                status=source.status,
            )
            return {"status": "skipped", "reason": "not_valid"}
        
        # Get the scraper
        scraper = get_scraper(source.source_type, source.source_key)
        
        jobs_scraped = 0
        jobs_new = 0
        jobs_updated = 0
        
        # Use rate limiting for API calls
        from shared.utils.rate_limiter import rate_limit
        
        try:
            with rate_limit(source.source_type):
                for raw_job in scraper.list_jobs():
                    # Store to MinIO
                    object_key, content_hash = storage.store_raw_payload(
                        source_type=raw_job.source_type,
                        source_key=raw_job.source_key,
                        source_job_id=raw_job.source_job_id,
                        payload=raw_job.payload,
                        timestamp=raw_job.fetched_at,
                    )
                    
                    # Check for existing job_raw with same content
                    existing = db.execute(
                        select(JobRaw).where(
                            and_(
                                JobRaw.source_type == raw_job.source_type,
                                JobRaw.source_key == raw_job.source_key,
                                JobRaw.source_job_id == raw_job.source_job_id,
                                JobRaw.content_hash == content_hash,
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if existing:
                        # Same content, skip
                        jobs_scraped += 1
                        continue
                    
                    # Check if this is a new job or content update
                    any_existing = db.execute(
                        select(JobRaw).where(
                            and_(
                                JobRaw.source_type == raw_job.source_type,
                                JobRaw.source_key == raw_job.source_key,
                                JobRaw.source_job_id == raw_job.source_job_id,
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if any_existing:
                        jobs_updated += 1
                    else:
                        jobs_new += 1
                    
                    # Create job_raw entry
                    job_raw = JobRaw(
                        id=str(uuid4()),
                        source_type=raw_job.source_type,
                        source_key=raw_job.source_key,
                        source_job_id=raw_job.source_job_id,
                        url=raw_job.url,
                        fetched_at=raw_job.fetched_at,
                        http_status=200,
                        content_hash=content_hash,
                        object_key=object_key,
                    )
                    db.add(job_raw)
                    jobs_scraped += 1
            
            # Update source last_scraped_at
            source.last_scraped_at = datetime.now(timezone.utc)
            db.commit()
            
            logger.info(
                "Scrape complete",
                company_source_id=company_source_id,
                source_key=source.source_key,
                jobs_scraped=jobs_scraped,
                jobs_new=jobs_new,
                jobs_updated=jobs_updated,
            )
            
            return {
                "status": "success",
                "jobs_scraped": jobs_scraped,
                "jobs_new": jobs_new,
                "jobs_updated": jobs_updated,
            }
            
        except Exception as e:
            logger.exception(
                "Scrape failed",
                company_source_id=company_source_id,
                error=str(e),
            )
            raise


@celery_app.task(bind=True, name="workers.scraper_worker.tasks.scrape_all_valid_sources")
def scrape_all_valid_sources(self, limit: int | None = None):
    """
    Scrape all valid sources.
    
    Enqueues scrape_source tasks for each valid source.
    
    Args:
        limit: Maximum number of sources to scrape
    """
    bind_task_context(self.request.id, "scrape_all_valid_sources")
    logger.info("Enqueueing scrape tasks for valid sources", limit=limit)
    
    with get_db() as db:
        query = select(CompanySource).where(CompanySource.status == "valid")
        if limit:
            query = query.limit(limit)
        
        sources = db.execute(query).scalars().all()
        
        for source in sources:
            scrape_source.delay(source.id)
        
        logger.info("Enqueued scrape tasks", count=len(sources))
        return {"enqueued": len(sources)}
