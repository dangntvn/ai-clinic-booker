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
# Description: Orchestrator Agent — classifies customer intent and
#              transfers session to the matching domain agent; Layer-2
#              emergency safety net (ARCH-001 §4, ADR-0019). The only agent
#              allowed to import its sub-agents (ARCH-001 §4's "Orchestrator
#              is the one place that calls down to child agents").
###############################################################################

from google.adk.agents import Agent
from google.genai import types

from common.config import settings
from common.resilience import build_adk_model

from .prompt import ORCHESTRATOR_INSTRUCTION

# faq/symptom/booking land in TASK-012/013/014, built after this task in the
# backlog order — import defensively so the Orchestrator degrades to
# "emergency-only routing" instead of crashing if run before they exist.
_SUB_AGENT_SOURCES = (
    ("..faq.agent", "faq_agent"),
    ("..symptom.agent", "symptom_agent"),
    ("..booking.agent", "booking_agent"),
    ("..emergency.agent", "emergency_agent"),
)


def _load_sub_agents() -> list:
    import importlib

    sub_agents = []
    for module_path, attr_name in _SUB_AGENT_SOURCES:
        try:
            module = importlib.import_module(module_path, package=__package__)
        except ImportError:
            continue
        agent = getattr(module, attr_name, None)
        if agent is not None:
            sub_agents.append(agent)
    return sub_agents


def build_orchestrator_agent() -> Agent:
    """Build the Orchestrator — sub_agents gives it ADK's built-in transfer tool."""
    return Agent(
        name="orchestrator_agent",
        model=build_adk_model(settings.orchestrator_llm_model),
        generate_content_config=types.GenerateContentConfig(
            temperature=settings.orchestrator_llm_temperature,
            max_output_tokens=settings.orchestrator_llm_max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        instruction=ORCHESTRATOR_INSTRUCTION,
        sub_agents=_load_sub_agents(),
    )


orchestrator_agent = build_orchestrator_agent()
