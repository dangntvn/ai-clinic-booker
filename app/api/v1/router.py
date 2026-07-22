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
# Description: Mounts the REST API routers exposed by modules/ (booking,
#              doctor, knowledge) and the booker agent conversation
#              controller under /api/v1 — no business logic here.
###############################################################################

from fastapi import APIRouter, Depends

from common.admin_lock import require_admin_unlocked
from modules.booking.controller import router as booking_router
from modules.conversation.controller import router as conversation_router
from modules.doctor.controller import router as doctor_router
from modules.knowledge.controller import router as knowledge_router


def build_router() -> APIRouter:
    """Assemble the /api/v1 router from modules/ and app/ sub-routers."""
    router = APIRouter(prefix="/api/v1")
    router.include_router(doctor_router)
    router.include_router(booking_router)
    # Every route in knowledge_router is an admin/write CRUD route (no
    # read-only exception here, unlike doctor/booking above) — lock the whole
    # sub-router at once instead of annotating each of its 5 routes
    # individually (common/admin_lock.py).
    router.include_router(knowledge_router, dependencies=[Depends(require_admin_unlocked)])
    router.include_router(conversation_router)
    return router
