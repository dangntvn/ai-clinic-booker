# Copyright 2026 DANG NT (dangnt.vn@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Description: APScheduler-based background scheduler for the ingestion
#              pipeline — polls ingestion_jobs, dispatches to
#              job_chunk/job_embedding, sweeps stuck jobs, retries failed
#              ones (ADR-0021). Adapted from rag-health's cron.py.
###############################################################################

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from common.config import settings
from common.database import AsyncSessionFactory
from common.observability import get_logger
from dal.lang_tables import ingestion_jobs_table
from modules.knowledge_ingestion import job_chunk, job_embedding

logger = get_logger(__name__)

# Suffixed per-language table name (multi-server deploy, 2026-07-22) — this module
# polls ingestion_jobs with raw SQL (not the ORM), so it must build the same
# settings.lang_suffix-suffixed name as dal/ingestion_job_repository.py's
# IngestionJob model rather than the old bare "ingestion_jobs" name, which no
# longer exists after alembic/versions/0002_partition_knowledge_by_language.py.
# Safe to interpolate directly (not a bind param — SQL can't parameterise
# identifiers): lang_suffix is restricted to {"vn", "jp", "en"} by
# Settings._validate_lang_suffix, never derived from unsanitised input.
_INGESTION_JOBS_TABLE = ingestion_jobs_table(settings.lang_suffix)

# APScheduler requires a synchronous SQLAlchemy URL for its job store; psycopg
# (v3, sync mode) is the driver installed in pyproject.toml, not psycopg2.
_sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg")

# SQLAlchemyJobStore.__init__(url=..., engine_options=None, ...) forwards
# engine_options straight to create_engine(url, **engine_options) (verified against the
# installed apscheduler source) — passing connect_args here (same sslmode
# settings.postgres_sync_connect_args used by alembic/env.py) keeps this jobstore's
# engine consistent with the rest of the app's SSL handling for managed Postgres.
scheduler = AsyncIOScheduler(
    jobstores={
        "default": SQLAlchemyJobStore(
            url=_sync_db_url,
            engine_options={"connect_args": settings.postgres_sync_connect_args},
        )
    }
)


async def poll_chunk_jobs() -> None:
    """Poll for pending_chunk jobs and process up to a batch of them."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text(
                f"SELECT id FROM {_INGESTION_JOBS_TABLE} WHERE status = 'pending_chunk' "
                "ORDER BY created_at ASC LIMIT :limit"
            ),
            {"limit": settings.ingestion_job_batch_size},
        )
        job_ids = [row[0] for row in result.fetchall()]

    logger.info("poll_chunk.found", count=len(job_ids))
    for job_id in job_ids:
        async with AsyncSessionFactory() as session:
            await job_chunk.run(job_id, session)


async def poll_embed_jobs() -> None:
    """Poll for pending_embed jobs and process up to a batch of them."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text(
                f"SELECT id FROM {_INGESTION_JOBS_TABLE} WHERE status = 'pending_embed' "
                "ORDER BY created_at ASC LIMIT :limit"
            ),
            {"limit": settings.ingestion_job_batch_size},
        )
        job_ids = [row[0] for row in result.fetchall()]

    logger.info("poll_embed.found", count=len(job_ids))
    for job_id in job_ids:
        async with AsyncSessionFactory() as session:
            await job_embedding.run(job_id, session)


async def sweep_stuck_jobs() -> None:
    """Reset jobs stuck in-progress or failed-under-retry-budget so they retry.

    Stuck jobs (chunking/embedding longer than job_stuck_minutes) revert to
    their preceding pending_* status; failed jobs under job_max_retry revert
    to pending_chunk for a full pipeline retry.
    """
    async with AsyncSessionFactory() as session:
        stuck_result = await session.execute(
            text(
                f"UPDATE {_INGESTION_JOBS_TABLE} "
                "SET status = CASE "
                "  WHEN status = 'chunking' THEN 'pending_chunk' "
                "  WHEN status = 'embedding' THEN 'pending_embed' "
                "END, "
                "updated_at = now() "
                "WHERE status IN ('chunking', 'embedding') "
                "  AND updated_at < now() - :minutes * interval '1 minute' "
                "  AND retry_count < :max_retry"
            ),
            {"minutes": settings.job_stuck_minutes, "max_retry": settings.job_max_retry},
        )
        reset_stuck = stuck_result.rowcount

        failed_result = await session.execute(
            text(
                f"UPDATE {_INGESTION_JOBS_TABLE} "
                "SET status = 'pending_chunk', updated_at = now() "
                "WHERE status = 'failed' AND retry_count < :max_retry"
            ),
            {"max_retry": settings.job_max_retry},
        )
        reset_failed = failed_result.rowcount

        await session.commit()

    logger.info("sweep.done", reset_stuck=reset_stuck, reset_failed=reset_failed)


def setup_scheduler() -> AsyncIOScheduler:
    """Register the three ingestion cron jobs and return the scheduler.

    ``replace_existing=True`` so a restart doesn't duplicate jobs already
    persisted in the APScheduler job store (Postgres ``apscheduler_jobs``).
    """
    scheduler.add_job(
        poll_chunk_jobs,
        "interval",
        seconds=settings.cron_chunk_interval_seconds,
        id="poll_chunk",
        replace_existing=True,
    )
    scheduler.add_job(
        poll_embed_jobs,
        "interval",
        seconds=settings.cron_embed_interval_seconds,
        id="poll_embed",
        replace_existing=True,
    )
    scheduler.add_job(
        sweep_stuck_jobs,
        "interval",
        seconds=settings.cron_sweep_interval_seconds,
        id="sweep_stuck",
        replace_existing=True,
    )
    return scheduler
