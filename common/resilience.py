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
# Description: Resilience decorator for async functions — retry + timeout
#              around every Gemini call (ARCH-001 §7 Resilience). Adapted
#              from rag-health's openai_retry (ADR-0021), renamed to match
#              the Gemini provider used in this project (ADR-0006).
###############################################################################

import asyncio
from functools import wraps

from tenacity import retry, stop_after_attempt, wait_exponential

from common.config import settings


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
