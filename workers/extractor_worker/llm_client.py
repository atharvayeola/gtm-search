"""
LLM Client

Interfaces with Ollama for job extraction using structured prompts.
"""

import json
from typing import Any, Literal
from enum import Enum

import httpx
from pydantic import BaseModel, Field, field_validator

from shared.utils.config import get_settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def normalize_llm_output(data: dict) -> dict:
    """Normalize LLM output to match expected enum values."""
    
    # Remote type normalization
    remote_map = {
        "on-site": "onsite",
        "on site": "onsite",
        "in-office": "onsite",
        "office": "onsite",
        "partially remote": "hybrid",
        "partial remote": "hybrid",
        "non-traditional": "hybrid",
        "Remote": "remote",
        "Hybrid": "hybrid",
        "Onsite": "onsite",
    }
    if "remote_type" in data and data["remote_type"] in remote_map:
        data["remote_type"] = remote_map[data["remote_type"]]
    elif "remote_type" in data and isinstance(data["remote_type"], str):
        data["remote_type"] = data["remote_type"].lower().replace("-", "").replace(" ", "")
        if data["remote_type"] not in ("onsite", "hybrid", "remote", "unknown"):
            data["remote_type"] = "unknown"
    
    # Employment type normalization
    employment_map = {
        "Full-time": "full_time",
        "full time": "full_time",
        "Part-time": "part_time",
        "part time": "part_time",
        "Contract": "contract",
        "Internship": "internship",
        "Temporary": "temporary",
    }
    if "employment_type" in data and data["employment_type"] in employment_map:
        data["employment_type"] = employment_map[data["employment_type"]]
    elif "employment_type" in data and isinstance(data["employment_type"], str):
        data["employment_type"] = data["employment_type"].lower().replace("-", "_").replace(" ", "_")
        if data["employment_type"] not in ("full_time", "part_time", "contract", "internship", "temporary", "unknown"):
            data["employment_type"] = "unknown"
    
    # Seniority level normalization
    if "seniority_level" in data:
        if data["seniority_level"] is None:
            data["seniority_level"] = "unknown"
        elif isinstance(data["seniority_level"], str):
            data["seniority_level"] = data["seniority_level"].lower()
            if data["seniority_level"] not in ("intern", "junior", "mid", "senior", "staff", "principal", "manager", "director", "vp", "cxo", "unknown"):
                data["seniority_level"] = "unknown"
    
    # Handle list values that should be strings (take first element)
    for field in ("location_city", "location_state", "location_country"):
        if field in data and isinstance(data[field], list):
            data[field] = data[field][0] if data[field] else None
    
    return data


# =============================================================================
# Extraction Schema
# =============================================================================

class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"
    MANAGER = "manager"
    DIRECTOR = "director"
    VP = "vp"
    CXO = "cxo"
    UNKNOWN = "unknown"


class JobFunction(str, Enum):
    SALES = "sales"
    SALES_OPS = "sales_ops"
    REVOPS = "revops"
    MARKETING = "marketing"
    PRODUCT_MARKETING = "product_marketing"
    CUSTOMER_SUCCESS = "customer_success"
    SOLUTIONS_ENGINEERING = "solutions_engineering"
    GTM_ENGINEERING = "gtm_engineering"
    FINANCE = "finance"
    HR = "hr"
    ENGINEERING = "engineering"
    DATA = "data"
    SECURITY = "security"
    IT = "it"
    LEGAL = "legal"
    OPERATIONS = "operations"
    OTHER = "other"


class RemoteType(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class JobExtracted(BaseModel):
    """Pydantic model for extracted job data."""
    
    # Identifiers (passed through)
    source_type: str
    source_key: str
    source_job_id: str
    
    # Core fields
    company_name: str
    company_domain: str | None = None
    role_title: str
    seniority_level: SeniorityLevel = SeniorityLevel.UNKNOWN
    department: str | None = None
    job_function: JobFunction = JobFunction.OTHER
    
    # Location
    location_city: str | None = None
    location_state: str | None = None
    location_country: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    
    # Employment
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    salary_min_usd: int | None = None
    salary_max_usd: int | None = None
    
    @field_validator('salary_min_usd', 'salary_max_usd', mode='before')
    @classmethod
    def convert_salary_to_int(cls, v):
        """Convert salary values to int, handling floats and strings."""
        if v is None:
            return None
        if isinstance(v, float):
            return int(round(v))
        if isinstance(v, str):
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return None
        return v
    
    # Content
    job_summary: str = ""
    key_functions_hired_for: list[str] = Field(default_factory=list, max_length=5)
    skills_raw: list[str] = Field(default_factory=list)
    tools_raw: list[str] = Field(default_factory=list)
    
    # Metadata
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    needs_tier2: bool = False
    
    @field_validator('job_summary')
    @classmethod
    def truncate_summary(cls, v: str) -> str:
        """Ensure summary is max 60 words."""
        words = v.split()
        if len(words) > 60:
            return ' '.join(words[:60]) + '...'
        return v
    
    @field_validator('seniority_level', mode='before')
    @classmethod
    def parse_seniority(cls, v: Any) -> SeniorityLevel:
        if isinstance(v, str):
            v = v.lower().strip()
            try:
                return SeniorityLevel(v)
            except ValueError:
                return SeniorityLevel.UNKNOWN
        return v
    
    @field_validator('job_function', mode='before')
    @classmethod
    def parse_function(cls, v: Any) -> JobFunction:
        if isinstance(v, str):
            v = v.lower().strip().replace(' ', '_')
            try:
                return JobFunction(v)
            except ValueError:
                return JobFunction.OTHER
        return v


# =============================================================================
# Prompt Templates
# =============================================================================

TIER1_SYSTEM_PROMPT = """You extract structured hiring signals from job descriptions. Output MUST be valid JSON only.

For each job, extract:
- company_name: The hiring company name
- role_title: The job title
- seniority_level: One of [intern, junior, mid, senior, staff, principal, manager, director, vp, cxo, unknown]
- job_function: One of [sales, sales_ops, revops, marketing, product_marketing, customer_success, solutions_engineering, gtm_engineering, finance, hr, engineering, data, security, it, legal, operations, other]
- remote_type: One of [onsite, hybrid, remote, unknown]
- employment_type: One of [full_time, part_time, contract, internship, temporary, unknown]
- location_city, location_state, location_country: Location components if mentioned
- salary_min_usd, salary_max_usd: Salary range in USD if explicitly stated, else null
- job_summary: A 1-2 sentence summary (max 60 words)
- skills_raw: Array of skills/technologies mentioned
- tools_raw: Array of specific tools/software mentioned
- confidence: Your confidence in the extraction (0.0-1.0)

Output a JSON array matching the input order."""

TIER1_USER_TEMPLATE = """Extract structured data from these job postings.

Input jobs:
{jobs_json}

Output a JSON array with one object per job. Each object must include the job_ref from input."""


# =============================================================================
# LLM Client
# =============================================================================

class OllamaClient:
    """Client for Ollama LLM API."""
    
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.tier1_model_name
        self.timeout = 300.0  # LLM can be slow, especially with thinking mode
    
    def generate(self, prompt: str, system: str | None = None) -> str:
        """
        Generate text from Ollama.
        
        Args:
            prompt: User prompt
            system: System prompt
            
        Returns:
            Generated text
        """
        url = f"{self.base_url}/api/generate"
        
        # Add /no_think to disable reasoning mode for faster responses
        if not prompt.startswith("/no_think"):
            prompt = f"/no_think {prompt}"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temp for consistent extraction
                "num_predict": 4096,
            },
        }
        
        if system:
            payload["system"] = system
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.HTTPError as e:
            logger.error("Ollama request failed", error=str(e))
            raise
    
    def extract_single(
        self,
        job_ref: str,
        text: str,
        title: str,
        company: str,
        location: str,
    ) -> JobExtracted | None:
        """
        Extract structured data from a single job.
        
        Args:
            job_ref: Job reference in format source_type|source_key|source_job_id
            text: Clean job description text
            title: Job title from metadata
            company: Company name from metadata
            location: Location from metadata
            
        Returns:
            JobExtracted object or None on failure
        """
        parts = job_ref.split("|")
        if len(parts) != 3:
            return None
        
        source_type, source_key, source_job_id = parts
        
        # Simpler prompt for single job
        prompt = f"""Extract structured information from this job posting. Return ONLY valid JSON.

Job Title: {title}
Company: {company}
Location: {location}

Job Description:
{text[:4000]}

Return JSON with these fields:
{{
  "role_title": "{title}",
  "company_name": "{company}",
  "seniority_level": "unknown",
  "job_function": "other",
  "remote_type": "unknown",
  "employment_type": "full_time",
  "location_city": null,
  "location_state": null,
  "location_country": null,
  "salary_min_usd": null,
  "salary_max_usd": null,
  "job_summary": "Brief 1-2 sentence summary",
  "skills_raw": ["skill1", "skill2"],
  "tools_raw": ["tool1", "tool2"],
  "confidence": 0.8
}}

Analyze the job and fill in accurate values based on the description."""

        try:
            raw_response = self.generate(prompt, "You are a job data extractor. Output ONLY valid JSON, no other text.")
            
            # Find JSON in response
            start_idx = raw_response.find('{')
            end_idx = raw_response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("No JSON object in response", job_ref=job_ref)
                # Return with metadata as fallback
                return JobExtracted(
                    source_type=source_type,
                    source_key=source_key,
                    source_job_id=source_job_id,
                    company_name=company or "Unknown",
                    role_title=title or "Unknown Role",
                    confidence=0.3,
                )
            
            json_str = raw_response[start_idx:end_idx]
            data = json.loads(json_str)
            
            # Normalize LLM output (fix enum values like "on-site" -> "onsite")
            data = normalize_llm_output(data)
            
            # Merge identifiers
            data["source_type"] = source_type
            data["source_key"] = source_key
            data["source_job_id"] = source_job_id
            
            # Ensure required fields have values
            data.setdefault("company_name", company or "Unknown")
            data.setdefault("role_title", title or "Unknown Role")
            
            return JobExtracted(**data)
            
        except Exception as e:
            logger.warning("Extraction failed, using fallback", job_ref=job_ref, error=str(e))
            # Return with metadata as fallback
            return JobExtracted(
                source_type=source_type,
                source_key=source_key,
                source_job_id=source_job_id,
                company_name=company or "Unknown",
                role_title=title or "Unknown Role",
                confidence=0.3,
            )
    
    def extract_batch(
        self,
        jobs: list[dict[str, Any]],
    ) -> list[JobExtracted]:
        """
        Extract structured data from a batch of jobs.
        
        Args:
            jobs: List of dicts with {job_ref, text, title, company, location}
            
        Returns:
            List of JobExtracted objects
        """
        logger.info("Starting batch extraction", count=len(jobs))

        if not jobs:
            return []

        def parse_json_array(raw_response: str) -> list[dict[str, Any]] | None:
            try:
                data = json.loads(raw_response)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

            start_idx = raw_response.find("[")
            end_idx = raw_response.rfind("]") + 1
            if start_idx == -1 or end_idx == 0:
                return None

            try:
                data = json.loads(raw_response[start_idx:end_idx])
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                return None
            return None

        def coerce_extracted(
            job_ref: str,
            item: dict[str, Any] | None,
            title: str,
            company: str,
        ) -> JobExtracted | None:
            parts = job_ref.split("|")
            if len(parts) != 3:
                return None

            source_type, source_key, source_job_id = parts
            data = dict(item or {})
            data = normalize_llm_output(data)

            data["source_type"] = source_type
            data["source_key"] = source_key
            data["source_job_id"] = source_job_id
            data.setdefault("company_name", company or "Unknown")
            data.setdefault("role_title", title or "Unknown Role")
            data.pop("job_ref", None)

            try:
                return JobExtracted(**data)
            except Exception as e:
                logger.debug("Batch item validation failed", job_ref=job_ref, error=str(e))
                return None

        # Build batch payload
        batch_payload = []
        for job in jobs:
            job_ref = job.get("job_ref", "")
            title = job.get("title", "")
            company = job.get("company", "")
            location = job.get("location", "")
            text = job.get("text", "")
            header = f"Title: {title}\nCompany: {company}\nLocation: {location}\n\n"
            batch_payload.append({
                "job_ref": job_ref,
                "text": header + text,
            })

        prompt = TIER1_USER_TEMPLATE.format(
            jobs_json=json.dumps(batch_payload, ensure_ascii=False)
        )

        extracted_items: list[dict[str, Any]] | None = None
        try:
            raw_response = self.generate(prompt, system=TIER1_SYSTEM_PROMPT)
            extracted_items = parse_json_array(raw_response)
        except Exception as e:
            logger.warning("Batch extraction failed, falling back to single", error=str(e))

        results: list[JobExtracted] = []
        items_by_ref: dict[str, dict[str, Any]] = {}

        if extracted_items:
            for item in extracted_items:
                if isinstance(item, dict) and item.get("job_ref"):
                    items_by_ref[str(item["job_ref"])] = item

        for idx, job in enumerate(jobs):
            job_ref = job.get("job_ref", "")
            title = job.get("title", "")
            company = job.get("company", "")
            location = job.get("location", "")
            text = job.get("text", "")

            item = None
            if job_ref in items_by_ref:
                item = items_by_ref[job_ref]
            elif extracted_items and idx < len(extracted_items) and isinstance(extracted_items[idx], dict):
                item = extracted_items[idx]

            extracted = coerce_extracted(job_ref, item, title, company)

            if not extracted:
                for _ in range(2):
                    extracted = self.extract_single(
                        job_ref=job_ref,
                        text=text,
                        title=title,
                        company=company,
                        location=location,
                    )
                    if extracted:
                        break

            if extracted:
                results.append(extracted)

        logger.info(
            "Batch extraction complete",
            input_count=len(jobs),
            output_count=len(results),
        )
        return results


class OpenAIClient:
    """Client for OpenAI API - much faster than local Ollama."""
    
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = "gpt-4o-mini"  # Fast and cheap
        self.timeout = 60.0  # Increased timeout for reliability
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
    
    def _call_openai_with_retry(self, prompt: str, job_ref: str) -> dict | None:
        """Call OpenAI API with exponential backoff retry for rate limits."""
        import time
        
        for attempt in range(self.MAX_RETRIES):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": "You are a job data extractor. Output ONLY valid JSON, no other text."},
                                {"role": "user", "content": prompt},
                            ],
                            "temperature": 0.1,
                            "max_tokens": 1000,
                        },
                    )
                    
                    # Handle rate limits
                    if response.status_code == 429:
                        delay = self.BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "Rate limited, retrying",
                            attempt=attempt + 1,
                            delay=delay,
                            job_ref=job_ref,
                        )
                        time.sleep(delay)
                        continue
                    
                    # Handle server errors
                    if response.status_code >= 500:
                        delay = self.BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "Server error, retrying",
                            status=response.status_code,
                            attempt=attempt + 1,
                            delay=delay,
                            job_ref=job_ref,
                        )
                        time.sleep(delay)
                        continue
                    
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.TimeoutException:
                delay = self.BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Request timeout, retrying",
                    attempt=attempt + 1,
                    delay=delay,
                    job_ref=job_ref,
                )
                time.sleep(delay)
                continue
            except httpx.RequestError as e:
                logger.warning(
                    "Request error",
                    error=str(e),
                    job_ref=job_ref,
                )
                return None
        
        logger.error("Max retries exceeded", job_ref=job_ref)
        return None
    
    def extract_single(
        self,
        job_ref: str,
        text: str,
        title: str,
        company: str,
        location: str,
    ) -> JobExtracted | None:
        """Extract structured data from a single job using OpenAI."""
        parts = job_ref.split("|")
        if len(parts) != 3:
            return None
        
        source_type, source_key, source_job_id = parts
        
        prompt = f"""Extract structured information from this job posting. Return ONLY valid JSON.

Job Title: {title}
Company: {company}
Location: {location}

Job Description:
{text[:6000]}

Return JSON with these exact fields:
{{
  "role_title": "exact job title",
  "company_name": "company name",
  "seniority_level": "one of: intern, junior, mid, senior, staff, principal, manager, director, vp, cxo, unknown",
  "job_function": "one of: sales, sales_ops, revops, marketing, product_marketing, customer_success, solutions_engineering, gtm_engineering, finance, hr, engineering, data, security, it, legal, operations, other",
  "remote_type": "one of: onsite, hybrid, remote, unknown",
  "employment_type": "one of: full_time, part_time, contract, internship, temporary, unknown",
  "location_city": "city name or null",
  "location_state": "state/province or null",
  "location_country": "country or null",
  "salary_min_usd": null,
  "salary_max_usd": null,
  "job_summary": "1-2 sentence summary of the role",
  "skills_raw": ["skill1", "skill2", "..."],
  "tools_raw": ["tool1", "tool2", "..."],
  "confidence": 0.8
}}"""

        try:
            data = self._call_openai_with_retry(prompt, job_ref)
            
            if not data:
                logger.warning("OpenAI request failed after retries", job_ref=job_ref)
                return JobExtracted(
                    source_type=source_type,
                    source_key=source_key,
                    source_job_id=source_job_id,
                    company_name=company or "Unknown",
                    role_title=title or "Unknown Role",
                    confidence=0.3,
                )
                
            content = data["choices"][0]["message"]["content"]
            
            # Parse JSON from response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("No JSON in OpenAI response", job_ref=job_ref)
                return JobExtracted(
                    source_type=source_type,
                    source_key=source_key,
                    source_job_id=source_job_id,
                    company_name=company or "Unknown",
                    role_title=title or "Unknown Role",
                    confidence=0.3,
                )
            
            json_str = content[start_idx:end_idx]
            extracted_data = json.loads(json_str)
            
            # Normalize LLM output (fix enum values like "on-site" -> "onsite")
            extracted_data = normalize_llm_output(extracted_data)
            
            # Add identifiers
            extracted_data["source_type"] = source_type
            extracted_data["source_key"] = source_key
            extracted_data["source_job_id"] = source_job_id
            extracted_data.setdefault("company_name", company or "Unknown")
            extracted_data.setdefault("role_title", title or "Unknown Role")
            
            return JobExtracted(**extracted_data)
            
        except Exception as e:
            logger.warning("OpenAI extraction failed", job_ref=job_ref, error=str(e))
            return JobExtracted(
                source_type=source_type,
                source_key=source_key,
                source_job_id=source_job_id,
                company_name=company or "Unknown",
                role_title=title or "Unknown Role",
                confidence=0.3,
            )
    
    def extract_batch(self, jobs: list[dict[str, Any]]) -> list[JobExtracted]:
        """Extract structured data from a batch of jobs."""
        logger.info("Starting OpenAI batch extraction", count=len(jobs))
        
        results = []
        for job in jobs:
            extracted = self.extract_single(
                job_ref=job.get("job_ref", ""),
                text=job.get("text", ""),
                title=job.get("title", ""),
                company=job.get("company", ""),
                location=job.get("location", ""),
            )
            if extracted:
                results.append(extracted)
        
        logger.info(
            "OpenAI batch extraction complete",
            input_count=len(jobs),
            output_count=len(results),
        )
        return results


def get_llm_client() -> OllamaClient | OpenAIClient:
    """Get LLM client instance based on configuration."""
    if settings.tier1_provider == "openai" and settings.openai_api_key:
        logger.info("Using OpenAI for extraction")
        return OpenAIClient()
    else:
        logger.info("Using Ollama for extraction")
        return OllamaClient()


def should_escalate_tier2(extracted: JobExtracted) -> bool:
    """
    Determine if a job should be escalated to Tier 2.
    
    Rules (any triggers escalation):
    - confidence < 0.60
    - missing company_name, role_title, or job_summary
    - skills_raw empty AND clean_text > 800 chars
    """
    if extracted.confidence < 0.60:
        return True
    
    if not extracted.company_name or not extracted.role_title:
        return True
    
    if not extracted.job_summary:
        return True
    
    # skills_raw empty check requires clean_text length (done by caller)
    
    return False
