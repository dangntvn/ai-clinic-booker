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
#              violation becomes SlotTakenError. Slot validity (work_days/
#              clinic hours, BUG-007) is checked here before the INSERT/
#              UPDATE, distinct from conflict detection which is entirely
#              the DB's job (ADR-0009), never a check-then-insert. All
#              slot_time values are normalized to UTC-aware (BUG-006 —
#              the column is TIMESTAMPTZ, naive datetimes silently never
#              compared-equal to the aware rows read back from it). Also
#              holds ChatSessionLink — a thin mapping table so
#              modules/booking can look up a booking's chat history via
#              ADK's SessionService, without storing message content here.
###############################################################################

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import BaseModel
from core.base_repository import BaseRepository
from core.exceptions import InvalidSlotError, NotFoundError, SlotTakenError
from dal.doctor_repository import Doctor

# Clinic hours (ARCH-001 doesn't pin these — a single-branch clinic default;
# revisit if per-doctor shifts need finer-grained slotting than "work_days").
CLINIC_OPEN_HOUR = 8
CLINIC_CLOSE_HOUR = 17
LUNCH_START_HOUR = 12
LUNCH_END_HOUR = 13
SLOT_DURATION_MINUTES = 30


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
    # DateTime(timezone=True) must be explicit — Mapped[datetime] alone infers
    # a naive DateTime(), mismatching the TIMESTAMPTZ column (BUG-006) and
    # making asyncpg reject aware-datetime bind parameters outright.
    slot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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


def _candidate_slots(target_date: date) -> list[datetime]:
    """Generate every clinic-hour slot for a date, lunch break excluded.

    UTC-aware (BUG-006) so membership checks against ``bookings.slot_time``
    (a TIMESTAMPTZ column) compare aware-to-aware, never naive-to-aware.
    """
    slots = []
    current = datetime.combine(target_date, time(hour=CLINIC_OPEN_HOUR, tzinfo=UTC))
    end = datetime.combine(target_date, time(hour=CLINIC_CLOSE_HOUR, tzinfo=UTC))
    step = timedelta(minutes=SLOT_DURATION_MINUTES)
    while current < end:
        if not (LUNCH_START_HOUR <= current.hour < LUNCH_END_HOUR):
            slots.append(current)
        current += step
    return slots


def _to_utc(dt: datetime) -> datetime:
    """Normalize to a UTC-aware datetime (BUG-006), treating naive input as UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


class BookingRepository(BaseRepository[Booking]):
    """Postgres repository for bookings — relies on the partial unique index (ADR-0009)."""

    model = Booking

    async def list_filtered(
        self,
        doctor_id: int | None = None,
        target_date: date | None = None,
        status: str | None = None,
    ) -> list[Booking]:
        """List bookings for the admin screen, filtered by any combination of
        doctor/date/status (ARCH-001 §4 — modules/booking never writes SQL itself).
        """
        stmt = select(Booking)
        if doctor_id is not None:
            stmt = stmt.where(Booking.doctor_id == doctor_id)
        if target_date is not None:
            day_start = datetime.combine(target_date, time.min, tzinfo=UTC)
            day_end = datetime.combine(target_date, time.max, tzinfo=UTC)
            stmt = stmt.where(Booking.slot_time >= day_start, Booking.slot_time <= day_end)
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def check_available_slots(self, doctor_id: int, target_date: date) -> list[datetime]:
        """Return open slots for a doctor on a date.

        Joins the doctor's ``work_days`` (does the doctor work that weekday
        at all) with active ``bookings`` (which of that day's slots are
        already taken) — read-only, so no race-condition concern here; the
        actual conflict guard is the DB constraint hit at ``create_booking``.

        Returns:
            Empty list if the doctor works but has no free slot that day
            (doesn't work that weekday, or every slot is already taken).

        Raises:
            NotFoundError: If ``doctor_id`` doesn't resolve to an active
                doctor. This is deliberately distinct from the empty-list
                "no free slot" result (BUG-017): a caller/agent must be able
                to tell "there is no such doctor" apart from "this doctor has
                nothing free that day", so the two are never phrased the same
                way to the patient. Mirrors ``_validate_slot``, which already
                errors on the same condition rather than silently returning.
        """
        doctor = await self.session.get(Doctor, doctor_id)
        if doctor is None or not doctor.is_active:
            raise NotFoundError(f"Doctor {doctor_id} not found or inactive")

        weekday_abbr = target_date.strftime("%a")  # "Mon", "Tue", ...
        if weekday_abbr not in doctor.work_days:
            return []

        day_start = datetime.combine(target_date, time.min, tzinfo=UTC)
        day_end = datetime.combine(target_date, time.max, tzinfo=UTC)
        stmt = select(Booking.slot_time).where(
            Booking.doctor_id == doctor_id,
            Booking.status != "cancelled",
            Booking.slot_time >= day_start,
            Booking.slot_time <= day_end,
        )
        taken = {row[0] for row in (await self.session.execute(stmt)).all()}

        return [slot for slot in _candidate_slots(target_date) if slot not in taken]

    async def _validate_slot(self, doctor_id: int, slot_time: datetime) -> None:
        """Reject slot_time if the doctor doesn't work that day/hour (BUG-007).

        This is validity, not availability — it does not check for conflicts
        with existing bookings (that stays the DB constraint's job, ADR-0009).
        """
        doctor = await self.session.get(Doctor, doctor_id)
        if doctor is None or not doctor.is_active:
            raise InvalidSlotError(f"Doctor {doctor_id} not found or inactive")

        weekday_abbr = slot_time.strftime("%a")
        if weekday_abbr not in doctor.work_days:
            raise InvalidSlotError(f"Doctor {doctor_id} does not work on {weekday_abbr}")

        if slot_time not in _candidate_slots(slot_time.date()):
            raise InvalidSlotError(f"{slot_time.isoformat()} is not a valid clinic-hour slot")

    async def create_booking(
        self, patient_name: str, phone: str, doctor_id: int, slot_time: datetime
    ) -> Booking:
        """Create a booking. Raises InvalidSlotError if the slot violates the
        doctor's work_days/clinic hours (BUG-007), or SlotTakenError on a
        partial-unique-index hit.

        No check-then-insert for conflicts: the INSERT either succeeds or the
        DB constraint rejects it — that remains the only conflict-detection
        mechanism (ADR-0009). Slot validity is a separate, cheaper check done
        up front since it doesn't race with concurrent callers.
        """
        slot_time = _to_utc(slot_time)
        await self._validate_slot(doctor_id, slot_time)

        booking = Booking(
            patient_name=patient_name, phone=phone, doctor_id=doctor_id, slot_time=slot_time
        )
        self.session.add(booking)
        try:
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            raise SlotTakenError(f"Slot {slot_time} for doctor {doctor_id} is already taken") from e
        await self.session.commit()
        return booking

    async def update_booking(self, booking_id: int, new_slot_time: datetime) -> Booking:
        """Reschedule a booking to a new slot. Same validity/conflict handling as create."""
        booking = await self.get(booking_id)
        if booking is None:
            raise NotFoundError(f"Booking {booking_id} not found")

        new_slot_time = _to_utc(new_slot_time)
        await self._validate_slot(booking.doctor_id, new_slot_time)

        booking.slot_time = new_slot_time
        try:
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            msg = f"Slot {new_slot_time} for doctor {booking.doctor_id} is already taken"
            raise SlotTakenError(msg) from e
        await self.session.commit()
        return booking

    async def cancel_booking(self, booking_id: int) -> Booking:
        """Cancel a booking — UPDATE status only, never deletes the row.

        Freeing the slot this way (not a DELETE) is what lets the partial
        unique index allow immediate re-booking of the same slot (ADR-0009).
        """
        booking = await self.get(booking_id)
        if booking is None:
            raise NotFoundError(f"Booking {booking_id} not found")

        booking.status = "cancelled"
        await self.session.flush()
        await self.session.commit()
        return booking
