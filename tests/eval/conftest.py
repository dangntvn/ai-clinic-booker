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
# Description: Shared helpers for tests/eval/test_deepeval_*.py — runs the
#              real ADK runtime (app/runtime.py, same one the conversation
#              controller uses) end-to-end, no mocking of agent/LLM/DB/Qdrant.
#              Captures retrieval_context by wrapping the real
#              dal/qdrant_client.search() call each agent's tools module
#              binds at import time (TASK-027 DoD: don't mock actual_output).
#
# UPDATED 2026-07-10 (senior-tester, TASK-015 batch 3/4) — added
# _deepeval_metrics_recorder(), a session-scoped autouse fixture that
# captures each DeepEval metric's real score/threshold/success and writes
# eval/DEEPEVAL_REPORT.md after `pytest -m eval` finishes. It does NOT change
# how any test calls assert_test() — deepeval's assert_test() mutates the
# metric objects passed to it in place (score/success/reason become
# attributes on the same instance) but never returns or exposes them to the
# caller, so this patches the `assert_test` name each test_deepeval_*.py
# module already imported (the same "patch the consumer module's bound
# name" pattern RetrievalCapture/BookingToolCapture below already use for
# `search`/`BookingRepository`), calls the real assert_test unchanged, then
# reads the now-populated metric objects out of the same list the test
# passed in — before re-raising whatever assert_test raised, if anything.
###############################################################################

import importlib
import uuid
from pathlib import Path

import pytest
from google.genai import types

from app.runtime import build_runtime


async def run_conversation(text: str) -> str:
    """Send one message through the real Orchestrator runtime, return the reply text.

    Each call uses a fresh conversation_id so agent transfer/session state from
    one test case never leaks into another (mirrors modules/conversation/controller.py).
    """
    replies = await run_conversation_turns([text])
    return replies[-1]


async def run_conversation_turns(messages: list[str]) -> list[str]:
    """Send multiple messages in the same conversation (shared session), in order.

    Needed for booking flows that require a confirm-then-execute round trip
    (BIZ-001 §9) — a single message never reaches create_booking, only
    check_available_slots.
    """
    conversation_id = f"eval-{uuid.uuid4()}"
    runner = build_runtime()
    replies = []
    for text in messages:
        message = types.Content(role="user", parts=[types.Part(text=text)])
        reply = ""
        events = runner.run_async(
            user_id=conversation_id, session_id=conversation_id, new_message=message
        )
        async for event in events:
            if event.content and event.content.parts:
                reply = "".join(part.text or "" for part in event.content.parts)
        replies.append(reply)
    return replies


class RetrievalCapture:
    """Wraps a tools module's `search` binding to record real Qdrant results.

    `ai_agents/faq/tools.py` and `ai_agents/symptom/tools.py` both do
    `from dal.qdrant_client import search` at import time, so patching
    `dal.qdrant_client.search` itself would miss calls made through those
    already-bound names. Patching the *tools module's* `search` attribute
    works because `search_knowledge_base` resolves `search` from its own
    module globals at call time, not at def time.
    """

    def __init__(self, tools_module_path: str):
        self._module = importlib.import_module(tools_module_path)
        self._original = self._module.search
        self.calls: list[list[dict]] = []

    def __enter__(self):
        real_search = self._original

        def _spy(*args, **kwargs):
            results = real_search(*args, **kwargs)
            self.calls.append(results)
            return results

        self._module.search = _spy
        return self

    def __exit__(self, *exc_info):
        self._module.search = self._original

    def contexts(self) -> list[str]:
        """Flatten every captured Qdrant hit's chunk text across all calls in this test."""
        texts = []
        for results in self.calls:
            for r in results:
                texts.append(r["payload"]["text"])
        return texts


@pytest.fixture
def faq_retrieval():
    with RetrievalCapture("ai_agents.faq.tools") as cap:
        yield cap


@pytest.fixture
def symptom_retrieval():
    with RetrievalCapture("ai_agents.symptom.tools") as cap:
        yield cap


class BookingToolCapture:
    """Records the real return value of every BookingRepository call the agent makes.

    Used as the "ground truth" a booking reply must stay faithful to — the
    Booking Agent doesn't use Qdrant retrieval, so FaithfulnessMetric doesn't
    apply; this plays the same role for a GEval check instead.

    Patches `ai_agents/booking/tools.py`'s `BookingRepository` binding (not
    the tool functions themselves) — `google.adk.agents.Agent(tools=[...])`
    captures the tool *function objects* directly at agent-build time, so
    swapping the module's `create_booking` attribute afterward would never
    be seen by the already-built Agent. `BookingRepository` is different:
    each tool function does `BookingRepository(session)` fresh on every
    call, resolved from its own module's globals — the same free-variable
    lookup that makes `RetrievalCapture` above work for `search`.
    """

    _METHODS = ("check_available_slots", "create_booking", "update_booking", "cancel_booking")

    def __init__(self):
        self._module = importlib.import_module("ai_agents.booking.tools")
        self._original_cls = self._module.BookingRepository
        self.calls: list[str] = []
        self.results: list[tuple[str, object]] = []

    def __enter__(self):
        base_cls = self._original_cls
        calls = self.calls
        results = self.results
        namespace = {}
        for name in self._METHODS:
            base_method = getattr(base_cls, name)

            def make_method(name=name, base_method=base_method):
                async def _method(self, *args, **kwargs):
                    # Record raised calls too: check_available_slots now raises
                    # NotFoundError for a missing/inactive doctor (BUG-017), and
                    # the tool wrapper catches it into {"status":
                    # "doctor_not_found"}. Without this, a doctor_not_found eval
                    # case would see "(no booking tool was called)" in context
                    # even though the DAL call really ran. Only successful calls
                    # go into `results` (used to extract created-booking ids for
                    # cleanup) — a raised call has no result object.
                    try:
                        result = await base_method(self, *args, **kwargs)
                    except Exception as e:
                        calls.append(f"{name}(args={args}, kwargs={kwargs}) -> raised {e!r}")
                        raise
                    calls.append(f"{name}(args={args}, kwargs={kwargs}) -> {result}")
                    results.append((name, result))
                    return result

                return _method

            namespace[name] = make_method()

        spy_cls = type("SpyBookingRepository", (base_cls,), namespace)
        self._module.BookingRepository = spy_cls
        return self

    def __exit__(self, *exc_info):
        self._module.BookingRepository = self._original_cls

    def context_text(self) -> str:
        return "\n".join(self.calls) if self.calls else "(no booking tool was called)"


@pytest.fixture
def booking_capture():
    with BookingToolCapture() as cap:
        yield cap


# --- DeepEval per-metric score capture -> eval/DEEPEVAL_REPORT.md (TASK-015 batch 3/4) ---
#
# assert_test() (deepeval/evaluate/evaluate.py) computes a full TestResult
# (with real per-metric score/threshold/success/reason in .metrics_data) but
# only ever exposes it to the caller by raising an AssertionError string on
# FAILURE — on success it's silently discarded, and even on failure only the
# text is available, not structured data. Two things were tried and
# rejected before this one:
#   1. Reading .score/.success off the *metric objects* the test passes to
#      assert_test() after the call returns/raises — doesn't work, because
#      deepeval internally measures *copies* of those metrics
#      (deepeval.metrics.utils.copy_metrics), never mutating the originals.
#   2. Monkeypatching `assert_test` itself on each test_deepeval_*.py
#      module — doesn't work either: with no tests/__init__.py, pytest's
#      default "prepend" import mode imports these files as top-level
#      modules (e.g. `test_deepeval_faq`), so `importlib.import_module(
#      "tests.eval.test_deepeval_faq")` resolves to a second, different
#      module object (confirmed: `tests`/`tests.eval` still resolve as PEP
#      420 namespace packages) and patching it silently patches a module
#      pytest never actually runs.
# What works: patch `a_execute_test_cases`/`execute_test_cases` on
# `deepeval.evaluate.evaluate` — the module `assert_test` itself is DEFINED
# in, and calls internally via its own module globals (regardless of how/where
# any *caller* imported `assert_test` from). Both functions return the full
# `list[TestResult]` (each with real `.metrics_data`) before assert_test ever
# discards it, so wrapping them to record that return value, then passing it
# through unchanged, captures real scores with zero behavior change.

# Populated by the recording wrapper below, one entry per (test, metric)
# pair; drained into eval/DEEPEVAL_REPORT.md at session end.
_deepeval_results: list[dict] = []
_current_test_name: dict[str, str | None] = {"name": None}


@pytest.fixture(autouse=True)
def _track_current_deepeval_test_name(request):
    """Record the currently-running test's node name for the recorder below.

    The execute_test_cases wrapper is patched once per session (not per
    test), so it has no other way to know which test it's being called from.
    """
    _current_test_name["name"] = request.node.name
    yield


def _record_test_results(test_results) -> None:
    """Record every metric's real score/threshold/success from a TestResult batch.

    Args:
        test_results: The ``list[TestResult]`` returned by deepeval's
            ``execute_test_cases``/``a_execute_test_cases`` — each has a
            ``.metrics_data`` list of ``MetricData`` (name/score/threshold/success/reason).
    """
    for test_result in test_results:
        for metric_data in test_result.metrics_data or []:
            _deepeval_results.append(
                {
                    "test": _current_test_name["name"] or "?",
                    "metric": metric_data.name,
                    "score": metric_data.score,
                    "threshold": metric_data.threshold,
                    "success": metric_data.success,
                }
            )


def _write_deepeval_report() -> None:
    """Write eval/DEEPEVAL_REPORT.md from every recorded (test, metric) result."""
    lines = [
        "# DeepEval Report",
        "",
        f"Cases recorded this session: {len({r['test'] for r in _deepeval_results})}",
        "",
        "| Test | Metric | Score | Target | Status |",
        "|------|--------|-------|--------|--------|",
    ]
    for r in _deepeval_results:
        score = r["score"]
        threshold = r["threshold"]
        score_str = f"{score:.3f}" if isinstance(score, int | float) else "—"
        threshold_str = f"≥ {threshold:.2f}" if isinstance(threshold, int | float) else "—"
        status = "✅" if r["success"] else "❌" if r["success"] is False else "—"
        lines.append(f"| {r['test']} | {r['metric']} | {score_str} | {threshold_str} | {status} |")

    report_path = Path(__file__).parent.parent.parent / "eval" / "DEEPEVAL_REPORT.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def _deepeval_metrics_recorder():
    """Wrap deepeval's own test-execution entry points to capture real per-metric scores.

    Restores the original functions at session teardown, then writes
    eval/DEEPEVAL_REPORT.md — after all DeepEval cases in this `pytest -m
    eval` run have finished, matching the classic gate's eval/REPORT.md
    (also written once per full run, not per test).
    """
    import sys

    import deepeval  # noqa: F401 — ensures deepeval.evaluate.evaluate is registered in sys.modules

    # NOT `import deepeval.evaluate.evaluate as m`: deepeval/__init__.py does
    # `from deepeval.evaluate.evaluate import evaluate`, which rebinds the
    # `evaluate` attribute on the `deepeval` package object to that
    # function — so `deepeval.evaluate` is a function, not the submodule,
    # and `deepeval.evaluate.evaluate` fails (function has no `.evaluate`
    # attribute). The submodule is still registered under its full dotted
    # name in sys.modules regardless, so fetch it from there instead.
    deepeval_evaluate_module = sys.modules["deepeval.evaluate.evaluate"]

    real_a_execute = deepeval_evaluate_module.a_execute_test_cases
    real_execute = deepeval_evaluate_module.execute_test_cases

    async def _recording_a_execute(*args, **kwargs):
        test_results = await real_a_execute(*args, **kwargs)
        _record_test_results(test_results)
        return test_results

    def _recording_execute(*args, **kwargs):
        test_results = real_execute(*args, **kwargs)
        _record_test_results(test_results)
        return test_results

    deepeval_evaluate_module.a_execute_test_cases = _recording_a_execute
    deepeval_evaluate_module.execute_test_cases = _recording_execute

    yield

    deepeval_evaluate_module.a_execute_test_cases = real_a_execute
    deepeval_evaluate_module.execute_test_cases = real_execute

    if _deepeval_results:
        _write_deepeval_report()
