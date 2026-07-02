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
# Description: Doctor admin service — calls data/doctor_repository, manages
#              both operational fields and profile fields (ADR-0020). Never
#              opens a DB connection itself; the session is injected by the
#              controller via common/database.get_session.
###############################################################################

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ValidationError
from data.doctor_repository import SPECIALTIES, Doctor, DoctorRepository


def validate_specialty(specialty: str) -> None:
    """Reject any specialty not in BIZ-001 §6's exact 14-item list.

    Raises:
        ValidationError: If ``specialty`` is not one of ``SPECIALTIES``.
    """
    if specialty not in SPECIALTIES:
        raise ValidationError(f"Unknown specialty '{specialty}' — must be one of {SPECIALTIES}")


async def create_doctor(session: AsyncSession, data: dict) -> Doctor:
    """Create a new doctor row. Validates specialty before writing."""
    validate_specialty(data["specialty"])
    repo = DoctorRepository(session)
    doctor = Doctor(**data)
    doctor = await repo.create(doctor)
    await session.commit()
    return doctor


async def list_doctors(session: AsyncSession, offset: int = 0, limit: int = 50) -> list[Doctor]:
    """List doctors for the admin screen."""
    repo = DoctorRepository(session)
    return await repo.list(offset=offset, limit=limit)


async def get_doctor(session: AsyncSession, doctor_id: int) -> Doctor | None:
    """Fetch a single doctor by id."""
    repo = DoctorRepository(session)
    return await repo.get(doctor_id)


async def update_doctor(session: AsyncSession, doctor_id: int, data: dict) -> Doctor:
    """Update a doctor record (operational or profile fields).

    Raises:
        core.exceptions.NotFoundError: If the doctor does not exist.
        core.exceptions.ValidationError: If ``data`` changes specialty to an invalid value.
    """
    from core.exceptions import NotFoundError

    repo = DoctorRepository(session)
    doctor = await repo.get(doctor_id)
    if doctor is None:
        raise NotFoundError(f"Doctor {doctor_id} not found")

    if "specialty" in data:
        validate_specialty(data["specialty"])

    for key, value in data.items():
        setattr(doctor, key, value)

    doctor = await repo.update(doctor)
    await session.commit()
    return doctor


async def deactivate_doctor(session: AsyncSession, doctor_id: int) -> Doctor:
    """Soft-delete a doctor by flipping is_active — never a hard DELETE.

    Bookings reference doctor_id with ON DELETE RESTRICT, so keeping the row
    (deactivated) preserves booking history integrity.
    """
    return await update_doctor(session, doctor_id, {"is_active": False})
