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
# Description: Unit test for common/config.py — Settings must load with
#              defaults alone (no .env required) and expose the Gemini
#              model fields via env var, not hardcoded (TASK-002 DoD).
###############################################################################

from common.config import Settings


def test_settings_defaults():
    settings = Settings(_env_file=None)

    assert settings.gemini_llm_model == "gemini-2.0-flash"
    assert settings.gemini_embedding_model == "text-embedding-004"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.qdrant_url.startswith("http://")


def test_settings_gemini_model_is_env_overridable(monkeypatch):
    monkeypatch.setenv("GEMINI_LLM_MODEL", "gemini-2.5-pro")

    settings = Settings(_env_file=None)

    assert settings.gemini_llm_model == "gemini-2.5-pro"
