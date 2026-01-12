"""
Skill Models

- Skill: Canonical skills/tools with aliases
- SkillUnmapped: Unmapped skill tokens for future review
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base


class Skill(Base):
    """
    Canonical skill/tool.
    
    Skill types: language, framework, cloud, database, crm, data_tool, security, other
    """

    __tablename__ = "skill"

    skill_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    canonical_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    skill_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="other",
    )  # language | framework | cloud | database | crm | data_tool | security | other
    aliases: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )

    # Relationships
    job_skills: Mapped[list["JobSkill"]] = relationship(back_populates="skill")
    company_rollups: Mapped[list["CompanySkillRollup"]] = relationship(back_populates="skill")


class SkillUnmapped(Base):
    """
    Unmapped skill tokens.
    
    Tracks raw skill values that couldn't be canonicalized.
    Count is incremented on each occurrence.
    """

    __tablename__ = "skill_unmapped"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    raw_value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
    )
    example_job_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("job.id"),
        nullable=True,
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Forward references
from shared.models.company import CompanySkillRollup
from shared.models.job import JobSkill
