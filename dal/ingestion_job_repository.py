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
# Description: Ingestion job repository — ORM model + get_pending
#              (SKIP LOCKED), get_by_knowledge, get_failed (ADR-0021).
###############################################################################

from sqlalchemy import ForeignKey, Integer, String, select, text
from sqlalchemy.orm import Mapped, mapped_column

from common.config import settings
from core.base_model import BaseModel
from core.base_repository import BaseRepository
from dal.lang_tables import ingestion_jobs_table, knowledge_base_table

# Suffixed per-language table name (multi-server deploy) — reused below by both
# the ORM model and the raw-SQL claim() query, so both stay in sync with a
# single source of truth instead of duplicating the f-string.
_TABLE_NAME = ingestion_jobs_table(settings.lang_suffix)


class IngestionJob(BaseModel):
    """ORM model for the ``ingestion_jobs_{lang_suffix}`` table (ADR-0021).

    status progresses: pending_chunk -> chunking -> pending_embed -> embedding
    -> done | failed.

    Table name (and the FK target below) is suffixed by ``settings.lang_suffix``
    — see dal/knowledge_repository.py::KnowledgeBase docstring for the
    multi-server rationale.
    """

    __tablename__ = _TABLE_NAME

    knowledge_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{knowledge_base_table(settings.lang_suffix)}.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending_chunk")
    error_msg: Mapped[str | None] = mapped_column(String(500))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class IngestionJobRepository(BaseRepository[IngestionJob]):
    """Postgres repository for ingestion_jobs (ADR-0021)."""

    model = IngestionJob

    async def get_by_knowledge(self, knowledge_id: int) -> list[IngestionJob]:
        """Return every ingestion job created for a given knowledge_base row."""
        stmt = select(self.model).where(self.model.knowledge_id == knowledge_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_failed(self, max_retry: int) -> list[IngestionJob]:
        """Return failed jobs still under the retry budget."""
        stmt = select(self.model).where(
            self.model.status == "failed", self.model.retry_count < max_retry
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def claim(self, job_id: int, from_status: str, to_status: str) -> bool:
        """Atomically claim a job by flipping its status, guarding against double-claim.

        Uses a plain conditional UPDATE (no SKIP LOCKED needed here since a
        single-row UPDATE ... WHERE status = X is already atomic under
        Postgres's row-level locking) — matches the claim pattern used by
        rag-health's job_chunk.py/job_embedding.py (ADR-0021).

        Returns:
            True if this call won the claim, False if another worker already did.
        """
        result = await self.session.execute(
            # Table name is an f-string, not a bind param — SQL doesn't allow
            # parameterising identifiers (table/column names), only values.
            # Safe here since _TABLE_NAME is built from settings.lang_suffix,
            # which field_validator._validate_lang_suffix (common/config.py)
            # already restricts to the fixed {"vn", "jp", "en"} set, never
            # from unsanitised user input.
            text(
                f"UPDATE {_TABLE_NAME} SET status = :to_status, updated_at = now() "
                "WHERE id = :id AND status = :from_status RETURNING id"
            ),
            {"id": job_id, "from_status": from_status, "to_status": to_status},
        )
        return result.fetchone() is not None
