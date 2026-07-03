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
# Description: FAQ Agent — answers policy/insurance/clinic-info questions
#              grounded in Qdrant (ARCH-001 §4, §5.2). Registering with the
#              Orchestrator happens automatically — orchestrator/agent.py
#              picks up faq_agent by name once this module is importable.
###############################################################################

from google.adk.agents import Agent
from google.genai import types

from common.config import settings

from .prompt import FAQ_INSTRUCTION
from .tools import search_knowledge_base


def build_faq_agent() -> Agent:
    """Build the FAQ Agent with its single grounded-search tool."""
    return Agent(
        name="faq_agent",
        model=settings.faq_llm_model,
        generate_content_config=types.GenerateContentConfig(
            temperature=settings.faq_llm_temperature,
            max_output_tokens=settings.faq_llm_max_tokens,
        ),
        instruction=FAQ_INSTRUCTION,
        tools=[search_knowledge_base],
    )


faq_agent = build_faq_agent()
