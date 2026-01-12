#!/usr/bin/env python3
"""
Celery Extraction Orchestrator

Enqueues extraction tasks to Celery workers for distributed processing.
Run this after starting Celery workers with:
    make worker-extractor
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func

from shared.db.session import get_db
from shared.models import JobRaw, Job
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


def get_pending_job_raw_ids(batch_size: int = 100) -> list[str]:
    """Get IDs of job_raw entries that haven't been extracted yet."""
    from sqlalchemy import exists, and_
    
    with get_db() as db:
        # Use NOT EXISTS with proper composite key matching
        subquery = select(Job.id).where(
            and_(
                Job.source_type == JobRaw.source_type,
                Job.source_key == JobRaw.source_key,
                Job.source_job_id == JobRaw.source_job_id,
            )
        )
        
        result = db.execute(
            select(JobRaw.id)
            .where(~exists(subquery))
            .order_by(JobRaw.fetched_at.desc())
            .limit(batch_size)
        ).scalars().all()
        
        return [str(id) for id in result]


def enqueue_extraction_batches(max_batches: int = 100):
    """Enqueue extraction tasks for pending job_raw entries."""
    from workers.extractor_worker.tasks import extract_batch_tier1
    
    batch_size = settings.tier1_batch_size
    batches_enqueued = 0
    
    while batches_enqueued < max_batches:
        # Get pending IDs
        pending_ids = get_pending_job_raw_ids(batch_size)
        
        if not pending_ids:
            print("   No more pending jobs to extract")
            break
        
        # Enqueue batch
        extract_batch_tier1.delay(pending_ids)
        batches_enqueued += 1
        
        if batches_enqueued % 10 == 0:
            print(f"   Enqueued {batches_enqueued} batches ({batches_enqueued * batch_size} jobs)")
    
    return batches_enqueued


def get_current_counts():
    """Get current database counts."""
    with get_db() as db:
        job_raw_count = db.execute(select(func.count(JobRaw.id))).scalar() or 0
        job_count = db.execute(select(func.count(Job.id))).scalar() or 0
        
        return {
            "job_raw": job_raw_count,
            "job": job_count,
            "pending": job_raw_count - job_count,
        }


def main():
    """Main orchestration loop."""
    print("=" * 60)
    print("🧠 GTM Engine - Celery Extraction Orchestrator")
    print("=" * 60)
    
    print("\n   Workers should be running:")
    print("   - make worker-extractor")
    print("")
    
    # Poll and enqueue batches periodically
    iteration = 0
    while True:
        iteration += 1
        counts = get_current_counts()
        
        print(f"\n📊 Status (iteration {iteration}):")
        print(f"   job_raw: {counts['job_raw']:,}")
        print(f"   job:     {counts['job']:,}")
        print(f"   pending: {counts['pending']:,}")
        
        if counts['pending'] <= 0:
            print(f"\n🎉 All jobs extracted! {counts['job']:,} total.")
            break
        
        # Enqueue extraction batches (200 batches = 4000 jobs, enough for 20 workers)
        print(f"\n📦 Enqueuing extraction batches...")
        batches = enqueue_extraction_batches(max_batches=200)
        print(f"   ✅ Enqueued {batches} batches to q.extract_t1")
        
        print("\n   Sleeping 30s before next check...")
        time.sleep(30)
    
    # Run company rollups
    print("\n📊 Enqueuing company rollups...")
    from workers.extractor_worker.tasks import rollup_company
    from shared.models import Company
    
    with get_db() as db:
        companies = db.execute(select(Company.id)).scalars().all()
        for company_id in companies:
            rollup_company.delay(str(company_id))
        print(f"   ✅ Enqueued {len(companies)} rollup tasks")
    
    print("\n✅ Extraction orchestration complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
