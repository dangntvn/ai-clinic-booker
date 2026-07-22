# Deploying to Render.com (demo)

| | |
|---|---|
| **Scope** | `demo/deploy-render` branch only — never merged to `main` |
| **Author** | Dang NT |
| **Date** | 2026-07-21 |
| **Related** | `Dockerfile`, `render.yaml`, `common/config.py`, `.env.example` |

This branch adapts the backend to run as a single Docker container on Render.com's free Web
Service tier. It intentionally diverges from `main`: no docker-compose stack, Postgres and
Qdrant are managed external services instead of sibling containers, because Render's free tier
only runs one container per service.

This is a deliberate, scoped override of [ADR-0010](../../../../01-docs/02-design/ADR/0010-self-host-docker.md)
("self-host the whole stack via docker-compose, avoid a cloud vendor's proprietary managed
service") — for this demo-only branch specifically, not a change to the ADR itself or to
`main`. `main`'s docker-compose-based self-hosted stack is untouched.

## History note — this branch was HF Space first

This branch previously targeted Hugging Face Spaces (`demo/deploy-hf-space`, this same file at
`docs/hf-space-deploy.md`). CEO decision 2026-07-21: switch to Render.com free tier instead
(HF Space costs money for the resources this demo needs). The branch was renamed
`demo/deploy-render`; HF-Space-specific files (`README.hfspace.md`, the old
`docs/hf-space-deploy.md`) were removed/renamed accordingly. The Postgres/Qdrant managed-service
adaptation (`common/config.py`'s `postgres_ssl`/`qdrant_https`/`qdrant_api_key`, wired into
`common/database.py`/`dal/qdrant_client.py`/`alembic/env.py`/`dal/session.py`/
`modules/knowledge_ingestion/cron.py`) is unchanged by this switch — Neon/Supabase + Qdrant
Cloud are still the managed services used, independent of which platform hosts the container.

## What changed vs. `main`

- `Dockerfile` — `CMD` now reads the listen port from the `$PORT` environment variable
  (`--port ${PORT:-8000}`) instead of hardcoding `8000`. **This is required, not cosmetic**:
  Render injects its own `$PORT` value into the container (it is not guaranteed to be 8000, and
  can differ between services/deploys) and expects the process to bind to it — a hardcoded port
  would make health checks and routing fail. `${PORT:-8000}` falls back to `8000` when `$PORT`
  is unset, so local `docker-compose up`/`docker run` (which never sets `PORT`) is unaffected.
  `EXPOSE 8000` stays as documentation only; Render does not read it.
- `common/config.py` / `dal/qdrant_client.py` / `common/database.py` / `alembic/env.py` /
  `dal/session.py` / `modules/knowledge_ingestion/cron.py` — added three new **opt-in,
  default-off** settings needed for managed services that plain docker-compose Postgres/Qdrant
  never required:
  - `QDRANT_HTTPS` (bool, default `false`) — Qdrant Cloud is HTTPS-only.
  - `QDRANT_API_KEY` (default empty) — Qdrant Cloud requires an `api-key` header; local
    docker-compose Qdrant has no auth. Without this, every retrieval call to Qdrant Cloud would
    fail (403), which would silently degrade every RAG-grounded answer to the
    not-found/abstain fallback — not a startup crash, so worth calling out explicitly.
  - `POSTGRES_SSL` (bool, default `false`) — Neon/Supabase reject non-SSL connections outright.
    Implemented as SQLAlchemy `connect_args`, not a `database_url` query-string param, because
    asyncpg (the app's async driver) and psycopg (alembic's sync driver) disagree on the
    param name (`ssl` vs. `sslmode`) — see the docstrings on
    `Settings.postgres_async_connect_args` / `postgres_sync_connect_args`. Applied consistently
    across **every** place that opens its own Postgres engine: the app's main async engine
    (`common/database.py`), Alembic's sync engine (`alembic/env.py`), the ADK
    `DatabaseSessionService`'s own async engine (`dal/session.py`), and APScheduler's
    `SQLAlchemyJobStore` sync engine (`modules/knowledge_ingestion/cron.py`) — the latter two
    each create their own engine independently of `common/database.py` and were missed in an
    earlier pass of this adaptation, then fixed once `code-reviewer` flagged it.
  - None of these change default behavior for local dev (`docker-compose.yml` unchanged,
    unaffected — all three default off/empty).
- `common/config.py` / `app/main.py` — added a fourth opt-in, default-**on** setting,
  `ENABLE_INGESTION_CRON` (bool, default `true`): when set to `false`, `app/main.py`'s
  `_lifespan` skips calling `modules/knowledge_ingestion/cron.setup_scheduler()` /
  `scheduler.start()` entirely (logs `ingestion_cron.disabled` instead) — the ingestion cron
  code itself is untouched, just not started. This Render demo deploy is the only place that
  sets it to `false` (CEO runs the ingestion/cron pipeline on a local machine instead; Render
  only needs to serve chat/API). Local docker-compose and every other deploy keep the cron
  running as before unless this is explicitly set.
- `render.yaml` (new file, root of this repo) — a Render Blueprint declaring the Web Service
  (Docker runtime, health check path `/health`) and the full list of environment variable
  *names* this app needs, so connecting the repo in the Render dashboard pre-fills the
  Environment tab instead of the CEO having to type every key by hand. Values still have to be
  filled in manually for anything secret (Render Blueprints intentionally never store secret
  values in the repo) — see the table below.
- `README.hfspace.md` — removed (HF-Space-only frontmatter, not applicable to Render).
- This file (renamed from `docs/hf-space-deploy.md`).

## Deploying — steps (Render Dashboard)

1. Push this branch (`demo/deploy-render`) to the repo's remote if not already there.
2. In the Render Dashboard: **New → Web Service**.
3. Connect the GitHub repo, select branch **`demo/deploy-render`**.
4. Runtime: **Docker** (Render auto-detects the root `Dockerfile`; no build/start command
   fields to fill in manually).
5. Plan: **Free**.
6. Health Check Path: **`/health`** (already exposed by `app/main.py`, returns
   `{"status": "ok"}`).
7. If `render.yaml` is present and detected, Render offers to use it as a Blueprint — this
   pre-fills the service definition and the env var *names* below (values still manual). If not
   using the Blueprint flow, configure the service fields above manually and add every env var
   from the table below under **Environment**.
8. Trigger the first deploy. Watch the build logs — `pip install --no-cache-dir .` then the
   container starts with `alembic upgrade head && uvicorn ...`.

## Deploying all 3 language servers (ADR-0023/ADR-0024)

`render.yaml` on this branch now declares **three** Web Services —
`ai-clinic-booker-backend-vn` / `-jp` / `-en` — one process per `LANG_SUFFIX`, all sharing the
same Postgres and Qdrant Cloud instances (see ADR-0023 for why: language isolation is at the
process level, business data stays shared, only RAG content + `doctors`/`bookings`/
`chat_session_links` are suffixed per language per ADR-0024). Steps:

1. Same repo/branch/Dockerfile/health-check as the single-service flow above — the difference is
   there are now 3 service definitions in `render.yaml` instead of 1.
2. If using the Blueprint flow (step 7 above), Render will offer to create all 3 services from
   one `render.yaml` at once. **Do not let it deploy all 3 simultaneously on the first-ever
   migrate.** See the sequencing constraint below — either create them one at a time in the
   dashboard, or create all 3 as Blueprint resources but pause/suspend `-jp` and `-en` before the
   first deploy, then resume them in order once `-vn` has migrated.
3. Fill in the **same** `POSTGRES_*` / `QDRANT_HOST` / `QDRANT_API_KEY` secret values (`sync:
   false` vars) in all three services' Environment tabs — they point at the one shared managed
   Postgres/Qdrant Cloud instance. `QDRANT_COLLECTION` and `LANG_SUFFIX` are the only two vars
   that must differ per service, and `render.yaml` already sets those correctly per block.
4. Set `ALLOWED_ORIGINS` per service to whichever frontend origin serves that language (or the
   same origin for all three if one widget deployment switches language client-side).

### Migrate sequentially — mandatory on first deploy only

ADR-0023's idempotent-migration guard (`_table_exists()` in
`alembic/versions/0001_initial_schema.py`) is check-then-act, not atomic. If two services run
`alembic upgrade head` against the shared Postgres at the same moment during the very first
migration, there's a race: both can see "table doesn't exist yet" and both attempt
`CREATE TABLE`, and the loser crashes. Once every service has migrated at least once, this is no
longer a concern (subsequent deploys/restarts are no-ops for already-applied revisions), but the
first migration on a fresh shared database **must** happen one service at a time:

1. Deploy `ai-clinic-booker-backend-vn` first. Watch its deploy logs until `alembic upgrade
   head` completes and `uvicorn` starts serving (health check goes green).
2. Only then deploy `ai-clinic-booker-backend-jp`. Same wait-for-green-health-check step.
3. Only then deploy `ai-clinic-booker-backend-en`.
4. After all three have migrated once, redeploys/restarts of any service can happen in any order
   or in parallel — the race window only exists on the first-ever `alembic upgrade head` against
   an empty shared database.

## Frontend routing to 3 backends

Each language server has its own base URL (3 separate Render services = 3 separate `.onrender.com`
hostnames, or 3 custom subdomains if mapped). Whatever selects the chat widget's language
(locale switcher, subdomain, `Accept-Language`) must point the widget at the matching backend's
URL — there is no single shared endpoint that routes by request the way a phương án A
multi-tenant server would (see ADR-0023 Context for why phương án B was chosen instead).

## Required environment variables (Render Dashboard → Environment)

Copy every variable in `.env.example` on this branch. The ones that **must** be filled with
real values for the demo to work (everything else already has a usable default in
`.env.example`):

| Variable | Set to |
|---|---|
| `GEMINI_API_KEY` | Real Gemini API key |
| `ALLOWED_ORIGINS` | The frontend's origin (e.g. the widget demo-site URL), comma-separated if more than one. Functionally `*` would still work (this app's `CORSMiddleware` doesn't set `allow_credentials=True`), but a public demo shouldn't leave the API open to every origin — set the real frontend origin once it's known. |
| `POSTGRES_HOST` | Neon/Supabase host |
| `POSTGRES_PORT` | Usually `5432` |
| `POSTGRES_DB` | Database name from the Neon/Supabase project |
| `POSTGRES_USER` | Database user from the Neon/Supabase project |
| `POSTGRES_PASSWORD` | Database password from the Neon/Supabase project |
| `POSTGRES_SSL` | `true` |
| `QDRANT_HOST` | Qdrant Cloud cluster host (no scheme, e.g. `xxxx-xxxx.aws.cloud.qdrant.io`) |
| `QDRANT_PORT` | Usually `6333` |
| `QDRANT_HTTPS` | `true` |
| `QDRANT_API_KEY` | Qdrant Cloud cluster API key |
| `QDRANT_COLLECTION` | Collection name — keep in sync with whatever ingestion writes to |
| `ENABLE_INGESTION_CRON` | `false` — CEO runs the ingestion/cron pipeline (`modules/knowledge_ingestion/cron.py`) on a local machine instead; this Render deploy only needs to serve chat/API traffic. Defaults to `true` (cron runs in-process) everywhere else — local docker-compose is unaffected unless this is explicitly set. See `common/config.py::Settings.enable_ingestion_cron` / `app/main.py::_lifespan` for how the scheduler start is skipped (code untouched, just not invoked). |

Everything else (`APP_ENV`, `LOG_LEVEL`, `CHAT_RATE_LIMIT_PER_MINUTE`, per-agent
`{ORCHESTRATOR,BOOKING,SYMPTOM,FAQ,EMERGENCY}_LLM_*`, `SIMILARITY_THRESHOLD`,
`FAQ_SIMILARITY_THRESHOLD`, `TOP_K`, ingestion `EMBEDDING_BATCH_SIZE`, etc.) can be left at the
`.env.example` defaults for the demo.

**Do not set `PORT`** — Render injects it itself; the Dockerfile's `CMD` reads whatever value
Render provides. Setting it manually is unnecessary and could conflict with what Render assigns.

## Free tier cold start — not a bug

Render's free Web Service tier spins the container down after ~15 minutes with no incoming
requests, and spins it back up on the next request. The first request after an idle period will
take roughly **30–60 seconds** to respond while the container boots (image already built, so
this is process start + `alembic upgrade head` + Gemini/DB/Qdrant client warmup, not a rebuild).
This is an inherent free-tier limitation, not an application bug — CEO/demo viewers should be
told to expect it, especially right after a period of no traffic.

## Not covered by this branch

- Knowledge ingestion (populating Qdrant with the clinic's actual content) still has to be run
  once against the managed Qdrant Cloud instance — same `modules/knowledge_ingestion` pipeline,
  just pointed at the service's env vars instead of local docker-compose. This is intentional
  and expected with `ENABLE_INGESTION_CRON=false` set on Render (see above): CEO runs that
  pipeline from a local machine against the same Postgres/Qdrant Cloud instances, so the
  in-process cron on Render would otherwise just be redundant polling.
- No CI/CD wired up; deploying is triggered by pushing to `demo/deploy-render` (Render can
  auto-deploy on push if configured in the dashboard) or a manual redeploy from the dashboard.
- No eval/DeepEval run as part of this deploy — out of scope per the task this branch was
  created for.
