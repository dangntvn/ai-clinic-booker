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
# Description: Unit test for TASK-022 — the conversation route moved into a
#              proper controller.py (matching modules/*/controller.py) and
#              under /api/v1, same as every other API in this app (TASK-021
#              had it inline in app/main.py, outside /api/v1).
###############################################################################

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

import app.conversation.controller as controller_module
import app.main as main_module


def test_conversation_message_returns_reply(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())
    fake_handle_message = AsyncMock(return_value="hello back")
    monkeypatch.setattr(controller_module, "handle_message", fake_handle_message)

    app = main_module.create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/booker/conversations/conv-1/messages",
            json={"text": "hi"},
        )

    assert response.status_code == 200
    assert response.json() == {"reply": "hello back"}
    fake_handle_message.assert_awaited_once_with("conv-1", "hi")


def test_conversation_message_reuses_same_conversation_id(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())
    fake_handle_message = AsyncMock(side_effect=["first", "second"])
    monkeypatch.setattr(controller_module, "handle_message", fake_handle_message)

    app = main_module.create_app()
    with TestClient(app) as client:
        client.post("/api/v1/agents/booker/conversations/conv-2/messages", json={"text": "a"})
        client.post("/api/v1/agents/booker/conversations/conv-2/messages", json={"text": "b"})

    assert fake_handle_message.await_args_list[0].args == ("conv-2", "a")
    assert fake_handle_message.await_args_list[1].args == ("conv-2", "b")


def test_route_without_v1_prefix_no_longer_exists(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())
    app = main_module.create_app()
    with TestClient(app) as client:
        response = client.post(
            "/agents/booker/conversations/conv-3/messages", json={"text": "hi"}
        )

    assert response.status_code == 404


def test_old_webhook_route_no_longer_exists(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())
    app = main_module.create_app()
    with TestClient(app) as client:
        response = client.post("/webhook", json={"user_id": "u1", "text": "hi"})

    assert response.status_code == 404
