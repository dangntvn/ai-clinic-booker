# AI Clinic Booking Agent — Backend

Backend for an AI-first, multi-agent clinic booking assistant (FastAPI + Google ADK +
Gemini + Postgres + Qdrant). Design lives in
[ARCH-001](../../../01-docs/02-design/01-architecture.md); this README covers what
actually exists in this source tree today and how to run it locally.

## Status

Built via the backlog in
[01-docs/99-project-management/backlog](../../../01-docs/99-project-management/backlog):

- [TASK-001](../../../01-docs/99-project-management/backlog/TASK-001-scaffold-project-structure.md) — done. Full directory/file skeleton per ARCH-001 §8, stubs only.
- [TASK-002](../../../01-docs/99-project-management/backlog/TASK-002-reuse-core-common-rag-health.md) — done. `core/` (generic CRUD base classes) and `common/` (config, Gemini client, observability, resilience) are real, working code reused/adapted from `rag-health`.
- Everything else (`ai-agents/`, `modules/`, `data/` repositories, `app/`) is still stub-only — `pass` / `raise NotImplementedError`.

## Layout

Full rationale in ARCH-001 §4/§8. Short version:

| Path | What's there |
|---|---|
| `app/` | FastAPI composition root — app factory, ADK runtime wiring, webhook, API router. Stub. |
| `ai-agents/` | AI layer — orchestrator + domain agents (faq, symptom, booking, emergency) and their prompts/tools. Stub. |
| `modules/` | Non-AI business layer — CRUD admin (booking, doctor, knowledge) + the RAG ingestion pipeline. Stub. |
| `core/` | Generic CRUD base classes (`BaseModel`, `BaseRepository`, `BaseService`, `StandardResponse`/`PaginatedResponse`, `AppException` hierarchy). **Implemented**, reused from rag-health. |
| `data/` | Data-access layer — one repository per table/collection, the only place that knows real schema. Stub except `qdrant_client.py`. |
| `common/` | Cross-cutting infra — `config.py` (Pydantic Settings), `database.py` (async SQLAlchemy engine/session), `gemini_client.py` (`embed_batch`/`generate`), `observability.py` (structlog + OTel), `resilience.py` (`gemini_retry`). **Implemented**. |
| `eval/` | AI quality gate (retrieval/intent/faithfulness metrics + golden sets). Stub. |
| `alembic/` | DB migrations. Stub. |
| `tests/` | `unit/`, `integration/`, `eval/`. Only `tests/unit/test_settings_defaults.py` has real assertions today; the rest are skipped placeholders. |

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

cp .env.example .env        # fill in GEMINI_API_KEY at minimum
```

Bring up Postgres + Qdrant:

```bash
docker compose up -d postgres qdrant
```

Run the test suite:

```bash
pytest
```

Lint:

```bash
ruff check .
```

There is no runnable app yet — `app/main.py:create_app()` is a stub. `docker compose up app`
will build but the container has nothing to serve until the AI/module layers land.

## Configuration

All settings are in `common/config.py` (Pydantic Settings, loaded from `.env`). Notably:

- `GEMINI_API_KEY`, `GEMINI_LLM_MODEL`, `GEMINI_EMBEDDING_MODEL` — model choice is
  env-driven, never hardcoded (ADR-0006).
- `POSTGRES_*` / `QDRANT_HOST`/`QDRANT_PORT` — composed into `database_url` /
  `qdrant_url` properties on `Settings`.
- `EMBEDDING_BATCH_SIZE` and the `semantic_chunker_*`/`chunk_*`/`cron_*` fields exist
  now for the ingestion pipeline reuse in TASK-003, even though that pipeline isn't
  wired up yet.

See `.env.example` for the full list with defaults.
