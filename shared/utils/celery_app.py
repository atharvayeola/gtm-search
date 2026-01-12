"""
Celery Application Configuration

Crash-safe settings as specified in PRD:
- acks_late = True
- task_reject_on_worker_lost = True  
- worker_prefetch_multiplier = 1
"""

from celery import Celery

from shared.utils.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "gtm_engine",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configure Celery with crash-safe settings
celery_app.conf.update(
    # Crash safety (required by PRD)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    
    # Task routing
    task_routes={
        "services.discovery_service.tasks.*": {"queue": "q.discovery"},
        "workers.scraper_worker.tasks.validate_source": {"queue": "q.discovery"},
        "workers.scraper_worker.tasks.scrape_source": {"queue": "q.scrape"},
        "workers.extractor_worker.tasks.extract_batch_tier1": {"queue": "q.extract_t1"},
        "workers.extractor_worker.tasks.extract_job_tier2": {"queue": "q.extract_t2"},
        "workers.extractor_worker.tasks.rollup_company": {"queue": "q.rollup"},
    },
    
    # Queue definitions
    task_queues={
        "q.discovery": {},
        "q.scrape": {},
        "q.extract_t1": {},
        "q.extract_t2": {},
        "q.rollup": {},
        "dlq.scrape": {},
        "dlq.extract": {},
    },
    
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Result backend settings
    result_expires=86400,  # 24 hours
    
    # Worker settings
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Autodiscover tasks from worker modules
celery_app.autodiscover_tasks([
    "services.discovery_service",
    "workers.scraper_worker",
    "workers.extractor_worker",
])
