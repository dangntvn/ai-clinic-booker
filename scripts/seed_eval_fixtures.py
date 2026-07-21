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
# Description: Reset the eval environment to a known-clean state and reseed
#              it from eval/fixtures/ (TASK-025) via the real API — the same
#              manual process TASK-026 ran by hand, made repeatable so every
#              eval run starts from identical real data instead of whatever
#              state a prior run left behind (BUG-001/BUG-008). Wipes every
#              domain table plus the Qdrant collection first, so ingestion
#              also re-proves BUG-001's ensure_collection() fix against a
#              genuinely missing collection, not a mock.
###############################################################################

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import httpx
import yaml
from sqlalchemy import text

from common.config import settings
from common.database import AsyncSessionFactory
from dal.qdrant_client import get_qdrant_client

_SUPPORTED_LANGS = {"vn", "jp", "en"}


def _seed_lang() -> str:
    """Pick the fixture language from SEED_LANG — never guess a default.

    Each language's fixtures (doctors, addresses, phone numbers) are
    fully independent datasets, so silently falling back to one (e.g.
    "vn") could seed the wrong language's data without anyone noticing.
    """
    lang = os.environ.get("SEED_LANG")
    if lang not in _SUPPORTED_LANGS:
        raise RuntimeError(
            f"SEED_LANG={lang!r} is not set to one of {sorted(_SUPPORTED_LANGS)} — "
            "set SEED_LANG=vn|jp|en explicitly before running this script."
        )
    return lang


FIXTURES_DIR = Path(__file__).parent.parent / "eval" / "fixtures" / _seed_lang()
API_BASE = "http://localhost:8000/api/v1"

# TASK-026 decision (eval/data_requirements.md §5.1, option a): the real site
# never published per-doctor schedules, so every seeded doctor gets this
# fixed test-only Mon-Sat schedule instead of a fabricated real one.
TEST_WORK_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Doctor ids 1-2 were already taken by unrelated earlier manual testing when
# TASK-026 first seeded — golden_set_booking.yaml hardcodes doctor_id 3/4, so
# the sequence is restarted at 3 to reproduce the same ids on every reseed.
DOCTOR_ID_SEQUENCE_START = 3


_SAFE_APP_ENVS = {"local", "eval", "test"}


def _guard_against_production() -> None:
    """Refuse to run against anything that isn't explicitly a throwaway env.

    This script TRUNCATEs every domain table — a wrong `.env` pointed at a
    real deployment would be an unrecoverable data-loss incident, not just a
    failed eval run.
    """
    if settings.app_env not in _SAFE_APP_ENVS:
        raise RuntimeError(
            f"settings.app_env={settings.app_env!r} is not one of {_SAFE_APP_ENVS} — "
            "refusing to truncate domain tables. Set APP_ENV explicitly if this really "
            "is a throwaway eval environment."
        )


async def wipe() -> None:
    """Delete every row from the domain tables and the Qdrant collection."""
    _guard_against_production()
    async with AsyncSessionFactory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE bookings, knowledge_chunks, ingestion_jobs, "
                "knowledge_base, doctors RESTART IDENTITY CASCADE"
            )
        )
        await session.execute(
            text(f"ALTER SEQUENCE doctors_id_seq RESTART WITH {DOCTOR_ID_SEQUENCE_START}")
        )
        await session.commit()

    client = get_qdrant_client()
    if client.collection_exists(settings.qdrant_collection):
        client.delete_collection(settings.qdrant_collection)


def _parse_fixture(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    _, front_matter, body = raw.split("---", 2)
    meta = yaml.safe_load(front_matter)
    return {"category": meta["category"], "title": meta["title"], "content": body.strip()}


# doctors.yaml holds every doctor for the language in seed order — ids are
# assigned sequentially starting at DOCTOR_ID_SEQUENCE_START, so keep this
# file's row order stable across reseeds to reproduce the same ids.
_DOCTORS_FILE = "doctors.yaml"


async def seed_doctors(http: httpx.AsyncClient) -> list[int]:
    fixture = yaml.safe_load((FIXTURES_DIR / _DOCTORS_FILE).read_text(encoding="utf-8"))
    ids = []
    for doctor in fixture["doctors"]:
        body = {
            "full_name": doctor["full_name"],
            "title": doctor.get("title"),
            "specialty": doctor["specialty"],
            "phone": doctor.get("phone"),
            "work_days": TEST_WORK_DAYS,
            "room": doctor.get("room"),
            "shift": doctor.get("shift"),
            "fee": doctor.get("fee"),
            "bio": doctor.get("bio"),
            "education": doctor.get("education"),
        }
        resp = await http.post(f"{API_BASE}/doctors", json=body)
        resp.raise_for_status()
        ids.append(resp.json()["id"])
    return ids


async def seed_knowledge(http: httpx.AsyncClient) -> list[int]:
    files = sorted((FIXTURES_DIR / "knowledge_base").glob("*/*.md"))
    ids = []
    for path in files:
        fixture = _parse_fixture(path)
        resp = await http.post(f"{API_BASE}/knowledge", json=fixture)
        resp.raise_for_status()
        knowledge_id = resp.json()["id"]
        publish_resp = await http.post(f"{API_BASE}/knowledge/{knowledge_id}/publish")
        publish_resp.raise_for_status()
        ids.append(knowledge_id)
    return ids


async def main() -> None:
    await wipe()

    async with httpx.AsyncClient(timeout=30.0) as http:
        doctor_ids = await seed_doctors(http)
        knowledge_ids = await seed_knowledge(http)

    print(f"seeded doctors: {doctor_ids}")
    print(f"seeded knowledge: {knowledge_ids}")

    subprocess.run([sys.executable, "scripts/run_ingestion_job.py", "--reindex-all"], check=True)


if __name__ == "__main__":
    asyncio.run(main())
