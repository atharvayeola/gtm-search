"""
Company Models

- Company: Base company information
- CompanySource: Greenhouse/Lever board tokens with validation status
- CompanySkillRollup: Aggregated skill counts per company
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base


class Company(Base):
    """Company entity."""

    __tablename__ = "company"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    sources: Mapped[list["CompanySource"]] = relationship(back_populates="company")
    jobs: Mapped[list["Job"]] = relationship(back_populates="company")
    skill_rollups: Mapped[list["CompanySkillRollup"]] = relationship(back_populates="company")


class CompanySource(Base):
    """
    Company source (Greenhouse board token or Lever site).
    
    Status transitions:
    - candidate: discovered but not validated
    - valid: list endpoint returns 200
    - invalid: list endpoint failed (don't retry for 7 days)
    """

    __tablename__ = "company_source"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    company_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("company.id"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # "greenhouse" | "lever"
    source_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # board token or site name
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="candidate",
    )  # candidate | valid | invalid
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    company: Mapped[Company | None] = relationship(back_populates="sources")

    __table_args__ = (
        UniqueConstraint("source_type", "source_key", name="uq_company_source_type_key"),
        Index("ix_company_source_status", "status"),
    )


class CompanySkillRollup(Base):
    """
    Aggregated skill counts per company.
    
    Computed from job_skill join to company.
    """

    __tablename__ = "company_skill_rollup"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    company_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("company.id"),
        nullable=False,
    )
    skill_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("skill.skill_id"),
        nullable=False,
    )
    job_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    company: Mapped[Company] = relationship(back_populates="skill_rollups")
    skill: Mapped["Skill"] = relationship(back_populates="company_rollups")

    __table_args__ = (
        UniqueConstraint("company_id", "skill_id", name="uq_company_skill_rollup"),
        Index("ix_company_skill_rollup_count", "company_id", "job_count"),
    )


# Forward reference for type hints
from shared.models.job import Job
from shared.models.skill import Skill
