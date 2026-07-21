FROM python:3.12-slim

WORKDIR /app

# `pip install .` needs the actual package source (app/, core/, data/,
# common/, modules/, eval/) to resolve setuptools' packages.find, so the
# source has to be copied before install — a pyproject.toml-first layer
# wouldn't give any real caching benefit here since this installs the local
# project itself, not just its third-party dependencies.
COPY . .
RUN pip install --no-cache-dir .

# Demo deploy note (branch demo/deploy-render, docs/render-deploy.md): this same image is
# also what's deployed to Render.com (Web Service, Docker runtime) for the live demo.
# Render injects the port the container must listen on via the $PORT env var — it is NOT
# fixed at 8000/7860 like some other PaaS free tiers, and can change between deploys, so the
# CMD below reads it at container start instead of hardcoding a port. EXPOSE 8000 is just
# documentation (Render ignores it and reads $PORT itself); ${PORT:-8000} keeps local
# docker-compose/`docker run` unchanged since docker-compose.yml never sets PORT. Postgres/
# Qdrant are managed external services in the Render deploy (Neon/Supabase, Qdrant Cloud)
# reachable purely via env vars (Render Dashboard → Environment); nothing in this Dockerfile
# or the app depends on docker-compose.yml's postgres/qdrant containers.
EXPOSE 8000

# Run migrations then serve — "automatic on first boot", no separate manual
# step (TASK-016 DoD). Safe to re-run: alembic upgrade head is idempotent
# once the schema is at head.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
