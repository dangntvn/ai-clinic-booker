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
# Description: Unit test for TASK-018 — app/main.py must start the ingestion
#              scheduler (modules/knowledge_ingestion/cron.setup_scheduler)
#              on FastAPI startup and stop it on shutdown, via lifespan.
#              FE-10 adds a regression test for the /static/widget.js route:
#              the exact Content-Type value returned depends on the host's
#              mimetypes table (application/javascript on Windows dev hosts,
#              text/javascript on the Linux slim container used for deploy),
#              so the test only asserts the response is a valid JS MIME type,
#              not one specific string.
###############################################################################

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app.main as main_module


def test_lifespan_starts_and_stops_the_ingestion_scheduler(monkeypatch):
    fake_scheduler = MagicMock()
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: fake_scheduler)

    app = main_module.create_app()
    with TestClient(app):
        fake_scheduler.start.assert_called_once()
        fake_scheduler.shutdown.assert_not_called()

    fake_scheduler.shutdown.assert_called_once()


def test_static_widget_js_is_served_with_a_valid_js_content_type(monkeypatch):
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: MagicMock())

    app = main_module.create_app()
    with TestClient(app) as client:
        response = client.get("/static/widget.js")

    assert response.status_code == 200
    content_type = response.headers["content-type"].split(";")[0].strip()
    assert content_type in ("application/javascript", "text/javascript")
