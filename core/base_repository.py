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
# Description: Generic async repository base class — implements common CRUD
#              operations (get/list/create/update/delete) over a SQLAlchemy
#              async session. Never names a concrete table (ADR-0013);
#              reused verbatim from rag-health (ADR-0021).
###############################################################################

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_model import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):  # noqa: UP046
    """Generic repository providing standard async CRUD operations for ORM models.

    Subclasses must set the class-level ``model`` attribute to the concrete
    SQLAlchemy model type they manage::

        class SomeRepository(BaseRepository[SomeModel]):
            model = SomeModel

    All mutations (create, update, delete) call ``session.flush()`` rather than
    ``session.commit()`` so that the unit-of-work boundary remains with the
    service layer — the repository never commits on its own.

    Args:
        session: An active async SQLAlchemy session, typically injected via
                 FastAPI's ``Depends(get_session)``.
    """

    model: type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id: int) -> T | None:
        """Fetch a single record by primary key.

        Args:
            id: The integer primary key of the record to fetch.

        Returns:
            The model instance if found, or ``None`` if no row matches.
        """
        result = await self.session.get(self.model, id)
        return result

    async def list(self, offset: int = 0, limit: int = 20) -> list[T]:
        """Return a paginated slice of all records, ordered by insertion order.

        Args:
            offset: Number of rows to skip (for pagination).
            limit: Maximum number of rows to return.

        Returns:
            A list of model instances (may be empty).
        """
        stmt = select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj: T) -> T:
        """Persist a new model instance and refresh it from the database.

        The object is added to the session and flushed (but not committed) so
        that auto-generated fields (``id``, ``created_at``) are populated before
        the method returns.

        Args:
            obj: A transient model instance to insert.

        Returns:
            The same instance, now in the ``persistent`` SQLAlchemy state with
            all server-generated fields populated.
        """
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: T) -> T:
        """Flush pending changes for an existing model instance and refresh it.

        Callers should modify the object's attributes directly, then call this
        method to push the changes to the database within the current transaction.

        Args:
            obj: A persistent model instance with modified attributes.

        Returns:
            The same instance after flushing and refreshing from the database.
        """
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> None:
        """Delete a record by primary key if it exists.

        Silently does nothing when no row with the given ``id`` is found,
        making the operation idempotent.

        Args:
            id: The primary key of the record to delete.
        """
        obj = await self.get(id)
        if obj is not None:
            await self.session.delete(obj)
            await self.session.flush()
