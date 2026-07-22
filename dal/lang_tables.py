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
# Description: Single source of truth for the 6 per-language-server suffixed
#              table names (multi-server deploy, 2026-07-22 — vn/jp/en, each
#              a fixed-language server for its whole process lifetime, all
#              sharing one Postgres instance). Originally just the 3 RAG
#              content tables (knowledge_base/knowledge_chunks/ingestion_jobs);
#              extended by ADR-0024 (2026-07-22) to also cover doctors/
#              bookings/chat_session_links, once the FK chain
#              bookings.doctor_id -> doctors.id forced those to partition by
#              the same suffix as soon as doctors did (ADR-0023 §3 is amended
#              accordingly — see that ADR's amendment note). Lives in dal/
#              (not common/) per ADR-0013/CONV-001 §4 — knowing the concrete
#              table names is repository-specific knowledge, and dal/ is the
#              one boundary allowed to hold it; common/ must stay
#              domain-agnostic (code-reviewer finding, 2026-07-22 review 1/3).
#              Every caller that needs one of these 6 table names — the ORM
#              models (dal/knowledge_repository.py, dal/chunk_repository.py,
#              dal/ingestion_job_repository.py, dal/doctor_repository.py,
#              dal/booking_repository.py), the raw-SQL cron poller
#              (modules/knowledge_ingestion/cron.py), the eval reset script
#              (scripts/seed_eval_fixtures.py), and the partitioning migrations
#              (alembic/versions/0002_partition_knowledge_by_language.py,
#              0003_partition_business_tables_by_language.py) — imports these
#              functions instead of re-deriving the f-string, so a naming typo
#              can't silently split callers across two different actual table
#              names.
###############################################################################


def knowledge_base_table(lang_suffix: str) -> str:
    """Table name for the knowledge_base ORM model/schema, suffixed by language."""
    return f"knowledge_base_{lang_suffix}"


def knowledge_chunks_table(lang_suffix: str) -> str:
    """Table name for the knowledge_chunks ORM model/schema, suffixed by language."""
    return f"knowledge_chunks_{lang_suffix}"


def ingestion_jobs_table(lang_suffix: str) -> str:
    """Table name for the ingestion_jobs ORM model/schema, suffixed by language."""
    return f"ingestion_jobs_{lang_suffix}"


def doctors_table(lang_suffix: str) -> str:
    """Table name for the doctors ORM model/schema, suffixed by language (ADR-0024)."""
    return f"doctors_{lang_suffix}"


def bookings_table(lang_suffix: str) -> str:
    """Table name for the bookings ORM model/schema, suffixed by language (ADR-0024)."""
    return f"bookings_{lang_suffix}"


def chat_session_links_table(lang_suffix: str) -> str:
    """Table name for the chat_session_links ORM model/schema, suffixed by language (ADR-0024)."""
    return f"chat_session_links_{lang_suffix}"
