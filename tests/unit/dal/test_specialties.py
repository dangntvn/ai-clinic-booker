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
# Description: Unit tests for dal/specialties.py (ADR-0026, 2026-07-22) — the
#              single source of truth for the 14 specialty codes plus their
#              vn/jp/en display-name registry. Covers: SPECIALTIES has exactly
#              14 distinct codes, every code round-trips to a non-empty
#              display name in all 3 languages, and specialty_display_name
#              raise-fasts on an unknown code/lang_suffix instead of silently
#              defaulting — mirrors the "never silently default" stance tested
#              for dal/lang_tables.py and common/config.py::reply_language_name.
#              ADR-0027 (2026-07-22): added resolve_specialty coverage — codes
#              and every display name (any of vn/jp/en) resolve back to the
#              canonical code, tolerant of casing/whitespace but never fuzzy;
#              an unrecognized string resolves to None. Includes the two cases
#              ADR-0027 calls out by name as easy-to-mis-guess ("Orthopedics &
#              Rheumatology"/"整形外科・リウマチ科" -> musculoskeletal,
#              "Urology & Andrology"/"泌尿器科" -> urology_andrology).
###############################################################################

import pytest

from dal.specialties import (
    SPECIALTIES,
    SPECIALTY_DISPLAY_NAMES,
    resolve_specialty,
    specialty_display_name,
)


def test_specialties_has_exactly_14_distinct_codes():
    assert len(SPECIALTIES) == 14
    assert len(set(SPECIALTIES)) == 14


def test_specialties_are_snake_case():
    # BIZ-001 §6/ADR-0026: codes are internal identifiers, never the
    # Vietnamese label — no accents, no spaces, no en-dash.
    for code in SPECIALTIES:
        assert code == code.lower()
        assert " " not in code
        assert "–" not in code


def test_display_names_registry_covers_every_specialty():
    assert set(SPECIALTY_DISPLAY_NAMES) == set(SPECIALTIES)


@pytest.mark.parametrize("lang_suffix", ["vn", "jp", "en"])
def test_every_specialty_has_a_non_empty_display_name_in_each_language(lang_suffix):
    for code in SPECIALTIES:
        name = specialty_display_name(code, lang_suffix)
        assert isinstance(name, str)
        assert name.strip() != ""


@pytest.mark.parametrize("lang_suffix", ["vn", "jp", "en"])
def test_display_names_are_distinct_across_specialties_within_one_language(lang_suffix):
    # Guards against a copy-paste collision collapsing two specialties onto
    # the same label within one language.
    names = {specialty_display_name(code, lang_suffix) for code in SPECIALTIES}
    assert len(names) == len(SPECIALTIES)


def test_specialty_display_name_raises_on_unknown_code():
    with pytest.raises(ValueError):
        specialty_display_name("not_a_real_specialty", "vn")


def test_specialty_display_name_raises_on_unknown_lang_suffix():
    with pytest.raises(ValueError):
        specialty_display_name("cardiology", "fr")


def test_vn_column_matches_triage_table_canonical_labels():
    """The vn display name is the exact label used in the Symptom Agent's
    TRIAGE_TABLE (ADR-0018/ADR-0026) — this is what agent.py's
    _render_specialty_display_table left-hand column renders, so a mismatch
    here would silently break that lookup table."""
    expected_vn = {
        "general_internal_medicine": "Nội tổng quát",
        "pediatrics": "Nhi",
        "obstetrics_gynecology": "Sản – Phụ khoa",
        "cardiology": "Tim mạch",
        "gastroenterology": "Tiêu hóa",
        "pulmonology": "Hô hấp",
        "endocrinology": "Nội tiết",
        "neurology": "Thần kinh",
        "musculoskeletal": "Cơ xương khớp",
        "dermatology": "Da liễu",
        "otolaryngology": "Tai Mũi Họng",
        "ophthalmology": "Mắt",
        "dentistry": "Răng Hàm Mặt",
        "urology_andrology": "Tiết niệu – Nam khoa",
    }
    for code, vn_label in expected_vn.items():
        assert specialty_display_name(code, "vn") == vn_label


@pytest.mark.parametrize("code", SPECIALTIES)
def test_resolve_specialty_returns_the_code_itself(code):
    assert resolve_specialty(code) == code


@pytest.mark.parametrize("code", SPECIALTIES)
@pytest.mark.parametrize("lang_suffix", ["vn", "jp", "en"])
def test_resolve_specialty_matches_every_display_name_in_every_language(code, lang_suffix):
    display_name = SPECIALTY_DISPLAY_NAMES[code][lang_suffix]
    assert resolve_specialty(display_name) == code


def test_resolve_specialty_tolerates_case_and_whitespace():
    # LLM-side mistakes resolve_specialty must forgive without being fuzzy
    # (ADR-0027 §2): wrong casing and leading/trailing whitespace.
    assert resolve_specialty("  Cardiology ") == "cardiology"
    assert resolve_specialty("CARDIOLOGY") == "cardiology"


def test_resolve_specialty_returns_none_for_an_unrecognized_string():
    assert resolve_specialty("not_a_real_specialty_or_label") is None
    assert resolve_specialty("") is None


@pytest.mark.parametrize(
    ("display_name", "expected_code"),
    [
        # ADR-0027 Context — the two specialties an LLM is most likely to
        # mis-guess a code for instead of looking up in {specialty_code_table}.
        ("Orthopedics & Rheumatology", "musculoskeletal"),
        ("整形外科・リウマチ科", "musculoskeletal"),
        ("Cơ xương khớp", "musculoskeletal"),
        ("Urology & Andrology", "urology_andrology"),
        ("泌尿器科", "urology_andrology"),
        ("Tiết niệu – Nam khoa", "urology_andrology"),
    ],
)
def test_resolve_specialty_covers_the_adr_0027_callout_cases(display_name, expected_code):
    assert resolve_specialty(display_name) == expected_code
