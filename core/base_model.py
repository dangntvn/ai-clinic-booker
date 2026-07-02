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
# Description: SQLAlchemy declarative base and reusable mixins — shared Base
#              class for every ORM model plus a TimestampMixin that tracks
#              creation/update times. Reused verbatim from rag-health (ADR-0021).
###############################################################################

from datetime import datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base shared by every ORM model in the application.

    Every concrete ORM model (defined under ``data/``) must inherit from this
    class so that Alembic's autogenerate and ``Base.metadata`` operations cover
    the full schema.
    """


class TimestampMixin:
    """Mixin that adds server-managed ``created_at`` / ``updated_at`` columns.

    Both timestamps are set by the database server (``server_default=func.now()``)
    so they remain accurate even if rows are inserted or updated outside the
    application (e.g. via SQL scripts or migrations).  ``updated_at`` is
    refreshed automatically on every UPDATE via the ``onupdate`` hook.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BaseModel(TimestampMixin, Base):
    """Abstract base ORM model combining auto-increment PK and timestamp columns.

    Inherit from this class instead of ``Base`` directly for any entity that
    needs a standard integer primary key plus created/updated tracking.  The
    ``__abstract__ = True`` flag prevents SQLAlchemy from creating a
    ``base_models`` table.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
