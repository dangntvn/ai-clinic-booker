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
# Description: Booking Agent DeepEval tests — real orchestrator run against
#              real doctor_id=3 ("Phạm Thị Lan Hương", Nội tổng quát, seeded
#              2026-07-08 via TASK-026, real work_days test schedule Mon-Sat).
#              No Qdrant retrieval here (Booking Agent doesn't do RAG), so
#              FaithfulnessMetric doesn't apply — GEval plays the same role,
#              checked against the real BookingRepository call captured by
#              `booking_capture` (TASK-027 DoD: no mocked actual_output, and
#              no metric added "for the sake of it").
###############################################################################

import re
from datetime import UTC, date, datetime, timedelta

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from eval.deepeval_gemini import build_judge

THRESHOLD = 0.7
REAL_DOCTOR_ID = 3  # Phạm Thị Lan Hương, Nội tổng quát — eval/seed_result_2026-07-08.json
WORK_DAY = "2026-07-13"  # Monday — inside the seeded Mon-Sat test schedule
NON_WORK_DAY = "2026-07-19"  # Sunday — outside the seeded Mon-Sat test schedule


@pytest.mark.eval
@pytest.mark.llm
async def test_booking_proposes_only_real_available_slot(booking_capture):
    from tests.eval.conftest import run_conversation

    question = f"Bác sĩ có mã doctor_id={REAL_DOCTOR_ID} còn giờ trống ngày {WORK_DAY} không?"
    actual_output = await run_conversation(question)

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        context=[booking_capture.context_text()],
    )
    judge = build_judge()
    faithful_to_tool = GEval(
        name="FaithfulToCheckAvailableSlots",
        criteria=(
            "'context' contains the real check_available_slots(...) tool call "
            "and its actual return value. 'actual_output' passes only if "
            "every specific time it offers the user is a time that literally "
            "appears in that tool's returned list — it must not invent a "
            "time slot not present in 'context'."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
        threshold=THRESHOLD,
        model=judge,
    )
    assert_test(test_case, [faithful_to_tool])


@pytest.mark.eval
@pytest.mark.llm
async def test_booking_confirms_before_create_then_creates_real_booking(booking_capture):
    """Exercises the full BIZ-001 §9 confirm-then-execute round trip.

    BUG-008: create_booking here creates a real, permanent row — cancel it in
    `finally` so a repeat run against the same DB finds the slot free again.
    """
    from common.database import AsyncSessionFactory
    from dal.booking_repository import BookingRepository
    from tests.eval.conftest import run_conversation_turns

    turn_1 = (
        f"Tôi tên Nguyễn Văn A, số điện thoại 0912345678. Tôi muốn đặt lịch khám với "
        f"bác sĩ có mã doctor_id={REAL_DOCTOR_ID} vào lúc 09:00 ngày {WORK_DAY}."
    )
    turn_2 = "Đúng rồi, xác nhận đặt lịch giúp tôi."
    try:
        first_reply, second_reply = await run_conversation_turns([turn_1, turn_2])

        assert "create_booking" in booking_capture.context_text(), (
            "create_booking was never called across the 2-turn conversation — "
            f"captured calls: {booking_capture.context_text()}"
        )

        test_case = LLMTestCase(
            input=f"{turn_1}\n{turn_2}",
            actual_output=f"[turn 1] {first_reply}\n[turn 2] {second_reply}",
            context=[booking_capture.context_text()],
        )
        judge = build_judge()
        faithful_to_tool = GEval(
            name="FaithfulToBookingOutcome",
            criteria=(
                "'context' contains the real create_booking(...) tool call and its "
                "actual return value (either {'status': 'confirmed', 'booking_id': "
                "N} or {'status': 'slot_taken'}). 'actual_output' passes only if it "
                "accurately reports that exact outcome (confirmed with a booking "
                "reference, or apologizes and offers another time if slot_taken) "
                "and does not claim success if the real result was slot_taken, or "
                "vice versa."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
            threshold=THRESHOLD,
            model=judge,
        )
        assert_test(test_case, [faithful_to_tool])
    finally:
        created_ids = [
            result.id for name, result in booking_capture.results if name == "create_booking"
        ]
        for booking_id in created_ids:
            async with AsyncSessionFactory() as session:
                await BookingRepository(session).cancel_booking(booking_id)


@pytest.mark.eval
@pytest.mark.llm
async def test_booking_non_work_day_no_fabricated_slots(booking_capture):
    """doctor_id=3's seeded work_days is Mon-Sat — Sunday must show zero real slots."""
    from tests.eval.conftest import run_conversation

    question = f"Bác sĩ có mã doctor_id={REAL_DOCTOR_ID} còn giờ trống ngày {NON_WORK_DAY} không?"
    actual_output = await run_conversation(question)

    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        context=[booking_capture.context_text()],
    )
    judge = build_judge()
    faithful_to_empty_result = GEval(
        name="NoFabricatedSlotsOnNonWorkDay",
        criteria=(
            f"'context' shows check_available_slots returned an empty list for "
            f"{NON_WORK_DAY} (doctor doesn't work Sundays). 'actual_output' "
            "passes only if it tells the user there are no available slots "
            "that day (optionally suggesting another day) — it must NOT list "
            "any specific available time for that date."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
        threshold=THRESHOLD,
        model=judge,
    )
    assert_test(test_case, [faithful_to_empty_result])


def _exact_relative_cases() -> list[tuple[str, date]]:
    """Unambiguous (phrase -> resolved date) pairs, computed off the SAME UTC anchor
    the Booking Agent uses (datetime.now(UTC).date(), see booking/agent.py).

    Only phrases with a single correct answer live here. "thứ N tuần sau" is
    deliberately excluded — from e.g. a Friday, whether "thứ 2 tuần sau" means
    the coming Monday or the one after is a genuine Vietnamese ambiguity, so it's
    checked separately (a future Monday, no ISO-format demand) rather than pinned
    to one date.
    """
    today = datetime.now(UTC).date()
    return [
        ("hôm nay", today),
        ("ngày mai", today + timedelta(days=1)),
    ]


def _dates_passed_to_check_slots(captured: str) -> list[date]:
    """Pull every datetime.date the agent passed to check_available_slots out of
    the BookingToolCapture log (calls are recorded as repr strings)."""
    pattern = r"check_available_slots\(args=\(\d+, datetime\.date\((\d+), (\d+), (\d+)\)"
    return [
        date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        for m in re.finditer(pattern, captured)
    ]


@pytest.mark.eval
@pytest.mark.llm
async def test_booking_resolves_relative_date_before_checking_slots(booking_capture):
    """BUG-009: a relative Vietnamese date must be resolved to YYYY-MM-DD and passed
    to check_available_slots — the bot must NOT demand the patient type an ISO date.

    Deterministic (no LLM judge needed): asserts the real BookingRepository call
    captured by `booking_capture` used the date each phrase resolves to.
    """
    from tests.eval.conftest import run_conversation

    for phrase, expected_date in _exact_relative_cases():
        question = f"Bác sĩ có mã doctor_id={REAL_DOCTOR_ID} còn giờ trống {phrase} không?"
        actual_output = await run_conversation(question)
        captured = booking_capture.context_text()

        assert "check_available_slots" in captured, (
            f'"{phrase}": agent never called check_available_slots — it likely '
            f"fell back to demanding a date format. Reply: {actual_output!r}"
        )
        # BookingRepository.check_available_slots(doctor_id, target_date) is called
        # with a datetime.date, so its repr is what lands in the capture string.
        assert repr(expected_date) in captured, (
            f'"{phrase}": expected resolved date {expected_date.isoformat()} '
            f"({expected_date!r}) not found in captured calls:\n{captured}"
        )
        assert "YYYY-MM-DD" not in actual_output, (
            f'"{phrase}": bot still demanded the YYYY-MM-DD format instead of '
            f"resolving the relative date. Reply: {actual_output!r}"
        )


@pytest.mark.eval
@pytest.mark.llm
async def test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday(booking_capture):
    """BUG-009: "thứ 2 tuần sau" must still be resolved (to some future Monday),
    not bounced back as "give me YYYY-MM-DD". The exact week offset is a real NL
    ambiguity, so assert the *shape* (a Monday, strictly after today), not a date.
    """
    from tests.eval.conftest import run_conversation

    today = datetime.now(UTC).date()
    phrase = "thứ 2 tuần sau"
    question = f"Bác sĩ có mã doctor_id={REAL_DOCTOR_ID} còn giờ trống {phrase} không?"
    actual_output = await run_conversation(question)
    captured = booking_capture.context_text()

    assert "YYYY-MM-DD" not in actual_output, (
        f'"{phrase}": bot demanded an ISO date instead of resolving it. '
        f"Reply: {actual_output!r}"
    )
    resolved = _dates_passed_to_check_slots(captured)
    assert resolved, (
        f'"{phrase}": agent never called check_available_slots with a date. '
        f"Captured: {captured}"
    )
    assert any(d.weekday() == 0 and d > today for d in resolved), (
        f'"{phrase}": expected a future Monday, got {[d.isoformat() for d in resolved]}'
    )
