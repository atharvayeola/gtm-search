#!/usr/bin/env python3
"""
Seed Skills Script

Loads skills_seed.json into the skill table with upsert semantics.
Usage: python scripts/seed_skills.py
"""

import json
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from shared.db.session import get_db
from shared.models import Skill
from shared.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def load_skills_seed() -> list[dict]:
    """Load skills from seed file."""
    seed_file = Path(__file__).parent.parent / "seed" / "skills_seed.json"
    
    if not seed_file.exists():
        logger.error("Seed file not found", path=str(seed_file))
        raise FileNotFoundError(f"Seed file not found: {seed_file}")
    
    with open(seed_file) as f:
        data = json.load(f)
    
    return data.get("skills", [])


def seed_skills() -> int:
    """
    Seed skills into database with upsert semantics.
    
    Returns:
        Number of skills upserted
    """
    skills_data = load_skills_seed()
    logger.info("Loading skills", count=len(skills_data))
    
    with get_db() as db:
        upserted = 0
        
        for skill_data in skills_data:
            canonical_name = skill_data["canonical_name"].lower().strip()
            
            # Check if exists
            existing = db.execute(
                select(Skill).where(Skill.canonical_name == canonical_name)
            ).scalar_one_or_none()
            
            if existing:
                # Update existing
                existing.skill_type = skill_data.get("skill_type", "other")
                existing.aliases = skill_data.get("aliases", [])
                logger.debug("Updated skill", canonical_name=canonical_name)
            else:
                # Insert new
                skill = Skill(
                    skill_id=str(uuid4()),
                    canonical_name=canonical_name,
                    skill_type=skill_data.get("skill_type", "other"),
                    aliases=skill_data.get("aliases", []),
                )
                db.add(skill)
                logger.debug("Inserted skill", canonical_name=canonical_name)
            
            upserted += 1
        
        db.commit()
    
    logger.info("Skills seeded successfully", count=upserted)
    return upserted


if __name__ == "__main__":
    try:
        count = seed_skills()
        print(f"✓ Seeded {count} skills")
    except Exception as e:
        logger.exception("Failed to seed skills")
        print(f"✗ Failed to seed skills: {e}")
        sys.exit(1)
