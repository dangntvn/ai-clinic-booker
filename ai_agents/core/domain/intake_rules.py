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
# Description: Hard intake rules by patient category (BIZ-001 §4) — pure
#              Python, no I/O, checked before any symptom-based triage.
#              Invariant: the first matching rule wins, in the exact order
#              BIZ-001 §4 lists them (age before pregnancy before referral
#              letter before named request before package exam before
#              vaccination) — order is meaningful, not incidental.
#              PEDIATRICS/OBSTETRICS_GYNECOLOGY/GENERAL_MEDICINE are the
#              snake_case specialty codes from dal/specialties.py (ADR-0026,
#              2026-07-22) — SPECIALTIES has no named accessors, so these are
#              literals validated against (not derived from) that registry via
#              the assert below, kept as the second consumer of the single
#              source of truth rather than a silently-drifting third copy of
#              the enum. classify_intake() is not yet wired into the live
#              agent runtime (ADR-0026 context) — if/when it is, its return
#              value is meant to match the `specialty` DB column directly.
###############################################################################

from dataclasses import dataclass

from dal.specialties import SPECIALTIES

PEDIATRICS = "pediatrics"
OBSTETRICS_GYNECOLOGY = "obstetrics_gynecology"
GENERAL_MEDICINE = "general_internal_medicine"

# Fail fast at import time if dal/specialties.py's registry ever drifts from
# these 3 codes this module depends on — cheaper than a runtime routing bug.
assert PEDIATRICS in SPECIALTIES
assert OBSTETRICS_GYNECOLOGY in SPECIALTIES
assert GENERAL_MEDICINE in SPECIALTIES

# "Phòng tiêm chủng" (vaccination room) is an administrative routing target,
# NOT one of the 14 SPECIALTIES — no doctor carries this as their specialty
# and it never goes through validate_specialty (ADR-0026 Decision §1). Kept
# as its own constant, deliberately outside the specialty registry.
VACCINATION_ROOM = "Phòng tiêm chủng"


@dataclass
class IntakeInfo:
    """Structured facts gathered before symptom-based triage (BIZ-001 §4).

    All fields default to "unknown/no" so callers only need to set what
    they actually learned from the patient.
    """

    age: int | None = None
    is_pregnant: bool = False
    has_gynecological_issue: bool = False
    follow_up_department: str | None = None  # BIZ-001 §4 rule 4: giấy hẹn tái khám
    referral_department: str | None = None  # BIZ-001 §4 rule 5: giấy chuyển tuyến
    requested_specialty: str | None = None  # BIZ-001 §4 rule 6: yêu cầu đích danh
    is_periodic_checkup: bool = False  # BIZ-001 §4 rule 7: khám định kỳ/gói/giấy tờ
    needs_vaccination: bool = False  # BIZ-001 §4 rule 8


def classify_intake(info: IntakeInfo) -> str | None:
    """Apply hard intake rules by patient category, in BIZ-001 §4 order.

    Returns:
        The department name to route to, or None if no hard rule matched —
        the caller (Symptom Agent) should fall through to symptom-based
        triage (BIZ-001 §6-7) in that case.
    """
    if info.age is not None and info.age < 16:
        return PEDIATRICS

    if info.is_pregnant:
        return OBSTETRICS_GYNECOLOGY

    if info.has_gynecological_issue:
        return OBSTETRICS_GYNECOLOGY

    if info.follow_up_department:
        return info.follow_up_department

    if info.referral_department:
        return info.referral_department

    if info.requested_specialty:
        return info.requested_specialty

    if info.is_periodic_checkup:
        return GENERAL_MEDICINE

    if info.needs_vaccination:
        return VACCINATION_ROOM

    return None
