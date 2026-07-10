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
# Description: Booking Agent tools — thin wrappers over
#              dal/booking_repository; no SQL, no race-condition handling
#              here (constraint lives in dal/, ARCH-001 §4). Each tool owns
#              its own DB session since ADK tool functions are called
#              independently by the LLM, not injected with a shared request
#              session the way FastAPI Depends() works.
###############################################################################

from datetime import datetime

from common.database import AsyncSessionFactory
from core.exceptions import InvalidSlotError, SlotTakenError
from dal.booking_repository import BookingRepository


async def check_available_slots(doctor_id: int, date_iso: str) -> list[str]:
    """Return open slots for a doctor on a date, as ISO datetime strings.

    Args:
        doctor_id: The doctor's id (from the Symptom Agent's rendered context).
        date_iso: Target date as "YYYY-MM-DD". The agent must resolve any
            relative expression ("hôm nay"/"mai"/"thứ 2"...) into this format
            first using the reference date in its instruction (BUG-009) — this
            tool does not parse relative or free-text dates.

    Returns:
        ISO datetime strings for every open slot. Empty list if the doctor
        doesn't work that day or has no free slots.
    """
    target_date = datetime.fromisoformat(date_iso).date()
    async with AsyncSessionFactory() as session:
        repo = BookingRepository(session)
        slots = await repo.check_available_slots(doctor_id, target_date)
    return [s.isoformat() for s in slots]


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
