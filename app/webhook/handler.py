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
# Description: Webhook entrypoint for the Web chat channel. TASK-005 scope:
#              receive an inbound message, resolve/create the ADK session,
#              run it through the runtime, return the reply. TASK-006 adds
#              the Layer-1 emergency_rules.is_emergency() check that must run
#              here *before* the runtime call (ARCH-001 §5.4, ADR-0019).
###############################################################################

from google.genai import types

from app.runtime import build_runtime


def _session_id_for_user(user_id: str) -> str:
    """One session per user_id for the Web chat channel — keeps the webhook
    stateless (no client-managed session_id) while still giving every user a
    continuous conversation across messages.
    """
    return f"web-{user_id}"


async def handle_webhook(user_id: str, text: str) -> str:
    """Handle one inbound Web chat message end-to-end.

    Runs the message through the ADK Runner, which resolves-or-creates the
    session via SessionService and appends both the user and agent events —
    this file never touches the adk_* tables directly (ARCH-001 §6.1).

    Args:
        user_id: Stable identifier for the sender (e.g. the chat widget's visitor id).
        text: The raw inbound message text.

    Returns:
        The agent's reply text (empty string if the run produced no text event).
    """
    runner = build_runtime()
    session_id = _session_id_for_user(user_id)

    message = types.Content(role="user", parts=[types.Part(text=text)])

    reply = ""
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=message)
    async for event in events:
        if event.content and event.content.parts:
            reply = "".join(part.text or "" for part in event.content.parts)

    return reply
