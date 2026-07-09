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
    """Exercises the full BIZ-001 §9 confirm-then-execute round trip."""
    from tests.eval.conftest import run_conversation_turns

    turn_1 = (
        f"Tôi tên Nguyễn Văn A, số điện thoại 0912345678. Tôi muốn đặt lịch khám với "
        f"bác sĩ có mã doctor_id={REAL_DOCTOR_ID} vào lúc 09:00 ngày {WORK_DAY}."
    )
    turn_2 = "Đúng rồi, xác nhận đặt lịch giúp tôi."
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
