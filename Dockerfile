FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY . .

# Run migrations then serve — "automatic on first boot", no separate manual
# step (TASK-016 DoD). Safe to re-run: alembic upgrade head is idempotent
# once the schema is at head.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
