# AI Clinic Booking Agent — Backend

Backend for an AI-first, multi-agent clinic booking assistant (FastAPI + Google ADK +
Gemini + Postgres + Qdrant). Design lives in
[ARCH-001](../../../01-docs/02-design/01-architecture.md); this README covers what
actually exists in this source tree today and how to run it locally.

## Status

All 16 backlog tasks in
[01-docs/99-project-management/backlog](../../../01-docs/99-project-management/backlog)
have code written. **Important:** tasks TASK-003 through TASK-016 were implemented in one
unattended overnight run, verified only by static checks (imports, ruff, synthetic-input unit
tests) — no live Postgres/Qdrant/Gemini was available in that session. Every task file's
Attempt log says exactly what was and wasn't checked. Treat this as "should work, not yet
proven against real infrastructure" until someone runs it end-to-end.

## Layout

Full rationale in ARCH-001 §4/§8. Short version:

| Path | What's there |
|---|---|
| `app/` | FastAPI composition root — app factory, ADK runtime (Orchestrator + placeholder-free real agents), booker agent conversation route (Layer-1 emergency screening + ADK Runner), `/api/v1` router. |
| `ai-agents/` | AI layer — Orchestrator + 4 domain agents (faq, symptom, booking, emergency), each with `agent.py`/`tools.py`/`prompt.py`. Note: this directory's hyphenated name can't be reached by a normal `import` statement — see `common/module_loader.py`. |
| `modules/` | Non-AI business layer — CRUD admin (booking, doctor, knowledge) + the RAG ingestion pipeline (chunk/embed/cron), adapted from `rag-health`. |
| `core/` | Generic CRUD base classes + `SlotTakenError`/`NotFoundError`/etc. Reused from `rag-health`. |
| `data/` | Data-access layer — one repository per table/collection (`booking_repository.py`, `doctor_repository.py`, `knowledge_repository.py`, `chunk_repository.py`, `ingestion_job_repository.py`, `qdrant_client.py`, `session.py`). |
| `common/` | Cross-cutting infra — `config.py`, `database.py`, `gemini_client.py`, `observability.py`, `resilience.py`, `module_loader.py`. |
| `eval/` | AI quality gate — 3 golden sets (≥10 items each, placeholder ids), `metrics.py` (formulas verified by real unit tests), `runner.py` (needs live infra, unexecuted). |
| `alembic/` | One hand-written revision (`0001_initial_schema.py`) covering all 6 tables, including the partial unique index for no-double-booking. Verified with `alembic upgrade/downgrade --sql` (offline SQL generation) — never run against a real Postgres. |
| `tests/` | Real assertions in `unit/test_settings_defaults.py` and `eval/test_retrieval_metrics.py`; everything else is either a skipped placeholder or gated behind live infra (`@pytest.mark.eval`, `@pytest.mark.llm`). |

## Requirements

- Python 3.12+
- Docker (for Postgres + Qdrant via `docker-compose.yml`)
- A Gemini API key

## Local setup

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -e ".[dev]"

cp .env.example .env        # fill in GEMINI_API_KEY, set a real POSTGRES_PASSWORD
```

Bring up the full stack:

```bash
docker compose up -d
```

`app` waits for Postgres/Qdrant to report healthy (compose healthchecks) before starting, and
runs `alembic upgrade head` automatically before serving (see `Dockerfile`'s `CMD`) — no manual
migration step.

Run the smoke test (one message per intent — faq/symptom/booking/emergency) against the running
stack:

```bash
python scripts/smoke_test.py
```

Run the (offline-safe) test suite:

```bash
pytest
```

Run the real AI quality gate (needs the live stack + `GEMINI_API_KEY`):

```bash
pytest -m eval
```

Lint:

```bash
ruff check .
```

## Configuration

All settings are in `common/config.py` (Pydantic Settings, loaded from `.env`). Notably:

- `GEMINI_API_KEY`, `GEMINI_LLM_MODEL`, `GEMINI_EMBEDDING_MODEL` — model choice is
  env-driven, never hardcoded (ADR-0006).
- `POSTGRES_*` / `QDRANT_HOST`/`QDRANT_PORT`/`QDRANT_COLLECTION` — composed into
  `database_url` / `qdrant_url` properties on `Settings`.
- `SIMILARITY_THRESHOLD`/`TOP_K` — RAG grounding cutoff (ADR-0008) and result count.
- `EMBEDDING_BATCH_SIZE` and the `semantic_chunker_*`/`chunk_*`/`cron_*` fields drive the
  knowledge ingestion pipeline (`modules/knowledge_ingestion/`).

See `.env.example` for the full list with defaults.

## Known gaps (see `.claude/memory/` for the full write-up)

- `ai-agents/`'s hyphenated directory name blocks normal `import` statements from outside
  it — worked around with `common/module_loader.py`, but a rename to `ai_agents` would be
  cleaner if the team decides to update ARCH-001 to match.
- Clinic hours/slot duration (`data/booking_repository.py`'s `CLINIC_OPEN_HOUR` etc.) are a
  judgment call — no doc pins these values.
- Golden sets in `eval/` use placeholder ids until real seed data exists.
