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
# Description: FastAPI dependency that locks admin/write CRUD routes on a
#              public deploy (ADMIN_API_LOCKED=true), while leaving read-only
#              doctor/booking lookups and the chat endpoint always open. Local
#              dev needs zero config: the flag defaults to false in
#              common/config.py, so this dependency is a no-op unless a deploy
#              explicitly opts in.
###############################################################################

from fastapi import HTTPException

from common.config import settings


def require_admin_unlocked() -> None:
    """Block admin/write endpoints when the deploy has ADMIN_API_LOCKED=true.

    Read-only doctor/booking lookups and the chat endpoint never depend on
    this — only the CRUD/admin routes that shouldn't be reachable from a
    public deploy.
    """
    if settings.admin_api_locked:
        raise HTTPException(status_code=403, detail="Admin API is locked on this deployment")
