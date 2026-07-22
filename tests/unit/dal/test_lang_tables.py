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
# Description: Unit test for dal/lang_tables.py — the single source of
#              truth for the 6 per-language-suffixed table names shared by
#              the ORM models, the ingestion cron's raw SQL, the eval reset
#              script, and the 0002/0003 partitioning migrations. Every
#              caller must agree on the exact string produced for a given
#              suffix. Lives under tests/unit/dal/ (not tests/unit/) to
#              mirror dal/lang_tables.py's own location (moved out of
#              common/ per ADR-0013/CONV-001 §4, code-reviewer finding
#              2026-07-22 review 1/3). doctors_table/bookings_table/
#              chat_session_links_table added by ADR-0024 (2026-07-22).
###############################################################################

import pytest

from dal.lang_tables import (
    bookings_table,
    chat_session_links_table,
    doctors_table,
    ingestion_jobs_table,
    knowledge_base_table,
    knowledge_chunks_table,
)


@pytest.mark.parametrize("suffix", ["vn", "jp", "en"])
def test_knowledge_base_table_appends_suffix(suffix):
    assert knowledge_base_table(suffix) == f"knowledge_base_{suffix}"


@pytest.mark.parametrize("suffix", ["vn", "jp", "en"])
def test_knowledge_chunks_table_appends_suffix(suffix):
    assert knowledge_chunks_table(suffix) == f"knowledge_chunks_{suffix}"


@pytest.mark.parametrize("suffix", ["vn", "jp", "en"])
def test_ingestion_jobs_table_appends_suffix(suffix):
    assert ingestion_jobs_table(suffix) == f"ingestion_jobs_{suffix}"


@pytest.mark.parametrize("suffix", ["vn", "jp", "en"])
def test_doctors_table_appends_suffix(suffix):
    assert doctors_table(suffix) == f"doctors_{suffix}"


@pytest.mark.parametrize("suffix", ["vn", "jp", "en"])
def test_bookings_table_appends_suffix(suffix):
    assert bookings_table(suffix) == f"bookings_{suffix}"


@pytest.mark.parametrize("suffix", ["vn", "jp", "en"])
def test_chat_session_links_table_appends_suffix(suffix):
    assert chat_session_links_table(suffix) == f"chat_session_links_{suffix}"


def test_table_names_are_distinct_across_suffixes():
    # Guards against a typo collapsing two languages onto the same table name.
    names = {knowledge_base_table(s) for s in ("vn", "jp", "en")}
    assert len(names) == 3


def test_business_table_names_are_distinct_across_suffixes():
    # Same guard as above, for the 3 business tables added by ADR-0024.
    assert len({doctors_table(s) for s in ("vn", "jp", "en")}) == 3
    assert len({bookings_table(s) for s in ("vn", "jp", "en")}) == 3
    assert len({chat_session_links_table(s) for s in ("vn", "jp", "en")}) == 3
