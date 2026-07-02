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
###############################################################################

import asyncio
import uuid
from pathlib import Path

import yaml

from eval.metrics import (
    booking_concurrency_pass_rate,
    intent_routing_accuracy,
    mean_hit_rate_at_k,
    mrr,
)

_EVAL_DIR = Path(__file__).parent

HIT_RATE_THRESHOLD = 0.7
MRR_THRESHOLD = 0.5
INTENT_ACCURACY_THRESHOLD = 0.8
BOOKING_PASS_THRESHOLD = 1.0  # correctness-critical — must be 100%


def _load_cases(filename: str) -> list[dict]:
    with open(_EVAL_DIR / filename, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


async def run_rag_eval() -> tuple[float, float, list[dict]]:
    """Run golden_set_rag.yaml against live Qdrant, return (hit_rate, mrr, raw_cases)."""
    from common.gemini_client import embed_batch
    from data.qdrant_client import search

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
    """Run golden_set_intent.yaml against the live Orchestrator, return (accuracy, raw_cases)."""
    from google.genai import types

    from app.runtime import build_runtime

    cases = _load_cases("golden_set_intent.yaml")
    runner = build_runtime()
    scored = []
    for case in cases:
        user_id = f"eval-{uuid.uuid4()}"
        message = types.Content(role="user", parts=[types.Part(text=case["message"])])
        actual_intent = None
        events = runner.run_async(user_id=user_id, session_id=user_id, new_message=message)
        async for event in events:
            if event.author and event.author != "orchestrator_agent":
                actual_intent = event.author
        scored.append({"expected_intent": case["expected_intent"], "actual_intent": actual_intent})

    return intent_routing_accuracy(scored), scored


async def run_booking_eval() -> tuple[float, list[dict]]:
    """Run golden_set_booking.yaml as real concurrent create_booking calls."""
    from datetime import datetime

    from common.database import AsyncSessionFactory
    from core.exceptions import SlotTakenError
    from data.booking_repository import BookingRepository

    cases = _load_cases("golden_set_booking.yaml")
    scored = []

    async def _one_attempt(doctor_id: int, slot_time: datetime) -> bool:
        async with AsyncSessionFactory() as session:
            repo = BookingRepository(session)
            try:
                await repo.create_booking("Eval Patient", "0000000000", doctor_id, slot_time)
                return True
            except SlotTakenError:
                return False

    for case in cases:
        slot_time = datetime.fromisoformat(case["slot_time"])
        attempts = [
            _one_attempt(case["doctor_id"], slot_time) for _ in range(case["concurrent_requests"])
        ]
        results = await asyncio.gather(*attempts)
        actual_successes = sum(1 for r in results if r)
        scored.append(
            {"expected_successes": case["expected_successes"], "actual_successes": actual_successes}
        )

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
    hit_rate, mrr_score, _ = asyncio.run(run_rag_eval())
    intent_accuracy, _ = asyncio.run(run_intent_eval())
    booking_pass_rate, _ = asyncio.run(run_booking_eval())

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
