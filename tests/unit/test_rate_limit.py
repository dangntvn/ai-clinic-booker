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
# Description: Unit tests for TASK-033 — the chat rate-limiter, both at the
#              pure-function level (common/rate_limit.py) and wired through
#              the real route (modules/conversation/controller.py).
###############################################################################

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main_module
import common.rate_limit as rate_limit_module
import modules.conversation.controller as controller_module


@pytest.fixture(autouse=True)
def _clear_rate_limit_state():
    rate_limit_module._hits.clear()
    yield
    rate_limit_module._hits.clear()


def test_check_rate_limit_allows_up_to_the_limit():
    for _ in range(3):
        rate_limit_module.check_rate_limit("key-a", limit=3)


def test_check_rate_limit_blocks_the_nth_plus_one_call():
    for _ in range(3):
        rate_limit_module.check_rate_limit("key-b", limit=3)

    with pytest.raises(HTTPException) as exc_info:
        rate_limit_module.check_rate_limit("key-b", limit=3)

    assert exc_info.value.status_code == 429


def test_check_rate_limit_keys_are_independent():
    for _ in range(3):
        rate_limit_module.check_rate_limit("key-c", limit=3)

    # A different key has its own, untouched quota.
    rate_limit_module.check_rate_limit("key-d", limit=3)


def test_route_blocks_the_nth_plus_one_message_for_same_conversation(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())
    monkeypatch.setattr(controller_module, "handle_message", AsyncMock(return_value="ok"))
    monkeypatch.setattr(rate_limit_module.settings, "chat_rate_limit_per_minute", 2)

    app = main_module.create_app()
    with TestClient(app) as client:
        for _ in range(2):
            response = client.post(
                "/api/v1/agents/booker/conversations/conv-rl-1/messages",
                json={"text": "hi"},
            )
            assert response.status_code == 200

        response = client.post(
            "/api/v1/agents/booker/conversations/conv-rl-1/messages",
            json={"text": "hi"},
        )

    assert response.status_code == 429


def test_route_does_not_rate_limit_a_different_conversation_id(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())
    monkeypatch.setattr(controller_module, "handle_message", AsyncMock(return_value="ok"))
    monkeypatch.setattr(rate_limit_module.settings, "chat_rate_limit_per_minute", 1)

    app = main_module.create_app()
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/agents/booker/conversations/conv-rl-2/messages",
            json={"text": "hi"},
        )
        second = client.post(
            "/api/v1/agents/booker/conversations/conv-rl-3/messages",
            json={"text": "hi"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
