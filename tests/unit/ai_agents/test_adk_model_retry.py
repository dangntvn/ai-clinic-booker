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
# Description: Unit tests for common.resilience.build_adk_model — proves ADK
#              agents' model calls now retry transient 503 UNAVAILABLE instead
#              of failing the whole turn (EVAL_FINDINGS.md §2). Verifies both
#              the wired retry policy and, using google-genai's own retry
#              machinery driven by our HttpRetryOptions, that a 503 is retried
#              and a following success is returned.
###############################################################################

import pytest
import tenacity
from google.genai._api_client import retry_args
from google.genai.errors import ServerError

from common.config import settings
from common.resilience import build_adk_model


def test_build_adk_model_wires_retry_from_settings():
    """The model instance carries a retry policy sourced from settings, not None."""
    model = build_adk_model("gemini-test-model")

    assert model.model == "gemini-test-model"
    # retry_options=None would mean google-genai's "never retry" path
    # (stop_after_attempt(1)) — the exact gap that made a single 503 fail an
    # agent turn. It must be a populated HttpRetryOptions instead.
    assert model.retry_options is not None
    assert model.retry_options.attempts == settings.llm_retry_max
    # http_status_codes left as None so google-genai applies its default
    # retryable set (408/429/500/502/503/504) — 503 is covered.
    assert model.retry_options.http_status_codes is None


def _server_error_503() -> ServerError:
    return ServerError(
        503,
        {"error": {"code": 503, "status": "UNAVAILABLE", "message": "overloaded"}},
    )


@pytest.mark.asyncio
async def test_retry_policy_retries_503_then_succeeds():
    """Drive google-genai's own retry machinery with our options: a first 503
    must be retried and the second-attempt success returned."""
    model = build_adk_model("gemini-test-model")
    retrying = tenacity.AsyncRetrying(**retry_args(model.retry_options))

    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _server_error_503()
        return "ok"

    result = await retrying(flaky)

    assert result == "ok"
    assert calls["n"] == 2  # failed once (503), succeeded on retry


@pytest.mark.asyncio
async def test_retry_policy_gives_up_after_max_attempts(monkeypatch):
    """A persistent 503 is retried up to `attempts` times, then re-raised —
    proves retries are bounded, not infinite."""
    monkeypatch.setattr(settings, "llm_retry_max", 3)
    model = build_adk_model("gemini-test-model")
    retrying = tenacity.AsyncRetrying(**retry_args(model.retry_options))

    calls = {"n": 0}

    async def always_503():
        calls["n"] += 1
        raise _server_error_503()

    with pytest.raises(ServerError):
        await retrying(always_503)

    assert calls["n"] == 3  # attempts includes the original call
