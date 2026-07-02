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
# Description: ADK runtime wiring — builds the Runner bound to the shared
#              DatabaseSessionService. TASK-005 registers a placeholder echo
#              root agent so the webhook is testable end-to-end before the
#              real Orchestrator Agent exists; TASK-011 replaces it.
###############################################################################

from google.adk.agents import Agent
from google.adk.runners import Runner

from common.config import settings
from data.session import get_session_service

APP_NAME = "ai-clinic-agent"

_runner: Runner | None = None


def _build_placeholder_agent() -> Agent:
    """Simple echo agent used only until the Orchestrator Agent lands (TASK-011)."""
    return Agent(
        name="placeholder_echo_agent",
        model=settings.gemini_llm_model,
        instruction="Repeat back exactly what the user said, prefixed with 'Echo: '.",
    )


def build_runtime() -> Runner:
    """Return the process-wide Runner, creating it (and its root agent) on first use."""
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=_build_placeholder_agent(),
            app_name=APP_NAME,
            session_service=get_session_service(),
        )
    return _runner
