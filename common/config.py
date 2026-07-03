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
# Description: Centralised application configuration — every tuneable
#              parameter is a Pydantic Settings field loaded from .env.
#              Adapted from rag-health (ADR-0021): OpenAI fields replaced by
#              Gemini (ADR-0006), model selection stays env-driven per SRS-001.
###############################################################################

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables / .env.

    All fields have sensible defaults so the application can start in a local
    development environment with minimal setup. Production deployments should
    override sensitive values (``gemini_api_key``, ``postgres_password``, etc.)
    via environment variables or a secrets manager — never commit real secrets.

    Attribute groups:
        App:        Environment name, logging.
        Gemini:     API credentials and model selection (LLM + embedding).
        Postgres:   Connection parts, composed into ``database_url``.
        Qdrant:     Connection parts, composed into ``qdrant_url``, plus
                    retrieval tuning (similarity threshold, top_k).
        Ingestion:  Chunking pipeline and job-queue configuration (ADR-0021).
        Cron:       Polling intervals for background scheduler jobs.
    """

    # App
    app_env: str = "local"
    log_level: str = "INFO"
    log_path: str = "./storage/logs"
    app_port: int = 8000

    # Gemini (ADR-0006) — model choice stays env-driven, never hardcoded.
    # gemini_llm_model/llm_temperature/llm_max_tokens below are legacy shared
    # defaults, superseded by the per-agent fields (TASK-017) that every
    # ai-agents/*/agent.py now reads instead. gemini_embedding_model is RAG's
    # own model (used only by common/gemini_client.embed_batch) and is
    # intentionally independent of every per-agent chat field below it.
    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"
    llm_temperature: float = 0.0
    # 2048 was too small for callers needing long structured output (e.g. eval/deepeval_gemini.py's
    # LLM-judge, which returns a JSON object with extracted facts/reasoning) — a `gemini-2.5-flash`
    # "thinking" call can burn part of this budget on hidden reasoning tokens before ever writing
    # the visible response, so a low ceiling risks silent mid-JSON truncation (BUG-003). 8192 gives
    # real headroom; `generate()` still accepts a smaller override per-call for latency-sensitive
    # short-reply callers.
    llm_max_tokens: int = 8192
    llm_timeout_seconds: int = 120
    llm_retry_max: int = 3

    # Per-agent LLM config (TASK-017) — each agent's model/temperature/
    # max_tokens is tunable independently via its own env var.
    orchestrator_llm_model: str = "gemini-2.0-flash"
    orchestrator_llm_temperature: float = 0.0
    orchestrator_llm_max_tokens: int = 2048

    booking_llm_model: str = "gemini-2.0-flash"
    booking_llm_temperature: float = 0.0
    booking_llm_max_tokens: int = 2048

    symptom_llm_model: str = "gemini-2.0-flash"
    symptom_llm_temperature: float = 0.0
    symptom_llm_max_tokens: int = 2048

    faq_llm_model: str = "gemini-2.0-flash"
    faq_llm_temperature: float = 0.0
    faq_llm_max_tokens: int = 2048

    emergency_llm_model: str = "gemini-2.0-flash"
    emergency_llm_temperature: float = 0.0
    emergency_llm_max_tokens: int = 2048

    # Postgres — composed into database_url below.
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ai_clinic_booker"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    # Qdrant — composed into qdrant_url below.
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "ai_clinic_knowledge"
    similarity_threshold: float = 0.72  # BUG-002: 0.5 let every irrelevant-topic query "ground"
    top_k: int = 6

    # Ingestion (ADR-0021) — chunk_max_size/overlap match ARCH-001 §5.5.
    embedding_batch_size: int = 100
    semantic_chunker_threshold_type: str = "percentile"
    semantic_chunker_threshold_amount: float = 80.0
    semantic_chunker_buffer_size: int = 2
    chunk_max_size: int = 1000
    chunk_overlap: int = 150
    chunk_min_size: int = 100
    ingestion_job_batch_size: int = 3
    job_stuck_minutes: int = 30
    job_max_retry: int = 3

    # Cron intervals (seconds), ADR-0021
    cron_chunk_interval_seconds: int = 300
    cron_embed_interval_seconds: int = 300
    cron_sweep_interval_seconds: int = 600

    # Grounded generation (ADR-0008)
    not_found_message: str = "I could not find relevant information in the knowledge base."

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection string composed from the postgres_* fields."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def qdrant_url(self) -> str:
        """Qdrant HTTP endpoint composed from the qdrant_host/qdrant_port fields."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


settings = Settings()
