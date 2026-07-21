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
#              The FE-10 /static/widget.js regression test was removed
#              2026-07-16 along with the route itself — the widget is no
#              longer hosted by this backend (see main.py's header comment).
#              2026-07-21 (Render demo deploy, docs/render-deploy.md): added
#              coverage for settings.enable_ingestion_cron=False skipping the
#              scheduler entirely, and confirmed the default (True) keeps the
#              original TASK-018 behavior unchanged (no regression).
###############################################################################

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app.main as main_module


def test_lifespan_starts_and_stops_the_ingestion_scheduler(monkeypatch):
    monkeypatch.setattr(main_module.settings, "enable_ingestion_cron", True)
    fake_scheduler = MagicMock()
    monkeypatch.setattr(main_module, "setup_scheduler", lambda: fake_scheduler)

    app = main_module.create_app()
    with TestClient(app):
        fake_scheduler.start.assert_called_once()
        fake_scheduler.shutdown.assert_not_called()

    fake_scheduler.shutdown.assert_called_once()


def test_lifespan_skips_the_ingestion_scheduler_when_disabled(monkeypatch):
    monkeypatch.setattr(main_module.settings, "enable_ingestion_cron", False)
    fake_setup_scheduler = MagicMock()
    monkeypatch.setattr(main_module, "setup_scheduler", fake_setup_scheduler)

    app = main_module.create_app()
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    fake_setup_scheduler.assert_not_called()
