"""
Structured JSON Logging for GTM Engine

All services must use this logger for consistent JSON structured logs.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from shared.utils.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()

    # Configure structlog processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.debug:
        # Pretty console output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **initial_context: Any) -> structlog.BoundLogger:
    """
    Get a structured logger with initial context.
    
    Args:
        name: Logger name (typically __name__ or service name)
        **initial_context: Initial context to bind to all log entries
    
    Returns:
        Bound structlog logger
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


# Convenience function for binding request context
def bind_request_context(request_id: str, **extra: Any) -> None:
    """Bind request context for all subsequent log calls in this context."""
    structlog.contextvars.bind_contextvars(request_id=request_id, **extra)


def bind_task_context(task_id: str, task_name: str, **extra: Any) -> None:
    """Bind Celery task context for worker logs."""
    structlog.contextvars.bind_contextvars(
        task_id=task_id,
        task_name=task_name,
        **extra,
    )


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
