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
# Description: Booking repository — relies on the partial unique index
#              UNIQUE(doctor_id, slot_time) WHERE status != cancelled
#              (ADR-0009); the only place a constraint violation becomes
#              SlotTakenError.
###############################################################################


class BookingRepository:
    """Postgres repository for bookings — relies on the partial unique index (ADR-0009)."""

    pass
