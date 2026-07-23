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
# Description: DatabaseSessionService (ADK) factory pointed at the same
#              Postgres instance used for transactional data (ADR-0015).
#              This is the only file allowed to touch ADK's own
#              sessions/events/app_states/user_states/adk_internal_metadata
#              tables — always through the SessionService API, never raw SQL.
###############################################################################

from google.adk.sessions import BaseSessionService, DatabaseSessionService

from common.config import settings

_session_service: BaseSessionService | None = None


def get_session_service() -> BaseSessionService:
    """Return the process-wide ADK session service, creating it on first use.

    Uses ``settings.database_url`` (async driver) directly — DatabaseSessionService
    creates its own async SQLAlchemy engine and, on first use, its 5 internal
    tables (``sessions``, ``events``, ``app_states``, ``user_states``,
    ``adk_internal_metadata``) in the same Postgres instance (ADR-0015).

    ``DatabaseSessionService.__init__(self, db_url, **kwargs)`` forwards every
    extra kwarg straight to ``create_async_engine(db_url, **kwargs)`` (verified
    against the installed ``google-adk==2.3.0`` source) — passing
    ``connect_args=settings.postgres_async_connect_args`` here keeps this
    engine's SSL behaviour consistent with ``common/database.py``'s own
    ``create_async_engine`` call for managed Postgres (Neon/Supabase).
    """
    global _session_service
    if _session_service is None:
        _session_service = DatabaseSessionService(
            settings.database_url, connect_args=settings.postgres_async_connect_args
        )
    return _session_service
