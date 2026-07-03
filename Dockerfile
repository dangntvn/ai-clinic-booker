FROM python:3.12-slim

WORKDIR /app

# `pip install .` needs the actual package source (app/, core/, data/,
# common/, modules/, eval/) to resolve setuptools' packages.find, so the
# source has to be copied before install — a pyproject.toml-first layer
# wouldn't give any real caching benefit here since this installs the local
# project itself, not just its third-party dependencies.
COPY . .
RUN pip install --no-cache-dir .

# Run migrations then serve — "automatic on first boot", no separate manual
# step (TASK-016 DoD). Safe to re-run: alembic upgrade head is idempotent
# once the schema is at head.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
