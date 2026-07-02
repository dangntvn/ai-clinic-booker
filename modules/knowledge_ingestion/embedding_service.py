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
# Description: Batches chunks (EMBEDDING_BATCH_SIZE=100), calls the Gemini embedding API, and upserts into Qdrant, reused from rag-health (ADR-0021).
###############################################################################


def embed_and_upsert(chunks):
    """Batch-embed chunks and upsert the resulting vectors into Qdrant."""
    raise NotImplementedError
