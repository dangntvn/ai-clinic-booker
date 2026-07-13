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
# Description: Unit tests for ai_agents/booking/tools.py — the BUG-017
#              distinction between "no such doctor" and "doctor exists but has
#              no free slot", plus find_doctor_by_name's empty-result path.
#              Offline: AsyncSessionFactory and the repositories are mocked, so
#              no docker/DB/LLM — the point is to exercise the tool's own branch
#              logic and return shape, since after the BUG-017 data seed every
#              specialty has doctors and the "empty roster" state can no longer
#              be reproduced with real data (only simulated here).
###############################################################################

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ai_agents.booking import tools
from core.exceptions import NotFoundError


class _FakeSession:
    """Minimal async context manager standing in for AsyncSessionFactory()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _patch_session():
    return patch.object(tools, "AsyncSessionFactory", lambda: _FakeSession())


@pytest.mark.asyncio
async def test_check_available_slots_reports_doctor_not_found_distinctly():
    """A doctor_id that doesn't resolve must return status 'doctor_not_found',
    NOT an empty slot list — the two are phrased differently to the patient
    (BUG-017: "no such doctor" is not "fully booked")."""
    with (
        _patch_session(),
        patch.object(tools, "BookingRepository") as mock_repo_cls,
    ):
        mock_repo_cls.return_value.check_available_slots = AsyncMock(
            side_effect=NotFoundError("Doctor 999 not found or inactive")
        )
        result = await tools.check_available_slots(999, "2026-07-20")

    assert result == {"status": "doctor_not_found"}


@pytest.mark.asyncio
async def test_check_available_slots_empty_list_is_ok_status_not_an_error():
    """A real doctor with no free slot that day returns status 'ok' with an
    empty slots list — a legitimate "no time this day", distinct from
    doctor_not_found."""
    with (
        _patch_session(),
        patch.object(tools, "BookingRepository") as mock_repo_cls,
    ):
        mock_repo_cls.return_value.check_available_slots = AsyncMock(return_value=[])
        result = await tools.check_available_slots(3, "2026-07-19")

    assert result == {"status": "ok", "slots": []}


@pytest.mark.asyncio
async def test_check_available_slots_returns_iso_strings_for_real_slots():
    """Open slots come back as ISO datetime strings under 'slots'."""
    slot_a = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    slot_b = datetime(2026, 7, 20, 8, 30, tzinfo=UTC)
    with (
        _patch_session(),
        patch.object(tools, "BookingRepository") as mock_repo_cls,
    ):
        mock_repo_cls.return_value.check_available_slots = AsyncMock(
            return_value=[slot_a, slot_b]
        )
        result = await tools.check_available_slots(3, "2026-07-20")

    assert result == {
        "status": "ok",
        "slots": [slot_a.isoformat(), slot_b.isoformat()],
    }


def _doctor(doctor_id, full_name, specialty="Nội tổng quát"):
    return SimpleNamespace(
        id=doctor_id,
        full_name=full_name,
        title="Bác sĩ",
        specialty=specialty,
        work_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    )


@pytest.mark.asyncio
async def test_find_doctor_by_name_returns_empty_for_unknown_name():
    """An unknown name yields [] — the agent must then say no doctor by that
    name was found, never substitute a different one (BUG-015/BUG-017)."""
    roster = [_doctor(3, "Phạm Thị Lan Hương"), _doctor(4, "Trần Thị Kim Anh")]
    with (
        _patch_session(),
        patch.object(tools, "DoctorRepository") as mock_repo_cls,
    ):
        mock_repo_cls.return_value.list_active = AsyncMock(return_value=roster)
        result = await tools.find_doctor_by_name("Bác sĩ Không Có Thật")

    assert result == []


@pytest.mark.asyncio
async def test_find_doctor_by_name_matches_a_real_doctor():
    """A name that matches the roster returns that doctor with the doctor_id
    the booking tools need."""
    roster = [_doctor(3, "Phạm Thị Lan Hương"), _doctor(4, "Trần Thị Kim Anh")]
    with (
        _patch_session(),
        patch.object(tools, "DoctorRepository") as mock_repo_cls,
    ):
        mock_repo_cls.return_value.list_active = AsyncMock(return_value=roster)
        result = await tools.find_doctor_by_name("Lan Hương")

    assert [d["doctor_id"] for d in result] == [3]
    assert result[0]["full_name"] == "Phạm Thị Lan Hương"
