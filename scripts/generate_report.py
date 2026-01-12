#!/usr/bin/env python3
"""
Report Generation Script

Generates `reports/run_{timestamp}.json` with pipeline stats and cost estimation.
Per PRD §15.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select, desc

from shared.db.session import get_db
from shared.models import JobRaw, Job, JobSkill, Skill
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()

# Tier 2 pricing constants (per 1M tokens)
TIER2_PRICING = {
    "openai": {
        "input": 3.00,   # GPT-4o-mini input
        "output": 12.00,  # GPT-4o-mini output
    },
    "anthropic": {
        "input": 3.00,   # Claude 3 Haiku input
        "output": 15.00,  # Claude 3 Haiku output
    },
}


def get_job_raw_count() -> int:
    """Get count of raw jobs ingested."""
    with get_db() as db:
        return db.execute(select(func.count(JobRaw.id))).scalar() or 0


def get_job_count() -> int:
    """Get count of extracted jobs."""
    with get_db() as db:
        return db.execute(select(func.count(Job.id))).scalar() or 0


def get_jobs_with_summary() -> int:
    """Get count of jobs with non-empty summary."""
    with get_db() as db:
        return db.execute(
            select(func.count(Job.id)).where(
                Job.job_summary != None,
                Job.job_summary != "",
            )
        ).scalar() or 0


def get_tier2_jobs() -> int:
    """Get count of jobs that needed Tier 2 extraction."""
    with get_db() as db:
        return db.execute(
            select(func.count(Job.id)).where(Job.needs_tier2 == True)
        ).scalar() or 0


def get_top_skills(limit: int = 20) -> list[dict]:
    """Get top skills by job count."""
    with get_db() as db:
        results = db.execute(
            select(
                Skill.canonical_name,
                func.count(JobSkill.job_id).label("job_count"),
            )
            .join(JobSkill, JobSkill.skill_id == Skill.skill_id)
            .group_by(Skill.skill_id)
            .order_by(desc("job_count"))
            .limit(limit)
        ).all()
        
        return [
            {"canonical_name": row.canonical_name, "job_count": row.job_count}
            for row in results
        ]


def estimate_tier2_cost(
    tier2_count: int,
    avg_input_tokens: int = 2000,
    avg_output_tokens: int = 500,
    provider: str = "openai",
) -> dict:
    """Estimate Tier 2 LLM costs."""
    pricing = TIER2_PRICING.get(provider, TIER2_PRICING["openai"])
    
    total_input_tokens = tier2_count * avg_input_tokens
    total_output_tokens = tier2_count * avg_output_tokens
    
    input_cost = (total_input_tokens / 1_000_000) * pricing["input"]
    output_cost = (total_output_tokens / 1_000_000) * pricing["output"]
    
    return {
        "tier2_tokens_in_total": total_input_tokens,
        "tier2_tokens_out_total": total_output_tokens,
        "tier2_estimated_cost_usd": round(input_cost + output_cost, 2),
    }


def generate_report() -> dict:
    """Generate the full pipeline report."""
    jobs_ingested = get_job_raw_count()
    jobs_extracted = get_job_count()
    jobs_with_summary = get_jobs_with_summary()
    jobs_tier2 = get_tier2_jobs()
    top_skills = get_top_skills(20)
    
    cost_estimate = estimate_tier2_cost(jobs_tier2)
    
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs_ingested": jobs_ingested,
        "jobs_extracted_t1": jobs_extracted - jobs_tier2,
        "jobs_escalated_t2": jobs_tier2,
        "jobs_with_summary": jobs_with_summary,
        **cost_estimate,
        "top_20_skills_by_count": top_skills,
    }
    
    return report


def main():
    """Generate and save report."""
    print("📊 Generating Pipeline Report...")
    
    report = generate_report()
    
    # Ensure reports directory exists
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"run_{timestamp}.json"
    
    # Save report
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📈 Report saved to: {report_path}")
    print("\n" + "=" * 50)
    print("PIPELINE SUMMARY")
    print("=" * 50)
    print(f"  Jobs Ingested:     {report['jobs_ingested']:,}")
    print(f"  Jobs Extracted T1: {report['jobs_extracted_t1']:,}")
    print(f"  Jobs Escalated T2: {report['jobs_escalated_t2']:,}")
    print(f"  Jobs with Summary: {report['jobs_with_summary']:,}")
    print(f"  Tier2 Cost Est.:   ${report['tier2_estimated_cost_usd']:.2f}")
    print("\n  Top 5 Skills:")
    for i, skill in enumerate(report['top_20_skills_by_count'][:5], 1):
        print(f"    {i}. {skill['canonical_name']}: {skill['job_count']} jobs")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
