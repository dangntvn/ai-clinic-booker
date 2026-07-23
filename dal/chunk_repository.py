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
# Description: Chunk repository — ORM model + CRUD for the knowledge_chunks
#              table (ADR-0021). vector_id points to the Qdrant point; a null
#              vector_id means the chunk is still pending_embed.
###############################################################################

from sqlalchemy import ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from common.config import settings
from core.base_model import BaseModel
from core.base_repository import BaseRepository
from dal.lang_tables import knowledge_base_table, knowledge_chunks_table


class KnowledgeChunk(BaseModel):
    """ORM model for the ``knowledge_chunks_{lang_suffix}`` table (ADR-0021).

    Table name (and the FK target below) is suffixed by ``settings.lang_suffix``
    — see dal/knowledge_repository.py::KnowledgeBase docstring for the
    multi-server rationale.
    """

    __tablename__ = knowledge_chunks_table(settings.lang_suffix)

    knowledge_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{knowledge_base_table(settings.lang_suffix)}.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    vector_id: Mapped[str | None] = mapped_column(String(64))
    embed_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending_embed")


class ChunkRepository(BaseRepository[KnowledgeChunk]):
    """Postgres repository for the knowledge_chunks table (ADR-0021)."""

    model = KnowledgeChunk

    async def get_by_knowledge(self, knowledge_id: int) -> list[KnowledgeChunk]:
        """Return every chunk belonging to a knowledge_base row, in ordinal order."""
        stmt = (
            select(self.model)
            .where(self.model.knowledge_id == knowledge_id)
            .order_by(self.model.ordinal)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_embed(self, knowledge_id: int) -> list[KnowledgeChunk]:
        """Return chunks for a knowledge_base row that still need embedding."""
        stmt = select(self.model).where(
            self.model.knowledge_id == knowledge_id,
            self.model.embed_status == "pending_embed",
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_knowledge(self, knowledge_id: int) -> None:
        """Delete every chunk for a knowledge_base row (used on delete/archive)."""
        chunks = await self.get_by_knowledge(knowledge_id)
        for chunk in chunks:
            await self.session.delete(chunk)
        await self.session.flush()
