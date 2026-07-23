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
#              env-driven (common/config.py::Settings.allowed_origins). The
#              FE-10 /static mount (ARCH-002 §9/§11 W6, "backend serves the
#              built widget bundle directly") was removed 2026-07-16 — the
#              widget is now hosted separately from this backend (CEO
#              decision, see .claude/memory/2026-07-16-widget-hosting-moved-off-backend.md).
#              Render demo deploy (docs/render-deploy.md): the ingestion cron can be disabled
#              via ``settings.enable_ingestion_cron`` (env ``ENABLE_INGESTION_CRON=false``) —
#              CEO runs ingestion/cron on a local machine for that demo, Render only serves
#              chat/API. Scheduler code itself is untouched, just not started.
###############################################################################

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import build_router
from common.config import settings
from common.observability import get_logger
from modules.knowledge_ingestion.cron import setup_scheduler

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Start the ingestion cron scheduler on boot, stop it on shutdown.

    Skipped entirely when ``settings.enable_ingestion_cron`` is False — the app still serves
    chat/API traffic normally, it just never calls ``setup_scheduler()``/starts the
    APScheduler jobstore (see docs/render-deploy.md for why the Render demo deploy sets this).
    """
    if not settings.enable_ingestion_cron:
        logger.info("ingestion_cron.disabled", reason="ENABLE_INGESTION_CRON=false")
        yield
        return
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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
