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
# Description: Knowledge admin service — publish() only inserts
#              ingestion_jobs(pending_chunk); it never runs chunk/embed
#              itself (ARCH-001 §5.5, ADR-0021). Delete/archive cleans up
#              chunks + vectors so nothing orphaned is left in Qdrant.
###############################################################################

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError, ValidationError
from dal.chunk_repository import ChunkRepository
from dal.ingestion_job_repository import IngestionJob, IngestionJobRepository
from dal.knowledge_repository import KNOWLEDGE_CATEGORIES, KnowledgeBase, KnowledgeRepository
from dal.qdrant_client import delete_by_knowledge_id


def _validate_category(category: str) -> None:
    if category not in KNOWLEDGE_CATEGORIES:
        allowed = ", ".join(KNOWLEDGE_CATEGORIES)
        raise ValidationError(f"Unknown category '{category}', must be one of: {allowed}")


async def create_draft(session: AsyncSession, data: dict) -> KnowledgeBase:
    """Create a new knowledge_base row in draft status."""
    _validate_category(data["category"])
    repo = KnowledgeRepository(session)
    row = KnowledgeBase(**data, status="draft")
    row = await repo.create(row)
    await session.commit()
    return row


async def update_draft(session: AsyncSession, knowledge_id: int, data: dict) -> KnowledgeBase:
    """Edit an existing knowledge_base row's content/title/category."""
    repo = KnowledgeRepository(session)
    row = await repo.get(knowledge_id)
    if row is None:
        raise NotFoundError(f"knowledge_base {knowledge_id} not found")

    if "category" in data:
        _validate_category(data["category"])

    for key, value in data.items():
        setattr(row, key, value)

    row = await repo.update(row)
    await session.commit()
    return row


async def list_knowledge(
    session: AsyncSession, category: str | None = None, status: str | None = None
) -> list[KnowledgeBase]:
    """List knowledge_base rows, optionally filtered by category/status."""
    repo = KnowledgeRepository(session)
    if category is not None:
        rows = await repo.list_by_category(category)
    else:
        rows = await repo.list(offset=0, limit=1000)
    if status is not None:
        rows = [r for r in rows if r.status == status]
    return rows


async def publish(session: AsyncSession, knowledge_id: int) -> dict:
    """Enqueue chunk+embed for a knowledge_base row — never runs it inline.

    Validates category before creating the job. Returns immediately with
    {job_id, status: pending} — TASK-003's cron (or scripts/run_ingestion_job.py)
    owns actual execution (ARCH-001 §5.5, ADR-0021).
    """
    knowledge_repo = KnowledgeRepository(session)
    row = await knowledge_repo.get(knowledge_id)
    if row is None:
        raise NotFoundError(f"knowledge_base {knowledge_id} not found")

    _validate_category(row.category)

    job_repo = IngestionJobRepository(session)
    job = IngestionJob(knowledge_id=knowledge_id, status="pending_chunk")
    job = await job_repo.create(job)
    await session.commit()

    return {"job_id": job.id, "status": "pending"}


async def delete_knowledge(session: AsyncSession, knowledge_id: int) -> None:
    """Delete a knowledge_base row and everything derived from it.

    Cascades to knowledge_chunks (DB FK ON DELETE CASCADE) and explicitly
    calls Qdrant's delete_by_knowledge_id — the FK cascade doesn't reach
    Qdrant, so this must happen here to avoid an orphaned vector
    (ARCH-001 §6.4).
    """
    repo = KnowledgeRepository(session)
    row = await repo.get(knowledge_id)
    if row is None:
        raise NotFoundError(f"knowledge_base {knowledge_id} not found")

    chunk_repo = ChunkRepository(session)
    await chunk_repo.delete_by_knowledge(knowledge_id)
    delete_by_knowledge_id(knowledge_id)

    await session.delete(row)
    await session.commit()
