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
# Description: Knowledge chunking service — splits knowledge_base.content
#              (plain text/markdown, no file loaders needed) via LangChain's
#              SemanticChunker (percentile 80) + MAX/MIN size guards, then
#              persists knowledge_chunks rows. Adapted from rag-health's
#              document-file pipeline (ADR-0021) — this project's source is
#              a Postgres text column, not uploaded files, so the loader
#              layer was dropped.
###############################################################################

from langchain_core.documents import Document as LCDocument
from langchain_experimental.text_splitter import SemanticChunker
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from common.observability import get_logger
from dal.chunk_repository import ChunkRepository, KnowledgeChunk
from dal.ingestion_job_repository import IngestionJob
from dal.knowledge_repository import KnowledgeRepository

logger = get_logger(__name__)


def _get_chunk_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Embeddings client used only to detect semantic split points.

    LangChain's SemanticChunker needs a LangChain-compatible sync embeddings
    object; the real batch-embedding-for-storage path uses
    common/gemini_client.embed_batch directly (embedding_service.py), not this.
    """
    return GoogleGenerativeAIEmbeddings(
        model=f"models/{settings.gemini_embedding_model}",
        google_api_key=settings.gemini_api_key,
    )


class ChunkService:
    """Splits one knowledge_base row's content into knowledge_chunks rows.

    Args:
        session: Active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.chunk_repo = ChunkRepository(session)
        self.knowledge_repo = KnowledgeRepository(session)

    async def process(self, job: IngestionJob) -> int:
        """Chunk the knowledge_base row referenced by the job.

        Idempotent: if chunks already exist for this knowledge_id (e.g. a
        retried job), skips re-chunking and returns the existing count.

        Args:
            job: The IngestionJob whose knowledge_id identifies the row to chunk.

        Returns:
            Number of knowledge_chunks rows created (or already existing).

        Raises:
            ValueError: If the knowledge_base row does not exist.
        """
        knowledge = await self.knowledge_repo.get(job.knowledge_id)
        if knowledge is None:
            raise ValueError(f"knowledge_base {job.knowledge_id} not found")

        existing = await self.chunk_repo.get_by_knowledge(knowledge.id)
        if existing:
            logger.info("chunk.idempotent_skip", knowledge_id=knowledge.id, count=len(existing))
            return len(existing)

        splitter = SemanticChunker(
            _get_chunk_embeddings(),
            buffer_size=settings.semantic_chunker_buffer_size,
            breakpoint_threshold_type=settings.semantic_chunker_threshold_type,
            breakpoint_threshold_amount=settings.semantic_chunker_threshold_amount,
            min_chunk_size=settings.chunk_min_size,
        )
        docs = splitter.create_documents([knowledge.content])

        # MAX guard: hard-split any chunk exceeding chunk_max_size (ARCH-001 §5.5).
        if settings.chunk_max_size > 0:
            hard_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.chunk_max_size,
                chunk_overlap=settings.chunk_overlap,
            )
            docs = hard_splitter.split_documents(docs)

        # MIN guard: merge any chunk shorter than chunk_min_size into the previous one.
        if settings.chunk_min_size > 0:
            merged: list[LCDocument] = []
            for doc in docs:
                if merged and len(doc.page_content) < settings.chunk_min_size:
                    merged_text = merged[-1].page_content + " " + doc.page_content
                    merged[-1] = LCDocument(page_content=merged_text)
                else:
                    merged.append(doc)
            docs = merged

        chunk_records = [
            KnowledgeChunk(
                knowledge_id=knowledge.id,
                ordinal=i,
                text=doc.page_content,
                embed_status="pending_embed",
            )
            for i, doc in enumerate(docs)
        ]
        self.session.add_all(chunk_records)
        await self.session.flush()

        logger.info("chunk.done", knowledge_id=knowledge.id, chunk_count=len(chunk_records))
        return len(chunk_records)
