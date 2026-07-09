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
# Description: Knowledge repository — ORM model + CRUD for the knowledge_base
#              table, the system of record for authored content (ARCH-001
#              §6.1). Chunking/embedding are derived state, not stored here.
###############################################################################

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import BaseModel
from core.base_repository import BaseRepository

# BIZ-001/SRS-001 knowledge categories — must match Qdrant payload filter values.
KNOWLEDGE_CATEGORIES = ("policy", "clinic_info", "medical_guide")


class KnowledgeBase(BaseModel):
    """ORM model for the ``knowledge_base`` table (ARCH-001 §6.1)."""

    __tablename__ = "knowledge_base"

    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeRepository(BaseRepository[KnowledgeBase]):
    """Postgres repository for the knowledge_base table."""

    model = KnowledgeBase

    async def list_by_category(self, category: str) -> list[KnowledgeBase]:
        """Return every knowledge_base row for a given category, any status."""
        from sqlalchemy import select

        stmt = select(self.model).where(self.model.category == category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
