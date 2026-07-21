FROM python:3.12-slim

WORKDIR /app

# `pip install .` needs the actual package source (app/, core/, data/,
# common/, modules/, eval/) to resolve setuptools' packages.find, so the
# source has to be copied before install — a pyproject.toml-first layer
# wouldn't give any real caching benefit here since this installs the local
# project itself, not just its third-party dependencies.
COPY . .
RUN pip install --no-cache-dir .

# Demo deploy note (branch demo/deploy-hf-space, docs/hf-space-deploy.md): this same image is
# also what's pushed to the HF Space (Docker SDK) for the live demo. HF Spaces proxies traffic
# to whatever port the Space's README.md frontmatter declares via `app_port` — set to 8000 there
# so this port doesn't need to change. Postgres/Qdrant are managed external services in that
# deploy (Neon/Supabase, Qdrant Cloud) reachable purely via env vars (HF Space Secrets); nothing
# in this Dockerfile or the app depends on docker-compose.yml's postgres/qdrant containers.
EXPOSE 8000

# Run migrations then serve — "automatic on first boot", no separate manual
# step (TASK-016 DoD). Safe to re-run: alembic upgrade head is idempotent
# once the schema is at head.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
