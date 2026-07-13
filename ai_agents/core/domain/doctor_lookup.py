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
# Description: Pure doctor name-matching helpers (BUG-015) — resolve a
#              patient-typed Vietnamese doctor name to the real roster.
#              No I/O and no ORM dependency (operates on plain strings), so
#              it's unit-testable without a live DB/LLM, same as the other
#              core/domain rule modules (ARCH-001 §7). The Booking Agent's
#              find_doctor_by_name tool loads active doctors via
#              dal/doctor_repository and filters them with name_matches here;
#              the numeric doctor_id stays the DB bridge (ARCH-001 §6.3,
#              ADR-0020) — this only maps a name back onto an existing id, it
#              never invents one.
###############################################################################

import re
import unicodedata

# Honorifics/titles a patient (or the LLM relaying them) commonly prefixes a
# doctor name with ("bác sĩ Phạm...", "ThS.BS Đỗ...", "bác sĩ chuyên khoa I
# Hoàng...", "BS. CKI ..."). Stripped from the QUERY (never from a stored
# full_name) before matching, so the caller doesn't have to isolate the bare
# name and a real doctor is still found when the patient echoes the full title.
#
# Matched as whole PHRASES, not independent tokens, on purpose: the multi-word
# titles "bác sĩ", "thạc sĩ" and especially "chuyên khoa [I/II/III]" contain
# words that are also real Vietnamese given names — most notably "khoa" (a
# common given name). Removing "chuyên khoa" only as a bigram keeps a doctor
# genuinely named "Khoa" findable (BUG-015 review), while still dropping the
# verbatim "Chuyên khoa I" title that 5 of the seeded doctors actually carry.
# A leftover standalone "si"/"khoa" is treated as a name token, so "Lê Sĩ
# Trung" and "Nguyễn Đăng Khoa" both stay matchable.
# The specialty grade may be written as a Roman numeral ("Chuyên khoa I") — the
# real seeded form — or as an Arabic digit ("chuyên khoa 1", "CK1") a patient
# might type instead; both are accepted so either phrasing is dropped.
_TITLE_RE = re.compile(
    r"\b(?:"
    r"bac\s*si|bacsi|bsi|bs|dr|doctor|"
    r"thac\s*si|thacsi|ths|"
    r"chuyen\s*khoa(?:\s+(?:i{1,3}|[123]))?|ck(?:i{1,3}|[123])?|"
    r"gs|pgs|ts"
    r")\b"
)


def normalize_vietnamese(text: str) -> str:
    """Lower-case and strip Vietnamese diacritics for accent-insensitive matching.

    Uses Unicode NFD decomposition to drop combining marks (so "Hương" ->
    "huong") and folds đ/Đ to d, which NFD does not decompose. Done in Python
    rather than a Postgres ILIKE/unaccent query because the unaccent extension
    is not assumed to be installed and the roster is only a few dozen rows —
    matching over the already-loaded list_active() set is cheap and portable.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.replace("đ", "d")


def _tokens(text: str) -> list[str]:
    """Normalized alphanumeric tokens of ``text``.

    Splits on any non-alphanumeric character (after diacritics are stripped and
    đ->d, every Vietnamese letter is already a-z) so punctuation-glued titles
    like "ThS.BS" or "BS.CKI" break into separate tokens instead of surviving
    as one unmatchable token. Does NOT drop honorifics — see _query_tokens.
    """
    return re.findall(r"[a-z0-9]+", normalize_vietnamese(text))


def _query_tokens(query: str) -> list[str]:
    """Meaningful tokens of a patient's query, with honorific title phrases removed.

    Title phrases are removed ONLY here (the query side), never from a stored
    full_name — stripping them from ground-truth data would erase real given
    names that collide with title words (BUG-015 review finding). Removal is
    done on the normalized string before tokenizing so multi-word titles like
    "chuyên khoa I" are dropped as a unit, not as separate "chuyen"/"khoa"/"i"
    tokens (which would otherwise wrongly demand those words in the name).
    """
    stripped = _TITLE_RE.sub(" ", normalize_vietnamese(query))
    return re.findall(r"[a-z0-9]+", stripped)


def name_matches(query: str, full_name: str) -> bool:
    """Whether a patient-typed name refers to the doctor with ``full_name``.

    Accent- and case-insensitive, honorific-tolerant, order-independent: every
    meaningful token in ``query`` must appear as a whole token in ``full_name``.
    So "Phạm Thị Lan Hương", "Lan Hương", and "hương" all match the doctor
    "Phạm Thị Lan Hương", while a bare surname like "Phạm" matches every doctor
    named Phạm (the caller then has the patient disambiguate rather than guess).

    Returns False when the query has no meaningful tokens left after dropping
    honorifics, so "bác sĩ" alone never matches anyone.
    """
    query_tokens = _query_tokens(query)
    if not query_tokens:
        return False
    name_tokens = set(_tokens(full_name))
    return all(token in name_tokens for token in query_tokens)
