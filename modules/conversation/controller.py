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
# Description: REST controller for the booker agent's chat API, mounted
#              under /api/v1 like every other module controller (doctor,
#              booking, knowledge) — the standard place to attach auth
#              (Depends()) later without touching app/main.py again.
#
#              Runs Layer-1 emergency screening (emergency_rules.is_emergency,
#              rule code, zero LLM calls) *before* the ADK runtime — a match
#              transfers straight to the Emergency Agent's dedicated runner,
#              skipping the Orchestrator entirely (ARCH-001 §5.4, ADR-0019,
#              BIZ-001 §3).
#
#              TASK-033: post_message is rate-limited (common/rate_limit.py)
#              since an open, unauthenticated chat endpoint costs a real LLM
#              call per message.
###############################################################################

from fastapi import APIRouter, Depends
from google.genai import types
from pydantic import BaseModel

from ai_agents.core.domain import emergency_rules
from app.runtime import build_emergency_runtime, build_runtime
from common.rate_limit import chat_rate_limit_dependency

router = APIRouter(prefix="/agents/booker/conversations", tags=["conversations"])


class ConversationMessageRequest(BaseModel):
    """Inbound chat message payload."""

    text: str


class ConversationMessageResponse(BaseModel):
    """Outbound reply payload."""

    reply: str


def _session_id_for_conversation(conversation_id: str) -> str:
    """Map a client-supplied conversation_id to an ADK session_id.

    conversation_id doubles as the ADK user_id too (TASK-021) — the Web
    channel has no separate notion of "user" distinct from "conversation".
    """
    return f"web-{conversation_id}"


async def _run(runner, user_id: str, session_id: str, text: str) -> str:
    message = types.Content(role="user", parts=[types.Part(text=text)])
    reply = ""
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=message)
    async for event in events:
        if event.content and event.content.parts:
            reply = "".join(part.text or "" for part in event.content.parts)
    return reply


async def handle_message(conversation_id: str, text: str) -> str:
    """Handle one inbound message for the booker agent, end-to-end.

    Layer 1 (rule code, no LLM call) runs first: if it matches a BIZ-001 §3
    red flag, the message goes straight to the Emergency Agent's own runner.
    Otherwise it falls through to the normal runtime (Orchestrator once
    TASK-011 lands; a placeholder echo agent until then). Layer 2 (the
    Orchestrator's own LLM-based emergency detection) lives inside that
    normal runtime path, not here.

    Args:
        conversation_id: Client-supplied id identifying the conversation;
            the session auto-creates on first use (TASK-019) so no separate
            "create conversation" call is needed.
        text: The raw inbound message text.

    Returns:
        The agent's reply text (empty string if the run produced no text event).
    """
    session_id = _session_id_for_conversation(conversation_id)

    if emergency_rules.is_emergency(text):
        return await _run(build_emergency_runtime(), conversation_id, session_id, text)

    return await _run(build_runtime(), conversation_id, session_id, text)


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
    dependencies=[Depends(chat_rate_limit_dependency)],
)
async def post_message(
    conversation_id: str, message: ConversationMessageRequest
) -> ConversationMessageResponse:
    reply = await handle_message(conversation_id, message.text)
    return ConversationMessageResponse(reply=reply)
