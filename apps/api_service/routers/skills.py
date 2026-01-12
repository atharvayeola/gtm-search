"""
Skills API Router

Endpoints for skill suggestions and lookup.
"""

from typing import Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from shared.db.session import get_db
from shared.models import JobSkill, Skill

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class SkillSuggestion(BaseModel):
    """Skill suggestion for typeahead."""
    id: str
    name: str
    type: Optional[str] = None
    job_count: int


class SkillSuggestResponse(BaseModel):
    """Skill suggestions response."""
    request_id: str
    suggestions: list[SkillSuggestion]


class SkillDetailResponse(BaseModel):
    """Skill detail response."""
    request_id: str
    id: str
    name: str
    type: Optional[str] = None
    aliases: list[str]
    job_count: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/suggest", response_model=SkillSuggestResponse)
def suggest_skills(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50, description="Max suggestions"),
) -> SkillSuggestResponse:
    """
    Typeahead skill suggestions.
    
    Searches canonical names and aliases.
    """
    with get_db() as db:
        query_term = q.strip().lower()

        results = db.execute(
            select(
                Skill.skill_id,
                Skill.canonical_name,
                Skill.skill_type,
                Skill.aliases,
                func.count(JobSkill.job_id).label("job_count"),
            )
            .outerjoin(JobSkill, JobSkill.skill_id == Skill.skill_id)
            .group_by(Skill.skill_id)
        ).all()

        matches = []
        for row in results:
            name = row.canonical_name or ""
            aliases = row.aliases or []
            alias_hits = any(
                isinstance(alias, str) and alias.lower().startswith(query_term)
                for alias in aliases
            )
            if name.lower().startswith(query_term) or alias_hits:
                matches.append(
                    SkillSuggestion(
                        id=row.skill_id,
                        name=name,
                        type=row.skill_type,
                        job_count=row.job_count,
                    )
                )

        matches.sort(key=lambda item: (-item.job_count, item.name.lower()))
        suggestions = matches[:limit]

        return SkillSuggestResponse(
            request_id=request.state.request_id,
            suggestions=suggestions,
        )


@router.get("/{skill_id}", response_model=SkillDetailResponse)
def get_skill(skill_id: str, request: Request) -> SkillDetailResponse:
    """Get skill details."""
    with get_db() as db:
        skill = db.execute(
            select(Skill).where(Skill.skill_id == skill_id)
        ).scalar_one_or_none()
        
        if not skill:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Skill not found")
        
        # Get job count
        job_count = db.execute(
            select(func.count(JobSkill.job_id))
            .where(JobSkill.skill_id == skill_id)
        ).scalar() or 0
        
        aliases = skill.aliases if skill.aliases else []
        
        return SkillDetailResponse(
            request_id=request.state.request_id,
            id=skill.skill_id,
            name=skill.canonical_name,
            type=skill.skill_type,
            aliases=aliases,
            job_count=job_count,
        )
