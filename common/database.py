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
# Description: SQLAlchemy async database engine and session factory — the
#              generic get_session dependency used by dal/*_repository.py
#              (ADR-0013) and core/base_repository.py. Reused verbatim from
#              rag-health (ADR-0021); not listed explicitly in ARCH-001 §8,
#              added here because core/base_repository.py needs a session
#              provider and this is domain-agnostic infra, not a dal/ concern.
###############################################################################

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.config import settings

# Module-level engine and session factory are created once at import time and
# reused for the lifetime of the process. echo=False keeps SQL out of logs in
# production; flip to True locally when debugging query issues. connect_args
# carries the asyncpg-specific SSL flag (settings.postgres_ssl) required by
# managed Postgres like Neon/Supabase; empty dict (no-op) for local docker-compose.
engine = create_async_engine(
    settings.database_url, echo=False, connect_args=settings.postgres_async_connect_args
)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a single AsyncSession for the duration of a request.

    Intended to be used as a FastAPI ``Depends`` provider. The session is
    automatically closed after the request (or background task) completes,
    whether or not an exception was raised. Commit/rollback logic is left to
    the service layer — this factory does not auto-commit.

    Yields:
        AsyncSession: An active SQLAlchemy async session bound to the
                      application's database engine.
    """
    async with AsyncSessionFactory() as session:
        yield session
