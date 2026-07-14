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
# Description: In-memory sliding-window rate limiter for the chat endpoint
#              (TASK-033) — every message costs a real LLM call, so an
#              unauthenticated, publicly embeddable widget needs a minimal
#              abuse guard. Keyed on (client IP, conversation_id) so one
#              noisy conversation cannot exhaust another's quota.
#
#              MVP scope only: state is a plain process-local dict, so this
#              is *not* accurate if the app ever runs as multiple instances
#              (each instance would enforce its own independent limit) —
#              acceptable for now, out of scope until the app needs to scale
#              horizontally (would need Redis or similar shared state then).
###############################################################################

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from common.config import settings

_WINDOW_SECONDS = 60.0

_hits: dict[str, deque[float]] = defaultdict(deque)


def _prune(bucket: deque[float], now: float) -> None:
    while bucket and now - bucket[0] >= _WINDOW_SECONDS:
        bucket.popleft()


def check_rate_limit(key: str, limit: int | None = None) -> None:
    """Raise HTTP 429 if ``key`` has already made ``limit`` calls in the last minute.

    Args:
        key: Identifies the caller, e.g. ``f"{client_ip}:{conversation_id}"``.
        limit: Max calls per rolling 60s window; defaults to
            ``settings.chat_rate_limit_per_minute``.

    Raises:
        HTTPException: 429 Too Many Requests if the caller is over the limit.
    """
    limit = settings.chat_rate_limit_per_minute if limit is None else limit
    now = time.monotonic()
    bucket = _hits[key]
    _prune(bucket, now)

    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded: max {limit} messages per minute for this "
                "conversation. Please wait before sending another message."
            ),
        )

    bucket.append(now)


def chat_rate_limit_dependency(request: Request, conversation_id: str) -> None:
    """FastAPI dependency enforcing the chat rate-limit for one route call.

    Keys on the client IP plus ``conversation_id`` (both from the request),
    per TASK-033: limiting by IP alone would let one user's several open
    conversations starve each other; by conversation_id alone would let a
    single IP spin up unlimited conversations to bypass the limit.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"{client_ip}:{conversation_id}")
