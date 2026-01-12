"""
Extractor Worker Tasks

Celery tasks for extracting structured data from raw job postings.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, func, and_

from shared.utils.celery_app import celery_app
from shared.utils.config import get_settings
from shared.utils.logging import bind_task_context, get_logger
from shared.db.session import get_db
from shared.models import JobRaw, Job, JobText, Company, CompanySource, CompanySkillRollup, JobSkill

logger = get_logger("extractor_worker")
settings = get_settings()


@celery_app.task(bind=True, name="workers.extractor_worker.tasks.extract_batch_tier1")
def extract_batch_tier1(self, job_raw_ids: list[str]):
    """
    Extract structured data from a batch of job_raw entries using Tier 1 LLM.
    
    Args:
        job_raw_ids: List of job_raw UUIDs to process (size = TIER1_BATCH_SIZE)
    """
    bind_task_context(self.request.id, "extract_batch_tier1")
    logger.info("Starting Tier 1 batch extraction", count=len(job_raw_ids))
    
    from workers.extractor_worker.text_cleaner import extract_clean_text, extract_job_metadata
    from workers.extractor_worker.llm_client import get_llm_client, should_escalate_tier2
    from workers.extractor_worker.skill_mapper import create_skill_mapper
    from workers.scraper_worker.storage import get_storage_client
    
    storage = get_storage_client()
    llm = get_llm_client()
    
    with get_db() as db:
        # Fetch job_raw entries
        job_raws = db.execute(
            select(JobRaw).where(JobRaw.id.in_(job_raw_ids))
        ).scalars().all()
        
        if not job_raws:
            logger.warning("No job_raw entries found", ids=job_raw_ids)
            return {"status": "empty"}
        
        # Prepare batch for LLM
        batch_jobs = []
        job_raw_map = {}
        empty_job_raws = []  # Jobs with no content to extract
        
        for jr in job_raws:
            try:
                # Load payload from MinIO
                payload = storage.get_payload(jr.object_key)
                
                # Extract clean text
                clean_text = extract_clean_text(jr.source_type, payload)
                metadata = extract_job_metadata(jr.source_type, payload)
                
                if not clean_text:
                    logger.warning("No clean text extracted", job_raw_id=jr.id)
                    # Mark as processed to prevent infinite re-queueing - add to empty jobs list
                    empty_job_raws.append({
                        "job_raw": jr,
                        "metadata": metadata,
                    })
                    continue
                
                # Build job_ref
                job_ref = f"{jr.source_type}|{jr.source_key}|{jr.source_job_id}"
                
                batch_jobs.append({
                    "job_ref": job_ref,
                    "text": clean_text[:8000],  # Truncate for LLM context
                    "title": metadata.get("title", ""),
                    "company": metadata.get("company_name", ""),
                    "location": metadata.get("location", ""),
                })
                
                job_raw_map[job_ref] = {
                    "job_raw": jr,
                    "clean_text": clean_text,
                    "metadata": metadata,
                    "payload": payload,
                }
                
            except Exception as e:
                logger.error("Failed to prepare job", job_raw_id=jr.id, error=str(e))
        
        # Process empty jobs immediately (create placeholders) to prevent re-enqueueing
        empty_jobs_created = 0
        if empty_job_raws:
            for empty_data in empty_job_raws:
                jr = empty_data["job_raw"]
                metadata = empty_data["metadata"]
                try:
                    # Check if already exists
                    existing = db.execute(
                        select(Job).where(
                            and_(
                                Job.source_type == jr.source_type,
                                Job.source_key == jr.source_key,
                                Job.source_job_id == jr.source_job_id,
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if not existing:
                        # Create placeholder company
                        company = _get_or_create_company(
                            db,
                            metadata.get("company_name", "Unknown"),
                            None,
                        )
                        
                        # Create minimal job entry
                        job = Job(
                            company_id=company.id,
                            source_type=jr.source_type,
                            source_key=jr.source_key,
                            source_job_id=jr.source_job_id,
                            role_title=metadata.get("title", "Unknown Role"),
                            confidence=0.1,  # Low confidence - no content
                            needs_re_extraction=True,
                        )
                        db.add(job)
                        empty_jobs_created += 1
                except Exception as e:
                    logger.warning("Failed to create placeholder job", job_raw_id=jr.id, error=str(e))
            
            db.commit()
            logger.info("Created placeholder jobs for empty content", count=empty_jobs_created)

        if not batch_jobs:
            return {
                "status": "no_jobs" if not empty_jobs_created else "empty_jobs_processed",
                "empty_jobs_created": empty_jobs_created
            }
        
        # Call LLM
        extracted_list = llm.extract_batch(batch_jobs)
        
        if not extracted_list:
            logger.error("LLM extraction returned empty")
            return {"status": "llm_failed"}
        
        # Create skill mapper
        skill_mapper = create_skill_mapper(db)
        
        # Process results
        jobs_created = 0
        
        for extracted in extracted_list:
            job_ref = f"{extracted.source_type}|{extracted.source_key}|{extracted.source_job_id}"
            
            if job_ref not in job_raw_map:
                logger.warning("Job ref not in map", job_ref=job_ref)
                continue
            
            job_data = job_raw_map[job_ref]
            jr = job_data["job_raw"]
            clean_text = job_data["clean_text"]
            metadata = job_data["metadata"]
            payload = job_data["payload"]
            
            try:
                # Find or create company
                company = _get_or_create_company(
                    db,
                    extracted.company_name or metadata.get("company_name", "Unknown"),
                    extracted.company_domain,
                )
                
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
                    # Update existing
                    _update_job(existing_job, extracted, company.id)
                    job_id = existing_job.id
                else:
                    # Create new
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
                        updated_at=datetime.now(timezone.utc),
                    )
                    db.add(job)
                
                # Create/update job_text
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
                matched, unmapped = skill_mapper.map_skills(
                    job_id,
                    extracted.skills_raw,
                    extracted.tools_raw,
                )
                
                # Check if needs Tier 2
                needs_tier2 = should_escalate_tier2(extracted)
                if needs_tier2 and len(extracted.skills_raw) == 0 and len(clean_text) > 800:
                    needs_tier2 = True
                
                # Enqueue Tier 2 if needed and enabled
                if needs_tier2 and settings.tier2_enabled:
                    extract_job_tier2.delay(jr.id)
                
                jobs_created += 1
                
            except Exception as e:
                logger.exception("Failed to process extracted job", job_ref=job_ref, error=str(e))
        
        db.commit()
        

        
        logger.info(
            "Batch extraction complete",
            input_count=len(job_raw_ids),
            extracted_count=len(extracted_list),
            jobs_created=jobs_created,
            empty_jobs_created=empty_jobs_created,
        )
        
        return {
            "status": "success",
            "jobs_created": jobs_created,
            "empty_jobs": empty_jobs_created,
        }


@celery_app.task(bind=True, name="workers.extractor_worker.tasks.extract_job_tier2")
def extract_job_tier2(self, job_raw_id: str):
    """
    Extract structured data using Tier 2 premium LLM.
    
    Only runs if TIER2_PROVIDER is not 'disabled'.
    """
    bind_task_context(self.request.id, "extract_job_tier2")
    
    if not settings.tier2_enabled:
        logger.debug("Tier 2 disabled, skipping", job_raw_id=job_raw_id)
        return {"status": "disabled"}
    
    # TODO: Implement Tier 2 with OpenAI/Anthropic
    logger.info("Tier 2 extraction placeholder", job_raw_id=job_raw_id)
    return {"status": "not_implemented"}


@celery_app.task(bind=True, name="workers.extractor_worker.tasks.rollup_company")
def rollup_company(self, company_id: str):
    """
    Compute skill rollups for a company.
    
    Aggregates job_skill counts per skill for the company.
    """
    bind_task_context(self.request.id, "rollup_company")
    logger.info("Computing company rollup", company_id=company_id)
    
    with get_db() as db:
        # Get company's jobs
        jobs = db.execute(
            select(Job.id, Job.updated_at).where(Job.company_id == company_id)
        ).all()
        
        job_ids = [j.id for j in jobs]
        max_updated = max((j.updated_at for j in jobs), default=datetime.now(timezone.utc))
        
        if not job_ids:
            return {"status": "no_jobs"}
        
        # Aggregate skills
        skill_counts = db.execute(
            select(
                JobSkill.skill_id,
                func.count(func.distinct(JobSkill.job_id)).label("job_count"),
            )
            .where(JobSkill.job_id.in_(job_ids))
            .group_by(JobSkill.skill_id)
        ).all()
        
        # Upsert rollups
        for skill_id, job_count in skill_counts:
            existing = db.execute(
                select(CompanySkillRollup).where(
                    and_(
                        CompanySkillRollup.company_id == company_id,
                        CompanySkillRollup.skill_id == skill_id,
                    )
                )
            ).scalar_one_or_none()
            
            if existing:
                existing.job_count = job_count
                existing.last_seen_at = max_updated
            else:
                rollup = CompanySkillRollup(
                    company_id=company_id,
                    skill_id=skill_id,
                    job_count=job_count,
                    last_seen_at=max_updated,
                )
                db.add(rollup)
        
        db.commit()
        
        logger.info(
            "Company rollup complete",
            company_id=company_id,
            skill_count=len(skill_counts),
        )
        
        return {"status": "success", "skills": len(skill_counts)}


def _get_or_create_company(db, name: str, domain: str | None) -> Company:
    """Get or create a company by name."""
    # Use .first() instead of .scalar_one_or_none() to handle race conditions
    # where multiple workers may create the same company simultaneously
    existing = db.execute(
        select(Company).where(Company.name == name).order_by(Company.created_at)
    ).scalars().first()
    
    if existing:
        return existing
    
    company = Company(
        id=str(uuid4()),
        name=name,
        domain=domain,
        created_at=datetime.now(timezone.utc),
    )
    db.add(company)
    db.flush()
    return company


def _update_job(job: Job, extracted, company_id: str):
    """Update an existing job with new extracted data."""
    job.company_id = company_id
    job.role_title = extracted.role_title
    job.seniority_level = extracted.seniority_level.value
    job.job_function = extracted.job_function.value
    job.department = extracted.department
    job.location_city = extracted.location_city
    job.location_state = extracted.location_state
    job.location_country = extracted.location_country
    job.remote_type = extracted.remote_type.value
    job.employment_type = extracted.employment_type.value
    job.salary_min_usd = extracted.salary_min_usd
    job.salary_max_usd = extracted.salary_max_usd
    job.job_summary = extracted.job_summary
    job.updated_at = datetime.now(timezone.utc)
