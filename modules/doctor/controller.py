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
# Description: REST CRUD controller for the doctor admin screen — replaces
#              Google Sheets (ADR-0016, ADR-0020). CRUD/orchestration only;
#              all business logic (specialty validation) lives in services.py.
###############################################################################

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_session
from core.exceptions import AppException
from modules.doctor import services

router = APIRouter(prefix="/doctors", tags=["doctors"])


class DoctorIn(BaseModel):
    full_name: str
    title: str | None = None
    specialty: str
    phone: str | None = None
    work_days: list[str] = []
    room: str | None = None
    shift: str | None = None
    fee: float | None = None
    bio: str | None = None
    education: str | None = None
    photo_url: str | None = None
    extra: dict | None = None


class DoctorUpdate(BaseModel):
    full_name: str | None = None
    title: str | None = None
    specialty: str | None = None
    phone: str | None = None
    work_days: list[str] | None = None
    room: str | None = None
    shift: str | None = None
    fee: float | None = None
    is_active: bool | None = None
    bio: str | None = None
    education: str | None = None
    photo_url: str | None = None
    extra: dict | None = None


@router.post("")
async def create_doctor(body: DoctorIn, session: AsyncSession = Depends(get_session)):
    try:
        doctor = await services.create_doctor(session, body.model_dump())
    except AppException as e:
        raise HTTPException(status_code=422, detail=e.message) from e
    return doctor


@router.get("")
async def list_doctors(
    offset: int = 0, limit: int = 50, session: AsyncSession = Depends(get_session)
):
    return await services.list_doctors(session, offset=offset, limit=limit)


@router.get("/{doctor_id}")
async def get_doctor(doctor_id: int, session: AsyncSession = Depends(get_session)):
    doctor = await services.get_doctor(session, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.patch("/{doctor_id}")
async def update_doctor(
    doctor_id: int, body: DoctorUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        return await services.update_doctor(
            session, doctor_id, body.model_dump(exclude_unset=True)
        )
    except AppException as e:
        code = 404 if e.code == "NOT_FOUND" else 422
        raise HTTPException(status_code=code, detail=e.message) from e


@router.post("/{doctor_id}/deactivate")
async def deactivate_doctor(doctor_id: int, session: AsyncSession = Depends(get_session)):
    try:
        return await services.deactivate_doctor(session, doctor_id)
    except AppException as e:
        raise HTTPException(status_code=404, detail=e.message) from e
