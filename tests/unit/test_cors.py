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
# Description: Unit test for TASK-032 — CORSMiddleware must reflect an
#              allow-listed Origin back in Access-Control-Allow-Origin, and
#              must not do so for an Origin outside the configured allow list.
###############################################################################

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app.main as main_module


def test_allowed_origin_gets_cors_header(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())
    monkeypatch.setattr(
        main_module.settings, "allowed_origins", "https://example-clinic.vn"
    )

    app = main_module.create_app()
    with TestClient(app) as client:
        response = client.get(
            "/health", headers={"Origin": "https://example-clinic.vn"}
        )

    assert response.headers["access-control-allow-origin"] == "https://example-clinic.vn"


def test_disallowed_origin_gets_no_cors_header(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())
    monkeypatch.setattr(
        main_module.settings, "allowed_origins", "https://example-clinic.vn"
    )

    app = main_module.create_app()
    with TestClient(app) as client:
        response = client.get(
            "/health", headers={"Origin": "https://not-allowed.example"}
        )

    assert "access-control-allow-origin" not in response.headers
