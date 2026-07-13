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
#
# UPDATED 2026-07-10 (senior-tester, TASK-029) — the first 3 DeepEval cases
# below (test_booking_proposes_only_real_available_slot,
# test_booking_confirms_before_create_then_creates_real_booking,
# test_booking_non_work_day_no_fabricated_slots) are now data-driven from
# eval/golden_set_deepeval_booking.yaml via
# eval/deepeval_dataset.py::load_dataset(), loaded into a real
# deepeval.dataset.EvaluationDataset. Behavior is unchanged: still real
# run_conversation()/run_conversation_turns() calls, still the real
# BookingToolCapture spy, still the same questions/metrics/thresholds/GEval
# criteria text, still the same booking cleanup in a `finally` block
# (BUG-008) — now applied defensively to every parametrized case rather
# than only the multi-turn one (harmless no-op for the 2 that never call
# create_booking, since booking_capture.results is then empty).
#
# test_booking_resolves_relative_date_before_checking_slots and
# test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday (BUG-009)
# are OUT OF SCOPE for TASK-029: they don't build an LLMTestCase or call
# assert_test at all (deterministic pytest asserts against the real captured
# tool calls, no LLM-judge metric involved) — TASK-029 is specifically about
# refactoring the LLM-judge-metric cases (see EVAL_FINDINGS.md/TASK-029 for
# why "9 case DeepEval" means these 9, not these 9 plus these 2). Left
# unchanged below.
###############################################################################

import re
from datetime import UTC, date, datetime, timedelta

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from eval.deepeval_dataset import build_metrics, load_dataset, substitute
from eval.deepeval_gemini import build_judge

REAL_DOCTOR_ID = 3  # Phạm Thị Lan Hương, Nội tổng quát — eval/seed_result_2026-07-08.json

# WORK_DAY / NON_WORK_DAY used to be hardcoded absolute dates (2026-07-13 /
# 2026-07-19). That drifts into the past over time and can coincide with
# "today" when the suite is run — which is exactly what caused
# test_booking_resolves_ambiguous_weekday_phrase_to_a_future_weekday (BUG-009)
# to fail 5/5 times on 2026-07-13, since that date happened to BE the Monday
# being asked about. Compute both dynamically, once at module scope (not
# per-test, so a single pytest run stays deterministic):
#   - WORK_DAY: "Monday of next week" relative to today, i.e. the Monday
#     that is at least 7 days out — never today/tomorrow — matching the
#     Mon-Sat seeded test schedule (scripts/seed_eval_fixtures.py
#     TEST_WORK_DAYS) and the "thứ 2 tuần sau" semantics used elsewhere.
#   - NON_WORK_DAY: the Sunday of that same following week — outside the
#     seeded Mon-Sat schedule.
_today = datetime.now(UTC).date()
_days_until_next_monday = (7 - _today.weekday()) % 7 + 7  # Monday=0; always >=7 days out
_work_day_date = _today + timedelta(days=_days_until_next_monday)
_non_work_day_date = _work_day_date + timedelta(days=6)  # Sunday of that week

WORK_DAY = _work_day_date.isoformat()  # Monday — inside the seeded Mon-Sat test schedule
NON_WORK_DAY = _non_work_day_date.isoformat()  # Sunday — outside the seeded Mon-Sat test schedule

_PLACEHOLDERS = {
    "REAL_DOCTOR_ID": REAL_DOCTOR_ID,
    "WORK_DAY": WORK_DAY,
    "NON_WORK_DAY": NON_WORK_DAY,
}

_dataset = load_dataset("golden_set_deepeval_booking.yaml")


@pytest.mark.eval
@pytest.mark.llm
@pytest.mark.parametrize("golden", _dataset.goldens, ids=[g.name for g in _dataset.goldens])
async def test_booking_cases(golden, booking_capture):
    """Run one Booking Agent DeepEval case (from golden.additional_metadata).

    See eval/golden_set_deepeval_booking.yaml for the 3 cases this
    parametrizes over: proposes-only-real-slots, the 2-turn confirm-then-book
    round trip (BIZ-001 §9), and non-work-day no-fabricated-slots — all
    GEval checks against the real BookingRepository call captured by
    `booking_capture`.
    """
    from common.database import AsyncSessionFactory
    from dal.booking_repository import BookingRepository
    from tests.eval.conftest import run_conversation, run_conversation_turns

    case = golden.additional_metadata
    turns = case.get("turns")

    try:
        if turns:
            resolved_turns = [substitute(t, **_PLACEHOLDERS) for t in turns]
            replies = await run_conversation_turns(resolved_turns)
            question = "\n".join(resolved_turns)
            actual_output = "\n".join(f"[turn {i + 1}] {reply}" for i, reply in enumerate(replies))
        else:
            question = substitute(case["input"], **_PLACEHOLDERS)
            actual_output = await run_conversation(question)

        tool_call = case.get("requires_tool_call")
        if tool_call:
            assert tool_call in booking_capture.context_text(), (
                f"{tool_call} was never called across the conversation — "
                f"captured calls: {booking_capture.context_text()}"
            )

        test_case = LLMTestCase(
            input=question,
            actual_output=actual_output,
            context=[booking_capture.context_text()],
        )
        judge = build_judge()
        assert_test(test_case, build_metrics(case, judge, **_PLACEHOLDERS))
    finally:
        # BUG-008: cancel any booking this case created so a repeat run starts
        # from the same free-slot state. No-op for cases that never reach
        # create_booking (booking_capture.results is then empty).
        created_ids = [
            result["booking_id"]
            for name, result in booking_capture.results
            if name == "create_booking" and result.get("status") == "confirmed"
        ]
        for booking_id in created_ids:
            async with AsyncSessionFactory() as session:
                await BookingRepository(session).cancel_booking(booking_id)


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
