#!/usr/bin/env python3
"""
Run Ingestion Pipeline

Orchestrates discovery, validation, and scraping until TARGET_JOB_COUNT is reached.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select

from shared.db.session import get_db
from shared.models import CompanySource, JobRaw
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


def get_job_count() -> int:
    """Get current count of distinct job_raw entries."""
    with get_db() as db:
        result = db.execute(
            select(func.count(JobRaw.id))
        ).scalar()
        return result or 0


def get_valid_source_count() -> int:
    """Get count of valid sources."""
    with get_db() as db:
        result = db.execute(
            select(func.count(CompanySource.id)).where(
                CompanySource.status == "valid"
            )
        ).scalar()
        return result or 0


def get_pending_source_count() -> int:
    """Get count of candidate (pending validation) sources."""
    with get_db() as db:
        result = db.execute(
            select(func.count(CompanySource.id)).where(
                CompanySource.status == "candidate"
            )
        ).scalar()
        return result or 0


def run_discovery_batch(batch_size: int = 100):
    """Run a discovery batch synchronously, with seed list fallback."""
    from services.discovery_service.cdx_client import CDXClient
    from services.discovery_service.tasks import validate_source
    from datetime import datetime, timezone
    from uuid import uuid4
    import json
    from pathlib import Path
    
    client = CDXClient()
    discovered = 0
    new_count = 0
    
    logger.info("Running discovery batch", batch_size=batch_size)
    
    with get_db() as db:
        # Try CDX discovery first
        for source in client.discover_all(limit=batch_size):
            discovered += 1
            
            # Check if exists
            existing = db.execute(
                select(CompanySource).where(
                    CompanySource.source_type == source.source_type,
                    CompanySource.source_key == source.source_key,
                )
            ).scalar_one_or_none()
            
            if existing:
                continue
            
            # Create candidate source
            company_source = CompanySource(
                id=str(uuid4()),
                source_type=source.source_type,
                source_key=source.source_key,
                status="candidate",
                first_seen_at=datetime.now(timezone.utc),
            )
            db.add(company_source)
            new_count += 1
        
        # Fallback to seed list if CDX returned nothing
        if discovered == 0:
            logger.warning("CDX returned no results, falling back to seed list")
            print("  ⚠️  CDX unavailable, using seed list fallback...")
            
            seed_path = Path(__file__).parent.parent / "seed" / "seed_companies.json"
            if seed_path.exists():
                with open(seed_path) as f:
                    seed_companies = json.load(f)
                
                for source in seed_companies[:batch_size]:
                    # Check if exists
                    existing = db.execute(
                        select(CompanySource).where(
                            CompanySource.source_type == source["source_type"],
                            CompanySource.source_key == source["source_key"],
                        )
                    ).scalar_one_or_none()
                    
                    if existing:
                        continue
                    
                    # Create candidate source
                    company_source = CompanySource(
                        id=str(uuid4()),
                        source_type=source["source_type"],
                        source_key=source["source_key"],
                        status="candidate",
                        first_seen_at=datetime.now(timezone.utc),
                    )
                    db.add(company_source)
                    new_count += 1
                    discovered += 1
            else:
                logger.error("Seed list not found", path=str(seed_path))
        
        db.commit()
    
    logger.info("Discovery batch complete", discovered=discovered, new=new_count)
    return new_count


def run_validation_batch(batch_size: int = 50):
    """Validate candidate sources synchronously."""
    from workers.scraper_worker.scrapers import get_scraper
    from datetime import datetime, timezone
    
    logger.info("Running validation batch", batch_size=batch_size)
    
    validated = 0
    valid_count = 0
    
    with get_db() as db:
        sources = db.execute(
            select(CompanySource).where(
                CompanySource.status == "candidate"
            ).limit(batch_size)
        ).scalars().all()
        
        for source in sources:
            try:
                scraper = get_scraper(source.source_type, source.source_key)
                is_valid = scraper.validate()
            except Exception as e:
                logger.debug("Validation error", source_key=source.source_key, error=str(e))
                is_valid = False
            
            source.status = "valid" if is_valid else "invalid"
            source.last_validated_at = datetime.now(timezone.utc)
            validated += 1
            
            if is_valid:
                valid_count += 1
        
        db.commit()
    
    logger.info("Validation batch complete", validated=validated, valid=valid_count)
    return valid_count


def run_scrape_batch(batch_size: int = 20):
    """Scrape valid sources synchronously."""
    from workers.scraper_worker.scrapers import get_scraper
    from workers.scraper_worker.storage import get_storage_client
    from datetime import datetime, timezone
    from uuid import uuid4
    
    storage = get_storage_client()
    
    logger.info("Running scrape batch", batch_size=batch_size)
    
    scraped_sources = 0
    total_jobs = 0
    
    with get_db() as db:
        # Get valid sources that haven't been scraped recently
        sources = db.execute(
            select(CompanySource).where(
                CompanySource.status == "valid"
            ).order_by(
                CompanySource.last_scraped_at.asc().nullsfirst()
            ).limit(batch_size)
        ).scalars().all()
        
        for source in sources:
            try:
                scraper = get_scraper(source.source_type, source.source_key)
                jobs_count = 0
                
                for raw_job in scraper.list_jobs():
                    # Store to MinIO
                    object_key, content_hash = storage.store_raw_payload(
                        source_type=raw_job.source_type,
                        source_key=raw_job.source_key,
                        source_job_id=raw_job.source_job_id,
                        payload=raw_job.payload,
                        timestamp=raw_job.fetched_at,
                    )
                    
                    # Check for duplicate
                    existing = db.execute(
                        select(JobRaw).where(
                            JobRaw.source_type == raw_job.source_type,
                            JobRaw.source_key == raw_job.source_key,
                            JobRaw.source_job_id == raw_job.source_job_id,
                            JobRaw.content_hash == content_hash,
                        )
                    ).scalar_one_or_none()
                    
                    if existing:
                        continue
                    
                    # Create job_raw
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
                    jobs_count += 1
                
                source.last_scraped_at = datetime.now(timezone.utc)
                scraped_sources += 1
                total_jobs += jobs_count
                
                logger.info(
                    "Scraped source",
                    source_key=source.source_key,
                    jobs=jobs_count,
                )
                
            except Exception as e:
                logger.warning(
                    "Scrape failed",
                    source_key=source.source_key,
                    error=str(e),
                )
        
        db.commit()
    
    logger.info(
        "Scrape batch complete",
        sources=scraped_sources,
        jobs=total_jobs,
    )
    return total_jobs


def main():
    """Run the ingestion pipeline."""
    target = settings.target_job_count
    
    logger.info("Starting ingestion pipeline", target=target)
    print(f"🚀 Starting ingestion pipeline (target: {target:,} jobs)")
    
    iteration = 0
    iteration = 0
    max_iterations = 10000  # Increased safety limit
    
    while iteration < max_iterations:
        iteration += 1
        
        # Check current counts
        job_count = get_job_count()
        valid_sources = get_valid_source_count()
        pending_sources = get_pending_source_count()
        
        print(f"\n📊 Iteration {iteration}: {job_count:,}/{target:,} jobs | {valid_sources} valid sources | {pending_sources} pending")
        
        # Check if target reached
        if job_count >= target:
            print(f"\n✅ Target reached! {job_count:,} jobs ingested")
            logger.info("Target reached", job_count=job_count)
            break
        
        # Discovery phase: get more sources if needed
        # Need ~2500 companies for 50k jobs (assuming ~20 jobs/company)
        if valid_sources < 5000 and pending_sources < 200:
            print("  🔍 Discovering new sources...")
            new_sources = run_discovery_batch(batch_size=100)
            print(f"     Found {new_sources} new sources")
        
        # Validation phase: validate pending sources
        if pending_sources > 0:
            print("  ✓ Validating sources...")
            valid = run_validation_batch(batch_size=50)
            print(f"     {valid} sources validated as valid")
        
        # Scraping phase: scrape valid sources
        if valid_sources > 0 or get_valid_source_count() > 0:
            print("  📥 Scraping jobs...")
            new_jobs = run_scrape_batch(batch_size=10)
            print(f"     Scraped {new_jobs} new jobs")
        
        # Small delay between iterations
        time.sleep(1)
    
    # Final stats
    final_count = get_job_count()
    print(f"\n📈 Final count: {final_count:,} jobs")
    
    if final_count >= target:
        print("✅ Ingestion complete!")
        return 0
    else:
        print(f"⚠️  Target not reached (need {target - final_count:,} more)")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n❌ Interrupted")
        sys.exit(1)
    except Exception as e:
        logger.exception("Ingestion failed")
        print(f"❌ Error: {e}")
        sys.exit(1)
