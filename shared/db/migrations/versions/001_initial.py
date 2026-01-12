"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Company table
    op.create_table(
        "company",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False, index=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Skill table
    op.create_table(
        "skill",
        sa.Column("skill_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("canonical_name", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("skill_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("aliases", postgresql.JSONB, nullable=True),
    )

    # Company source table
    op.create_table(
        "company_source",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("company.id"), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_type", "source_key", name="uq_company_source_type_key"),
    )
    op.create_index("ix_company_source_status", "company_source", ["status"])

    # Job raw table
    op.create_table(
        "job_raw",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("source_job_id", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("http_status", sa.Integer, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("object_key", sa.Text, nullable=False),
        sa.UniqueConstraint("source_type", "source_key", "source_job_id", "content_hash", name="uq_job_raw_dedupe"),
    )
    op.create_index("ix_job_raw_source", "job_raw", ["source_type", "source_key", "source_job_id"])

    # Job table
    op.create_table(
        "job",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("source_job_id", sa.String(255), nullable=False),
        sa.Column("role_title", sa.String(500), nullable=False),
        sa.Column("seniority_level", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("job_function", sa.String(50), nullable=False, server_default="other"),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("location_city", sa.String(255), nullable=True),
        sa.Column("location_state", sa.String(255), nullable=True),
        sa.Column("location_country", sa.String(255), nullable=True),
        sa.Column("remote_type", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("employment_type", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("salary_min_usd", sa.Integer, nullable=True),
        sa.Column("salary_max_usd", sa.Integer, nullable=True),
        sa.Column("job_summary", sa.Text, nullable=True),
        sa.Column("key_functions", postgresql.JSONB, nullable=True),
        sa.Column("highlights", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("needs_tier2", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_type", "source_key", "source_job_id", name="uq_job_source_identity"),
    )
    op.create_index("ix_job_source", "job", ["source_type", "source_key", "source_job_id"])
    op.create_index("ix_job_location", "job", ["location_state", "location_city"])
    op.create_index("ix_job_filters", "job", ["seniority_level", "job_function"])
    op.create_index("ix_job_salary", "job", ["salary_min_usd", "salary_max_usd"])

    # Job text table with FTS
    op.create_table(
        "job_text",
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("job.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("clean_text", sa.Text, nullable=False),
        sa.Column("raw_excerpt", sa.Text, nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
    )
    op.create_index("ix_job_text_fts", "job_text", ["search_vector"], postgresql_using="gin")

    # Create trigger for FTS auto-update
    op.execute("""
        CREATE OR REPLACE FUNCTION job_text_search_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.clean_text, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER job_text_search_update
        BEFORE INSERT OR UPDATE ON job_text
        FOR EACH ROW EXECUTE FUNCTION job_text_search_trigger();
    """)

    # Job skill table
    op.create_table(
        "job_skill",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("job.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("skill.skill_id"), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),
    )
    op.create_index("ix_job_skill_skill", "job_skill", ["skill_id"])

    # Company skill rollup table
    op.create_table(
        "company_skill_rollup",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("skill_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("skill.skill_id"), nullable=False),
        sa.Column("job_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "skill_id", name="uq_company_skill_rollup"),
    )
    op.create_index("ix_company_skill_rollup_count", "company_skill_rollup", ["company_id", "job_count"])

    # Skill unmapped table
    op.create_table(
        "skill_unmapped",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("raw_value", sa.String(500), nullable=False, unique=True, index=True),
        sa.Column("example_job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("job.id"), nullable=True),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("skill_unmapped")
    op.drop_table("company_skill_rollup")
    op.drop_table("job_skill")
    op.execute("DROP TRIGGER IF EXISTS job_text_search_update ON job_text")
    op.execute("DROP FUNCTION IF EXISTS job_text_search_trigger()")
    op.drop_table("job_text")
    op.drop_table("job")
    op.drop_table("job_raw")
    op.drop_table("company_source")
    op.drop_table("skill")
    op.drop_table("company")
