#!/usr/bin/env python3
"""
Celery Ingestion Orchestrator

Enqueues ingestion tasks to Celery workers for distributed processing.
Run this after starting Celery workers with:
    make worker-scraper
    make worker-discovery
"""

import sys
import json
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, func

from shared.db.session import get_db
from shared.models import CompanySource, JobRaw
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


def load_seed_companies():
    """Load seed companies from JSON file."""
    seed_path = Path(__file__).parent.parent / "seed" / "seed_companies.json"
    if not seed_path.exists():
        logger.error("Seed file not found", path=str(seed_path))
        return []
    
    with open(seed_path) as f:
        return json.load(f)


def seed_company_sources():
    """Add seed companies to company_source table if not exists."""
    seed_companies = load_seed_companies()
    
    print(f"\n📋 Loading {len(seed_companies)} seed companies...")
    
    new_count = 0
    with get_db() as db:
        for source in seed_companies:
            existing = db.execute(
                select(CompanySource).where(
                    CompanySource.source_type == source["source_type"],
                    CompanySource.source_key == source["source_key"],
                )
            ).scalar_one_or_none()
            
            if not existing:
                company_source = CompanySource(
                    id=str(uuid4()),
                    source_type=source["source_type"],
                    source_key=source["source_key"],
                    status="candidate",
                    first_seen_at=datetime.now(timezone.utc),
                )
                db.add(company_source)
                new_count += 1
        
        db.commit()
    
    print(f"   ✅ Added {new_count} new sources (skipped {len(seed_companies) - new_count} existing)")
    return new_count


def enqueue_validation_tasks():
    """Enqueue validation tasks for candidate sources."""
    from services.discovery_service.tasks import validate_source
    
    with get_db() as db:
        candidates = db.execute(
            select(CompanySource).where(CompanySource.status == "candidate")
        ).scalars().all()
        
        print(f"\n🔍 Enqueuing {len(candidates)} validation tasks...")
        
        for source in candidates:
            validate_source.delay(source.id)
        
        print(f"   ✅ Enqueued {len(candidates)} tasks to q.discovery")
        return len(candidates)


def enqueue_scrape_tasks():
    """Enqueue scrape tasks for valid sources."""
    from workers.scraper_worker.tasks import scrape_source
    
    with get_db() as db:
        valid_sources = db.execute(
            select(CompanySource).where(CompanySource.status == "valid")
        ).scalars().all()
        
        print(f"\n🔧 Enqueuing {len(valid_sources)} scrape tasks...")
        
        for source in valid_sources:
            scrape_source.delay(source.id)
        
        print(f"   ✅ Enqueued {len(valid_sources)} tasks to q.scrape")
        return len(valid_sources)


def get_current_counts():
    """Get current database counts."""
    with get_db() as db:
        job_raw_count = db.execute(select(func.count(JobRaw.id))).scalar() or 0
        valid_sources = db.execute(
            select(func.count(CompanySource.id)).where(CompanySource.status == "valid")
        ).scalar() or 0
        candidate_sources = db.execute(
            select(func.count(CompanySource.id)).where(CompanySource.status == "candidate")
        ).scalar() or 0
        
        return {
            "job_raw": job_raw_count,
            "valid_sources": valid_sources,
            "candidate_sources": candidate_sources,
        }


def main():
    """Main orchestration loop."""
    target = settings.target_job_count
    
    print("=" * 60)
    print("🚀 GTM Engine - Celery Ingestion Orchestrator")
    print("=" * 60)
    print(f"\n   Target: {target:,} jobs")
    
    # Step 1: Seed companies
    seed_company_sources()
    
    # Step 2: Enqueue validation
    enqueue_validation_tasks()
    
    print("\n⏳ Waiting for validations to complete...")
    print("   Monitor progress with: celery -A shared.utils.celery_app flower")
    print("\n   Workers should be running:")
    print("   - make worker-discovery")
    print("   - make worker-scraper")
    print("")
    
    # Poll and enqueue scrapes periodically
    iteration = 0
    while True:
        iteration += 1
        counts = get_current_counts()
        
        print(f"\n📊 Status (iteration {iteration}):")
        print(f"   job_raw: {counts['job_raw']:,} / {target:,}")
        print(f"   valid_sources: {counts['valid_sources']}")
        print(f"   pending_validation: {counts['candidate_sources']}")
        
        if counts['job_raw'] >= target:
            print(f"\n🎉 Target reached! {counts['job_raw']:,} jobs ingested.")
            break
        
        # Enqueue scrapes for newly validated sources
        if counts['valid_sources'] > 0:
            enqueue_scrape_tasks()
        
        print("\n   Sleeping 30s before next check...")
        time.sleep(30)
    
    print("\n✅ Ingestion orchestration complete!")
    print("   Now run extraction workers: make worker-extractor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
