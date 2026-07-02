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
# Description: Booking admin service — calls data/booking_repository directly, the same repository used by ai-agents/booking (ARCH-001 §4).
###############################################################################


def list_bookings():
    """List bookings for the admin screen."""
    raise NotImplementedError


def cancel_booking(booking_id):
    """Cancel a booking directly from the admin screen."""
    raise NotImplementedError
