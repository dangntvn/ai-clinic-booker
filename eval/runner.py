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
# Description: Evaluation runner — runs the three golden sets against a
#              live app instance (real Gemini/Qdrant/Postgres), writes
#              REPORT.md, and exits 1 if any metric misses its threshold
#              (ARCH-001 §7, §8's real quality gate). Requires network/DB —
#              not something a plain `pytest` run should ever invoke
#              (that's what @pytest.mark.eval is for).
#
# UPDATED 2026-07-10 (senior-tester, TASK-015 batch 2/4) — run_intent_eval()
# no longer imports app/runtime.py and drives the ADK Runner in-process; it
# now calls the real HTTP conversation endpoint (the exact path an end-user
# hits: app/api/v1/router.py -> modules/conversation/controller.py), then
# reads back which sub-agent authored the reply from the same
# DatabaseSessionService the app itself persists to (dal/session.py) — a
# read of state the real API call already produced, not a call into
# orchestrator/agent logic (the same category of exception already granted
# to run_rag_eval()'s direct Qdrant read). See _call_conversation_api() and
# run_intent_eval() docstrings for the full rationale, and the TASK-015
# batch report for the one open gap this surfaced: the public API has no
# field exposing "which agent handled this", so this read-back-from-session
# approach is a considered design choice, not a full architecture fix.
# run_booking_eval() intentionally still calls BookingRepository.create_booking
# directly — see its docstring for why (no booking-creation REST endpoint
# exists at all; the only reachable path is a 2-turn LLM-mediated
# conversation, unsuitable for a deterministic DB race-condition test).
###############################################################################

import asyncio
import uuid
from pathlib import Path

import httpx
import yaml

from eval.metrics import (
    booking_concurrency_pass_rate,
    intent_routing_accuracy,
    mean_hit_rate_at_k,
    mrr,
)

_EVAL_DIR = Path(__file__).parent

# Production conversation endpoint (modules/conversation/controller.py) — the
# runner calls this instead of building/driving the ADK Runner in-process, so
# the reply used for eval metrics is identical to what a real end user gets.
CONVERSATION_API_URL = (
    "http://localhost:8000/api/v1/agents/booker/conversations/{conversation_id}/messages"
)

HIT_RATE_THRESHOLD = 0.7
MRR_THRESHOLD = 0.9
INTENT_ACCURACY_THRESHOLD = 0.8
BOOKING_PASS_THRESHOLD = 1.0  # correctness-critical — must be 100%


def _load_cases(filename: str) -> list[dict]:
    with open(_EVAL_DIR / filename, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


async def _call_conversation_api(client: httpx.AsyncClient, conversation_id: str, text: str) -> str:
    """Call the real conversation HTTP endpoint and return the agent's reply text.

    Exercises the exact same path a real end user (or webhook) hits —
    app/api/v1/router.py -> modules/conversation/controller.py -> the real
    ADK runtime (Orchestrator or, on a Layer-1 emergency match, the
    dedicated Emergency runner) — instead of importing app.runtime and
    driving a Runner in-process. ``conversation_id`` doubles as the ADK
    user_id (see modules/conversation/controller.py's
    ``_session_id_for_conversation``), so a fresh uuid per call keeps every
    eval case's session state isolated.

    Args:
        client:          Shared async httpx client for the eval run.
        conversation_id: Caller-chosen id; a fresh one per case/attempt.
        text:            The user message to send.

    Returns:
        The ``reply`` string from the API response.
    """
    url = CONVERSATION_API_URL.format(conversation_id=conversation_id)
    response = await client.post(url, json={"text": text}, timeout=60.0)
    response.raise_for_status()
    return response.json()["reply"]


async def run_rag_eval() -> tuple[float, float, list[dict]]:
    """Run golden_set_rag.yaml against live Qdrant, return (hit_rate, mrr, raw_cases).

    Retrieval-only: queries Qdrant directly (embed_batch + dal/qdrant_client.search)
    to obtain retrieved_ids for the doc-id-level metrics below. This is a read
    of already-indexed data, not "generating an answer", so it's exempt from
    the "must go through the real HTTP API" rule that applies to run_intent_eval/
    run_booking_eval's generation/action step (TASK-015 batch 2/4 decision).
    """
    from common.gemini_client import embed_batch
    from dal.qdrant_client import search

    cases = _load_cases("golden_set_rag.yaml")
    scored = []
    for case in cases:
        vectors = await embed_batch([case["query"]])
        results = search(vectors[0], category=case["category"], top_k=10)
        retrieved_ids = [r["payload"]["knowledge_id"] for r in results]
        relevant_ids = case["relevant_knowledge_ids"]
        scored.append({"retrieved_ids": retrieved_ids, "relevant_ids": relevant_ids})

    return mean_hit_rate_at_k(scored, k=5), mrr(scored), scored


async def run_intent_eval() -> tuple[float, list[dict]]:
    """Run golden_set_intent.yaml against the live app over the real HTTP API.

    Generation (the reply itself) now comes from a real POST to
    ``CONVERSATION_API_URL`` — no more in-process ``build_runtime()`` +
    ``Runner.run_async()``. The one thing the public API doesn't expose is
    *which* sub-agent produced the reply (no "handled_by" field on
    ``ConversationMessageResponse``), which is exactly the signal
    ``actual_intent`` needs. Rather than add a new response field on our own
    initiative (a real API/architecture change — see TASK-015 batch report
    for this as an open recommendation), this reads the ADK session the HTTP
    call just wrote via ``dal/session.py::get_session_service()`` — the same
    ``DatabaseSessionService`` the app itself persists every event to. That's
    a read of state the real API call already produced (mirrors the
    already-accepted "query Qdrant directly for retrieval" exemption in
    run_rag_eval()), not a call into orchestrator/agent business logic.

    Returns:
        (accuracy, raw_cases) — same shape as before this change.
    """
    from app.runtime import APP_NAME
    from dal.session import get_session_service

    cases = _load_cases("golden_set_intent.yaml")
    session_service = get_session_service()
    scored = []
    async with httpx.AsyncClient() as http_client:
        for case in cases:
            conversation_id = f"eval-{uuid.uuid4()}"
            session_id = f"web-{conversation_id}"  # mirrors _session_id_for_conversation()
            await _call_conversation_api(http_client, conversation_id, case["message"])

            session = await session_service.get_session(
                app_name=APP_NAME, user_id=conversation_id, session_id=session_id
            )
            actual_intent = None
            if session is not None:
                for event in session.events:
                    if event.author and event.author != "orchestrator_agent":
                        actual_intent = event.author
            scored.append({"expected_intent": case["expected_intent"], "actual_intent": actual_intent})

    return intent_routing_accuracy(scored), scored


async def run_booking_eval() -> tuple[float, list[dict]]:
    """Run golden_set_booking.yaml as real concurrent create_booking calls.

    Intentionally still calls ``BookingRepository.create_booking`` directly
    (in-process), NOT through the HTTP API — unlike run_intent_eval() above.
    Rationale (TASK-015 batch 2/4, senior-tester decision, flagged for Team
    Lead review): there is no REST endpoint that creates a booking at all.
    ``modules/booking/controller.py`` only exposes list/cancel/reschedule;
    the only reachable path to ``create_booking`` is the agent's own 2-turn
    "check availability, then confirm" conversation (BIZ-001 §9), which is
    LLM-mediated and non-deterministic (the model isn't guaranteed to reach
    the tool call, and each of the up-to-10 concurrent attempts per case
    would need its own full LLM round trip). This golden set's entire
    purpose is proving the DB partial-unique-index race guard (ADR-0009)
    under real concurrent writes — routing it through chat would trade a
    precise, fast, deterministic DB-level test for a slow, flaky,
    LLM-dependent one, for a "safety/critical" case (booking concurrency)
    this role is explicitly supposed to protect from false positives. If an
    HTTP-level path is wanted here (e.g. an admin "create booking" endpoint)
    that's a real architecture decision (new endpoint) — not something to
    add unilaterally; escalate to software-architect if desired.

    BUG-008: every booking created here is cancelled again before returning,
    so a repeat run against the same DB starts from the same "slot is free"
    state instead of finding yesterday's run's slots already taken.
    """
    from datetime import datetime

    from common.database import AsyncSessionFactory
    from core.exceptions import InvalidSlotError, SlotTakenError
    from dal.booking_repository import BookingRepository

    cases = _load_cases("golden_set_booking.yaml")
    scored = []

    async def _one_attempt(doctor_id: int, slot_time: datetime) -> int | None:
        async with AsyncSessionFactory() as session:
            repo = BookingRepository(session)
            try:
                booking = await repo.create_booking(
                    "Eval Patient", "0000000000", doctor_id, slot_time
                )
                return booking.id
            except (SlotTakenError, InvalidSlotError):
                return None

    for case in cases:
        slot_time = datetime.fromisoformat(case["slot_time"])
        attempts = [
            _one_attempt(case["doctor_id"], slot_time) for _ in range(case["concurrent_requests"])
        ]
        results = await asyncio.gather(*attempts)
        created_ids = [booking_id for booking_id in results if booking_id is not None]
        actual_successes = len(created_ids)
        scored.append(
            {"expected_successes": case["expected_successes"], "actual_successes": actual_successes}
        )

        for booking_id in created_ids:
            async with AsyncSessionFactory() as session:
                await BookingRepository(session).cancel_booking(booking_id)

    return booking_concurrency_pass_rate(scored), scored


def _write_report(results: dict) -> None:
    lines = ["# Eval Report", ""]
    for name, (value, threshold, passed) in results.items():
        status = "PASS" if passed else "FAIL"
        lines.append(f"- **{name}**: {value:.3f} (threshold {threshold}) — {status}")
    (_EVAL_DIR / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_eval() -> int:
    """Run the evaluation suite, write REPORT.md, return exit code (0 pass / 1 fail).

    Requires GEMINI_API_KEY + live Qdrant + live Postgres — this is the
    real quality gate (ARCH-001 §7), invoked via `pytest -m eval`, never as
    part of a normal `pytest` run.
    """
    async def _run_all():
        return (
            await run_rag_eval(),
            await run_intent_eval(),
            await run_booking_eval(),
        )

    (hit_rate, mrr_score, _), (intent_accuracy, _), (booking_pass_rate, _) = asyncio.run(_run_all())

    results = {
        "retrieval_hit_rate@5": (hit_rate, HIT_RATE_THRESHOLD, hit_rate >= HIT_RATE_THRESHOLD),
        "retrieval_mrr": (mrr_score, MRR_THRESHOLD, mrr_score >= MRR_THRESHOLD),
        "intent_routing_accuracy": (
            intent_accuracy,
            INTENT_ACCURACY_THRESHOLD,
            intent_accuracy >= INTENT_ACCURACY_THRESHOLD,
        ),
        "booking_concurrency_pass_rate": (
            booking_pass_rate,
            BOOKING_PASS_THRESHOLD,
            booking_pass_rate >= BOOKING_PASS_THRESHOLD,
        ),
    }
    _write_report(results)

    return 0 if all(passed for _, _, passed in results.values()) else 1


if __name__ == "__main__":
    import sys

    sys.exit(run_eval())
