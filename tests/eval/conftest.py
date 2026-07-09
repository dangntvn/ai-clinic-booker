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
###############################################################################

import importlib
import uuid

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

    `ai-agents/faq/tools.py` and `ai-agents/symptom/tools.py` both do
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
    with RetrievalCapture("ai-agents.faq.tools") as cap:
        yield cap


@pytest.fixture
def symptom_retrieval():
    with RetrievalCapture("ai-agents.symptom.tools") as cap:
        yield cap


class BookingToolCapture:
    """Records the real return value of every BookingRepository call the agent makes.

    Used as the "ground truth" a booking reply must stay faithful to — the
    Booking Agent doesn't use Qdrant retrieval, so FaithfulnessMetric doesn't
    apply; this plays the same role for a GEval check instead.

    Patches `ai-agents/booking/tools.py`'s `BookingRepository` binding (not
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
        self._module = importlib.import_module("ai-agents.booking.tools")
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
                    result = await base_method(self, *args, **kwargs)
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
