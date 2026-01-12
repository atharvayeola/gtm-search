"""
Search API Router

Natural language query parsing using OpenAI.
"""

import json
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

router = APIRouter()
logger = get_logger("search")
settings = get_settings()


class ParsedQuery(BaseModel):
    """Parsed natural language query into structured filters."""
    q: Optional[str] = None  # Text search term
    seniority: list[str] = []
    job_function: list[str] = []
    remote_type: list[str] = []
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    company: Optional[str] = None


class ParseQueryRequest(BaseModel):
    """Request for parsing natural language query."""
    query: str


class ParseQueryResponse(BaseModel):
    """Response with parsed filters."""
    original_query: str
    filters: ParsedQuery
    explanation: str


@router.post("/parse", response_model=ParseQueryResponse)
def parse_natural_language_query(request: ParseQueryRequest) -> ParseQueryResponse:
    """
    Parse a natural language query into structured filters.
    
    Example: "Staff roles paying over $200k in NYC" →
    {seniority: ["staff"], salary_min: 200000, city: "New York"}
    """
    if not settings.openai_api_key:
        # Fallback: basic text search
        return ParseQueryResponse(
            original_query=request.query,
            filters=ParsedQuery(q=request.query),
            explanation="Natural language parsing disabled (no OpenAI key)"
        )
    
    prompt = f"""Parse this job search query into structured filters. Return ONLY valid JSON.

Query: "{request.query}"

Return JSON with these fields (use null for unspecified):
{{
    "q": "text search term or null",
    "seniority": ["list of: intern, junior, mid, senior, staff, principal, manager, director, vp, cxo"],
    "job_function": ["list of: sales, marketing, engineering, data, product_marketing, customer_success, hr, finance, operations, other"],
    "remote_type": ["list of: remote, hybrid, onsite"],
    "city": "city name or null",
    "state": "state name or null", 
    "country": "country name or null",
    "salary_min": number in USD or null,
    "salary_max": number in USD or null,
    "company": "company name or null"
}}

Examples:
- "Staff roles paying over $200k in NYC" → {{"seniority": ["staff"], "salary_min": 200000, "city": "New York"}}
- "Remote engineering jobs at Stripe" → {{"job_function": ["engineering"], "remote_type": ["remote"], "company": "Stripe"}}
- "Senior sales roles in San Francisco" → {{"seniority": ["senior"], "job_function": ["sales"], "city": "San Francisco"}}

Also provide a brief explanation of what you parsed."""

    try:
        # Use OpenAI for fast search parsing
        import time
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": "You are a search query parser. Output valid JSON only."},
                                {"role": "user", "content": prompt},
                            ],
                            "temperature": 0.1,
                            "max_tokens": 500,
                        },
                    )
                    
                    # Check for quota exhausted or rate limit
                    if response.status_code == 429:
                        error_data = response.json().get("error", {})
                        if error_data.get("code") == "insufficient_quota":
                            # Quota exhausted - fall back immediately
                            return ParseQueryResponse(
                                original_query=request.query,
                                filters=ParsedQuery(q=request.query),
                                explanation="OpenAI quota exhausted, using text search"
                            )
                        # Rate limited - wait and retry
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                        time.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    break  # Success, exit retry loop
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                    time.sleep(wait_time)
                    continue
                raise
        else:
            # All retries failed - fall back to text search
            return ParseQueryResponse(
                original_query=request.query,
                filters=ParsedQuery(q=request.query),
                explanation="LLM unavailable, using text search"
            )
        
        # Extract JSON
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        
        if start_idx == -1 or end_idx == 0:
            return ParseQueryResponse(
                original_query=request.query,
                filters=ParsedQuery(q=request.query),
                explanation="Could not parse query"
            )
        
        json_str = content[start_idx:end_idx]
        parsed = json.loads(json_str)
        
        # Normalize list fields (ensure they're always lists, not None or strings)
        list_fields = ['seniority', 'job_function', 'remote_type']
        for field in list_fields:
            if field not in parsed or parsed[field] is None:
                parsed[field] = []
            elif isinstance(parsed[field], str):
                parsed[field] = [parsed[field]]
        
        # Ensure q is None if empty
        if parsed.get('q') in [None, '', 'null']:
            parsed['q'] = None
        
        # Extract explanation if present after JSON
        explanation = "Query parsed successfully"
        if end_idx < len(content):
            remaining = content[end_idx:].strip()
            if remaining:
                explanation = remaining[:200]
        
        return ParseQueryResponse(
            original_query=request.query,
            filters=ParsedQuery(**parsed),
            explanation=explanation
        )
            
    except Exception as e:
        logger.warning("Query parsing failed", error=str(e))
        return ParseQueryResponse(
            original_query=request.query,
            filters=ParsedQuery(q=request.query),
            explanation=f"Parsing failed: {str(e)[:100]}"
        )
