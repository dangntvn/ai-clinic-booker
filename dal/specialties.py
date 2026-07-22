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
# Description: Single source of truth for the clinic's 14 specialties
#              (ADR-0026) — the snake_case internal codes (BIZ-001 §6) plus
#              their vn/jp/en display-name registry. Supersedes the Vietnamese
#              tuple that used to live inline in dal/doctor_repository.py:
#              `specialty` is now an internal identifier (DB column, tool
#              parameter, validate_specialty, intake_rules) that never changes
#              across the 3 language servers, while the human-readable label
#              lives here, keyed by settings.lang_suffix. Lives at dal/ (not
#              common/) because this is clinic domain knowledge (CONV-001 §4
#              keeps common/ domain-agnostic), and dal/ does not import
#              upward into ai_agents/ or modules/ (ADR-0013) — so this is the
#              one place both modules/doctor and ai_agents/ can import from
#              without a backward dependency.
###############################################################################

# BIZ-001 §6 — the clinic's 14 specialties as snake_case internal codes
# (ADR-0026 Decision §1). This is the single source of truth other layers
# validate `specialty` against (modules/doctor/services.py::validate_specialty)
# and the enum ai_agents/core/domain/intake_rules.py's hard rules route into.
SPECIALTIES: tuple[str, ...] = (
    "general_internal_medicine",
    "pediatrics",
    "obstetrics_gynecology",
    "cardiology",
    "gastroenterology",
    "pulmonology",
    "endocrinology",
    "neurology",
    "musculoskeletal",
    "dermatology",
    "otolaryngology",
    "ophthalmology",
    "dentistry",
    "urology_andrology",
)

# Human-readable display name per specialty code, keyed by settings.lang_suffix
# (ADR-0026 Decision §2) — deterministic data a developer edits, never LLM
# output. This is the ONLY place a specialty's native-language label is
# defined; every surface that shows a specialty name to a patient (doctors
# context, booking tool responses, the Symptom Agent's display table) must
# read from here via specialty_display_name(), never let the LLM translate it.
SPECIALTY_DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "general_internal_medicine": {
        "vn": "Nội tổng quát",
        "en": "General Internal Medicine",
        "jp": "総合内科",
    },
    "pediatrics": {
        "vn": "Nhi",
        "en": "Pediatrics",
        "jp": "小児科",
    },
    "obstetrics_gynecology": {
        "vn": "Sản – Phụ khoa",
        "en": "Obstetrics & Gynecology",
        "jp": "産婦人科",
    },
    "cardiology": {
        "vn": "Tim mạch",
        "en": "Cardiology",
        "jp": "循環器内科",
    },
    "gastroenterology": {
        "vn": "Tiêu hóa",
        "en": "Gastroenterology",
        "jp": "消化器内科",
    },
    "pulmonology": {
        "vn": "Hô hấp",
        "en": "Pulmonology",
        "jp": "呼吸器内科",
    },
    "endocrinology": {
        "vn": "Nội tiết",
        "en": "Endocrinology",
        "jp": "内分泌内科",
    },
    "neurology": {
        "vn": "Thần kinh",
        "en": "Neurology",
        "jp": "神経内科",
    },
    "musculoskeletal": {
        "vn": "Cơ xương khớp",
        "en": "Orthopedics & Rheumatology",
        "jp": "整形外科・リウマチ科",
    },
    "dermatology": {
        "vn": "Da liễu",
        "en": "Dermatology",
        "jp": "皮膚科",
    },
    "otolaryngology": {
        "vn": "Tai Mũi Họng",
        "en": "Otolaryngology (ENT)",
        "jp": "耳鼻咽喉科",
    },
    "ophthalmology": {
        "vn": "Mắt",
        "en": "Ophthalmology",
        "jp": "眼科",
    },
    "dentistry": {
        "vn": "Răng Hàm Mặt",
        "en": "Dentistry",
        "jp": "歯科口腔外科",
    },
    "urology_andrology": {
        "vn": "Tiết niệu – Nam khoa",
        "en": "Urology & Andrology",
        "jp": "泌尿器科",
    },
}


def specialty_display_name(code: str, lang_suffix: str) -> str:
    """Look up the display label for a specialty code in one language.

    Raise-fast on an unknown code/suffix (same "never silently default"
    stance as common.config.reply_language_name/validate_specialty) — a typo
    here must surface immediately, not silently fall back to some default
    label shown to a patient.

    Args:
        code: One of SPECIALTIES' 14 snake_case codes.
        lang_suffix: One of "vn"/"jp"/"en" (common.config.SUPPORTED_LANG_SUFFIXES).

    Raises:
        ValueError: If ``code`` is not in SPECIALTY_DISPLAY_NAMES, or
            ``lang_suffix`` is not a key of that specialty's display-name dict.
    """
    try:
        names = SPECIALTY_DISPLAY_NAMES[code]
    except KeyError:
        raise ValueError(
            f"specialty code={code!r} is not one of {sorted(SPECIALTY_DISPLAY_NAMES)}"
        ) from None
    try:
        return names[lang_suffix]
    except KeyError:
        raise ValueError(
            f"lang_suffix={lang_suffix!r} is not one of {sorted(names)} for specialty={code!r}"
        ) from None
