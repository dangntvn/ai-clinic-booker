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
# Description: Doctor repository — ORM model + CRUD for the doctors table,
#              which holds both operational fields (specialty, schedule) and
#              profile fields (bio, education) in one row (ADR-0020). Table
#              name is suffixed by language (ADR-0024, 2026-07-22) — each of
#              the 3 servers (vn/jp/en) owns its own roster with localized
#              full_name data, not a shared clinic-wide table.
###############################################################################

from sqlalchemy import ARRAY, JSON, Boolean, Numeric, String, select
from sqlalchemy.orm import Mapped, mapped_column

from common.config import settings
from core.base_model import BaseModel
from core.base_repository import BaseRepository
from dal.lang_tables import doctors_table

# BIZ-001 §6 — the clinic's 14 specialties, exact Vietnamese names (this is
# the single source of truth other tasks validate `specialty` against).
SPECIALTIES: tuple[str, ...] = (
    "Nội tổng quát",
    "Nhi",
    "Sản – Phụ khoa",
    "Tim mạch",
    "Tiêu hóa",
    "Hô hấp",
    "Nội tiết",
    "Thần kinh",
    "Cơ xương khớp",
    "Da liễu",
    "Tai Mũi Họng",
    "Mắt",
    "Răng Hàm Mặt",
    "Tiết niệu – Nam khoa",
)


class Doctor(BaseModel):
    """ORM model for the ``doctors_{lang_suffix}`` table (ARCH-001 §6.1, ADR-0020).

    Operational fields (specialty, phone, work_days, room, shift, fee,
    is_active) and profile fields (bio, education, photo_url, extra) live in
    the same row — a deliberate merge documented in ADR-0020, not an
    oversight.

    Table name is suffixed by ``settings.lang_suffix`` (multi-server deploy,
    ADR-0024, 2026-07-22, see dal/lang_tables.py) so each of the 3
    language-specific servers (vn/jp/en) owns its own doctor roster — the
    roster is a *different set of people with localized names* per language,
    not one clinic's roster viewed through 3 storefronts. ``settings`` is a
    module-load-time singleton (common/config.py), so this is evaluated once
    per process, matching that process's fixed language.
    """

    __tablename__ = doctors_table(settings.lang_suffix)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(64))
    specialty: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    work_days: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False, default=list)
    room: Mapped[str | None] = mapped_column(String(32))
    shift: Mapped[str | None] = mapped_column(String(32))
    fee: Mapped[float | None] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Profile fields (ADR-0020) — rendered into Symptom Agent context, not RAG.
    bio: Mapped[str | None] = mapped_column(String)
    education: Mapped[str | None] = mapped_column(String)
    photo_url: Mapped[str | None] = mapped_column(String(512))
    extra: Mapped[dict | None] = mapped_column(JSON)


class DoctorRepository(BaseRepository[Doctor]):
    """Postgres repository for the doctors table (ADR-0020)."""

    model = Doctor

    async def list_active(self) -> list[Doctor]:
        """Return every active doctor — the set rendered into agent context."""
        stmt = select(self.model).where(self.model.is_active.is_(True)).order_by(self.model.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_specialty(self, specialty: str) -> list[Doctor]:
        """Return active doctors for one specialty (BIZ-001 §6 department).

        Ordered by id so callers that auto-pick "the first result" (e.g. the
        Booking Agent's no-doctor-named fallback, BUG-029) get a deterministic
        pick instead of depending on unordered SQL result order.
        """
        stmt = (
            select(self.model)
            .where(self.model.specialty == specialty, self.model.is_active.is_(True))
            .order_by(self.model.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
