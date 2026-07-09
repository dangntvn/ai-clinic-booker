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
# Description: Manual ingestion trigger — calls the exact same
#              job_chunk.run()/job_embedding.run() the cron uses, so there is
#              no separate code path for "manual" vs "automatic" (ADR-0021).
#              --knowledge-id runs one row through both phases immediately;
#              --retry-failed resets failed jobs then runs them;
#              --reindex-all re-chunks/re-embeds every published row.
###############################################################################

import argparse
import asyncio

from common.database import AsyncSessionFactory
from dal.ingestion_job_repository import IngestionJob, IngestionJobRepository
from dal.knowledge_repository import KnowledgeRepository
from modules.knowledge_ingestion import job_chunk, job_embedding


async def _run_job_id(job_id: int) -> None:
    async with AsyncSessionFactory() as session:
        await job_chunk.run(job_id, session)
    async with AsyncSessionFactory() as session:
        await job_embedding.run(job_id, session)


async def _run_for_knowledge(knowledge_id: int) -> None:
    async with AsyncSessionFactory() as session:
        job = IngestionJob(knowledge_id=knowledge_id, status="pending_chunk")
        session.add(job)
        await session.flush()
        await session.commit()
        job_id = job.id
    await _run_job_id(job_id)


async def _retry_failed() -> None:
    async with AsyncSessionFactory() as session:
        job_repo = IngestionJobRepository(session)
        from common.config import settings

        failed = await job_repo.get_failed(settings.job_max_retry)
        for job in failed:
            job.status = "pending_chunk"
        await session.commit()
        job_ids = [job.id for job in failed]

    for job_id in job_ids:
        await _run_job_id(job_id)


async def _reindex_all() -> None:
    async with AsyncSessionFactory() as session:
        knowledge_repo = KnowledgeRepository(session)
        rows = await knowledge_repo.list(offset=0, limit=10_000)
        knowledge_ids = [row.id for row in rows]

    for knowledge_id in knowledge_ids:
        await _run_for_knowledge(knowledge_id)


def main() -> None:
    """CLI entrypoint for manual ingestion triggers (ADR-0021)."""
    parser = argparse.ArgumentParser(description="Manually trigger knowledge ingestion")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--knowledge-id", type=int, help="Run chunk+embed for one row")
    group.add_argument("--retry-failed", action="store_true", help="Retry every failed job")
    group.add_argument("--reindex-all", action="store_true", help="Re-chunk/re-embed every row")
    args = parser.parse_args()

    if args.knowledge_id is not None:
        asyncio.run(_run_for_knowledge(args.knowledge_id))
    elif args.retry_failed:
        asyncio.run(_retry_failed())
    elif args.reindex_all:
        asyncio.run(_reindex_all())


if __name__ == "__main__":
    main()
