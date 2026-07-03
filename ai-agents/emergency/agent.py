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
# Description: Emergency Agent — static safety response only, no tools, no
#              dal/ access (ADR-0014). Reached two ways: Layer 1
#              (modules/conversation/controller.py, before the ADK runtime even starts —
#              see emergency_rules.is_emergency) or Layer 2 (Orchestrator
#              transfer, TASK-011) for paraphrased red-flag language.
###############################################################################

from google.adk.agents import Agent
from google.genai import types

from common.config import settings

from .prompt import EMERGENCY_INSTRUCTION


def build_emergency_agent() -> Agent:
    """Build the Emergency Agent — no tools, no sub_agents, no dal/ calls."""
    return Agent(
        name="emergency_agent",
        model=settings.emergency_llm_model,
        generate_content_config=types.GenerateContentConfig(
            temperature=settings.emergency_llm_temperature,
            max_output_tokens=settings.emergency_llm_max_tokens,
        ),
        instruction=EMERGENCY_INSTRUCTION,
        disallow_transfer_to_peers=True,
    )


emergency_agent = build_emergency_agent()
