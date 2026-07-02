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
# Description: Booking Agent tools — thin wrappers over data/booking_repository; no SQL, no race-condition handling here (constraint lives in data/, ARCH-001 §4).
###############################################################################


def check_available_slots(doctor_id):
    """Return open slots for a doctor by joining doctors + bookings in data/."""
    raise NotImplementedError


def create_booking(doctor_id, slot_time, patient_name, phone):
    """Create a booking; relies on the DB partial unique constraint (ADR-0009)."""
    raise NotImplementedError


def update_booking(booking_id, new_slot_time):
    """Reschedule an existing booking to a new slot."""
    raise NotImplementedError


def cancel_booking(booking_id):
    """Cancel an existing booking, freeing its slot."""
    raise NotImplementedError
