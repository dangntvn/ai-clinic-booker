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
#              `_env_file=None` only turns off pydantic-settings' own dotenv
#              parsing — it can't stop a real os.environ value from another
#              source (e.g. deepeval's pytest plugin calls python-dotenv's
#              load_dotenv() on collection, which writes .env straight into
#              os.environ). Every "defaults" test below explicitly delenv's
#              the vars it asserts on so it stays correct regardless.
###############################################################################

import pytest

from common.config import Settings

_ENV_VARS_UNDER_TEST = [
    "GEMINI_LLM_MODEL",
    "GEMINI_EMBEDDING_MODEL",
    "ORCHESTRATOR_LLM_MODEL",
    "ORCHESTRATOR_LLM_TEMPERATURE",
    "ORCHESTRATOR_LLM_MAX_TOKENS",
    "BOOKING_LLM_MODEL",
    "BOOKING_LLM_TEMPERATURE",
    "BOOKING_LLM_MAX_TOKENS",
    "SYMPTOM_LLM_MODEL",
    "SYMPTOM_LLM_TEMPERATURE",
    "SYMPTOM_LLM_MAX_TOKENS",
    "FAQ_LLM_MODEL",
    "FAQ_LLM_TEMPERATURE",
    "FAQ_LLM_MAX_TOKENS",
    "EMERGENCY_LLM_MODEL",
    "EMERGENCY_LLM_TEMPERATURE",
    "EMERGENCY_LLM_MAX_TOKENS",
    "POSTGRES_SSL",
    "QDRANT_HTTPS",
    "QDRANT_API_KEY",
]


@pytest.fixture(autouse=True)
def _clear_leaked_env_vars(monkeypatch):
    for name in _ENV_VARS_UNDER_TEST:
        monkeypatch.delenv(name, raising=False)


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


AGENT_PREFIXES = ["orchestrator", "booking", "symptom", "faq", "emergency"]


@pytest.mark.parametrize("prefix", AGENT_PREFIXES)
def test_per_agent_llm_defaults_match_global_defaults(prefix):
    settings = Settings(_env_file=None)

    assert getattr(settings, f"{prefix}_llm_model") == "gemini-2.0-flash"
    assert getattr(settings, f"{prefix}_llm_temperature") == 0.0
    assert getattr(settings, f"{prefix}_llm_max_tokens") == 2048


@pytest.mark.parametrize("prefix", AGENT_PREFIXES)
def test_per_agent_llm_fields_are_independently_env_overridable(monkeypatch, prefix):
    monkeypatch.setenv(f"{prefix.upper()}_LLM_MODEL", "custom-model")
    monkeypatch.setenv(f"{prefix.upper()}_LLM_TEMPERATURE", "0.7")
    monkeypatch.setenv(f"{prefix.upper()}_LLM_MAX_TOKENS", "512")

    settings = Settings(_env_file=None)

    assert getattr(settings, f"{prefix}_llm_model") == "custom-model"
    assert getattr(settings, f"{prefix}_llm_temperature") == 0.7
    assert getattr(settings, f"{prefix}_llm_max_tokens") == 512

    other_prefixes = [p for p in AGENT_PREFIXES if p != prefix]
    for other in other_prefixes:
        assert getattr(settings, f"{other}_llm_model") == "gemini-2.0-flash"


def test_embedding_model_independent_of_per_agent_fields(monkeypatch):
    for prefix in AGENT_PREFIXES:
        monkeypatch.setenv(f"{prefix.upper()}_LLM_MODEL", "some-agent-model")

    settings = Settings(_env_file=None)

    assert settings.gemini_embedding_model == "text-embedding-004"


# Managed-service settings (demo/deploy-render branch — Neon/Supabase Postgres,
# Qdrant Cloud) default off/empty so local docker-compose is unaffected; see
# common/config.py's postgres_ssl/qdrant_https/qdrant_api_key docstrings.


def test_postgres_ssl_defaults_to_false_and_no_connect_args():
    settings = Settings(_env_file=None)

    assert settings.postgres_ssl is False
    assert settings.postgres_async_connect_args == {}
    assert settings.postgres_sync_connect_args == {}


def test_postgres_ssl_true_adds_connect_args(monkeypatch):
    monkeypatch.setenv("POSTGRES_SSL", "true")

    settings = Settings(_env_file=None)

    assert settings.postgres_ssl is True
    assert settings.postgres_async_connect_args == {"ssl": "require"}
    assert settings.postgres_sync_connect_args == {"sslmode": "require"}


def test_qdrant_https_defaults_to_false_and_http_scheme():
    settings = Settings(_env_file=None)

    assert settings.qdrant_https is False
    assert settings.qdrant_url.startswith("http://")


def test_qdrant_https_true_switches_to_https_scheme(monkeypatch):
    monkeypatch.setenv("QDRANT_HTTPS", "true")

    settings = Settings(_env_file=None)

    assert settings.qdrant_https is True
    assert settings.qdrant_url.startswith("https://")


def test_qdrant_api_key_defaults_to_empty_and_is_env_overridable(monkeypatch):
    settings = Settings(_env_file=None)
    assert settings.qdrant_api_key == ""

    monkeypatch.setenv("QDRANT_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.qdrant_api_key == "test-key"
