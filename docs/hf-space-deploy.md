# Deploying to Hugging Face Spaces (demo)

| | |
|---|---|
| **Scope** | `demo/deploy-hf-space` branch only — never merged to `main` |
| **Author** | Dang NT |
| **Date** | 2026-07-21 |
| **Related** | `Dockerfile`, `common/config.py`, `README.hfspace.md`, `.env.example` |

This branch adapts the backend to run as a single Docker container on Hugging Face Spaces
(free tier). It intentionally diverges from `main`: no docker-compose stack, Postgres and
Qdrant are managed external services instead of sibling containers, because HF Spaces' free
tier only runs one container per Space.

This is a deliberate, scoped override of [ADR-0010](../../../../01-docs/02-design/ADR/0010-self-host-docker.md)
("self-host the whole stack via docker-compose, avoid a cloud vendor's proprietary managed
service") — for this demo-only branch specifically, not a change to the ADR itself or to
`main`. `main`'s docker-compose-based self-hosted stack is untouched.

## What changed vs. `main`

- `Dockerfile` — added `EXPOSE 8000` and a comment; **no functional change** to the
  install/CMD steps. The image still runs `alembic upgrade head && uvicorn ...` on container
  start, same as local docker-compose.
- `common/config.py` / `dal/qdrant_client.py` / `common/database.py` / `alembic/env.py` — added
  three new **opt-in, default-off** settings needed for managed services that plain
  docker-compose Postgres/Qdrant never required:
  - `QDRANT_HTTPS` (bool, default `false`) — Qdrant Cloud is HTTPS-only.
  - `QDRANT_API_KEY` (default empty) — Qdrant Cloud requires an `api-key` header; local
    docker-compose Qdrant has no auth. Without this, every retrieval call to Qdrant Cloud would
    fail (403), which would silently degrade every RAG-grounded answer to the
    not-found/abstain fallback — not a startup crash, so worth calling out explicitly.
  - `POSTGRES_SSL` (bool, default `false`) — Neon/Supabase reject non-SSL connections outright.
    Implemented as SQLAlchemy `connect_args`, not a `database_url` query-string param, because
    asyncpg (the app's async driver) and psycopg (alembic's sync driver) disagree on the
    param name (`ssl` vs. `sslmode`) — see the docstrings on
    `Settings.postgres_async_connect_args` / `postgres_sync_connect_args`.
  - None of these change default behavior for local dev (`docker-compose.yml` unchanged,
    unaffected — all three default off/empty).
- `README.hfspace.md` (new file, root of this repo) — HF Space frontmatter (`sdk: docker`,
  `app_port: 8000`, etc). **Not** a rename/edit of the existing `README.md` — see
  "README caveat" below for why, and what to do with it at actual deploy time.
- This file.

## Why no separate `Dockerfile.hfspace`

HF Spaces (Docker SDK) always builds the file literally named `Dockerfile` at the Space repo
root — there's no documented frontmatter key to point it at an alternate filename. A
`Dockerfile.hfspace` would simply never be picked up, so editing the one `Dockerfile` in place
was the only option that actually works, not just the simpler one. This is safe here because
`demo/deploy-hf-space` is a standalone branch never merged back to `main` — local dev on `main`
is untouched, and docker-compose on *this* branch still works unchanged (`build: .` still
resolves to the same, backward-compatible Dockerfile).

## README caveat — read before deploying

HF Spaces discovers Space metadata (title, SDK, `app_port`, etc.) **only** from the YAML
frontmatter of a file literally named `README.md` at the Space's git repo root. This repo
already has a `README.md` at root (the project's portfolio-facing write-up) which the task
explicitly said not to overwrite. `README.hfspace.md` in this branch holds the required
frontmatter + a short demo-specific blurb instead.

**When you actually push this repo to the HF Space's own git remote**, the file that ends up
named `README.md` in *that* remote is what HF reads — it does not have to be identical to this
branch's `README.md`. Two ways to do that without touching this branch's `README.md`:

1. Push this branch as-is, then in the Space's git working copy (or via the HF web UI file
   editor) replace `README.md` with the contents of `README.hfspace.md`, and delete/keep the
   original under a different name — whichever you'd rather have visible on the Space page.
2. Or, if you'd rather the Space page show the full project README, prepend the frontmatter
   block from `README.hfspace.md` to the top of the existing `README.md` in the Space's copy
   only (not in this git branch).

Either way this is a one-time step on the Space side, not something this branch's code needs to
handle.

## Required environment variables (HF Space → Settings → Repository secrets)

Copy every variable in `.env.example` on this branch into the Space's secrets. The ones that
must be filled with **real values** for the demo to work (everything else already has a usable
default in `.env.example`):

| Variable | Set to |
|---|---|
| `GEMINI_API_KEY` | Real Gemini API key |
| `ALLOWED_ORIGINS` | The Vercel frontend's origin (e.g. `https://<project>.vercel.app`), comma-separated if more than one. Functionally `*` would still work (this app's `CORSMiddleware` doesn't set `allow_credentials=True`), but a public demo shouldn't leave the API open to every origin — set the real Vercel origin once it's known. |
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

Everything else (`APP_ENV`, `LOG_LEVEL`, `CHAT_RATE_LIMIT_PER_MINUTE`, per-agent
`{ORCHESTRATOR,BOOKING,SYMPTOM,FAQ,EMERGENCY}_LLM_*`, `SIMILARITY_THRESHOLD`,
`FAQ_SIMILARITY_THRESHOLD`, `TOP_K`, ingestion `EMBEDDING_BATCH_SIZE`, etc.) can be left at the
`.env.example` defaults for the demo.

## Not covered by this branch

- Knowledge ingestion (populating Qdrant with the clinic's actual content) still has to be run
  once against the managed Qdrant Cloud instance — same `modules/knowledge_ingestion` pipeline,
  just pointed at the Space's env vars instead of local docker-compose.
- No CI/CD wired up; deploying is a manual `git push` to the Space's remote.
- No eval/DeepEval run as part of this deploy — out of scope per the task this branch was
  created for.
