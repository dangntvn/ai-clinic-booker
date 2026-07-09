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
# Description: Domain exception hierarchy — typed application exceptions
#              caught by FastAPI exception handlers and translated into
#              structured HTTP error responses. Generic, no concrete domain
#              names. Reused verbatim from rag-health (ADR-0021).
###############################################################################


class AppException(Exception):
    """Base class for all application-level exceptions.

    Carries a human-readable ``message`` and a machine-readable ``code`` string
    so API clients can branch on error type without parsing message text.

    Args:
        message: A descriptive error message suitable for logging and API responses.
        code: A short, uppercase identifier (e.g. ``"NOT_FOUND"``).  Defaults to
              ``"INTERNAL_ERROR"`` for unexpected failures.
    """

    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundError(AppException):
    """Raised when a requested resource does not exist in the data store.

    Maps to HTTP 404 via the FastAPI exception handler registered in
    ``app.main``.

    Args:
        message: Optional override for the default "Resource not found" text.
    """

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="NOT_FOUND")


class ValidationError(AppException):
    """Raised when incoming data fails business-rule or format validation.

    Maps to HTTP 422 via the FastAPI exception handler registered in
    ``app.main``.  Prefer this over Pydantic's own ValidationError when the
    constraint is domain-specific (e.g. unsupported input format).

    Args:
        message: A description of the validation failure.
    """

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, code="VALIDATION_ERROR")


class SlotTakenError(AppException):
    """Raised when a booking slot is no longer available (ADR-0009).

    Lives here rather than ai-agents/core/exceptions.py — ARCH-001 §4
    explicitly allows either location, and data/booking_repository.py (a
    lower layer than ai-agents/) needs to raise this without depending
    upward on the AI layer, and without the ai-agents/ hyphen import
    workaround (common/module_loader.py) for something this hot-path.

    Args:
        message: Optional override for the default message.
    """

    def __init__(self, message: str = "Slot is no longer available"):
        super().__init__(message, code="SLOT_TAKEN")


class InvalidSlotError(AppException):
    """Raised when a slot violates a doctor's work_days/clinic hours (BUG-007).

    Distinct from SlotTakenError: this means the requested slot could never
    be valid (wrong weekday, outside clinic hours, or off the slot grid),
    not merely that someone else already holds it.

    Args:
        message: Optional override for the default message.
    """

    def __init__(self, message: str = "Requested slot is not a valid clinic slot"):
        super().__init__(message, code="INVALID_SLOT")


class InfrastructureError(AppException):
    """Raised when an external dependency (database, Qdrant, Gemini) fails.

    Service-layer code should catch low-level exceptions from third-party
    clients and re-raise them as InfrastructureError so that callers receive a
    consistent exception type and HTTP 500 responses are generated uniformly.

    Args:
        message: Details about the infrastructure failure (safe to log).
    """

    def __init__(self, message: str = "Infrastructure error"):
        super().__init__(message, code="INFRASTRUCTURE_ERROR")
