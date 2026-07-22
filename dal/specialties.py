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
#              ADR-0027 (2026-07-22): added resolve_specialty() — the Booking
#              Agent's input-side counterpart to specialty_display_name()'s
#              output-side lookup. Recognizes a code OR any of the 42 display
#              names as belonging to the closed 14-specialty set (strip +
#              casefold, deterministic, NOT fuzzy) so a false negative
#              ("phòng khám không có bác sĩ khoa X") can never come from the
#              Booking Agent guessing a wrong code — see
#              ai_agents/booking/tools.py::list_doctors_by_specialty.
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


def _build_specialty_resolution_index() -> dict[str, str]:
    """Precompute casefold(candidate) -> code across codes + every display name.

    Built once at module-load time (SPECIALTIES/SPECIALTY_DISPLAY_NAMES are a
    fixed 14-row literal, not per-request data) so resolve_specialty() is an
    O(1) dict lookup, and so a future copy-paste collision (two specialties
    sharing one casefolded label) fails LOUDLY at import time instead of
    silently resolving to whichever specialty happened to be indexed last.
    """
    index: dict[str, str] = {}
    for code in SPECIALTIES:
        index[code.casefold()] = code
    for code, names in SPECIALTY_DISPLAY_NAMES.items():
        for name in names.values():
            key = name.strip().casefold()
            existing = index.get(key)
            if existing is not None and existing != code:
                raise ValueError(
                    f"specialty resolution collision: {key!r} maps to both "
                    f"{existing!r} and {code!r} — display names must be "
                    "distinct across specialties (see "
                    "test_display_names_are_distinct_across_specialties_within_one_language)"
                )
            index[key] = code
    return index


_SPECIALTY_RESOLUTION_INDEX = _build_specialty_resolution_index()


def resolve_specialty(value: str) -> str | None:
    """Recognize a specialty code OR display name from the closed set of 14
    codes x 3 languages — a deterministic membership check, NOT fuzzy
    matching or translation (ADR-0027 §2, the tool-layer defense for the
    Booking Agent's input side).

    Serves ai_agents/booking/tools.py::list_doctors_by_specialty: the LLM is
    only ever trusted to *copy* a code verbatim from the
    {specialty_code_table} prompt block, but it may instead echo back a
    display name it just used in conversation, or get the casing/whitespace
    slightly off — this function tolerates exactly those two mistakes while
    staying deterministic (no guessing beyond the known 14 x 3 = 42 strings).
    NOT used by dal/doctor_repository.py, which keeps matching by exact code
    — input recognition belongs to the ai_agents/ tool layer, not the dal/
    repo (ADR-0013).

    Args:
        value: Whatever string the caller passes — a code, a display name in
            any of vn/jp/en, or (if truly unrecognized) an arbitrary string.

    Returns:
        The canonical snake_case code, or None if `value` matches none of the
        14 codes or their 42 display names.
    """
    return _SPECIALTY_RESOLUTION_INDEX.get(value.strip().casefold())
