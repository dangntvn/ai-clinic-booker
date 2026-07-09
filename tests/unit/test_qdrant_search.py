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
# Description: Unit test for TASK-020 — search() must return [] when the
#              Qdrant collection doesn't exist yet (fresh deploy, nothing
#              ingested), not crash — ADR-0008's not-found fallback should
#              still apply, same as a real "no grounded results" case.
###############################################################################

from unittest.mock import MagicMock

import httpx
import pytest
from qdrant_client.http.exceptions import UnexpectedResponse

from dal import qdrant_client


def _make_unexpected_response(status_code: int) -> UnexpectedResponse:
    return UnexpectedResponse(
        status_code=status_code,
        reason_phrase="Not Found",
        content=b'{"status":{"error":"Not found: Collection `x` doesn\'t exist!"}}',
        headers=httpx.Headers(),
    )


def test_search_returns_empty_when_collection_missing(monkeypatch):
    fake_client = MagicMock()
    fake_client.query_points.side_effect = _make_unexpected_response(404)
    monkeypatch.setattr(qdrant_client, "get_qdrant_client", lambda: fake_client)

    results = qdrant_client.search(query_vector=[0.1, 0.2], category="policy")

    assert results == []


def test_search_still_raises_on_other_errors(monkeypatch):
    fake_client = MagicMock()
    fake_client.query_points.side_effect = _make_unexpected_response(500)
    monkeypatch.setattr(qdrant_client, "get_qdrant_client", lambda: fake_client)

    with pytest.raises(UnexpectedResponse):
        qdrant_client.search(query_vector=[0.1, 0.2], category="policy")
