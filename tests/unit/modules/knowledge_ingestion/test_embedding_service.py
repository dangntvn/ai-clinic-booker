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
# Description: Unit tests for embedding_service — BUG-001 regression: the
#              first upsert of a run must be preceded by ensure_collection()
#              so a fresh Qdrant instance (no collection yet) doesn't 404.
###############################################################################

from unittest.mock import AsyncMock, MagicMock

import pytest

from dal.chunk_repository import ChunkRepository, KnowledgeChunk
from dal.ingestion_job_repository import IngestionJob
from dal.knowledge_repository import KnowledgeRepository
from modules.knowledge_ingestion import embedding_service as embedding_service_module
from modules.knowledge_ingestion.embedding_service import EmbeddingService


def _make_chunk(chunk_id: int) -> KnowledgeChunk:
    chunk = KnowledgeChunk(knowledge_id=1, ordinal=chunk_id, text=f"chunk {chunk_id}")
    chunk.id = chunk_id
    return chunk


@pytest.mark.asyncio
async def test_process_calls_ensure_collection_before_upsert(monkeypatch):
    chunks = [_make_chunk(1), _make_chunk(2)]
    knowledge = MagicMock(id=1, category="policy", title="Test doc")

    session = AsyncMock()
    monkeypatch.setattr(ChunkRepository, "get_pending_embed", AsyncMock(return_value=chunks))
    monkeypatch.setattr(KnowledgeRepository, "get", AsyncMock(return_value=knowledge))

    fake_vectors = [[0.1] * 3072, [0.2] * 3072]
    monkeypatch.setattr(
        embedding_service_module, "embed_batch", AsyncMock(return_value=fake_vectors)
    )
    ensure_collection_mock = MagicMock()
    upsert_chunks_mock = MagicMock()
    calls: list[str] = []
    ensure_collection_mock.side_effect = lambda *a, **kw: calls.append("ensure_collection")
    upsert_chunks_mock.side_effect = lambda *a, **kw: calls.append("upsert_chunks")
    monkeypatch.setattr(embedding_service_module, "ensure_collection", ensure_collection_mock)
    monkeypatch.setattr(embedding_service_module, "upsert_chunks", upsert_chunks_mock)

    service = EmbeddingService(session)
    job = IngestionJob(knowledge_id=1)
    total = await service.process(job)

    assert total == 2
    ensure_collection_mock.assert_called_once_with(3072)
    assert calls == ["ensure_collection", "upsert_chunks"]
