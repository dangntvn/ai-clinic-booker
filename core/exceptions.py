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
# Description: AppException hierarchy (NotFoundError, ValidationError, ...), generic — no concrete domain names (ADR-0021).
###############################################################################


class AppException(Exception):
    """Root of the generic application exception hierarchy."""

    pass


class NotFoundError(AppException):
    """Raised when a requested entity does not exist."""

    pass


class ValidationError(AppException):
    """Raised when input fails validation."""

    pass
