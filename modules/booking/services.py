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
# Description: Booking admin service — calls data/booking_repository
#              directly, the same repository ai-agents/booking will use
#              (ARCH-001 §4). No SQL here — filtering lives in the
#              repository so both entry points share one query shape.
###############################################################################

from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from data.booking_repository import Booking, BookingRepository


async def list_bookings(
    session: AsyncSession,
    doctor_id: int | None = None,
    target_date: date | None = None,
    status: str | None = None,
) -> list[Booking]:
    """List bookings for the admin screen, filtered by doctor/date/status."""
    repo = BookingRepository(session)
    return await repo.list_filtered(doctor_id=doctor_id, target_date=target_date, status=status)


async def cancel_booking(session: AsyncSession, booking_id: int) -> Booking:
    """Cancel a booking directly from the admin screen — same repository
    call an agent would make, so the two paths are indistinguishable at the
    DB level (TASK-009 DoD).
    """
    repo = BookingRepository(session)
    return await repo.cancel_booking(booking_id)


async def reschedule_booking(
    session: AsyncSession, booking_id: int, new_slot_time: datetime
) -> Booking:
    """Manually reschedule a booking to a new slot time."""
    repo = BookingRepository(session)
    return await repo.update_booking(booking_id, new_slot_time)
