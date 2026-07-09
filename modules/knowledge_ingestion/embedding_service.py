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
# Description: Embedding service — batches pending knowledge_chunks
#              (EMBEDDING_BATCH_SIZE), embeds via common/gemini_client, and
#              upserts into Qdrant with the {knowledge_id, chunk_id, category,
#              title, text} payload (ARCH-001 §6.2). Adapted from rag-health's
#              embedding_service.py (ADR-0021) — OpenAI/LangChain swapped for
#              the project's own Gemini client, no LangChain dependency here.
###############################################################################

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from common.gemini_client import embed_batch
from common.observability import get_logger
from dal.chunk_repository import ChunkRepository
from dal.ingestion_job_repository import IngestionJob
from dal.knowledge_repository import KnowledgeRepository
from dal.qdrant_client import ensure_collection, upsert_chunks

logger = get_logger(__name__)


class EmbeddingService:
    """Embeds un-vectorised knowledge_chunks and upserts them into Qdrant.

    Args:
        session: Active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.chunk_repo = ChunkRepository(session)
        self.knowledge_repo = KnowledgeRepository(session)

    async def process(self, job: IngestionJob) -> int:
        """Embed all pending chunks for the knowledge_base row and upsert into Qdrant.

        Args:
            job: The IngestionJob whose knowledge_id identifies the row to embed.

        Returns:
            Total number of chunks embedded in this run (0 if already done).

        Raises:
            ValueError: If the knowledge_base row does not exist.
        """
        from common.config import settings

        pending = await self.chunk_repo.get_pending_embed(job.knowledge_id)
        if not pending:
            return 0

        knowledge = await self.knowledge_repo.get(job.knowledge_id)
        if knowledge is None:
            raise ValueError(f"knowledge_base {job.knowledge_id} not found")

        total_embedded = 0
        for i in range(0, len(pending), settings.embedding_batch_size):
            batch = pending[i : i + settings.embedding_batch_size]
            vectors = await embed_batch([c.text for c in batch])
            ensure_collection(len(vectors[0]))  # BUG-001: idempotent, no-op after first call

            points = [
                {
                    "id": str(uuid4()),
                    "vector": vector,
                    "payload": {
                        "knowledge_id": knowledge.id,
                        "chunk_id": chunk.id,
                        "category": knowledge.category,
                        "title": knowledge.title,
                        "text": chunk.text,
                    },
                }
                for chunk, vector in zip(batch, vectors, strict=True)
            ]
            upsert_chunks(points)

            for chunk, point in zip(batch, points, strict=True):
                chunk.vector_id = point["id"]
                chunk.embed_status = "embedded"

            await self.session.flush()
            total_embedded += len(batch)
            logger.info("batch_embedded", job_id=job.id, count=len(batch))

        knowledge.status = "published"
        from datetime import UTC, datetime

        knowledge.last_indexed_at = datetime.now(UTC)
        await self.session.flush()

        return total_embedded
