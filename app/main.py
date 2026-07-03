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
# Description: FastAPI app factory — creates the app instance, mounts the
#              booker agent conversation route and the /api/v1 router.
#              TASK-005 wires a minimal chat route so
#              app/conversation/handler.py is testable end-to-end over HTTP;
#              TASK-016 adds startup readiness waits. TASK-018: lifespan
#              starts/stops the ingestion cron scheduler
#              (modules/knowledge_ingestion/cron.setup_scheduler), which was
#              defined but never invoked anywhere until now. TASK-021: route
#              renamed from `/webhook` to `/agents/booker/conversations/{id}/
#              messages` — this is a client-invoked chat API, not a webhook
#              (no third party pushes events into it), matching the
#              conversation-resource convention used by AWS Bedrock Agents /
#              OpenAI Threads.
###############################################################################

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.api.v1.router import build_router
from app.conversation.handler import handle_message
from modules.knowledge_ingestion.cron import setup_scheduler


class ConversationMessageRequest(BaseModel):
    """Inbound chat message payload."""

    text: str


class ConversationMessageResponse(BaseModel):
    """Outbound reply payload."""

    reply: str


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
    app.include_router(build_router())

    @app.post(
        "/agents/booker/conversations/{conversation_id}/messages",
        response_model=ConversationMessageResponse,
    )
    async def post_message(
        conversation_id: str, message: ConversationMessageRequest
    ) -> ConversationMessageResponse:
        reply = await handle_message(conversation_id, message.text)
        return ConversationMessageResponse(reply=reply)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
