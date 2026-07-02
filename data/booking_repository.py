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
# Description: Booking repository — ORM model + CRUD; correctness relies on
#              the partial unique index UNIQUE(doctor_id, slot_time) WHERE
#              status != 'cancelled' (ADR-0009) — the only place a constraint
#              violation becomes SlotTakenError. Query methods
#              (check_available_slots/create_booking/...) land in TASK-008.
#              Also holds ChatSessionLink — a thin mapping table so
#              modules/booking can look up a booking's chat history via
#              ADK's SessionService, without storing message content here.
###############################################################################

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import BaseModel
from core.base_repository import BaseRepository


class Booking(BaseModel):
    """ORM model for the ``bookings`` table (ARCH-001 §6.1, ADR-0009).

    The partial unique index is created in the Alembic migration, not here —
    SQLAlchemy's declarative ``Index`` with a ``postgresql_where`` clause is
    used so ``Base.metadata`` reflects it for autogenerate.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        Index(
            "ix_bookings_doctor_slot_active",
            "doctor_id",
            "slot_time",
            unique=True,
            postgresql_where=text("status != 'cancelled'"),
        ),
    )

    patient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    doctor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False
    )
    slot_time: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")


class ChatSessionLink(BaseModel):
    """ORM model for ``chat_session_links`` — thin booking-to-session mapping.

    No message content lives here; ``session_id`` is the key into ADK's own
    ``sessions``/``events`` tables via ``SessionService.get_session()``
    (ARCH-001 §6.1) — never queried directly.
    """

    __tablename__ = "chat_session_links"

    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)


class BookingRepository(BaseRepository[Booking]):
    """Postgres repository for bookings — relies on the partial unique index (ADR-0009)."""

    model = Booking
