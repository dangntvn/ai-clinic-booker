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
# Description: Qdrant client factory + collection helpers — connection,
#              upsert, category-filtered search, delete_by_knowledge_id
#              (ARCH-001 §6.2/§7, ADR-0007). Adapted from rag-health's
#              common/qdrant.py (ADR-0021), relocated to dal/ per ARCH-001
#              §4/§8 — this is the data-access boundary, not shared infra.
###############################################################################

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from common.config import settings

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Return the process-wide Qdrant client, creating it on first use.

    The connection URL is read from ``settings.qdrant_url``, keeping all
    infrastructure coordinates in one place.

    Returns:
        QdrantClient: A ready-to-use Qdrant client instance.
    """
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def ensure_collection(vector_size: int) -> None:
    """Create the knowledge collection if it does not already exist.

    Idempotent — safe to call on every startup/ingestion run.
    """
    client = get_qdrant_client()
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )


def upsert_chunks(points: list[dict]) -> None:
    """Upsert a batch of chunk vectors with their payload.

    Args:
        points: Each dict must have ``id`` (Qdrant point id, str/int), ``vector``
                (list[float]), and ``payload`` with
                ``{knowledge_id, chunk_id, category, title, text}`` (ARCH-001 §6.2).
    """
    client = get_qdrant_client()
    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            models.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
            for p in points
        ],
    )


def search(query_vector: list[float], category: str, top_k: int | None = None) -> list[dict]:
    """Search the knowledge collection, filtered to one category.

    Args:
        query_vector: Embedding of the user's query.
        category: One of policy/clinic_info/medical_guide — payload filter so
                  different agents never see each other's knowledge domain.
        top_k: Max results; defaults to ``settings.top_k``.

    Returns:
        List of ``{score, payload}`` dicts, best match first. Empty if the
        collection doesn't exist yet (fresh deploy, nothing ingested) — same
        as "no grounded results" so callers fall through to the ADR-0008
        not-found fallback instead of crashing.
    """
    client = get_qdrant_client()
    try:
        results = client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(key="category", match=models.MatchValue(value=category))
                ]
            ),
            limit=top_k or settings.top_k,
        )
    except UnexpectedResponse as e:
        if e.status_code == 404:
            return []
        raise
    return [{"score": point.score, "payload": point.payload} for point in results.points]


def delete_by_knowledge_id(knowledge_id: int) -> None:
    """Delete every vector belonging to a knowledge_base row.

    Called when a knowledge entry is deleted/archived, so Qdrant never holds
    an orphaned vector for content that no longer exists in Postgres
    (ARCH-001 §6.4).
    """
    client = get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="knowledge_id", match=models.MatchValue(value=knowledge_id)
                    )
                ]
            )
        ),
    )
