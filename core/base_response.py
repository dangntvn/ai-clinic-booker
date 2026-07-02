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
# Description: Shared Pydantic response envelope models — standard API
#              response shapes (single item, paginated list, error) used
#              across every feature module controller. Reused verbatim from
#              rag-health (ADR-0021).
###############################################################################

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):  # noqa: UP046
    """Envelope for a single-item successful API response.

    Wraps any data payload with a consistent top-level shape so clients can
    always find the resource under the ``data`` key.

    Attributes:
        data: The response payload — any serialisable type.
        message: A human-readable status string, defaults to ``"success"``.
    """

    data: T
    message: str = "success"


class PaginatedResponse(BaseModel, Generic[T]):  # noqa: UP046
    """Envelope for a paginated list API response.

    Provides the metadata needed for client-side pagination UI (total count,
    current page, and page size) alongside the data slice.

    Attributes:
        data: The current page of items.
        total: Total number of records matching the query (across all pages).
        page: Current 1-based page number.
        page_size: Number of items per page.
    """

    data: list[T]
    total: int
    page: int
    page_size: int


class ErrorDetail(BaseModel):
    """Machine-readable error detail carried inside an ErrorResponse.

    Attributes:
        code: A short uppercase identifier (e.g. ``"NOT_FOUND"``).
        message: A human-readable description of the error.
    """

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Top-level error response envelope returned on API failures.

    Attributes:
        error: Structured error detail with code and message.
    """

    error: ErrorDetail
