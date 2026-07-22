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
# Description: Single source of truth for the 3 per-language-server suffixed
#              table names (multi-server deploy, 2026-07-22 — vn/jp/en, each
#              a fixed-language server for its whole process lifetime, all
#              sharing one Postgres instance). knowledge_base/knowledge_chunks/
#              ingestion_jobs are the only tables split this way (doctors/
#              bookings/chat_session_links stay shared, see ARCH-001). Lives
#              in dal/ (not common/) per ADR-0013/CONV-001 §4 — knowing the
#              concrete table names is repository-specific knowledge, and
#              dal/ is the one boundary allowed to hold it; common/ must stay
#              domain-agnostic (code-reviewer finding, 2026-07-22 review 1/3).
#              Every caller that needs one of these 3 table names — the ORM
#              models (dal/knowledge_repository.py, dal/chunk_repository.py,
#              dal/ingestion_job_repository.py), the raw-SQL cron poller
#              (modules/knowledge_ingestion/cron.py), the eval reset script
#              (scripts/seed_eval_fixtures.py), and the partitioning migration
#              (alembic/versions/0002_partition_knowledge_by_language.py) —
#              imports these functions instead of re-deriving the f-string,
#              so a naming typo can't silently split callers across two
#              different actual table names.
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
