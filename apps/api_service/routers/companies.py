"""
Companies API Router

Endpoints for viewing companies and their skill rollups.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from shared.db.session import get_db
from shared.models import Company, CompanySkillRollup, Job, Skill

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class CompanyListItem(BaseModel):
    """Company item in list response."""
    id: str
    name: str
    domain: Optional[str] = None
    job_count: int

    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    """Paginated company list."""
    request_id: str
    companies: list[CompanyListItem]
    total: int
    page: int
    page_size: int


class SkillRollupItem(BaseModel):
    """Skill rollup for company."""
    skill_id: str
    skill_name: str
    job_count: int


class CompanyJobItem(BaseModel):
    """Job item for company detail."""
    id: str
    role_title: str
    seniority_level: str
    job_function: str
    location_city: Optional[str] = None
    remote_type: str


class CompanyDetailResponse(BaseModel):
    """Full company details."""
    request_id: str
    id: str
    name: str
    domain: Optional[str] = None
    job_count: int
    top_skills: list[SkillRollupItem]
    recent_jobs: list[CompanyJobItem]

    class Config:
        from_attributes = True


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=CompanyListResponse)
def list_companies(
    request: Request,
    q: Optional[str] = Query(None, description="Search by company name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> CompanyListResponse:
    """
    List companies with job counts.
    """
    with get_db() as db:
        # Build query with job counts
        query = (
            select(
                Company.id,
                Company.name,
                Company.domain,
                func.count(Job.id).label("job_count"),
            )
            .outerjoin(Job, Job.company_id == Company.id)
            .group_by(Company.id)
        )
        
        if q:
            query = query.where(func.lower(Company.name).like(f"%{q.lower()}%"))
        
        # Get total count
        count_subquery = query.subquery()
        total = db.execute(select(func.count()).select_from(count_subquery)).scalar() or 0
        
        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = query.order_by(func.count(Job.id).desc()).offset(offset).limit(page_size)
        
        results = db.execute(query).all()
        
        companies = [
            CompanyListItem(
                id=row.id,
                name=row.name,
                domain=row.domain,
                job_count=row.job_count,
            )
            for row in results
        ]
        
        return CompanyListResponse(
            request_id=request.state.request_id,
            companies=companies,
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/{company_id}", response_model=CompanyDetailResponse)
def get_company(company_id: str, request: Request) -> CompanyDetailResponse:
    """Get company details with skill rollups and recent jobs."""
    with get_db() as db:
        # Fetch company
        company = db.execute(
            select(Company).where(Company.id == company_id)
        ).scalar_one_or_none()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Get job count
        job_count = db.execute(
            select(func.count(Job.id)).where(Job.company_id == company_id)
        ).scalar() or 0
        
        # Get top skills from rollup
        skill_results = db.execute(
            select(CompanySkillRollup, Skill.canonical_name)
            .join(Skill, Skill.skill_id == CompanySkillRollup.skill_id)
            .where(CompanySkillRollup.company_id == company_id)
            .order_by(CompanySkillRollup.job_count.desc())
            .limit(20)
        ).all()
        
        top_skills = [
            SkillRollupItem(
                skill_id=rollup.skill_id,
                skill_name=skill_name,
                job_count=rollup.job_count,
            )
            for rollup, skill_name in skill_results
        ]
        
        # Get recent jobs
        recent_jobs_result = db.execute(
            select(Job)
            .where(Job.company_id == company_id)
            .order_by(Job.updated_at.desc())
            .limit(10)
        ).scalars().all()
        
        recent_jobs = [
            CompanyJobItem(
                id=job.id,
                role_title=job.role_title,
                seniority_level=job.seniority_level,
                job_function=job.job_function,
                location_city=job.location_city,
                remote_type=job.remote_type,
            )
            for job in recent_jobs_result
        ]
        
        return CompanyDetailResponse(
            request_id=request.state.request_id,
            id=company.id,
            name=company.name,
            domain=company.domain,
            job_count=job_count,
            top_skills=top_skills,
            recent_jobs=recent_jobs,
        )
