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
# Description: ADK runtime wiring — builds the two Runners the webhook needs:
#              the main runner (placeholder echo agent until TASK-011 swaps
#              in the real Orchestrator) and a dedicated emergency runner
#              (ADR-0019) so Layer-1 red-flag matches skip the Orchestrator
#              entirely, as ARCH-001 §5.4 requires.
###############################################################################

from google.adk.agents import Agent
from google.adk.runners import Runner

from common.config import settings
from common.module_loader import load_ai_agents
from data.session import get_session_service

APP_NAME = "ai-clinic-agent"

_runner: Runner | None = None
_emergency_runner: Runner | None = None


def _build_placeholder_agent() -> Agent:
    """Simple echo agent used only until the Orchestrator Agent lands (TASK-011)."""
    return Agent(
        name="placeholder_echo_agent",
        model=settings.gemini_llm_model,
        instruction="Repeat back exactly what the user said, prefixed with 'Echo: '.",
    )


def build_runtime() -> Runner:
    """Return the process-wide main Runner, creating it (and its root agent) on first use."""
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=_build_placeholder_agent(),
            app_name=APP_NAME,
            session_service=get_session_service(),
        )
    return _runner


def build_emergency_runtime() -> Runner:
    """Return the process-wide emergency-only Runner (ADR-0019 Layer 1/2 target).

    Bound to the same session service as the main runner so both share one
    event history per user, but running the Emergency Agent directly — no
    Orchestrator involvement, per ARCH-001 §5.4.
    """
    global _emergency_runner
    if _emergency_runner is None:
        emergency_module = load_ai_agents("emergency.agent")
        _emergency_runner = Runner(
            agent=emergency_module.emergency_agent,
            app_name=APP_NAME,
            session_service=get_session_service(),
        )
    return _emergency_runner
