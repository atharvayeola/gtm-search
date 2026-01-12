.PHONY: up down migrate seed ingest extract report validate test clean api worker-scraper worker-extractor worker-discovery celery-ingest celery-extract flower ui

# ============================================================================
# Docker Commands
# ============================================================================

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

# ============================================================================
# Database Commands
# ============================================================================

migrate:
	cd shared/db && python -m alembic upgrade head

migrate-new:
	cd shared/db && python -m alembic revision --autogenerate -m "$(MSG)"

# ============================================================================
# Data Commands
# ============================================================================

seed:
	python scripts/seed_skills.py

ingest:
	python scripts/run_ingest.py

extract:
	python scripts/run_extract.py

# ============================================================================
# Validation
# ============================================================================

report:
	python scripts/generate_report.py

validate:
	python scripts/validate.py

# ============================================================================
# Development
# ============================================================================

venv:
	python3.11 -m venv .venv
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check --fix .

# ============================================================================
# Local Development (without Docker)
# ============================================================================

api:
	uvicorn apps.api_service.main:app --reload --port 8000

# Celery Workers (run each in separate terminal)
worker-scraper:
	celery -A shared.utils.celery_app worker -Q q.scrape,q.discovery,dlq.scrape -l info -c 5

worker-extractor:
	celery -A shared.utils.celery_app worker -Q q.extract_t1,q.extract_t2,q.rollup,dlq.extract -l info -c 3

worker-discovery:
	celery -A shared.utils.celery_app worker -Q q.discovery -l info -c 2

# Celery Orchestrators (enqueue tasks to workers)
celery-ingest:
	python scripts/run_celery_ingest.py

celery-extract:
	python scripts/run_celery_extract.py

# Celery Monitoring
flower:
	celery -A shared.utils.celery_app flower --port=5555

ui:
	cd apps/web_ui && npm run dev

# ============================================================================
# Cleanup
# ============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
