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
# Description: Unit tests for ai-agents/core/domain/doctor_lookup.py
#              (BUG-015). Pure name-matching, no I/O — covers the real seeded
#              roster (eval/fixtures/doctors.yaml) plus the collision cases the
#              BUG-015 code review raised: given names that double as honorific
#              words ("Khoa", "Sĩ") must stay findable, because honorifics are
#              stripped only from the query, never from a stored full_name.
###############################################################################

import importlib

import pytest

doctor_lookup = importlib.import_module("ai-agents.core.domain.doctor_lookup")
name_matches = doctor_lookup.name_matches
normalize_vietnamese = doctor_lookup.normalize_vietnamese


def test_normalize_strips_diacritics_and_folds_d():
    assert normalize_vietnamese("Phạm Thị Lan Hương") == "pham thi lan huong"
    assert normalize_vietnamese("Đỗ Như Chinh") == "do nhu chinh"


@pytest.mark.parametrize(
    "query",
    [
        "Phạm Thị Lan Hương",  # full name, exact
        "bác sĩ Phạm Thị Lan Hương",  # with honorific prefix
        "Lan Hương",  # partial (given name)
        "hương",  # single token, lower-case, no diacritics on input
        "PHẠM THỊ LAN HƯƠNG",  # upper-case
    ],
)
def test_matches_real_doctor_by_various_phrasings(query):
    assert name_matches(query, "Phạm Thị Lan Hương") is True


@pytest.mark.parametrize(
    "query",
    [
        "ThS.BS Đỗ Như Chinh",  # punctuation-glued title splits and drops
        "BS. Đỗ Như Chinh",
        "bs cki Hoàng Đức Hạnh",
    ],
)
def test_honorific_prefixes_are_tolerated(query):
    target = "Đỗ Như Chinh" if "Chinh" in query else "Hoàng Đức Hạnh"
    assert name_matches(query, target) is True


def test_does_not_match_a_different_doctor():
    assert name_matches("Phạm Thị Lan Hương", "Trần Thị Kim Anh") is False
    assert name_matches("Đào Thanh Thủy", "Nguyễn Thị Thúy") is False


@pytest.mark.parametrize(
    "query,target",
    [
        # 5 seeded doctors carry the verbatim title "Bác sĩ Chuyên khoa I";
        # a patient may echo it. The "chuyên khoa [grade]" phrase must drop as
        # a unit so it does not wrongly demand those words in the name — for
        # the Roman ("I"/"II") and the Arabic ("1") grade spelling alike.
        ("bác sĩ chuyên khoa I Hoàng Đức Hạnh", "Hoàng Đức Hạnh"),
        ("bác sĩ chuyên khoa Đoàn Việt Hùng", "Đoàn Việt Hùng"),
        ("Thạc sĩ, Bác sĩ chuyên khoa Đỗ Như Chinh", "Đỗ Như Chinh"),
        ("chuyên khoa II Nguyễn Thị Thúy", "Nguyễn Thị Thúy"),
        ("bác sĩ chuyên khoa 1 Hoàng Đức Hạnh", "Hoàng Đức Hạnh"),
        ("CK1 Hoàng Đức Hạnh", "Hoàng Đức Hạnh"),
    ],
)
def test_verbatim_specialty_title_phrase_is_dropped(query, target):
    assert name_matches(query, target) is True


@pytest.mark.parametrize("query", ["", "   ", "bác sĩ", "BS.", "ThS.BS", "bác sĩ chuyên khoa"])
def test_honorific_only_or_empty_query_matches_nobody(query):
    assert name_matches(query, "Phạm Thị Lan Hương") is False


def test_bare_surname_matches_every_doctor_with_that_surname():
    # "Phạm" must match both Phạm doctors so the caller can disambiguate,
    # rather than silently pick one.
    assert name_matches("Phạm", "Phạm Thị Lan Hương") is True
    assert name_matches("Phạm", "Phạm Sơn Tùng") is True
    assert name_matches("Phạm", "Trần Thị Kim Anh") is False


@pytest.mark.parametrize(
    "query",
    ["Nguyễn Đăng Khoa", "Đăng Khoa", "Khoa", "bác sĩ Khoa"],
)
def test_given_name_colliding_with_a_title_word_stays_findable(query):
    # BUG-015 review: honorifics are stripped from the query only, never from
    # the stored full_name — so a doctor genuinely named "Khoa" is not erased.
    assert name_matches(query, "Nguyễn Đăng Khoa") is True


def test_multi_token_name_with_title_like_middle_name_still_matches():
    # "Sĩ" collides with the honorific "sĩ", but the other tokens carry the match.
    assert name_matches("Lê Sĩ Trung", "Lê Sĩ Trung") is True
    assert name_matches("bác sĩ Sĩ Trung", "Lê Sĩ Trung") is True
