"""
Text Cleaner

Extracts and cleans text from raw job payloads (Greenhouse/Lever).
"""

import re
from typing import Any

from lxml import html
from lxml.html.clean import Cleaner
from readability import Document

from shared.utils.logging import get_logger

logger = get_logger(__name__)

# HTML cleaner configuration
html_cleaner = Cleaner(
    scripts=True,
    javascript=True,
    comments=True,
    style=True,
    links=True,
    meta=True,
    page_structure=True,
    processing_instructions=True,
    remove_unknown_tags=True,
    safe_attrs_only=True,
    remove_tags=["head", "script", "style", "noscript"],
)


def clean_html(html_content: str) -> str:
    """
    Clean HTML and extract plain text.
    
    Args:
        html_content: Raw HTML string
        
    Returns:
        Cleaned plain text
    """
    if not html_content or not html_content.strip():
        return ""
    
    try:
        # Try readability first for article extraction
        doc = Document(html_content)
        summary_html = doc.summary()
        
        # Parse and clean
        tree = html.fromstring(summary_html)
        cleaned = html_cleaner.clean_html(tree)
        
        # Extract text
        text = cleaned.text_content()
        
    except Exception as e:
        logger.debug("Readability failed, falling back to direct parsing", error=str(e))
        try:
            tree = html.fromstring(html_content)
            text = tree.text_content()
        except Exception:
            # Last resort: strip tags with regex
            text = re.sub(r'<[^>]+>', ' ', html_content)
    
    # Normalize whitespace
    text = normalize_whitespace(text)
    
    return text


def normalize_whitespace(text: str) -> str:
    """
    Collapse multiple whitespace and newlines.
    
    Args:
        text: Input text
        
    Returns:
        Normalized text
    """
    # Replace multiple spaces/tabs with single space
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    
    # Trim lines
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def extract_greenhouse_text(payload: dict[str, Any]) -> str:
    """
    Extract clean text from Greenhouse job payload.
    
    Order of preference:
    1. content (HTML)
    2. description (HTML)
    
    Args:
        payload: Greenhouse job JSON payload
        
    Returns:
        Cleaned job description text
    """
    # Prefer 'content' field
    content = payload.get("content", "")
    if content:
        return clean_html(content)
    
    # Fall back to 'description'
    description = payload.get("description", "")
    if description:
        return clean_html(description)
    
    # Check nested locations for embedded descriptions
    if "departments" in payload:
        for dept in payload.get("departments", []):
            if isinstance(dept, dict) and dept.get("name"):
                pass  # Just metadata
    
    logger.warning("No content found in Greenhouse payload", job_id=payload.get("id"))
    return ""


def extract_lever_text(payload: dict[str, Any]) -> str:
    """
    Extract clean text from Lever job payload.
    
    Lever stores description as HTML in 'description' or 'descriptionPlain'.
    
    Args:
        payload: Lever job JSON payload
        
    Returns:
        Cleaned job description text
    """
    # Try plain text first
    plain = payload.get("descriptionPlain", "")
    if plain:
        return normalize_whitespace(plain)
    
    # Fall back to HTML description
    description = payload.get("description", "")
    if description:
        return clean_html(description)
    
    # Try lists content
    lists = payload.get("lists", [])
    if lists:
        sections = []
        for lst in lists:
            if isinstance(lst, dict):
                text = lst.get("text", "") or lst.get("content", "")
                if text:
                    sections.append(clean_html(text))
        if sections:
            return "\n\n".join(sections)
    
    logger.warning("No content found in Lever payload", job_id=payload.get("id"))
    return ""


def extract_clean_text(source_type: str, payload: dict[str, Any]) -> str:
    """
    Extract clean text from a job payload based on source type.
    
    Args:
        source_type: 'greenhouse' or 'lever'
        payload: Raw job JSON payload
        
    Returns:
        Cleaned job description text
    """
    if source_type == "greenhouse":
        return extract_greenhouse_text(payload)
    elif source_type == "lever":
        return extract_lever_text(payload)
    else:
        logger.error("Unknown source type", source_type=source_type)
        return ""


def extract_job_metadata(source_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Extract structured metadata from job payload.
    
    Args:
        source_type: 'greenhouse' or 'lever'
        payload: Raw job JSON payload
        
    Returns:
        Dict with title, company, location, etc.
    """
    if source_type == "greenhouse":
        # Greenhouse has company_name at top level
        company_name = payload.get("company_name", "")
        if not company_name:
            # Fallback to nested company
            company = payload.get("company", {})
            company_name = company.get("name", "") if isinstance(company, dict) else ""
        
        location = payload.get("location", {})
        location_name = location.get("name", "") if isinstance(location, dict) else location if isinstance(location, str) else ""
        
        return {
            "title": payload.get("title", ""),
            "company_name": company_name,
            "location": location_name,
            "departments": [d.get("name", "") for d in payload.get("departments", []) if isinstance(d, dict)],
            "offices": [o.get("name", "") for o in payload.get("offices", []) if isinstance(o, dict)],
        }
    elif source_type == "lever":
        categories = payload.get("categories", {})
        if not isinstance(categories, dict):
            categories = {}
        
        return {
            "title": payload.get("text", ""),
            "company_name": categories.get("company", ""),
            "location": categories.get("location", ""),
            "team": categories.get("team", ""),
            "commitment": categories.get("commitment", ""),
        }
    
    return {}
