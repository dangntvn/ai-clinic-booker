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
# Description: Partition the business tables (doctors/bookings/
#              chat_session_links) by language, one table set per suffix
#              (ADR-0024, 2026-07-22). CEO decision: each of the 3 language
#              servers (vn/jp/en) owns its own doctor roster (different
#              people, localized names) rather than one shared clinic
#              roster — this amends ADR-0023 §3, which had put these 3
#              tables in the "shared, un-suffixed" bucket alongside doctors/
#              bookings/chat_session_links. Doctors partitioned by table
#              (not a row-level `lang` column) forces bookings and
#              chat_session_links to follow: bookings.doctor_id is a real FK
#              to doctors.id, and a single FK column can't point at 3
#              different parent tables, so bookings must live in the same
#              per-suffix table as the doctors it references — same
#              reasoning chat_session_links.booking_id -> bookings.id.
#
#              Same settings.lang_suffix-scoped shape as 0002
#              (partition_knowledge_by_language): only ever creates/drops the
#              ONE suffix's tables for whichever server runs this, guarded by
#              _table_exists() so replay from a 2nd/3rd server's own
#              alembic_version_{suffix} bookkeeping (independent per server,
#              alembic/env.py) is safe — see 0001/0002's docstrings for the
#              full replay rationale, unchanged here.
#
#              The partial unique index that makes double-booking impossible
#              (ADR-0009, UNIQUE(doctor_id, slot_time) WHERE status !=
#              'cancelled') is preserved byte-for-byte in behaviour, just
#              recreated per-suffix with a suffixed name
#              (ix_bookings_{suffix}_doctor_slot_active) so 3 servers' indexes
#              don't collide by name on the one shared Postgres instance.
#
#              OPERATIONAL REQUIREMENT (inherited from 0001/0002, still
#              applies): every _table_exists() guard below is check-then-act,
#              not atomic — safe only when the 3 servers run
#              `alembic upgrade head` one at a time, never concurrently, on
#              their first migration against this shared DB. Deploy runbooks
#              must serialise this exactly like 0001/0002.
###############################################################################
"""partition business tables (doctors/bookings/chat_session_links) by language

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-22

"""

import sqlalchemy as sa

from alembic import op
from common.config import settings
from dal.lang_tables import bookings_table, chat_session_links_table, doctors_table

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# The one language this migration run partitions for — settings.lang_suffix is
# a module-load-time singleton fixed for this process's whole lifetime (same
# reasoning as 0002's _SUFFIX).
_SUFFIX = settings.lang_suffix
_DOCTORS_TABLE = doctors_table(_SUFFIX)
_BOOKINGS_TABLE = bookings_table(_SUFFIX)
_CSL_TABLE = chat_session_links_table(_SUFFIX)
_BOOKINGS_INDEX = f"ix_bookings_{_SUFFIX}_doctor_slot_active"

# The 3 un-suffixed tables 0001 created, now superseded by the per-language
# ones above. Listed child-before-parent (FK dependency order) for dropping.
_LEGACY_TABLES = ("chat_session_links", "bookings", "doctors")
_LEGACY_BOOKINGS_INDEX = "ix_bookings_doctor_slot_active"


def _table_exists(name: str) -> bool:
    """Whether ``name`` already exists — see module docstring for why every
    create/drop here needs this guard (safe replay across multiple servers
    independently migrating the one shared DB)."""
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table(name)


def upgrade() -> None:
    if not _table_exists(_DOCTORS_TABLE):
        op.create_table(
            _DOCTORS_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("title", sa.String(64)),
            sa.Column("specialty", sa.String(64), nullable=False),
            sa.Column("phone", sa.String(32)),
            sa.Column("work_days", sa.ARRAY(sa.String(16)), nullable=False, server_default="{}"),
            sa.Column("room", sa.String(32)),
            sa.Column("shift", sa.String(32)),
            sa.Column("fee", sa.Numeric(12, 2)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("bio", sa.String()),
            sa.Column("education", sa.String()),
            sa.Column("photo_url", sa.String(512)),
            sa.Column("extra", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _table_exists(_BOOKINGS_TABLE):
        op.create_table(
            _BOOKINGS_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("patient_name", sa.String(255), nullable=False),
            sa.Column("phone", sa.String(32), nullable=False),
            sa.Column(
                "doctor_id",
                sa.Integer(),
                sa.ForeignKey(f"{_DOCTORS_TABLE}.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("slot_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="confirmed"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        # Partial unique index (ADR-0009) — NOT a plain unique constraint. A
        # cancelled row must free its slot for a new booking, which a plain
        # UNIQUE on (doctor_id, slot_time) would forever block. Name is
        # suffixed (ADR-0024) so it doesn't collide with the other 2
        # servers' own indexes on this shared Postgres instance.
        op.create_index(
            _BOOKINGS_INDEX,
            _BOOKINGS_TABLE,
            ["doctor_id", "slot_time"],
            unique=True,
            postgresql_where=sa.text("status != 'cancelled'"),
        )

    if not _table_exists(_CSL_TABLE):
        op.create_table(
            _CSL_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "booking_id",
                sa.Integer(),
                sa.ForeignKey(f"{_BOOKINGS_TABLE}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("session_id", sa.String(128), nullable=False),
            sa.Column("user_id", sa.String(128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # Drop the legacy un-suffixed tables — guarded because only the FIRST
    # server to reach this point in the shared DB's lifetime will find them.
    # Every subsequent server has its own alembic_version_{suffix} tracking
    # (alembic/env.py), so it replays 0001/0002 (both already guarded) before
    # reaching here; by then an earlier server may have already dropped
    # these, and re-dropping an already-gone table raises "table does not
    # exist" without this guard. The index is dropped implicitly with its
    # table, so no separate op.drop_index() call is needed here.
    for legacy_table in _LEGACY_TABLES:
        if _table_exists(legacy_table):
            op.drop_table(legacy_table)


def downgrade() -> None:
    # Recreate the legacy un-suffixed tables (empty — this is a structural
    # rollback, not a data migration; the split can't be losslessly reversed
    # once 3 servers have been writing independently) so a downgrade to 0002
    # restores that revision's schema shape. Guarded the same way as
    # upgrade() — see module docstring on why more than one server may
    # independently reach this downgrade against the same shared DB.
    if not _table_exists("doctors"):
        op.create_table(
            "doctors",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("title", sa.String(64)),
            sa.Column("specialty", sa.String(64), nullable=False),
            sa.Column("phone", sa.String(32)),
            sa.Column("work_days", sa.ARRAY(sa.String(16)), nullable=False, server_default="{}"),
            sa.Column("room", sa.String(32)),
            sa.Column("shift", sa.String(32)),
            sa.Column("fee", sa.Numeric(12, 2)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("bio", sa.String()),
            sa.Column("education", sa.String()),
            sa.Column("photo_url", sa.String(512)),
            sa.Column("extra", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _table_exists("bookings"):
        op.create_table(
            "bookings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("patient_name", sa.String(255), nullable=False),
            sa.Column("phone", sa.String(32), nullable=False),
            sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("slot_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="confirmed"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index(
            _LEGACY_BOOKINGS_INDEX,
            "bookings",
            ["doctor_id", "slot_time"],
            unique=True,
            postgresql_where=sa.text("status != 'cancelled'"),
        )

    if not _table_exists("chat_session_links"):
        op.create_table(
            "chat_session_links",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_id", sa.String(128), nullable=False),
            sa.Column("user_id", sa.String(128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # Drop this server's own suffixed tables (child-before-parent).
    if _table_exists(_CSL_TABLE):
        op.drop_table(_CSL_TABLE)
    if _table_exists(_BOOKINGS_TABLE):
        op.drop_table(_BOOKINGS_TABLE)
    if _table_exists(_DOCTORS_TABLE):
        op.drop_table(_DOCTORS_TABLE)
