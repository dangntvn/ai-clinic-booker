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
# Description: Unit test for the ADMIN_API_LOCKED deploy toggle
#              (common/admin_lock.py) — when settings.admin_api_locked is
#              True, the admin/write CRUD routes (doctor create/update/
#              deactivate, booking cancel/reschedule, all of
#              modules/knowledge) must respond 403, while the read-only
#              doctor/booking lookups and the chat endpoint stay open
#              regardless of the flag. Default (False) must leave every
#              route's existing behavior unchanged (no regression).
###############################################################################

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from common.database import get_session


@pytest.fixture
def app_client(monkeypatch):
    """A TestClient with the scheduler/DB session dependency stubbed out."""
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())

    app = main_module.create_app()
    app.dependency_overrides[get_session] = lambda: iter([MagicMock()])

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_admin_api_locked_defaults_to_false():
    from common.config import Settings

    assert Settings(_env_file=None).admin_api_locked is False


LOCKED_ADMIN_ROUTES = [
    ("post", "/api/v1/doctors", {"full_name": "Dr X", "specialty": "General"}),
    ("patch", "/api/v1/doctors/1", {"full_name": "Dr Y"}),
    ("post", "/api/v1/doctors/1/deactivate", None),
    ("post", "/api/v1/bookings/1/cancel", None),
    ("post", "/api/v1/bookings/1/reschedule", {"new_slot_time": "2026-08-01T10:00:00"}),
    ("post", "/api/v1/knowledge", {"category": "policy", "title": "t", "content": "c"}),
    ("get", "/api/v1/knowledge", None),
    ("patch", "/api/v1/knowledge/1", {"title": "t2"}),
    ("post", "/api/v1/knowledge/1/publish", None),
    ("delete", "/api/v1/knowledge/1", None),
]


@pytest.mark.parametrize("method, path, body", LOCKED_ADMIN_ROUTES)
def test_admin_routes_return_403_when_locked(app_client, monkeypatch, method, path, body):
    # settings is a module-level singleton (common.config.settings) shared by
    # every importer (common.admin_lock, app.main, ...), so patching the one
    # attribute here is visible everywhere the flag is read.
    monkeypatch.setattr(main_module.settings, "admin_api_locked", True)

    kwargs = {"json": body} if body is not None else {}
    response = getattr(app_client, method)(path, **kwargs)

    assert response.status_code == 403


ALWAYS_OPEN_ROUTES = [
    ("get", "/api/v1/doctors"),
    ("get", "/api/v1/doctors/1"),
    ("get", "/api/v1/bookings"),
]


@pytest.mark.parametrize("method, path", ALWAYS_OPEN_ROUTES)
def test_readonly_routes_never_return_403_when_locked(app_client, monkeypatch, method, path):
    monkeypatch.setattr(main_module.settings, "admin_api_locked", True)
    monkeypatch.setattr("modules.doctor.services.list_doctors", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "modules.doctor.services.get_doctor", AsyncMock(return_value={"id": 1})
    )
    monkeypatch.setattr("modules.booking.services.list_bookings", AsyncMock(return_value=[]))

    response = getattr(app_client, method)(path)

    assert response.status_code != 403


def test_chat_route_never_return_403_when_locked(app_client, monkeypatch):
    monkeypatch.setattr(main_module.settings, "admin_api_locked", True)
    monkeypatch.setattr(
        "modules.conversation.controller.handle_message",
        AsyncMock(return_value="hello back"),
    )

    response = app_client.post(
        "/api/v1/agents/booker/conversations/conv-lock/messages",
        json={"text": "hi"},
    )

    assert response.status_code != 403


@pytest.mark.parametrize("method, path, body", LOCKED_ADMIN_ROUTES)
def test_admin_routes_not_locked_by_default(app_client, monkeypatch, method, path, body):
    # admin_api_locked defaults to False — these routes must not be blocked by
    # this dependency (they may still fail for unrelated reasons, e.g. a
    # service-layer 404 on a fake id, but never 403 from the admin lock).
    monkeypatch.setattr(main_module.settings, "admin_api_locked", False)
    monkeypatch.setattr(
        "modules.doctor.services.create_doctor", AsyncMock(return_value={"id": 1})
    )
    monkeypatch.setattr(
        "modules.doctor.services.update_doctor", AsyncMock(return_value={"id": 1})
    )
    monkeypatch.setattr(
        "modules.doctor.services.deactivate_doctor", AsyncMock(return_value={"id": 1})
    )
    monkeypatch.setattr(
        "modules.booking.services.cancel_booking", AsyncMock(return_value={"id": 1})
    )
    monkeypatch.setattr(
        "modules.booking.services.reschedule_booking", AsyncMock(return_value={"id": 1})
    )
    monkeypatch.setattr(
        "modules.knowledge.services.create_draft", AsyncMock(return_value={"id": 1})
    )
    monkeypatch.setattr(
        "modules.knowledge.services.list_knowledge", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        "modules.knowledge.services.update_draft", AsyncMock(return_value={"id": 1})
    )
    monkeypatch.setattr("modules.knowledge.services.publish", AsyncMock(return_value={"id": 1}))
    monkeypatch.setattr(
        "modules.knowledge.services.delete_knowledge", AsyncMock(return_value=None)
    )

    kwargs = {"json": body} if body is not None else {}
    response = getattr(app_client, method)(path, **kwargs)

    assert response.status_code != 403
