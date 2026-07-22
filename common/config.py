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

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Multi-server deploy (ARCH-001 decision 2026-07-22): 3 independent backend servers
# (vn/jp/en), each fixed to exactly one language for its whole process lifetime, all
# sharing one Postgres instance and one Qdrant instance. Public (not a leading
# underscore) so other modules reuse this exact set instead of redefining their
# own copy — scripts/seed_eval_fixtures.py's _seed_lang() imports this instead
# of keeping its own duplicate (code-reviewer finding, 2026-07-22 review 1/3).
# Table-name-building itself lives in dal/lang_tables.py, not here — that's
# repository-specific knowledge that belongs behind the dal/ boundary
# (ADR-0013/CONV-001 §4); this set is just "which language codes the app
# supports at all", a config-layer concern common/ can own without depending
# on dal/ (avoiding a common -> dal backward dependency).
SUPPORTED_LANG_SUFFIXES = {"vn", "jp", "en"}


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
    # CORS (TASK-032) — comma-separated origin list for the widget's cross-origin
    # requests. "*" (default) is fine for local/dev; production deployments must
    # set this explicitly since FastAPI/Starlette forbids "*" together with
    # allow_credentials=True.
    allowed_origins: str = "*"
    # Chat rate-limit (TASK-033) — max messages per minute per (client IP,
    # conversation_id) key, enforced in-memory (common/rate_limit.py). MVP-only:
    # not accurate across multiple app instances, see that module's docstring.
    chat_rate_limit_per_minute: int = 10
    # Admin API lock (security hardening) — when true, blocks the admin/write
    # CRUD routes (doctor create/update/deactivate, booking cancel/reschedule,
    # all of modules/knowledge) with a 403 (common/admin_lock.py). Defaults to
    # false so local dev keeps full access with zero config; set
    # IS_ADMIN_API_LOCKED=true only on public deploys (e.g. Render) where those
    # admin routes shouldn't be reachable. Read-only doctor/booking lookups and
    # the chat endpoint (modules/conversation) never depend on this — they stay
    # open regardless of this flag.
    is_admin_api_locked: bool = False

    # Gemini (ADR-0006) — model choice stays env-driven, never hardcoded.
    # gemini_llm_model/llm_temperature/llm_max_tokens below are legacy shared
    # defaults, superseded by the per-agent fields (TASK-017) that every
    # ai_agents/*/agent.py now reads instead. gemini_embedding_model is RAG's
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
    # Managed Postgres (Neon/Supabase, used by the Render.com demo deploy) rejects non-SSL
    # connections; local docker-compose Postgres has no such requirement, so this defaults to
    # off. Kept as a single connect_args flag (see postgres_*_connect_args below) rather than a
    # database_url query-string param because asyncpg and psycopg disagree on the param name
    # (asyncpg wants `ssl`, libpq/psycopg wants `sslmode`) — a single string wouldn't work for
    # both the app's async engine (common/database.py) and alembic's sync engine.
    # CONV-001 §2 exception: kept without an is_/has_/should_ prefix so the field name matches
    # its env var 1:1 (`POSTGRES_SSL`) — a name a deployer sets by copying from a provider's own
    # docs/dashboard, not a name read in application business logic.
    postgres_ssl: bool = False

    # Qdrant — composed into qdrant_url below.
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    # Managed Qdrant (e.g. Qdrant Cloud, used by the Render.com demo deploy) is HTTPS-only and
    # requires an api-key header; local docker-compose Qdrant needs neither, so both default
    # to the previous plain-HTTP/no-auth behaviour and must be opted into via env. Same
    # CONV-001 §2 naming exception as postgres_ssl above (env var `QDRANT_HTTPS`).
    qdrant_https: bool = False
    qdrant_api_key: str = ""
    qdrant_collection: str = "ai_clinic_knowledge"

    # Language partition suffix (multi-server deploy, see SUPPORTED_LANG_SUFFIXES
    # above) — appended to the RAG content tables (knowledge_base/knowledge_chunks/
    # ingestion_jobs, see dal/*_repository.py) so each of the 3 language-specific
    # servers owns its own tables on the one shared Postgres instance, instead of
    # 3 servers racing to write the same rows. Qdrant needs no equivalent field:
    # qdrant_collection above is already set to a different value per server via
    # env (e.g. ai_clinic_knowledge_vn/_jp/_en), so the 3 servers already use
    # separate Qdrant collections without any extra code. alembic/env.py also
    # reads this to give each server its own alembic_version_{suffix} tracking
    # table (see that module's docstring for why a shared alembic_version would
    # be a silent-skip trap across servers).
    # Raise-fast on an invalid value here (same "never silently default" spirit
    # as scripts/seed_eval_fixtures.py::_seed_lang()) — a typo would otherwise
    # point a server at the wrong (or a nonexistent) set of tables with no error
    # at startup, only a confusing failure later at first query.
    lang_suffix: str = "vn"
    similarity_threshold: float = 0.7  # BUG-002: 0.5 let every irrelevant-topic query "ground"
    # FAQ-only recall knob (Nhóm B task 5 — FAQ improvements, 2026-07-10). FAQ answers non-medical clinic content (policy/clinic_info)
    # where a marginal miss only costs a false "not found", not the safety risk that a loose
    # grounding cutoff poses for symptom triage — so FAQ retrieval runs slightly more permissive
    # than the global 0.7 while the safety-critical Symptom Agent keeps using similarity_threshold
    # unchanged. Kept well above the 0.5 that BUG-002 proved too permissive.
    faq_similarity_threshold: float = 0.6
    top_k: int = 6

    # Ingestion cron toggle (Render demo deploy, docs/render-deploy.md) — lets a deploy opt out
    # of running the APScheduler-based ingestion cron (modules/knowledge_ingestion/cron.py)
    # in-process, while leaving every line of that scheduler/jobstore code untouched for later
    # reuse (e.g. a real production deploy, or flipping it back on). Defaults to True so local
    # docker-compose and every existing deploy keep running the cron exactly as before; the
    # Render demo deploy is the only place that sets this to false (CEO runs ingestion/cron on
    # a local machine instead, Render only serves chat/API). Same CONV-001 §2 boolean-prefix
    # exception as postgres_ssl/qdrant_https above: kept as `enable_...` (not `should_enable_...`)
    # so the field name matches the env var (`ENABLE_INGESTION_CRON`) used verbatim across
    # render.yaml/docs/render-deploy.md/this file, not a name read only in application logic.
    enable_ingestion_cron: bool = True

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

    @field_validator("lang_suffix")
    @classmethod
    def _validate_lang_suffix(cls, v: str) -> str:
        """Fail fast if LANG_SUFFIX isn't one of the 3 supported servers' languages.

        Mirrors scripts/seed_eval_fixtures.py::_seed_lang()'s "never guess/silently
        accept a bad value" stance — an invalid suffix here would otherwise point a
        whole server's RAG tables at the wrong (or a nonexistent) table set with no
        error until some later query fails confusingly.
        """
        if v not in SUPPORTED_LANG_SUFFIXES:
            raise ValueError(
                f"LANG_SUFFIX={v!r} is not one of {sorted(SUPPORTED_LANG_SUFFIXES)} — "
                "set LANG_SUFFIX=vn|jp|en explicitly."
            )
        return v

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection string composed from the postgres_* fields."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def qdrant_url(self) -> str:
        """Qdrant endpoint composed from the qdrant_host/qdrant_port fields.

        Scheme is http unless qdrant_https is set (managed Qdrant Cloud clusters are
        HTTPS-only; local docker-compose Qdrant is plain HTTP).
        """
        scheme = "https" if self.qdrant_https else "http"
        return f"{scheme}://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def postgres_async_connect_args(self) -> dict:
        """Extra kwargs for create_async_engine (common/database.py, asyncpg driver).

        asyncpg's SQLAlchemy dialect passes connect_args straight through as kwargs to
        asyncpg.connect(), which has no `sslmode` kwarg (only `sslmode` inside a raw DSN
        *string* is parsed that way) — but asyncpg's own `ssl` kwarg natively accepts the
        same libpq-style mode strings (asyncpg.connect_utils.SSLMode.parse), so passing the
        string "require" here (not the bool True) keeps this in sync with
        postgres_sync_connect_args below instead of asking for the stricter
        certificate-verifying behaviour a plain `ssl=True` would trigger.
        """
        return {"ssl": "require"} if self.postgres_ssl else {}

    @property
    def postgres_sync_connect_args(self) -> dict:
        """Extra kwargs for alembic's sync engine (alembic/env.py, psycopg/libpq driver).

        libpq expects `sslmode`, not asyncpg's `ssl` kwarg name — see
        postgres_async_connect_args. Same "require" value on both sides: encrypt the
        connection, don't require certificate verification (adequate for Neon/Supabase,
        which don't ship a customer-facing root CA to verify against).
        """
        return {"sslmode": "require"} if self.postgres_ssl else {}

    @property
    def allowed_origins_list(self) -> list[str]:
        """``allowed_origins`` parsed into a list for CORSMiddleware."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


settings = Settings()
