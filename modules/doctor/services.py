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
# Description: Doctor admin service — calls data/doctor_repository, manages both operational fields and profile fields (ADR-0020).
###############################################################################


def list_doctors():
    """List doctors for the admin screen."""
    raise NotImplementedError


def update_doctor(doctor_id, data):
    """Update a doctor record (operational or profile fields)."""
    raise NotImplementedError
