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
# Description: REST CRUD controller for the internal booking admin screen —
#              no agent/LLM involved (ARCH-001 §4). CRUD/orchestration only.
###############################################################################

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from common.admin_lock import require_admin_unlocked
from common.database import get_session
from core.exceptions import AppException
from modules.booking import services

router = APIRouter(prefix="/bookings", tags=["bookings"])


class RescheduleIn(BaseModel):
    new_slot_time: datetime


@router.get("")
async def list_bookings(
    doctor_id: int | None = None,
    target_date: date | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await services.list_bookings(
        session, doctor_id=doctor_id, target_date=target_date, status=status
    )


@router.post("/{booking_id}/cancel", dependencies=[Depends(require_admin_unlocked)])
async def cancel_booking(booking_id: int, session: AsyncSession = Depends(get_session)):
    try:
        return await services.cancel_booking(session, booking_id)
    except AppException as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.post("/{booking_id}/reschedule", dependencies=[Depends(require_admin_unlocked)])
async def reschedule_booking(
    booking_id: int, body: RescheduleIn, session: AsyncSession = Depends(get_session)
):
    try:
        return await services.reschedule_booking(session, booking_id, body.new_slot_time)
    except AppException as e:
        code = {"NOT_FOUND": 404, "INVALID_SLOT": 422}.get(e.code, 409)
        raise HTTPException(status_code=code, detail=e.message) from e
