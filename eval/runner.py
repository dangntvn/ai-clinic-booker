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
#
# UPDATED 2026-07-10 (senior-tester, TASK-015 batch 3/4) — run_rag_eval() now
# also calls the real conversation HTTP API per question (generation), so it
# can compute the new span-level + keyword + faithfulness metrics from
# eval/metrics.py against real answers, not just doc-id retrieval. Report
# format rewritten to the 7-row RAG quality table (Span Hit Rate@5/MRR,
# Context Precision@5, doc-id Hit Rate@5/MRR, Keyword Match, Faithfulness)
# plus separate intent-routing/booking-concurrency sections — see
# RAG_TARGETS below for the full threshold provenance note (existing doc-id
# thresholds preserved unchanged; the newly-added metrics get the reference
# project's suggested targets since this project never had thresholds for
# them before, flagged for Team Lead review).
###############################################################################

import asyncio
import uuid
from pathlib import Path

import httpx
import yaml

from eval.metrics import (
    booking_concurrency_pass_rate,
    chunk_hits,
    faithfulness_score,
    first_hit_rank,
    hit_rate_at_k_from_hits,
    intent_routing_accuracy,
    keyword_match,
    mean_hit_rate_at_k,
    mrr,
    mrr_from_hits,
    precision_from_hits,
)

_EVAL_DIR = Path(__file__).parent

# Production conversation endpoint (modules/conversation/controller.py) — the
# runner calls this instead of building/driving the ADK Runner in-process, so
# the reply used for eval metrics is identical to what a real end user gets.
CONVERSATION_API_URL = (
    "http://localhost:8000/api/v1/agents/booker/conversations/{conversation_id}/messages"
)

# Rank cutoff applied to every @K metric in the RAG quality table.
K = 5

INTENT_ACCURACY_THRESHOLD = 0.8
BOOKING_PASS_THRESHOLD = 1.0  # correctness-critical — must be 100%

# Targets for the RAG quality table (retrieval + generation), in report order.
# PROVENANCE (TASK-015 batch 3/4, don't change silently — see task instructions):
#   - "Hit Rate@5 (doc-id)" / "MRR (doc-id)": this project's PRE-EXISTING,
#     previously-confirmed thresholds (was HIT_RATE_THRESHOLD=0.7 /
#     MRR_THRESHOLD=0.9 before this refactor) — kept exactly as-is, NOT
#     changed to the rag-health reference's own 0.90/0.80 example numbers.
#   - "Span Hit Rate@5" / "Span MRR" / "Context Precision@5" / "Keyword
#     Match" / "Faithfulness": brand new metrics this project never
#     computed before this task, so there is no pre-existing threshold to
#     preserve. Values below are the rag-health reference project's own
#     suggested targets, adopted as a starting point — flagged here for
#     Team Lead review, not something to treat as already-validated for
#     this project's data/thresholds.
RAG_TARGETS = {
    "Span Hit Rate@5": 0.80,
    "Span MRR": 0.60,
    "Context Precision@5": 0.20,
    "Hit Rate@5 (doc-id)": 0.70,
    "MRR (doc-id)": 0.90,
    "Keyword Match": 0.70,
    "Faithfulness": 0.75,
}


def _mean(xs: list[float]) -> float:
    """Arithmetic mean of a list of floats, 0.0 for an empty list."""
    return sum(xs) / len(xs) if xs else 0.0


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


async def run_rag_eval() -> dict:
    """Run golden_set_rag.yaml's retrieval + generation quality, real infra end-to-end.

    For each case:
        1. Retrieval: embed the query and search Qdrant directly
           (dal/qdrant_client.search) — a read of already-indexed data, not
           "generating an answer", so exempt from the HTTP-only rule
           (TASK-015 batch 2/4 decision). Produces doc-id hit/MRR and,
           via ``answer_span``, the span-level hit/MRR/precision family.
        2. Generation: call the real conversation HTTP API
           (``_call_conversation_api``) to get the answer an end user would
           actually see, then score it with ``keyword_match`` and the
           LLM-judged ``faithfulness_score`` (judged against the top-K
           retrieved chunk texts).

    Returns:
        A dict with keys:
            - ``scores``:       Aggregated metric scores keyed by RAG_TARGETS' labels.
            - ``per_question``: List of per-case detail dicts (for the report's
                                 per-question breakdown).
            - ``n``:            Number of cases evaluated.
    """
    from common.gemini_client import embed_batch, generate
    from dal.qdrant_client import search

    cases = _load_cases("golden_set_rag.yaml")

    span_hit, span_mrr_scores, span_prec = [], [], []
    doc_hit, doc_mrr = [], []
    kw_scores, faith_scores = [], []
    per_question: list[dict] = []

    async with httpx.AsyncClient() as http_client:
        for case in cases:
            query = case["query"]
            span = (case.get("answer_span") or "").strip()
            keywords = case.get("answer_keywords") or []
            relevant_ids = case.get("relevant_knowledge_ids") or []

            vectors = await embed_batch([query])
            results = search(vectors[0], category=case["category"], top_k=10)
            retrieved_ids = [r["payload"]["knowledge_id"] for r in results]
            retrieved_texts = [r["payload"].get("text", "") for r in results]

            # --- doc-id-level retrieval (pre-existing metric, unchanged formula) ---
            doc_hit.append(
                1.0 if set(retrieved_ids[:K]) & set(relevant_ids) else 0.0
            )
            doc_rr = 0.0
            for rank, kid in enumerate(retrieved_ids, start=1):
                if kid in relevant_ids:
                    doc_rr = 1.0 / rank
                    break
            doc_mrr.append(doc_rr)

            # --- span-level retrieval (new) ---
            span_rank = None
            span_prec_val = None
            if span:
                hits = chunk_hits(retrieved_texts, span)
                span_hit.append(hit_rate_at_k_from_hits(hits, K))
                span_mrr_scores.append(mrr_from_hits(hits))
                span_prec_val = precision_from_hits(hits, K)
                span_prec.append(span_prec_val)
                span_rank = first_hit_rank(hits)

            # --- generation: call the real conversation API (new) ---
            conversation_id = f"eval-{uuid.uuid4()}"
            answer = await _call_conversation_api(http_client, conversation_id, query)

            context_texts = retrieved_texts[:K]
            kw = keyword_match(answer, keywords)
            faith = await faithfulness_score(answer, context_texts, generate)
            kw_scores.append(kw)
            faith_scores.append(faith)

            per_question.append(
                {
                    "query": query,
                    "answer_span": span,
                    "generated_answer": answer,
                    "span_rank": span_rank,
                    "span_prec": span_prec_val,
                    "keyword_match": kw,
                    "faithfulness": faith,
                }
            )

    scores = {
        "Span Hit Rate@5": _mean(span_hit),
        "Span MRR": _mean(span_mrr_scores),
        "Context Precision@5": _mean(span_prec),
        "Hit Rate@5 (doc-id)": _mean(doc_hit),
        "MRR (doc-id)": _mean(doc_mrr),
        "Keyword Match": _mean(kw_scores),
        "Faithfulness": _mean(faith_scores),
    }
    return {"scores": scores, "per_question": per_question, "n": len(cases)}


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

    # ``session.events`` (unlike the in-process Runner.run_async() event
    # stream this replaced) includes the user's own input turn, persisted
    # with author="user" — must be excluded here or a message the
    # Orchestrator answers directly (no sub-agent transfer at all) would be
    # misread as "handled by user" instead of "no transfer happened".
    _NON_AGENT_AUTHORS = {"orchestrator_agent", "user"}

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
                    if event.author and event.author not in _NON_AGENT_AUTHORS:
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


def _write_report(rag_result: dict, intent_result: tuple, booking_result: tuple) -> None:
    """Write evaluation results to ``eval/REPORT.md`` in Markdown table format.

    Args:
        rag_result:     Return value of ``run_rag_eval()``.
        intent_result:  ``(accuracy, raw_cases)`` from ``run_intent_eval()``.
        booking_result: ``(pass_rate, raw_cases)`` from ``run_booking_eval()``.
    """
    scores = rag_result["scores"]
    intent_accuracy, _ = intent_result
    booking_pass_rate, _ = booking_result

    lines = [
        "# Eval Report",
        "",
        f"RAG questions: {rag_result['n']} · cutoff k = {K}",
        "",
        "## 1. RAG retrieval + generation quality",
        "",
        "| Metric | Score | Target | Status |",
        "|--------|-------|--------|--------|",
    ]
    for metric, target in RAG_TARGETS.items():
        score = scores[metric]
        status = "✅" if score >= target else "❌"
        lines.append(f"| {metric} | {score:.3f} | ≥ {target:.2f} | {status} |")

    lines += [
        "",
        "### Per-question breakdown",
        "",
        "| # | Query | Span rank | Span Prec@5 | Keyword | Faithfulness |",
        "|---|-------|-----------|-------------|---------|--------------|",
    ]
    for i, q in enumerate(rag_result["per_question"], start=1):
        query = q["query"].replace("|", "\\|")
        rank = q["span_rank"] if q["span_rank"] else "—"
        prec = f"{q['span_prec']:.2f}" if q["span_prec"] is not None else "—"
        lines.append(
            f"| {i} | {query} | {rank} | {prec} | "
            f"{q['keyword_match']:.2f} | {q['faithfulness']:.2f} |"
        )

    intent_status = "✅" if intent_accuracy >= INTENT_ACCURACY_THRESHOLD else "❌"
    booking_status = "✅" if booking_pass_rate >= BOOKING_PASS_THRESHOLD else "❌"
    lines += [
        "",
        "## 2. Intent routing",
        "",
        "| Metric | Score | Target | Status |",
        "|--------|-------|--------|--------|",
        f"| Intent Routing Accuracy | {intent_accuracy:.3f} | ≥ {INTENT_ACCURACY_THRESHOLD:.2f} | {intent_status} |",
        "",
        "## 3. Booking concurrency",
        "",
        "| Metric | Score | Target | Status |",
        "|--------|-------|--------|--------|",
        f"| Booking Concurrency Pass Rate | {booking_pass_rate:.3f} | = {BOOKING_PASS_THRESHOLD:.2f} | {booking_status} |",
    ]

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

    rag_result, intent_result, booking_result = asyncio.run(_run_all())
    intent_accuracy, _ = intent_result
    booking_pass_rate, _ = booking_result

    _write_report(rag_result, intent_result, booking_result)

    rag_passed = all(rag_result["scores"][m] >= t for m, t in RAG_TARGETS.items())
    intent_passed = intent_accuracy >= INTENT_ACCURACY_THRESHOLD
    booking_passed = booking_pass_rate >= BOOKING_PASS_THRESHOLD

    return 0 if (rag_passed and intent_passed and booking_passed) else 1


if __name__ == "__main__":
    import sys

    sys.exit(run_eval())
