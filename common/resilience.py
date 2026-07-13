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
# Description: Retry policy for every Gemini call (ARCH-001 §7 Resilience).
#              gemini_retry wraps the *direct* genai client in gemini_client.py
#              (retry + timeout; adapted from rag-health's openai_retry,
#              ADR-0021/ADR-0006). build_adk_model applies the same *retry*
#              policy to *ADK-driven* calls (ai_agents/*/agent.py), which use
#              google-adk's own genai client and never reach gemini_retry.
#              Note: the ADK path carries retry only, not gemini_retry's
#              asyncio timeout — see .claude/memory/2026-07-09-adk-model-retry-503.md.
###############################################################################

import asyncio
from functools import wraps
from typing import TYPE_CHECKING

from tenacity import retry, stop_after_attempt, wait_exponential

from common.config import settings

if TYPE_CHECKING:
    from google.adk.models import Gemini


def gemini_retry(func):
    """Decorator that adds exponential-backoff retry and a hard timeout to an async function.

    Combines two layers of protection:

    1. **Timeout** — ``asyncio.wait_for`` enforces ``settings.llm_timeout_seconds``
       so a stalled Gemini request cannot block the event loop indefinitely.
    2. **Retry** — ``tenacity`` retries up to ``settings.llm_retry_max`` times
       with exponential back-off (1 s → 4 s) before re-raising the last exception.

    Both limits are sourced from application settings so they can be tuned
    without code changes.

    Args:
        func: An async callable (coroutine function) to wrap.

    Returns:
        A new async callable with retry + timeout behaviour applied.

    Example::

        @gemini_retry
        async def embed_batch(texts: list[str]) -> list[list[float]]:
            ...
    """

    @retry(
        stop=stop_after_attempt(settings.llm_retry_max),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.wait_for(func(*args, **kwargs), timeout=settings.llm_timeout_seconds)

    return wrapper


def build_adk_model(model_name: str) -> "Gemini":
    """Build an ADK ``Gemini`` model instance wired with the project retry policy.

    ``google.adk.agents.Agent(model="gemini-...")`` resolves a bare model-name
    string through ADK's ``LLMRegistry``, which constructs ``Gemini(retry_options=None)``.
    With ``retry_options=None`` the underlying google-genai client uses
    ``stop_after_attempt(1)`` — i.e. **no retries at all** — so a single transient
    ``503 UNAVAILABLE`` from Gemini fails the whole agent turn (see
    ``eval/EVAL_FINDINGS.md`` §2). ``common/gemini_client.py``'s ``gemini_retry``
    does not help here: ADK calls the model through its own genai client, never
    through ``gemini_client.py``.

    Passing an explicit ``Gemini`` instance with ``retry_options`` set makes
    google-genai wrap each request in ``tenacity.AsyncRetrying`` whose default
    retryable set already covers 408/429/500/502/503/504 plus httpx
    timeout/connect errors — exactly the transient failures ``gemini_retry``
    protects the direct-client path against. Attempts are sourced from
    ``settings.llm_retry_max`` so both retry layers stay in lockstep; the
    exponential backoff cap mirrors ``gemini_retry``'s ``wait_exponential(max=4)``.

    Args:
        model_name: The Gemini model id (e.g. ``settings.orchestrator_llm_model``).

    Returns:
        A ``Gemini`` model instance ready to pass as ``Agent(model=...)``.
    """
    from google.adk.models import Gemini
    from google.genai import types

    return Gemini(
        model=model_name,
        retry_options=types.HttpRetryOptions(
            attempts=settings.llm_retry_max,
            initial_delay=1.0,
            max_delay=4.0,
        ),
    )
