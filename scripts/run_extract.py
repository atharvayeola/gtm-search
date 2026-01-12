#!/usr/bin/env python3
"""
Run Extraction Pipeline

Orchestrates LLM extraction on pending job_raw entries.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select, not_, exists

from shared.db.session import get_db
from shared.models import JobRaw, Job, Company
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


def get_pending_job_raws(limit: int) -> list[str]:
    """Get job_raw IDs that haven't been extracted yet."""
    with get_db() as db:
        # Find job_raw entries without corresponding job entry
        subq = select(Job.source_job_id).where(
            Job.source_type == JobRaw.source_type,
            Job.source_key == JobRaw.source_key,
            Job.source_job_id == JobRaw.source_job_id,
        ).exists()
        
        result = db.execute(
            select(JobRaw.id)
            .where(not_(subq))
            .order_by(JobRaw.fetched_at.desc())
            .limit(limit)
        ).scalars().all()
        
        return list(result)


def get_job_count() -> int:
    """Get count of extracted jobs."""
    with get_db() as db:
        return db.execute(select(func.count(Job.id))).scalar() or 0


def get_job_raw_count() -> int:
    """Get count of raw jobs."""
    with get_db() as db:
        return db.execute(select(func.count(JobRaw.id))).scalar() or 0


def run_extraction_batch(job_raw_ids: list[str]) -> int:
    """Run extraction on a batch of job_raw entries."""
    from workers.extractor_worker.text_cleaner import extract_clean_text, extract_job_metadata
    from workers.extractor_worker.llm_client import get_llm_client, should_escalate_tier2
    from workers.extractor_worker.skill_mapper import create_skill_mapper
    from workers.scraper_worker.storage import get_storage_client
    from datetime import datetime, timezone
    from uuid import uuid4
    from shared.models import Job, JobText, Company
    from sqlalchemy import and_
    
    storage = get_storage_client()
    llm = get_llm_client()
    
    with get_db() as db:
        # Fetch job_raw entries
        job_raws = db.execute(
            select(JobRaw).where(JobRaw.id.in_(job_raw_ids))
        ).scalars().all()
        
        if not job_raws:
            return 0
        
        # Prepare batch for LLM
        batch_jobs = []
        job_raw_map = {}
        
        for jr in job_raws:
            try:
                payload = storage.get_payload(jr.object_key)
                clean_text = extract_clean_text(jr.source_type, payload)
                metadata = extract_job_metadata(jr.source_type, payload)
                
                if not clean_text:
                    continue
                
                job_ref = f"{jr.source_type}|{jr.source_key}|{jr.source_job_id}"
                
                batch_jobs.append({
                    "job_ref": job_ref,
                    "text": clean_text[:8000],
                    "title": metadata.get("title", ""),
                    "company": metadata.get("company_name", ""),
                    "location": metadata.get("location", ""),
                })
                
                job_raw_map[job_ref] = {
                    "job_raw": jr,
                    "clean_text": clean_text,
                    "metadata": metadata,
                }
                
            except Exception as e:
                logger.error("Failed to prepare job", job_raw_id=jr.id, error=str(e))
        
        if not batch_jobs:
            return 0
        
        # Call LLM
        extracted_list = llm.extract_batch(batch_jobs)
        
        if not extracted_list:
            return 0
        
        # Create skill mapper
        skill_mapper = create_skill_mapper(db)
        
        # Process results
        jobs_created = 0
        
        for extracted in extracted_list:
            job_ref = f"{extracted.source_type}|{extracted.source_key}|{extracted.source_job_id}"
            
            if job_ref not in job_raw_map:
                continue
            
            job_data = job_raw_map[job_ref]
            jr = job_data["job_raw"]
            clean_text = job_data["clean_text"]
            metadata = job_data["metadata"]
            
            try:
                # Find or create company
                company_name = extracted.company_name or metadata.get("company_name", "Unknown")
                existing_company = db.execute(
                    select(Company).where(Company.name == company_name)
                ).scalar_one_or_none()
                
                if existing_company:
                    company = existing_company
                else:
                    company = Company(
                        id=str(uuid4()),
                        name=company_name,
                        domain=extracted.company_domain,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(company)
                    db.flush()
                
                # Check for existing job
                existing_job = db.execute(
                    select(Job).where(
                        and_(
                            Job.source_type == jr.source_type,
                            Job.source_key == jr.source_key,
                            Job.source_job_id == jr.source_job_id,
                        )
                    )
                ).scalar_one_or_none()
                
                if existing_job:
                    job_id = existing_job.id
                else:
                    job_id = str(uuid4())
                    job = Job(
                        id=job_id,
                        company_id=company.id,
                        source_type=jr.source_type,
                        source_key=jr.source_key,
                        source_job_id=jr.source_job_id,
                        role_title=extracted.role_title,
                        seniority_level=extracted.seniority_level.value,
                        job_function=extracted.job_function.value,
                        department=extracted.department,
                        location_city=extracted.location_city,
                        location_state=extracted.location_state,
                        location_country=extracted.location_country,
                        remote_type=extracted.remote_type.value,
                        employment_type=extracted.employment_type.value,
                        salary_min_usd=extracted.salary_min_usd,
                        salary_max_usd=extracted.salary_max_usd,
                        job_summary=extracted.job_summary,
                        confidence=extracted.confidence,
                        needs_tier2=extracted.needs_tier2,
                        updated_at=datetime.now(timezone.utc),
                    )
                    db.add(job)
                    jobs_created += 1
                
                # Create job_text
                existing_text = db.execute(
                    select(JobText).where(JobText.job_id == job_id)
                ).scalar_one_or_none()
                
                if not existing_text:
                    job_text = JobText(
                        job_id=job_id,
                        clean_text=clean_text,
                        raw_excerpt=clean_text[:1000] if clean_text else "",
                    )
                    db.add(job_text)
                
                # Map skills
                skill_mapper.map_skills(
                    job_id,
                    extracted.skills_raw,
                    extracted.tools_raw,
                )
                
                db.commit()  # Commit per job to ensure persistence
                print(f"      + Saved job: {extracted.role_title[:50]}...")
                
            except Exception as e:
                logger.exception("Failed to process extracted job", job_ref=job_ref)
                db.rollback() # Rollback on error
        
        return jobs_created


def run_company_rollups():
    """Run rollups for all companies."""
    from workers.extractor_worker.tasks import rollup_company
    
    with get_db() as db:
        companies = db.execute(select(Company.id)).scalars().all()
        
        for company_id in companies:
            rollup_company(company_id)


def main():
    """Run the extraction pipeline."""
    batch_size = settings.tier1_batch_size
    
    logger.info("Starting extraction pipeline", batch_size=batch_size)
    print(f"🧠 Starting extraction pipeline (batch size: {batch_size})")
    
    job_raw_count = get_job_raw_count()
    print(f"   Total job_raw: {job_raw_count:,}")
    
    iteration = 0
    max_iterations = 10000  # Increased to support 50k jobs w/ small batches
    total_extracted = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Get pending jobs
        pending_ids = get_pending_job_raws(batch_size)
        
        if not pending_ids:
            print("\n✅ No more pending jobs to extract")
            break
        
        print(f"\n📦 Batch {iteration}: Processing {len(pending_ids)} jobs...")
        
        try:
            extracted = run_extraction_batch(pending_ids)
            total_extracted += extracted
            print(f"   ✅ Extracted {extracted} jobs (total: {total_extracted})")
        except Exception as e:
            logger.exception("Batch extraction failed")
            print(f"   ❌ Error: {e}")
        
        # Small delay between batches
        time.sleep(0.5)
    
    # Run company rollups
    print("\n📊 Computing company skill rollups...")
    run_company_rollups()
    
    # Final stats
    job_count = get_job_count()
    print(f"\n📈 Final: {job_count:,} extracted jobs")
    print("✅ Extraction complete!")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n❌ Interrupted")
        sys.exit(1)
    except Exception as e:
        logger.exception("Extraction failed")
        print(f"❌ Error: {e}")
        sys.exit(1)
