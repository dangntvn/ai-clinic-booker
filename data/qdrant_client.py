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
# Description: Qdrant client factory — connection only for now; search +
#              upsert + delete_by_knowledge_id land with the ingestion
#              pipeline reuse (TASK-003, ADR-0021). Adapted from rag-health's
#              common/qdrant.py (ADR-0021), relocated to data/ per ARCH-001
#              §4/§8 — this is the data-access boundary, not shared infra.
###############################################################################

from qdrant_client import QdrantClient

from common.config import settings


def get_qdrant_client() -> QdrantClient:
    """Create and return a Qdrant client connected to the configured endpoint.

    The connection URL is read from ``settings.qdrant_url``, keeping all
    infrastructure coordinates in one place. A new client object is returned
    on every call; the underlying HTTP connection pool is managed by the
    ``qdrant_client`` library.

    Returns:
        QdrantClient: A ready-to-use Qdrant client instance.
    """
    return QdrantClient(url=settings.qdrant_url)
