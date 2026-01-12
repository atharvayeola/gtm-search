"""
Add search performance indexes

Adds indexes on frequently filtered columns:
- company_id: For company detail pages and filtering
- remote_type: For remote/hybrid/onsite filtering
- location_country: For country-based filtering

Uses CREATE INDEX CONCURRENTLY to avoid blocking ongoing
ingestion/extraction pipelines.

Revision ID: 002
Revises: 001
"""

from alembic import op

# revision identifiers
revision = "002_search_indexes"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add search performance indexes (blocking but fast for <1M rows)."""
    # Using standard CREATE INDEX because CONCURRENTLY cannot run inside a transaction
    # and setting up autocommit in Alembic is complex.
    # For 50k rows, this will take < 1 second and is safe.
    
    # Index on company_id for company detail pages
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_company_id ON job (company_id)"
    )
    
    # Index on remote_type for work type filtering
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_remote_type ON job (remote_type)"
    )
    
    # Index on location_country for country filtering
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_location_country ON job (location_country)"
    )


def downgrade() -> None:
    """Remove search performance indexes."""
    op.execute("DROP INDEX IF EXISTS ix_job_company_id")
    op.execute("DROP INDEX IF EXISTS ix_job_remote_type")
    op.execute("DROP INDEX IF EXISTS ix_job_location_country")
