# GTM Engine

**Job GTM Intelligence Platform** — Ingest and analyze 50,000+ job postings from Greenhouse and Lever with AI-powered extraction.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- Ollama (for local LLM extraction)

### 1. Set Up Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings (OpenAI key optional but recommended for search)
# For extraction, Ollama is used by default (free, no API key needed)

# Create Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### 2. Start Infrastructure

```bash
# Start all services (Postgres, Redis, MinIO)
make up

# Run database migrations
make migrate

# Seed skills data (200+ canonical skills)
make seed

# Pull Ollama model for extraction
ollama pull qwen3:4b
```

### 3. Run the Pipeline

**Option A: Celery-based (Recommended)**

```bash
# Terminal 1: Flower dashboard (optional, monitoring)
make flower

# Terminal 2: Scraper worker
make worker-scraper

# Terminal 3: Extractor worker
make worker-extractor

# Terminal 4: Start ingestion orchestration
make ingest-celery
```

**Option B: Direct execution**

```bash
make ingest    # Discovery + scraping
make extract   # Extraction pipeline
```

### 4. Run the Application

```bash
# Terminal: API server (port 8000)
make api

# Terminal: Web UI (port 3000)
make ui
```

Access the UI at **http://localhost:3000**

### 5. Verify

```bash
# Health check
curl http://localhost:8000/health

# Validation suite
make validate
```

`make validate` expects the API and UI to be running and Playwright available. If needed:
```bash
python -m playwright install chromium
```

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Common Crawl   │────▶│   Discovery     │────▶│   Scraper       │
│  CDX API        │     │   Service       │     │   Worker        │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web UI        │◀───▶│   API Service   │◀───▶│   PostgreSQL    │
│   (Next.js)     │     │   (FastAPI)     │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         ▲
                                                         │
┌─────────────────┐     ┌─────────────────┐     ┌────────┴────────┐
│   Ollama        │◀────│   Extractor     │────▶│   MinIO         │
│   (Local LLM)   │     │   Worker        │     │   (Raw Storage) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐     ┌─────────────────┐
│   OpenAI        │     │   Redis         │
│   (Search/Tier2)│     │   (Celery)      │
└─────────────────┘     └─────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Celery + Redis** | Crash-safe task queue with `acks_late=True` |
| **Two-tier LLM** | Local Ollama (free) for bulk, OpenAI for search/escalation |
| **MinIO for raw storage** | S3-compatible, stores original payloads for re-extraction |
| **Batched extraction** | Single LLM call per 20 jobs with per-job fallback for resiliency |

---

## Discovery (Common Crawl CDX)

The discovery service queries Common Crawl CDX API for indexed URLs matching:

- `boards.greenhouse.io/*`
- `boards-api.greenhouse.io/v1/boards/*`
- `jobs.lever.co/*`

### Token Extraction Rules

| Source | URL Pattern | Extracted Token |
|--------|-------------|-----------------|
| Greenhouse | `boards.greenhouse.io/{token}` | `source_key = token` |
| Lever | `jobs.lever.co/{site}` | `source_key = site` |

### Validation

A source is marked `valid` if its list endpoint returns HTTP 200. Invalid sources are not retried for 7 days.

---

## Rate Limit Handling

We implement compliant rate limiting, not adversarial bypass:

| Host | Max Concurrent | Retry Codes | Backoff |
|------|---------------|-------------|---------|
| `boards-api.greenhouse.io` | 5 | 429, 500-504 | 2s→4s→8s→16s→32s |
| `api.lever.co` | 5 | 429, 500-504 | 2s→4s→8s→16s→32s |

After 5 retries, tasks move to the dead letter queue (`dlq.scrape`).

---

## Operational FAQ

### How do you handle 50k requests without getting banned?
- Use Common Crawl discovery to avoid crawling arbitrary pages and focus on public posting APIs.
- Enforce per-host concurrency caps (5) and centralized rate limiting via Redis.
- Retry only on `429/5xx` with exponential backoff (2s → 4s → 8s → 16s → 32s).
- Skip invalid sources for 7 days to avoid repeated failing calls.

### How much would this run cost in LLM tokens?
- Tier 1 runs on local Ollama, so there is no per-token API cost.
- Tier 2 is optional; the report uses average tokens per escalation and the pricing constants below.
- Estimated tokens = `jobs_escalated_t2 * (avg_input_tokens + avg_output_tokens)`.
- Run `make report` for a cost estimate based on actual counts.

### How would you scale this to 1 Million jobs?
See **Scaling to 1,000,000 Jobs** below (queue sharding, autoscaling, partitioning, and search offload).

---

## LLM Pipeline

### Two-Tier Architecture

| Tier | Model | Batch Size | When Used |
|------|-------|------------|-----------|
| **Tier 1** | Ollama (qwen3:4b) | 20 jobs | Default for all jobs |
| **Tier 2** | OpenAI/Anthropic | 1 job | Low confidence escalation (optional) |

### Tier 1 Model Selection

| Model | Size | Speed | Quality | Recommended For |
|-------|------|-------|---------|-----------------|
| `qwen3:4b` | 2.5GB | ~3-5s/job | Excellent | Best balanced |
| `llama3` | 4.7GB | ~20s/job | Good | Default |
| `phi4:14b` | 8GB | ~8s/job | Excellent | Higher quality |

### Tier 2 Routing Rules

Escalate to Tier 2 when ANY is true:
- `confidence < 0.60`
- Missing `company_name`, `role_title`, or `job_summary`
- `skills_raw` empty AND text length > 800 characters

### Extracted Schema (`job_extracted_v1`)

```json
{
  "source_type": "greenhouse | lever",
  "source_key": "string",
  "source_job_id": "string",
  "company_name": "string",
  "company_domain": "string | null",
  "role_title": "string",
  "seniority_level": "intern | junior | mid | senior | staff | principal | manager | director | vp | cxo | unknown",
  "job_function": "sales | revops | marketing | engineering | ...",
  "location_city": "string | null",
  "location_state": "string | null",
  "location_country": "string | null",
  "remote_type": "onsite | hybrid | remote | unknown",
  "employment_type": "full_time | part_time | contract | internship | temporary | unknown",
  "salary_min_usd": "int | null",
  "salary_max_usd": "int | null",
  "job_summary": "string (max 60 words)",
  "key_functions_hired_for": ["string"],
  "skills_raw": ["skill1", "skill2"],
  "tools_raw": ["tool1", "tool2"],
  "highlights": [{"label": "string", "text": "string", "start_char": 0, "end_char": 10}],
  "confidence": 0.85,
  "needs_tier2": false
}
```

---

## Cost Estimation

After each run, a report is generated at `reports/run_{timestamp}.json` (values below are illustrative):

```json
{
  "jobs_ingested": 50000,
  "jobs_extracted_t1": 48500,
  "jobs_escalated_t2": 1500,
  "tier2_tokens_in_total": 3000000,
  "tier2_tokens_out_total": 750000,
  "tier2_estimated_cost_usd": 18.00,
  "top_20_skills_by_count": [...]
}
```

### Tier 2 Pricing Constants

| Provider | Input (per 1M) | Output (per 1M) |
|----------|---------------|-----------------|
| OpenAI (default) | $3.00 | $12.00 |
| Anthropic (default) | $3.00 | $15.00 |

---

## API & UI Notes

- All API responses include `request_id` in the JSON body and `X-Request-Id` header.
- `/jobs` supports full-text search (Postgres FTS) with fallback to `LIKE` and supports `skill` filters.
- `/skills/suggest` returns top prefix matches across canonical names and aliases.
- The Jobs UI includes a skills typeahead filter that maps to canonical skill names.

---

## Scaling to 1,000,000 Jobs

### 1. Queue Sharding
Partition queues by `source_type` (Greenhouse/Lever) for parallel processing.

### 2. Autoscaling Workers
Scale Celery workers based on queue depth using Kubernetes HPA or AWS ECS.

### 3. Database Partitioning
Partition `job_raw` and `job` tables by month or source_type for faster queries.

### 4. Search Backend
Replace PostgreSQL FTS with OpenSearch/Elasticsearch for sub-second faceted search.

### 5. Incremental Updates
Only process jobs where `content_hash` has changed since last scrape.

### 6. Reduce Tier 2 Usage
Improve Tier 1 prompts and raise confidence thresholds to minimize premium API calls.

---

## Environment Variables

See `.env.example` for the complete list with descriptions.

### Infrastructure
| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_URL` | `postgresql://gtm:gtm_password@localhost:5433/gtm_engine` | Database URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker |
| `S3_ENDPOINT` | `http://localhost:9000` | MinIO endpoint |
| `S3_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `S3_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `S3_BUCKET` | `gtm-raw` | Raw payload bucket |

### LLM
| Variable | Default | Description |
|----------|---------|-------------|
| `TIER1_PROVIDER` | `ollama` | `ollama` (local) or `openai` |
| `TIER1_MODEL_NAME` | `qwen3:4b` | Model for extraction |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Tier 1 LLM |
| `TIER2_PROVIDER` | `disabled` | `openai`, `anthropic`, or `disabled` |
| `OPENAI_API_KEY` | - | Required for search parsing |
| `ANTHROPIC_API_KEY` | - | Optional for Tier 2 |

### Pipeline
| Variable | Default | Description |
|----------|---------|-------------|
| `TARGET_JOB_COUNT` | `50000` | Ingestion target |
| `TIER1_BATCH_SIZE` | `20` | Jobs per Tier 1 batch |

---

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make up` | Start Docker containers |
| `make down` | Stop Docker containers |
| `make migrate` | Run Alembic migrations |
| `make seed` | Seed canonical skills |
| `make ingest` | Run discovery + scraping |
| `make ingest-celery` | Celery-based ingestion orchestration |
| `make extract` | Run extraction pipeline |
| `make extract-celery` | Celery-based extraction orchestration |
| `make worker-scraper` | Start scraper Celery worker |
| `make worker-extractor` | Start extractor Celery worker |
| `make api` | Start API server |
| `make ui` | Start web UI |
| `make flower` | Start Celery monitoring dashboard |
| `make validate` | Run acceptance tests |
| `make report` | Generate run report |

---

## Design Decisions & Tradeoffs

### 1. Two-Tier LLM Architecture

**Decision**: Use local Ollama for bulk extraction, premium APIs for escalation.

**Tradeoff**: 
- ✅ Cost-effective for 50k+ jobs
- ✅ No rate limits with local models
- ❌ Slower per-request than cloud APIs
- ❌ Requires Ollama installation

**Alternative considered**: All-OpenAI with rate limiting. Rejected due to cost (~$50+ for 50k jobs vs ~$0 for Ollama).

### 2. Batch Size of 20

**Decision**: Process 20 jobs per LLM call.

**Tradeoff**:
- ✅ Reduces LLM overhead (1 call vs 20)
- ✅ Better context for extraction
- ❌ One failure affects entire batch
- ❌ Memory constraints on smaller models

### 3. Common Crawl for Discovery

**Decision**: Use Common Crawl CDX API instead of manual source lists.

**Tradeoff**:
- ✅ Automated, no manual curation
- ✅ Discovers new sources automatically
- ❌ CDX data may be stale (months old)
- ❌ Rate limited, slower discovery phase

### 4. Single-Threaded Ollama

**Decision**: Limit Celery concurrency to 1 when using Ollama.

**Tradeoff**:
- ✅ No request timeouts
- ✅ Predictable throughput
- ❌ Can't parallelize on single machine
- ❌ Full extraction takes ~24-48 hours

**Mitigation**: Can scale horizontally with multiple machines, each running Ollama.

### 5. PostgreSQL Full-Text Search

**Decision**: Use built-in Postgres FTS instead of Elasticsearch.

**Tradeoff**:
- ✅ Simpler infrastructure
- ✅ Good for 50k records
- ❌ Slower for faceted search at scale
- ❌ Would need migration for 1M+ jobs

---

## Assumptions Made

1. Common Crawl CDX is the primary discovery source (no manual source lists)
2. Only Greenhouse and Lever APIs are scraped (no HTML scraping)
3. Salary is extracted only when explicitly stated in text
4. Remote type defaults to "unknown" if not determinable
5. Company domain enrichment is deferred (stored as null in MVP)

---

## Troubleshooting

### Ollama Timeouts
```
error='timed out'
```
**Solution**: Reduce worker concurrency to 1:
```bash
celery -A shared.utils.celery_app worker -Q q.extract_t1 -l info -c 1
```

### OpenAI Rate Limits
```
429 Too Many Requests
```
**Solution**: Use Ollama for extraction, reserve OpenAI for search only:
```bash
TIER1_PROVIDER=ollama
```

### "ruthless removal did not work"
This is a benign log message from text cleaning, not an error.

---

## License

MIT
