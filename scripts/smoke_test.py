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
# Description: Smoke test — sends one webhook message per intent (faq,
#              symptom, booking, emergency) against a running stack and
#              asserts each gets a non-empty reply (TASK-016 DoD). Run after
#              `docker compose up`, not as part of `pytest` — it needs a
#              live HTTP server, real Gemini/Qdrant/Postgres.
###############################################################################

import sys
import uuid

import httpx

WEBHOOK_URL = "http://localhost:8000/webhook"

CASES = {
    "faq": "Phòng khám mở cửa mấy giờ?",
    "symptom": "Tôi bị đau bụng âm ỉ vùng thượng vị mấy ngày nay, nên khám khoa nào?",
    "booking": "Tôi muốn đặt lịch khám sáng mai",
    "emergency": "Ba tôi đột nhiên không nói được, méo miệng một bên",
}


def main() -> int:
    """Send one message per intent, print pass/fail per case, exit 1 on any failure."""
    failures = []
    with httpx.Client(timeout=60.0) as client:
        for intent, message in CASES.items():
            user_id = f"smoke-{intent}-{uuid.uuid4()}"
            response = client.post(WEBHOOK_URL, json={"user_id": user_id, "text": message})
            ok = response.status_code == 200 and bool(response.json().get("reply", "").strip())
            print(f"[{'PASS' if ok else 'FAIL'}] {intent}: {message!r}")
            if not ok:
                failures.append(intent)

    if failures:
        print(f"\nSmoke test FAILED for: {', '.join(failures)}")
        return 1

    print("\nSmoke test PASSED for all 4 intents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
