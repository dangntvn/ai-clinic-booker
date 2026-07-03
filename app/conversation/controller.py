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
###############################################################################

from fastapi import APIRouter
from pydantic import BaseModel

from app.conversation.handler import handle_message

router = APIRouter(prefix="/agents/booker/conversations", tags=["conversations"])


class ConversationMessageRequest(BaseModel):
    """Inbound chat message payload."""

    text: str


class ConversationMessageResponse(BaseModel):
    """Outbound reply payload."""

    reply: str


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse)
async def post_message(
    conversation_id: str, message: ConversationMessageRequest
) -> ConversationMessageResponse:
    reply = await handle_message(conversation_id, message.text)
    return ConversationMessageResponse(reply=reply)
