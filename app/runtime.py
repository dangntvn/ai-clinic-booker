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
#              the main runner (now the real Orchestrator Agent, TASK-011)
#              and a dedicated emergency runner (ADR-0019) so Layer-1
#              red-flag matches skip the Orchestrator entirely, as
#              ARCH-001 §5.4 requires. auto_create_session=True (TASK-019)
#              because the webhook never pre-creates a session — ADK raises
#              SessionNotFoundError on a brand-new user_id otherwise.
###############################################################################

from google.adk.runners import Runner

from common.module_loader import load_ai_agents
from data.session import get_session_service

APP_NAME = "ai-clinic-agent"

_runner: Runner | None = None
_emergency_runner: Runner | None = None


def build_runtime() -> Runner:
    """Return the process-wide main Runner, creating it (and the Orchestrator) on first use."""
    global _runner
    if _runner is None:
        orchestrator_module = load_ai_agents("orchestrator.agent")
        _runner = Runner(
            agent=orchestrator_module.orchestrator_agent,
            app_name=APP_NAME,
            session_service=get_session_service(),
            auto_create_session=True,
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
            auto_create_session=True,
        )
    return _emergency_runner
