"""
Jobs API Router

Endpoints for searching and viewing jobs.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from shared.db.session import get_db
from shared.models import Company, Job, JobSkill, JobText, Skill, SkillUnmapped

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class SkillResponse(BaseModel):
    """Skill in job response."""
    id: str
    name: str
    type: Optional[str] = None
    
class JobStatItem(BaseModel):
    """General statistics item (name and count)."""
    name: str
    count: int

class SalaryStat(BaseModel):
    """Salary statistics."""
    median_salary: float
    total_with_salary: int


class JobListItem(BaseModel):
    """Job item in search results."""
    id: str
    role_title: str
    company_name: str
    company_id: str
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    remote_type: str
    seniority_level: str
    job_function: str
    employment_type: str
    salary_min_usd: Optional[int] = None
    salary_max_usd: Optional[int] = None
    confidence: float

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Paginated job search results."""
    request_id: str
    jobs: list[JobListItem]
    total: int
    page: int
    page_size: int


class JobDetailResponse(BaseModel):
    """Full job details."""
    request_id: str
    id: str
    role_title: str
    company_name: str
    company_id: str
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    remote_type: str
    seniority_level: str
    job_function: str
    department: Optional[str] = None
    employment_type: str
    salary_min_usd: Optional[int] = None
    salary_max_usd: Optional[int] = None
    job_summary: Optional[str] = None
    clean_text: Optional[str] = None
    skills: list[SkillResponse]
    confidence: float

    class Config:
        from_attributes = True


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=JobListResponse)
def search_jobs(
    request: Request,
    q: Optional[str] = Query(None, description="Full-text search query"),
    seniority: Optional[list[str]] = Query(None, description="Filter by seniority levels"),
    function: Optional[list[str]] = Query(None, description="Filter by job functions"),
    skill: Optional[list[str]] = Query(None, description="Filter by skills (canonical names)"),
    remote_type: Optional[list[str]] = Query(None, description="Filter by remote type"),
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    country: Optional[str] = Query(None, description="Filter by country"),
    salary_min: Optional[int] = Query(None, description="Minimum salary (USD)"),
    salary_max: Optional[int] = Query(None, description="Maximum salary (USD)"),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> JobListResponse:
    """
    Search and filter jobs.
    
    Supports full-text search, multi-select filters, and pagination.
    """
    with get_db() as db:
        # Base query
        query = (
            select(Job, Company.name.label("company_name"))
            .join(Company, Job.company_id == Company.id)
        )
        
        # Apply filters
        conditions = []
        needs_distinct = False
        
        if q:
            query = query.outerjoin(JobText, JobText.job_id == Job.id)
            search_term = f"%{q.lower()}%"
            fts_query = func.plainto_tsquery("english", q)
            conditions.append(
                or_(
                    JobText.search_vector.op("@@")(fts_query),
                    func.lower(Job.role_title).like(search_term),
                    func.lower(Job.job_summary).like(search_term),
                )
            )
        
        if seniority:
            conditions.append(Job.seniority_level.in_(seniority))
        
        if function:
            conditions.append(Job.job_function.in_(function))

        if skill:
            query = (
                query.join(JobSkill, JobSkill.job_id == Job.id)
                .join(Skill, Skill.skill_id == JobSkill.skill_id)
            )
            conditions.append(Skill.canonical_name.in_(skill))
            needs_distinct = True
        
        if remote_type:
            conditions.append(Job.remote_type.in_(remote_type))
        
        if city:
            conditions.append(func.lower(Job.location_city) == city.lower())
        
        if state:
            conditions.append(func.lower(Job.location_state) == state.lower())
        
        if country:
            conditions.append(func.lower(Job.location_country) == country.lower())
        
        if salary_min is not None:
            conditions.append(Job.salary_min_usd >= salary_min)
        
        if salary_max is not None:
            conditions.append(Job.salary_max_usd <= salary_max)
        
        if company_id:
            conditions.append(Job.company_id == company_id)
        
        if conditions:
            query = query.where(*conditions)

        if needs_distinct:
            query = query.distinct()
        
        # Get total count
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        total = db.execute(count_query).scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(Job.updated_at.desc()).offset(offset).limit(page_size)
        
        # Execute query
        results = db.execute(query).all()
        
        jobs = []
        for job, company_name in results:
            jobs.append(JobListItem(
                id=job.id,
                role_title=job.role_title,
                company_name=company_name,
                company_id=job.company_id,
                location_city=job.location_city,
                location_state=job.location_state,
                location_country=job.location_country,
                remote_type=job.remote_type,
                seniority_level=job.seniority_level,
                job_function=job.job_function,
                employment_type=job.employment_type,
                salary_min_usd=job.salary_min_usd,
                salary_max_usd=job.salary_max_usd,
                confidence=job.confidence,
            ))
        
        return JobListResponse(
            request_id=request.state.request_id,
            jobs=jobs,
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/stats/functions", response_model=list[JobStatItem])
def get_job_function_stats(request: Request) -> list[JobStatItem]:
    """Get job count stats grouped by function."""
    with get_db() as db:
        result = db.execute(text("SELECT name, count FROM mv_job_function_stats")).all()
        return [JobStatItem(name=row.name, count=row.count) for row in result]

@router.get("/stats/seniority", response_model=list[JobStatItem])
def get_seniority_stats(request: Request) -> list[JobStatItem]:
    """Get job count stats grouped by seniority."""
    with get_db() as db:
        result = db.execute(text("SELECT name, count FROM mv_seniority_stats")).all()
        return [JobStatItem(name=row.name, count=row.count) for row in result]

@router.get("/stats/remote", response_model=list[JobStatItem])
def get_remote_stats(request: Request) -> list[JobStatItem]:
    """Get job count stats grouped by remote type."""
    with get_db() as db:
        result = db.execute(text("SELECT name, count FROM mv_remote_stats")).all()
        return [JobStatItem(name=row.name, count=row.count) for row in result]

@router.get("/stats/salary", response_model=SalaryStat)
def get_salary_stats(request: Request) -> SalaryStat:
    """Get overall salary statistics (median)."""
    with get_db() as db:
        row = db.execute(text("SELECT median_salary, total_with_salary FROM mv_salary_stats")).first()
        if not row:
            return SalaryStat(median_salary=0, total_with_salary=0)
        return SalaryStat(median_salary=row.median_salary or 0, total_with_salary=row.total_with_salary)

@router.get("/stats/salary/buckets", response_model=list[JobStatItem])
def get_salary_bucket_stats(request: Request) -> list[JobStatItem]:
    """Get job count stats grouped by salary bucket."""
    with get_db() as db:
        result = db.execute(text("SELECT name, count FROM mv_salary_bucket_stats ORDER BY sort_order")).all()
        return [JobStatItem(name=row.name, count=row.count) for row in result]

@router.get("/stats/locations", response_model=list[JobStatItem])
def get_location_stats(request: Request) -> list[JobStatItem]:
    """Get job count stats grouped by location (City, State)."""
    with get_db() as db:
        result = db.execute(text("SELECT name, count FROM mv_location_stats ORDER BY count DESC LIMIT 50")).all()
        return [JobStatItem(name=row.name, count=row.count) for row in result]


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: str, request: Request) -> JobDetailResponse:
    """Get full job details by ID."""
    with get_db() as db:
        # Fetch job with company
        result = db.execute(
            select(Job, Company.name.label("company_name"))
            .join(Company, Job.company_id == Company.id)
            .where(Job.id == job_id)
        ).first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job, company_name = result
        
        # Get clean text
        job_text = db.execute(
            select(JobText).where(JobText.job_id == job_id)
        ).scalar_one_or_none()
        
        # Get skills
        skill_results = db.execute(
            select(Skill)
            .join(JobSkill, JobSkill.skill_id == Skill.skill_id)
            .where(JobSkill.job_id == job_id)
        ).scalars().all()
        
        skills = [
            SkillResponse(id=s.skill_id, name=s.canonical_name, type=s.skill_type)
            for s in skill_results
        ]
        
        return JobDetailResponse(
            request_id=request.state.request_id,
            id=job.id,
            role_title=job.role_title,
            company_name=company_name,
            company_id=job.company_id,
            location_city=job.location_city,
            location_state=job.location_state,
            location_country=job.location_country,
            remote_type=job.remote_type,
            seniority_level=job.seniority_level,
            job_function=job.job_function,
            department=job.department,
            employment_type=job.employment_type,
            salary_min_usd=job.salary_min_usd,
            salary_max_usd=job.salary_max_usd,
            job_summary=job.job_summary,
            clean_text=job_text.clean_text if job_text else None,
            skills=skills,
            confidence=job.confidence,
        )
