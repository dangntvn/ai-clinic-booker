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
# Description: Webhook entrypoint for the Web chat channel. Runs Layer-1
#              emergency screening (emergency_rules.is_emergency, rule code,
#              zero LLM calls) *before* the ADK runtime — a match transfers
#              straight to the Emergency Agent's dedicated runner, skipping
#              the Orchestrator entirely (ARCH-001 §5.4, ADR-0019, BIZ-001 §3).
###############################################################################

from google.genai import types

from app.runtime import build_emergency_runtime, build_runtime
from common.module_loader import load_ai_agents


def _session_id_for_user(user_id: str) -> str:
    """One session per user_id for the Web chat channel — keeps the webhook
    stateless (no client-managed session_id) while still giving every user a
    continuous conversation across messages.
    """
    return f"web-{user_id}"


async def _run(runner, user_id: str, session_id: str, text: str) -> str:
    message = types.Content(role="user", parts=[types.Part(text=text)])
    reply = ""
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=message)
    async for event in events:
        if event.content and event.content.parts:
            reply = "".join(part.text or "" for part in event.content.parts)
    return reply


async def handle_webhook(user_id: str, text: str) -> str:
    """Handle one inbound Web chat message end-to-end.

    Layer 1 (rule code, no LLM call) runs first: if it matches a BIZ-001 §3
    red flag, the message goes straight to the Emergency Agent's own runner.
    Otherwise it falls through to the normal runtime (Orchestrator once
    TASK-011 lands; a placeholder echo agent until then). Layer 2 (the
    Orchestrator's own LLM-based emergency detection) lives inside that
    normal runtime path, not here.

    Args:
        user_id: Stable identifier for the sender (e.g. the chat widget's visitor id).
        text: The raw inbound message text.

    Returns:
        The agent's reply text (empty string if the run produced no text event).
    """
    session_id = _session_id_for_user(user_id)

    emergency_rules = load_ai_agents("core.domain.emergency_rules")
    if emergency_rules.is_emergency(text):
        return await _run(build_emergency_runtime(), user_id, session_id, text)

    return await _run(build_runtime(), user_id, session_id, text)
