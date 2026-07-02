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
# Description: Abstract base service class — structured logging helpers plus
#              a unified exception handler that wraps unexpected infra errors
#              into the application exception hierarchy. Reused verbatim from
#              rag-health (ADR-0021).
###############################################################################

import structlog

from core.exceptions import AppException, InfrastructureError

logger = structlog.get_logger(__name__)


class BaseService:
    """Base class for all application service objects.

    Provides three protected helpers that standardise how service methods
    log their lifecycle and handle exceptions:

    - ``_log_enter``: emits a structured INFO log when a method is entered.
    - ``_log_exit``:  emits a structured INFO log when a method completes.
    - ``_handle_exception``: classifies exceptions and re-raises with the
      correct domain type, ensuring consistent error responses upstream.

    Subclasses should call these helpers at the start and end of each public
    method, and route all ``except`` blocks through ``_handle_exception``.
    """

    def _log_enter(self, method: str, **kwargs) -> None:
        """Log entry into a service method with optional contextual fields.

        Args:
            method: Name of the service method being entered (e.g. ``"create"``).
            **kwargs: Additional key-value pairs to include in the log record.
        """
        logger.info("service.enter", method=method, **kwargs)

    def _log_exit(self, method: str, **kwargs) -> None:
        """Log successful completion of a service method with optional contextual fields.

        Args:
            method: Name of the service method that completed.
            **kwargs: Additional key-value pairs to include in the log record.
        """
        logger.info("service.exit", method=method, **kwargs)

    def _handle_exception(self, exc: Exception, method: str) -> None:
        """Classify an exception and re-raise it with the appropriate domain type.

        - If the exception is already an ``AppException`` (or subclass), it is
          re-raised as-is after a WARNING log — the error is expected and the
          caller knows how to handle it.
        - Any other exception is treated as an unexpected infrastructure failure,
          logged at ERROR level, and re-raised as ``InfrastructureError`` to
          avoid leaking internal details to API clients.

        Args:
            exc: The caught exception.
            method: Name of the service method where the exception occurred
                    (used for log context).

        Raises:
            AppException: Re-raised unchanged if ``exc`` is already an AppException.
            InfrastructureError: Wraps ``exc`` when it is an unexpected error.
        """
        if isinstance(exc, AppException):
            logger.warning("service.app_error", method=method, code=exc.code, error=str(exc))
            raise
        logger.error("service.infra_error", method=method, error=str(exc))
        raise InfrastructureError(str(exc)) from exc
