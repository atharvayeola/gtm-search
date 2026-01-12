"""
Job Models

- JobRaw: Raw job posting data with deduplication
- Job: Structured extracted job data
- JobText: Clean text with FTS index
- JobSkill: Job-skill mappings
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base


class JobRaw(Base):
    """
    Raw job posting storage metadata.
    
    Points to object storage for actual raw payload.
    Deduplication via content_hash.
    """

    __tablename__ = "job_raw"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # "greenhouse" | "lever"
    source_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # board token or site
    source_job_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # job ID from source
    url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )  # SHA-256 hex
    object_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )  # S3/MinIO object key

    __table_args__ = (
        # Unique constraint for deduplication/versioning
        UniqueConstraint(
            "source_type",
            "source_key",
            "source_job_id",
            "content_hash",
            name="uq_job_raw_dedupe",
        ),
        Index("ix_job_raw_source", "source_type", "source_key", "source_job_id"),
    )


class Job(Base):
    """
    Structured job data extracted by LLM.
    """

    __tablename__ = "job"

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
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_job_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Core fields
    role_title: Mapped[str] = mapped_column(String(500), nullable=False)
    seniority_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
    )  # intern|junior|mid|senior|staff|principal|manager|director|vp|cxo|unknown
    job_function: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="other",
    )  # sales|sales_ops|revops|marketing|...
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Location
    location_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
    )  # onsite|hybrid|remote|unknown

    # Employment
    employment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
    )  # full_time|part_time|contract|internship|temporary|unknown

    # Salary (USD)
    salary_min_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Summary
    job_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extraction metadata
    key_functions: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # array of strings
    highlights: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # highlight spans
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    needs_tier2: Mapped[bool] = mapped_column(default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="jobs")
    text: Mapped["JobText"] = relationship(back_populates="job", uselist=False)
    skills: Mapped[list["JobSkill"]] = relationship(back_populates="job")

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_key",
            "source_job_id",
            name="uq_job_source_identity",
        ),
        Index("ix_job_source", "source_type", "source_key", "source_job_id"),
        Index("ix_job_location", "location_state", "location_city"),
        Index("ix_job_filters", "seniority_level", "job_function"),
        Index("ix_job_salary", "salary_min_usd", "salary_max_usd"),
    )


class JobText(Base):
    """
    Clean job text for full-text search.
    """

    __tablename__ = "job_text"

    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("job.id", ondelete="CASCADE"),
        primary_key=True,
    )
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full-text search vector (populated by trigger)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    job: Mapped[Job] = relationship(back_populates="text")

    __table_args__ = (
        Index(
            "ix_job_text_fts",
            "search_vector",
            postgresql_using="gin",
        ),
    )


class JobSkill(Base):
    """
    Job-skill mapping with evidence.
    """

    __tablename__ = "job_skill"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("job.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("skill.skill_id"),
        nullable=False,
    )
    evidence_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Relationships
    job: Mapped[Job] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="job_skills")

    __table_args__ = (
        UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),
        Index("ix_job_skill_skill", "skill_id"),
    )


# Forward references
from shared.models.company import Company
from shared.models.skill import Skill
