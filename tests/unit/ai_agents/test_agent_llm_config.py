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
# Description: Unit tests for TASK-017 — every agent must build its `model` /
#              temperature / max_output_tokens from its own settings fields,
#              never the shared gemini_llm_model/llm_temperature/llm_max_tokens.
###############################################################################

import pytest

from common.config import settings
from common.module_loader import load_ai_agents

AGENTS = [
    ("orchestrator.agent", "build_orchestrator_agent", "orchestrator"),
    ("booking.agent", "build_booking_agent", "booking"),
    ("symptom.agent", "build_symptom_agent", "symptom"),
    ("faq.agent", "build_faq_agent", "faq"),
    ("emergency.agent", "build_emergency_agent", "emergency"),
]


@pytest.mark.parametrize("module_path, builder_name, prefix", AGENTS)
def test_agent_uses_its_own_llm_config(monkeypatch, module_path, builder_name, prefix):
    monkeypatch.setattr(settings, f"{prefix}_llm_model", "test-model-x")
    monkeypatch.setattr(settings, f"{prefix}_llm_temperature", 0.42)
    monkeypatch.setattr(settings, f"{prefix}_llm_max_tokens", 999)

    module = load_ai_agents(module_path)
    agent = getattr(module, builder_name)()

    assert agent.model == "test-model-x"
    assert agent.generate_content_config.temperature == 0.42
    assert agent.generate_content_config.max_output_tokens == 999


def test_overriding_one_agent_does_not_affect_another(monkeypatch):
    monkeypatch.setattr(settings, "faq_llm_model", "faq-only-model")

    faq_module = load_ai_agents("faq.agent")
    booking_module = load_ai_agents("booking.agent")
    faq_agent = faq_module.build_faq_agent()
    booking_agent = booking_module.build_booking_agent()

    assert faq_agent.model == "faq-only-model"
    assert booking_agent.model == settings.booking_llm_model
    assert booking_agent.model != "faq-only-model"
