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
# Description: Partition the RAG content tables (knowledge_base/
#              knowledge_chunks/ingestion_jobs) by language, one table set
#              per suffix (multi-server deploy, 2026-07-22). ARCH-001
#              decision: 3 independent backend servers (vn/jp/en) are
#              deployed, each serving exactly one fixed language for its
#              whole process lifetime (no per-request language switching),
#              but all 3 share one Postgres instance and one Qdrant instance.
#              doctors/bookings/chat_session_links stay shared/un-suffixed —
#              only the 3 RAG content tables (system of record for authored
#              knowledge, ARCH-001 §6.1/ADR-0021) need a table per language.
#
#              This migration is deliberately settings.lang_suffix-scoped: it
#              only ever creates/drops the ONE suffix's tables for whichever
#              server runs it (settings is a module-load-time singleton, one
#              fixed value per process — common/config.py), never all 3
#              language's tables in a single run. Each of the 3 servers runs
#              `alembic upgrade head` independently against the shared DB
#              with its own LANG_SUFFIX; see alembic/env.py's version_table
#              override (also 2026-07-22) for why each server needs its own
#              alembic_version_{suffix} bookkeeping table to avoid one server
#              silently skipping this migration because another server
#              already stamped the shared alembic_version at this revision.
#
#              Every op.create_table()/op.drop_table() call below is guarded
#              by an existence check for the same reason 0001 now is: a
#              2nd/3rd server's independent alembic_version_{suffix} tracking
#              starts this migration run from a from-base replay of 0001 (see
#              that file's docstring), so by the time this migration's own
#              upgrade() runs, the un-suffixed legacy tables it expects to
#              drop may or may not still exist depending on whether an
#              earlier server already dropped them.
#
#              OPERATIONAL REQUIREMENT (code-reviewer finding, 2026-07-22
#              review 1/3): same as 0001 — every _table_exists() guard here
#              is check-then-act, not atomic, so it's only safe when the 3
#              servers run `alembic upgrade head` one at a time, not
#              concurrently. Deploy runbooks must serialise the 3 servers'
#              first migration run against this shared DB.
###############################################################################
"""partition knowledge tables by language

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22

"""

import sqlalchemy as sa

from alembic import op
from common.config import settings
from dal.lang_tables import ingestion_jobs_table, knowledge_base_table, knowledge_chunks_table

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# The one language this migration run partitions for — settings.lang_suffix is
# a module-load-time singleton fixed for this process's whole lifetime, so
# this is safe to resolve once at import time (matches the pattern already
# used by dal/knowledge_repository.py etc. for the ORM __tablename__ fields).
_SUFFIX = settings.lang_suffix
_KB_TABLE = knowledge_base_table(_SUFFIX)
_KC_TABLE = knowledge_chunks_table(_SUFFIX)
_IJ_TABLE = ingestion_jobs_table(_SUFFIX)

# The 3 un-suffixed tables 0001 created, now superseded by the per-language
# ones above. Listed child-before-parent (FK dependency order) for dropping.
_LEGACY_TABLES = ("ingestion_jobs", "knowledge_chunks", "knowledge_base")


def _table_exists(name: str) -> bool:
    """Whether ``name`` already exists — see module docstring for why every
    create/drop here needs this guard (safe replay across multiple servers
    independently migrating the one shared DB)."""
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table(name)


def upgrade() -> None:
    if not _table_exists(_KB_TABLE):
        op.create_table(
            _KB_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("category", sa.String(32), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("last_indexed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _table_exists(_KC_TABLE):
        op.create_table(
            _KC_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "knowledge_id",
                sa.Integer(),
                sa.ForeignKey(f"{_KB_TABLE}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("text", sa.String(), nullable=False),
            sa.Column("vector_id", sa.String(64)),
            sa.Column("embed_status", sa.String(16), nullable=False, server_default="pending_embed"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _table_exists(_IJ_TABLE):
        op.create_table(
            _IJ_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "knowledge_id",
                sa.Integer(),
                sa.ForeignKey(f"{_KB_TABLE}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending_chunk"),
            sa.Column("error_msg", sa.String(500)),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # Drop the legacy un-suffixed tables — guarded because only the FIRST
    # server to reach this point in the shared DB's lifetime will find them.
    # Every subsequent server has its own alembic_version_{suffix} tracking
    # (alembic/env.py), so it replays 0001 (itself now guarded, see that
    # file) before reaching here; by then an earlier server may have already
    # dropped these, and re-dropping an already-gone table raises
    # "table does not exist" without this guard.
    for legacy_table in _LEGACY_TABLES:
        if _table_exists(legacy_table):
            op.drop_table(legacy_table)


def downgrade() -> None:
    # Recreate the legacy un-suffixed tables (empty — this is a structural
    # rollback, not a data migration; the split can't be losslessly reversed
    # once 3 servers have been writing independently) so a downgrade to 0001
    # restores that revision's schema shape. Guarded the same way as
    # upgrade() — see module docstring on why more than one server may
    # independently reach this downgrade against the same shared DB.
    if not _table_exists("knowledge_base"):
        op.create_table(
            "knowledge_base",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("category", sa.String(32), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("last_indexed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _table_exists("knowledge_chunks"):
        op.create_table(
            "knowledge_chunks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "knowledge_id", sa.Integer(), sa.ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("text", sa.String(), nullable=False),
            sa.Column("vector_id", sa.String(64)),
            sa.Column("embed_status", sa.String(16), nullable=False, server_default="pending_embed"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _table_exists("ingestion_jobs"):
        op.create_table(
            "ingestion_jobs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "knowledge_id", sa.Integer(), sa.ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending_chunk"),
            sa.Column("error_msg", sa.String(500)),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # Drop this server's own suffixed tables (child-before-parent).
    if _table_exists(_IJ_TABLE):
        op.drop_table(_IJ_TABLE)
    if _table_exists(_KC_TABLE):
        op.drop_table(_KC_TABLE)
    if _table_exists(_KB_TABLE):
        op.drop_table(_KB_TABLE)
