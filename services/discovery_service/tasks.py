"""
Discovery Service Tasks

Celery tasks for discovering Greenhouse and Lever company sources via Common Crawl CDX.
"""

from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select, and_

from shared.utils.celery_app import celery_app
from shared.utils.logging import bind_task_context, get_logger
from shared.db.session import get_db
from shared.models import CompanySource

logger = get_logger("discovery_service")

# How long to wait before retrying invalid sources
INVALID_RETRY_DAYS = 7


@celery_app.task(bind=True, name="services.discovery_service.tasks.discover_sources")
def discover_sources(self, source_type: str = "all", limit: int = 100):
    """
    Discover company sources from Common Crawl CDX API.
    
    Queries for:
    - boards.greenhouse.io/*
    - boards-api.greenhouse.io/v1/boards/*
    - jobs.lever.co/*
    
    Args:
        source_type: 'greenhouse', 'lever', or 'all'
        limit: Maximum number of sources to discover per run
    """
    bind_task_context(self.request.id, "discover_sources")
    logger.info("Starting source discovery", source_type=source_type, limit=limit)
    
    from services.discovery_service.cdx_client import CDXClient
    
    client = CDXClient()
    discovered_count = 0
    new_count = 0
    
    try:
        # Get sources based on type
        if source_type == "greenhouse":
            sources = client.discover_greenhouse(limit=limit)
        elif source_type == "lever":
            sources = client.discover_lever(limit=limit)
        else:
            sources = client.discover_all(limit=limit)
        
        with get_db() as db:
            for source in sources:
                discovered_count += 1
                
                # Check if already exists
                existing = db.execute(
                    select(CompanySource).where(
                        and_(
                            CompanySource.source_type == source.source_type,
                            CompanySource.source_key == source.source_key,
                        )
                    )
                ).scalar_one_or_none()
                
                if existing:
                    logger.debug(
                        "Source already exists",
                        source_type=source.source_type,
                        source_key=source.source_key,
                    )
                    continue
                
                # Create new candidate source
                company_source = CompanySource(
                    id=str(uuid4()),
                    source_type=source.source_type,
                    source_key=source.source_key,
                    status="candidate",
                    first_seen_at=datetime.now(timezone.utc),
                )
                db.add(company_source)
                new_count += 1
                
                # Enqueue validation task
                validate_source.delay(company_source.id)
            
            db.commit()
        
        logger.info(
            "Discovery complete",
            discovered=discovered_count,
            new_sources=new_count,
        )
        return {"discovered": discovered_count, "new": new_count}
        
    except Exception as e:
        logger.exception("Discovery failed", error=str(e))
        raise


@celery_app.task(bind=True, name="services.discovery_service.tasks.validate_source")
def validate_source(self, company_source_id: str):
    """
    Validate a discovered company source.
    
    Calls the list endpoint for Greenhouse/Lever to verify the source is valid.
    Updates company_source.status to 'valid' or 'invalid'.
    
    Args:
        company_source_id: UUID of the company_source to validate
    """
    bind_task_context(self.request.id, "validate_source")
    logger.info("Validating source", company_source_id=company_source_id)
    
    from workers.scraper_worker.scrapers import get_scraper
    
    with get_db() as db:
        # Fetch the source
        source = db.execute(
            select(CompanySource).where(CompanySource.id == company_source_id)
        ).scalar_one_or_none()
        
        if not source:
            logger.error("Source not found", company_source_id=company_source_id)
            return {"status": "error", "reason": "not_found"}
        
        # Check if we should skip (invalid within retry window)
        if source.status == "invalid" and source.last_validated_at:
            retry_after = source.last_validated_at + timedelta(days=INVALID_RETRY_DAYS)
            if datetime.now(timezone.utc) < retry_after:
                logger.debug(
                    "Skipping validation (within retry window)",
                    company_source_id=company_source_id,
                    retry_after=retry_after.isoformat(),
                )
                return {"status": "skipped", "reason": "retry_window"}
        
        # Get the appropriate scraper and validate
        try:
            scraper = get_scraper(source.source_type, source.source_key)
            is_valid = scraper.validate()
        except Exception as e:
            logger.warning(
                "Validation error",
                company_source_id=company_source_id,
                error=str(e),
            )
            is_valid = False
        
        # Update source status
        now = datetime.now(timezone.utc)
        source.status = "valid" if is_valid else "invalid"
        source.last_validated_at = now
        
        db.commit()
        
        logger.info(
            "Validation complete",
            company_source_id=company_source_id,
            source_key=source.source_key,
            status=source.status,
        )
        
        # If valid, enqueue scrape task
        if is_valid:
            from workers.scraper_worker.tasks import scrape_source
            scrape_source.delay(company_source_id)
        
        return {"status": source.status}


@celery_app.task(bind=True, name="services.discovery_service.tasks.discover_and_validate_batch")
def discover_and_validate_batch(self, batch_size: int = 50):
    """
    Discover a batch of sources and validate them.
    
    Convenience task that runs discovery and waits for validation.
    """
    bind_task_context(self.request.id, "discover_and_validate_batch")
    
    # Run discovery
    result = discover_sources(source_type="all", limit=batch_size)
    
    logger.info("Batch discovery complete", result=result)
    return result
