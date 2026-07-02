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
# Description: REST CRUD controller for the knowledge base admin screen.
#              CRUD/orchestration only — category validation and publish
#              semantics live in services.py.
###############################################################################

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_session
from core.exceptions import AppException
from modules.knowledge import services

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeIn(BaseModel):
    category: str
    title: str
    content: str


class KnowledgeUpdate(BaseModel):
    category: str | None = None
    title: str | None = None
    content: str | None = None


@router.post("")
async def create_draft(body: KnowledgeIn, session: AsyncSession = Depends(get_session)):
    try:
        return await services.create_draft(session, body.model_dump())
    except AppException as e:
        raise HTTPException(status_code=422, detail=e.message) from e


@router.get("")
async def list_knowledge(
    category: str | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await services.list_knowledge(session, category=category, status=status)


@router.patch("/{knowledge_id}")
async def update_draft(
    knowledge_id: int, body: KnowledgeUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        data = body.model_dump(exclude_unset=True)
        return await services.update_draft(session, knowledge_id, data)
    except AppException as e:
        code = 404 if e.code == "NOT_FOUND" else 422
        raise HTTPException(status_code=code, detail=e.message) from e


@router.post("/{knowledge_id}/publish")
async def publish(knowledge_id: int, session: AsyncSession = Depends(get_session)):
    try:
        return await services.publish(session, knowledge_id)
    except AppException as e:
        code = 404 if e.code == "NOT_FOUND" else 422
        raise HTTPException(status_code=code, detail=e.message) from e


@router.delete("/{knowledge_id}")
async def delete_knowledge(knowledge_id: int, session: AsyncSession = Depends(get_session)):
    try:
        await services.delete_knowledge(session, knowledge_id)
    except AppException as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    return {"status": "deleted"}
