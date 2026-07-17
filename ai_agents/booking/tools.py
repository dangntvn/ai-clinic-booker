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
# Description: Booking Agent tools — thin wrappers over dal/ repositories
#              (booking_repository for slots/bookings, doctor_repository for
#              the name->doctor_id lookup added for BUG-015, and the
#              specialty-based listing/multi-day scan added for TASK-034's
#              doctor/date auto-defaults); no SQL, no race-condition handling
#              here (constraint lives in dal/, ARCH-001 §4). Name matching is
#              a pure core/domain helper, not SQL. Each tool owns its own DB
#              session since ADK tool functions are called independently by
#              the LLM, not injected with a shared request session the way
#              FastAPI Depends() works.
###############################################################################

from datetime import datetime, timedelta

from common.database import AsyncSessionFactory
from core.exceptions import InvalidSlotError, NotFoundError, SlotTakenError
from dal.booking_repository import BookingRepository
from dal.doctor_repository import Doctor, DoctorRepository

from ..core.domain.doctor_lookup import name_matches

# BUG-031: cap on how many consecutive days find_earliest_available_slot scans
# — a whole-week window is enough to answer "khám sớm nhất có thể" without
# unbounded DB round-trips if a doctor is fully booked for a long stretch.
_MAX_SCAN_DAYS = 7


def _doctor_to_dict(d: Doctor) -> dict:
    """Shape a Doctor row into the dict find_doctor_by_name/list_doctors_by_specialty
    return — doctor_id front and center since that's the only field the agent
    is allowed to pass into check_available_slots/create_booking."""
    return {
        "doctor_id": d.id,
        "full_name": d.full_name,
        "title": d.title,
        "specialty": d.specialty,
        "work_days": d.work_days,
    }


async def find_doctor_by_name(name: str) -> list[dict]:
    """Resolve a doctor named by the patient into the real roster (BUG-015).

    Use this when the patient names a doctor directly (e.g. "bác sĩ Phạm Thị
    Lan Hương") and no numeric doctor_id is known yet — never ask the patient
    for an internal doctor_id. Matching is accent-insensitive and tolerant of
    honorifics ("bác sĩ", "ThS.BS", "CKI"), so passing the name as the patient
    said it is fine.

    Args:
        name: The doctor name the patient gave (with or without a title).

    Returns:
        One dict per matching active doctor, each with the doctor_id needed for
        check_available_slots/create_booking plus enough detail to disambiguate:
        {"doctor_id": int, "full_name": str, "title": str | None,
         "specialty": str, "work_days": list[str]}. Empty list if no active
        doctor matches — in that case tell the patient honestly that no doctor
        by that name was found; do NOT substitute a different doctor.
    """
    async with AsyncSessionFactory() as session:
        repo = DoctorRepository(session)
        doctors = await repo.list_active()
    return [_doctor_to_dict(d) for d in doctors if name_matches(name, d.full_name)]


async def list_doctors_by_specialty(specialty: str | None = None) -> list[dict]:
    """List active doctors, optionally by specialty, to auto-pick one (BUG-029).

    Use this when the patient has NOT named a specific doctor. Pass the
    specialty already known (from a Symptom Agent handoff, or one the patient
    just stated) to get candidates for that specialty; pass specialty=None (or
    the clinic's default specialty, e.g. "Nội tổng quát") when no specialty is
    known at all, so the flow can auto-select a reasonable default doctor
    instead of blocking the booking on an extra question.

    Args:
        specialty: One of the clinic's specialty names (BIZ-001 §6), or None
            to list every active doctor regardless of specialty.

    Returns:
        One dict per matching active doctor, same shape as
        find_doctor_by_name: {"doctor_id": int, "full_name": str,
        "title": str | None, "specialty": str, "work_days": list[str]}. Empty
        list if no active doctor matches — do NOT fabricate a doctor_id in
        that case; tell the patient honestly and offer a different specialty
        instead of silently substituting one.
    """
    async with AsyncSessionFactory() as session:
        repo = DoctorRepository(session)
        doctors = await repo.list_by_specialty(specialty) if specialty else await repo.list_active()
    return [_doctor_to_dict(d) for d in doctors]


async def check_available_slots(doctor_id: int, date_iso: str) -> dict:
    """Return open slots for a doctor on a date.

    Args:
        doctor_id: The doctor's id (from the Symptom Agent's rendered context
            or resolved via find_doctor_by_name).
        date_iso: Target date as "YYYY-MM-DD". The agent must resolve any
            relative expression ("hôm nay"/"mai"/"thứ 2"...) into this format
            first using the reference date in its instruction (BUG-009) — this
            tool does not parse relative or free-text dates.

    Returns:
        {"status": "ok", "slots": [<ISO datetime str>, ...]} when the doctor
        exists and is active. ``slots`` is the list of every open clinic-hour
        slot; it is EMPTY when the doctor doesn't work that day or is fully
        booked — that is a real "no free time this day" state, tell the patient
        so and offer another day.

        {"status": "doctor_not_found"} when doctor_id doesn't resolve to an
        active doctor (BUG-017). This is a DIFFERENT situation from an empty
        slot list — it means there is no such doctor, so the agent must NOT say
        "no slots left / fully booked"; it should say no doctor by that
        reference was found and re-check the name (find_doctor_by_name) or
        offer specialty-based routing instead of substituting another doctor.
    """
    target_date = datetime.fromisoformat(date_iso).date()
    async with AsyncSessionFactory() as session:
        repo = BookingRepository(session)
        try:
            slots = await repo.check_available_slots(doctor_id, target_date)
        except NotFoundError:
            return {"status": "doctor_not_found"}
    return {"status": "ok", "slots": [s.isoformat() for s in slots]}


async def find_earliest_available_slot(
    doctor_id: int, start_date_iso: str, max_days: int = _MAX_SCAN_DAYS
) -> dict:
    """Scan forward from a date to find the earliest day with an open slot (BUG-031).

    Use this when the patient states no date preference at all (e.g. "khám
    sớm nhất có thể", "lúc nào trống thì khám") — after doctor_id is already
    known (find_doctor_by_name/list_doctors_by_specialty). Scans
    start_date_iso and each day after it, capped at _MAX_SCAN_DAYS (7) days
    total, and returns the first day whose slot list isn't empty — this
    replaces calling check_available_slots per day in a loop from the agent
    side with one deterministic tool call.

    Args:
        doctor_id: The doctor to check — must be a real id, never fabricated.
        start_date_iso: First date to check, "YYYY-MM-DD" — normally today
            (the NGÀY THAM CHIẾU anchor), since "sớm nhất có thể" means
            starting from now, not some later day.
        max_days: How many consecutive days to scan. Callers should not pass
            more than _MAX_SCAN_DAYS; values above it are silently capped.

    Returns:
        {"status": "ok", "date_iso": "YYYY-MM-DD", "slots": [<ISO datetime
        str>, ...]} for the first day in the window with a non-empty slot
        list — "slots" is already the real result for that day, no need to
        call check_available_slots again for it.

        {"status": "no_slot_in_window", "days_checked": int} if every day in
        the window is closed/fully booked — tell the patient honestly and
        offer to check further out or a different doctor, never fabricate a
        date.

        {"status": "doctor_not_found"} if doctor_id doesn't resolve to an
        active doctor (BUG-017) — same meaning as check_available_slots's
        doctor_not_found; say no such doctor was found, do not say "no slots".
    """
    start_date = datetime.fromisoformat(start_date_iso).date()
    capped_days = min(max_days, _MAX_SCAN_DAYS)
    async with AsyncSessionFactory() as session:
        repo = BookingRepository(session)
        for offset in range(capped_days):
            target_date = start_date + timedelta(days=offset)
            try:
                slots = await repo.check_available_slots(doctor_id, target_date)
            except NotFoundError:
                return {"status": "doctor_not_found"}
            if slots:
                return {
                    "status": "ok",
                    "date_iso": target_date.isoformat(),
                    "slots": [s.isoformat() for s in slots],
                }
    return {"status": "no_slot_in_window", "days_checked": capped_days}


async def create_booking(doctor_id: int, slot_time_iso: str, patient_name: str, phone: str) -> dict:
    """Create a booking. The DB constraint is the only conflict guard (ADR-0009).

    Returns:
        {"status": "confirmed", "booking_id": int} on success,
        {"status": "slot_taken"} if the slot was taken between check and create, or
        {"status": "invalid_slot", "reason": str} if the slot violates the doctor's
        work_days/clinic hours — in either failure case the agent must call
        check_available_slots again and re-offer, never retry blindly.
    """
    slot_time = datetime.fromisoformat(slot_time_iso)
    async with AsyncSessionFactory() as session:
        repo = BookingRepository(session)
        try:
            booking = await repo.create_booking(patient_name, phone, doctor_id, slot_time)
        except SlotTakenError:
            return {"status": "slot_taken"}
        except InvalidSlotError as e:
            return {"status": "invalid_slot", "reason": e.message}
    return {"status": "confirmed", "booking_id": booking.id}


async def update_booking(booking_id: int, new_slot_time_iso: str) -> dict:
    """Reschedule an existing booking to a new slot. Same validity/conflict handling as create."""
    new_slot_time = datetime.fromisoformat(new_slot_time_iso)
    async with AsyncSessionFactory() as session:
        repo = BookingRepository(session)
        try:
            booking = await repo.update_booking(booking_id, new_slot_time)
        except SlotTakenError:
            return {"status": "slot_taken"}
        except InvalidSlotError as e:
            return {"status": "invalid_slot", "reason": e.message}
    return {"status": "confirmed", "booking_id": booking.id}


async def cancel_booking(booking_id: int) -> dict:
    """Cancel an existing booking, freeing its slot for immediate re-booking."""
    async with AsyncSessionFactory() as session:
        repo = BookingRepository(session)
        booking = await repo.cancel_booking(booking_id)
    return {"status": "cancelled", "booking_id": booking.id}
