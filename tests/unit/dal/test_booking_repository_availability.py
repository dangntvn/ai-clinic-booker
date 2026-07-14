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
# Description: Unit tests for BookingRepository.check_available_slots' branch
#              logic (BUG-017), with a mocked session so no live DB is needed:
#              a missing/inactive doctor RAISES NotFoundError (so callers can
#              tell "no such doctor" apart from "no free slot"), while a real
#              doctor who simply doesn't work the queried weekday returns an
#              empty list (the genuine "no time this day" state).
###############################################################################

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.exceptions import NotFoundError
from dal.booking_repository import BookingRepository


def _repo_with_doctor(doctor):
    """A BookingRepository whose session.get() returns ``doctor`` (or None)."""
    session = SimpleNamespace(get=AsyncMock(return_value=doctor))
    return BookingRepository(session)


@pytest.mark.asyncio
async def test_check_available_slots_raises_when_doctor_missing():
    repo = _repo_with_doctor(None)
    with pytest.raises(NotFoundError):
        await repo.check_available_slots(999, date(2026, 7, 20))


@pytest.mark.asyncio
async def test_check_available_slots_raises_when_doctor_inactive():
    inactive = SimpleNamespace(is_active=False, work_days=["Mon", "Tue"])
    repo = _repo_with_doctor(inactive)
    with pytest.raises(NotFoundError):
        await repo.check_available_slots(3, date(2026, 7, 20))


@pytest.mark.asyncio
async def test_check_available_slots_empty_when_doctor_off_that_weekday():
    """Real, active doctor who doesn't work the queried weekday -> [] (not an
    error): a legitimate "no time this day", distinct from doctor-not-found."""
    # 2026-07-19 is a Sunday; doctor works Mon-Sat only.
    doctor = SimpleNamespace(
        is_active=True, work_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    )
    repo = _repo_with_doctor(doctor)
    slots = await repo.check_available_slots(3, date(2026, 7, 19))
    assert slots == []
