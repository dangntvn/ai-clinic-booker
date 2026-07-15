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
# Description: FastAPI app factory — creates the app instance and mounts the
#              /api/v1 router (modules/ CRUD controllers + the booker agent
#              conversation controller, TASK-022). TASK-016 adds startup
#              readiness waits. TASK-018: lifespan starts/stops the ingestion
#              cron scheduler (modules/knowledge_ingestion/cron.setup_scheduler),
#              which was defined but never invoked anywhere until now. TASK-032:
#              CORSMiddleware for the embeddable chat widget, origin list is
#              env-driven (common/config.py::Settings.allowed_origins). FE-10:
#              mounts app/static/ at /static so the built widget bundle
#              (app/static/widget.js) is served by this backend directly —
#              ARCH-002 §9/§11 W6 MVP hosting decision (no separate CDN yet).
###############################################################################

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import build_router
from common.config import settings
from modules.knowledge_ingestion.cron import setup_scheduler

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Start the ingestion cron scheduler on boot, stop it on shutdown."""
    scheduler = setup_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(title="AI Clinic Booking Agent", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_router())
    # FE-10: serves app/static/widget.js at /static/widget.js (ARCH-002 §9,
    # W6 — MVP hosting: backend serves the built widget bundle directly,
    # no separate CDN). StaticFiles guesses Content-Type from the file
    # extension via Python's mimetypes module. The exact value for .js
    # depends on the mimetypes table of the running environment (e.g.
    # "application/javascript" on Windows hosts vs. "text/javascript" on
    # the Linux slim container used for deploy, per RFC 9239) — both are
    # valid JS MIME types for a <script> tag, so no extra media-type
    # handling is needed.
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
