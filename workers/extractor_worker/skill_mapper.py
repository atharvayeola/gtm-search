"""
Skill Mapper

Canonicalizes extracted skills/tools to seeded skill entries.
"""

import re
from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from shared.models import Skill, JobSkill, SkillUnmapped
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# Normalization
# =============================================================================

# Common alias replacements
ALIAS_REPLACEMENTS = {
    "nodejs": "node.js",
    "node js": "node.js",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    "ms sql": "microsoft sql server",
    "mssql": "microsoft sql server",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "tf": "terraform",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "angular.js": "angular",
    "angularjs": "angular",
    "aws": "amazon web services",
    "sfdc": "salesforce",
    "hubspot crm": "hubspot",
    "hs": "hubspot",
}


def normalize_skill(raw: str) -> str:
    """
    Normalize a raw skill string.
    
    Steps:
    1. Lowercase
    2. Trim whitespace
    3. Remove extra spaces
    4. Apply alias replacements
    
    Args:
        raw: Raw skill string
        
    Returns:
        Normalized skill string
    """
    # Lowercase and trim
    normalized = raw.lower().strip()
    
    # Remove extra spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Apply replacements
    if normalized in ALIAS_REPLACEMENTS:
        normalized = ALIAS_REPLACEMENTS[normalized]
    
    return normalized


# =============================================================================
# Skill Matching
# =============================================================================

class SkillMapper:
    """Maps raw skills to canonical skill entries."""
    
    def __init__(self, db: Session):
        self.db = db
        self._cache: dict[str, Skill | None] = {}
        self._load_skills()
    
    def _load_skills(self):
        """Load all skills into cache for fast matching."""
        skills = self.db.execute(select(Skill)).scalars().all()
        
        for skill in skills:
            # Cache by canonical name
            self._cache[skill.canonical_name.lower()] = skill
            
            # Cache by aliases
            if skill.aliases:
                for alias in skill.aliases:
                    self._cache[alias.lower()] = skill
        
        logger.debug("Loaded skills into cache", count=len(skills))
    
    def match(self, raw: str) -> Skill | None:
        """
        Match a raw skill string to a canonical skill.
        
        Args:
            raw: Raw skill string
            
        Returns:
            Matched Skill or None
        """
        normalized = normalize_skill(raw)
        return self._cache.get(normalized)
    
    def map_skills(
        self,
        job_id: str,
        skills_raw: list[str],
        tools_raw: list[str],
    ) -> tuple[int, int]:
        """
        Map raw skills and tools to canonical skills.
        
        Creates job_skill entries for matches and skill_unmapped for misses.
        
        Args:
            job_id: Job UUID
            skills_raw: List of raw skill strings
            tools_raw: List of raw tool strings
            
        Returns:
            Tuple of (matched_count, unmapped_count)
        """
        all_raw = set(skills_raw + tools_raw)
        matched = 0
        unmapped = 0
        
        # Track matched skill_ids to avoid duplicates
        # (e.g., "Rails" and "Ruby on Rails" map to same skill)
        matched_skill_ids: dict[str, str] = {}  # skill_id -> first raw value
        
        for raw in all_raw:
            if not raw or not raw.strip():
                continue
            
            skill = self.match(raw)
            
            if skill:
                # Only add if we haven't matched this skill_id yet
                if skill.skill_id not in matched_skill_ids:
                    matched_skill_ids[skill.skill_id] = raw
                    matched += 1
            else:
                # Upsert to skill_unmapped
                self._upsert_unmapped(raw, job_id)
                unmapped += 1
        
        # Create job_skill entries for deduplicated matches
        for skill_id, raw_value in matched_skill_ids.items():
            self._create_job_skill(job_id, skill_id, raw_value)
        
        return matched, unmapped
    
    def _create_job_skill(self, job_id: str, skill_id: str, raw_value: str):
        """Create a job_skill entry."""
        # Check if exists
        existing = self.db.execute(
            select(JobSkill).where(
                JobSkill.job_id == job_id,
                JobSkill.skill_id == skill_id,
            )
        ).scalar_one_or_none()
        
        if existing:
            return
        
        job_skill = JobSkill(
            job_id=job_id,
            skill_id=skill_id,
            evidence_json={"raw": raw_value},
            confidence=1.0,  # Exact match = full confidence
        )
        self.db.add(job_skill)
    
    def _upsert_unmapped(self, raw_value: str, example_job_id: str):
        """Upsert an unmapped skill."""
        from datetime import datetime, timezone
        from uuid import uuid4
        
        normalized = normalize_skill(raw_value)
        
        # Try to find existing
        existing = self.db.execute(
            select(SkillUnmapped).where(SkillUnmapped.raw_value == normalized)
        ).scalar_one_or_none()
        
        if existing:
            existing.count += 1
            existing.last_seen_at = datetime.now(timezone.utc)
        else:
            unmapped = SkillUnmapped(
                id=str(uuid4()),
                raw_value=normalized,
                example_job_id=example_job_id,
                count=1,
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
            )
            self.db.add(unmapped)


def create_skill_mapper(db: Session) -> SkillMapper:
    """Factory for SkillMapper."""
    return SkillMapper(db)
