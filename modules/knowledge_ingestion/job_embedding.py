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
# Description: Embedding-phase worker — contract run(job_id), claims the job
#              by conditional UPDATE before processing, idempotent on re-run
#              (ADR-0021). Adapted from rag-health's job_embedding.py.
###############################################################################

from sqlalchemy.ext.asyncio import AsyncSession

from common.observability import get_logger
from dal.ingestion_job_repository import IngestionJobRepository
from modules.knowledge_ingestion.embedding_service import EmbeddingService

logger = get_logger(__name__)


async def run(job_id: int, session: AsyncSession) -> None:
    """Claim and execute a single embedding job.

    On success, advances the job to ``done``. On failure, marks the job
    ``failed`` with the error message and bumps ``retry_count``.

    Args:
        job_id:  Primary key of the IngestionJob to process.
        session: Active async SQLAlchemy session.
    """
    job_repo = IngestionJobRepository(session)

    claimed = await job_repo.claim(job_id, from_status="pending_embed", to_status="embedding")
    if not claimed:
        logger.info("job_embedding.skip", job_id=job_id)
        return

    try:
        job = await job_repo.get(job_id)
        if job is None:
            return

        service = EmbeddingService(session)
        count = await service.process(job)

        job.status = "done"
        await session.flush()
        logger.info("job_embedding.done", job_id=job_id, embedded_count=count)

    except Exception as e:
        job = await job_repo.get(job_id)
        if job is not None:
            job.status = "failed"
            job.error_msg = str(e)[:500]
            job.retry_count += 1
        logger.error("job_embedding.failed", job_id=job_id, error=str(e))

    await session.commit()
