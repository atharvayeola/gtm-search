#!/usr/bin/env python3
"""
Validation Script for PRD Acceptance

Runs all checks required by PRD §17 to validate MVP completion.
"""

import sys
import requests
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select, and_, tuple_

from shared.db.session import get_db
from shared.models import JobRaw, Job
from shared.utils.config import get_settings
from shared.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


def check_job_raw_count(min_count: int = 50000) -> tuple[bool, int]:
    """Check that job_raw has at least min_count distinct jobs."""
    with get_db() as db:
        # Count distinct (source_type, source_key, source_job_id)
        count = db.execute(
            select(
                func.count(
                    func.distinct(
                        tuple_(JobRaw.source_type, JobRaw.source_key, JobRaw.source_job_id)
                    )
                )
            )
        ).scalar() or 0
        
    passed = count >= min_count
    return passed, count


def check_job_count(min_count: int = 45000) -> tuple[bool, int]:
    """Check that job table has at least min_count rows."""
    with get_db() as db:
        count = db.execute(
            select(func.count(Job.id))
        ).scalar() or 0
        
    passed = count >= min_count
    return passed, count


def check_extraction_quality(min_count: int = 40000) -> tuple[bool, int]:
    """Check that at least min_count jobs have non-empty job_summary."""
    with get_db() as db:
        count = db.execute(
            select(func.count(Job.id)).where(
                and_(
                    Job.job_summary != None,
                    Job.job_summary != "",
                )
            )
        ).scalar() or 0
        
    passed = count >= min_count
    return passed, count


def check_api_health(base_url: str = "http://localhost:8000") -> tuple[bool, str]:
    """Check that API /jobs endpoint returns 200."""
    try:
        response = requests.get(
            f"{base_url}/jobs",
            params={"q": "staff", "state": "NY", "page_size": 5},
            timeout=10
        )
        passed = response.status_code == 200
        message = f"HTTP {response.status_code}"
        if passed:
            data = response.json()
            message += f" - {data.get('total', 0)} results"
        return passed, message
    except requests.RequestException as e:
        return False, str(e)


def check_ui_smoke(
    ui_base_url: str = "http://localhost:3000",
    api_base_url: str = "http://localhost:8000",
) -> tuple[bool, str]:
    """Smoke test UI pages with Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return False, f"Playwright not available: {e}"

    # Get a job and company id from the API
    try:
        response = requests.get(
            f"{api_base_url}/jobs",
            params={"page_size": 1},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])
        if not jobs:
            return False, "No jobs found for UI smoke test"
        job_id = jobs[0]["id"]
        company_id = jobs[0]["company_id"]
    except requests.RequestException as e:
        return False, f"API unavailable for UI smoke test: {e}"
    except Exception as e:
        return False, f"Failed to load job id: {e}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()

            response = page.goto(f"{ui_base_url}/jobs", wait_until="networkidle", timeout=15000)
            if not response or response.status >= 400:
                return False, f"/jobs returned {response.status if response else 'no response'}"

            response = page.goto(f"{ui_base_url}/jobs/{job_id}", wait_until="networkidle", timeout=15000)
            if not response or response.status >= 400:
                return False, f"/jobs/{job_id} returned {response.status if response else 'no response'}"

            response = page.goto(f"{ui_base_url}/companies/{company_id}", wait_until="networkidle", timeout=15000)
            if not response or response.status >= 400:
                return False, f"/companies/{company_id} returned {response.status if response else 'no response'}"

            browser.close()
        return True, "UI smoke test passed"
    except Exception as e:
        return False, f"UI smoke test failed: {str(e)[:200]}"


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("🔍 GTM Engine - PRD Validation")
    print("=" * 60)
    
    all_passed = True
    results = []
    
    # Check 1: job_raw count
    print("\n📦 Check 1: Raw Job Ingestion (target: 50,000)")
    passed, count = check_job_raw_count(50000)
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   {status}: {count:,} job_raw records")
    results.append(("Raw Jobs >= 50k", passed, count))
    if not passed:
        all_passed = False
    
    # Check 2: job count
    print("\n📊 Check 2: Structured Jobs (target: 45,000)")
    passed, count = check_job_count(45000)
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   {status}: {count:,} job records")
    results.append(("Structured Jobs >= 45k", passed, count))
    if not passed:
        all_passed = False
    
    # Check 3: extraction quality
    print("\n🧠 Check 3: Extraction Quality (target: 40,000 with summaries)")
    passed, count = check_extraction_quality(40000)
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   {status}: {count:,} jobs with non-empty job_summary")
    results.append(("Quality Jobs >= 40k", passed, count))
    if not passed:
        all_passed = False
    
    # Check 4: API health
    print("\n🌐 Check 4: API Endpoint")
    passed, message = check_api_health()
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   {status}: GET /jobs?q=staff&state=NY - {message}")
    results.append(("API /jobs", passed, message))
    if not passed:
        all_passed = False

    # Check 5: UI smoke test
    print("\n🧪 Check 5: UI Smoke Test")
    passed, message = check_ui_smoke()
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   {status}: {message}")
    results.append(("UI Smoke", passed, message))
    if not passed:
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 VALIDATION SUMMARY")
    print("=" * 60)
    
    for name, passed, value in results:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}: {value}")
    
    print()
    if all_passed:
        print("🎉 ALL CHECKS PASSED - MVP ACCEPTED!")
        return 0
    else:
        print("⚠️  SOME CHECKS FAILED - See details above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
