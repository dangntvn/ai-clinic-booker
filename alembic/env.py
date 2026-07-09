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
# Description: Alembic migration environment — target_metadata is
#              core.base_model.Base, populated by importing every concrete
#              model module in dal/ so autogenerate sees the full schema.
#              Uses settings.database_url (sync psycopg driver, not asyncpg)
#              since Alembic itself runs synchronously.
###############################################################################

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from common.config import settings
from core.base_model import Base

# Import every concrete model module so Base.metadata is fully populated
# before autogenerate compares it against the live database.
from dal import (  # noqa: F401
    booking_repository,
    chunk_repository,
    doctor_repository,
    ingestion_job_repository,
    knowledge_repository,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic runs synchronously — swap the asyncpg driver for psycopg (v3, sync).
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", "+psycopg"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection, emitting raw SQL."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
