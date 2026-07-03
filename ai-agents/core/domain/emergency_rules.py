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
# Description: Layer-1 emergency red-flag screening, called from
#              modules/conversation/controller.py before the ADK runtime — rule code
#              only, no LLM call (BIZ-001 §3, ADR-0019). Pure function, zero
#              I/O, unit-testable offline. Better a false positive (routes an
#              ordinary message to the Emergency Agent) than a false
#              negative — BIZ-001 §3: "thà chuyển cấp cứu thừa còn hơn bỏ sót".
###############################################################################

import re
import unicodedata

# BIZ-001 §3 red-flag groups, transcribed as lowercase, accent-stripped
# substrings so matching is robust to Vietnamese diacritics being typed
# inconsistently. Each entry is checked as a substring against the
# normalized input — deliberately permissive (recall over precision).
_RED_FLAG_PHRASES: tuple[str, ...] = (
    # Ý thức
    "lo mo", "goi hoi khong dap", "co giat", "ngat xiu", "bat tinh",
    # Hô hấp
    "kho tho du doi", "kho tho nang", "tho rit", "tim moi", "tim dau chi",
    "nghen di vat", "ngat tho",
    # Tuần hoàn
    "dau nguc du doi", "dau nguc de ep", "dau nguc lan vai", "dau nguc lan tay",
    "dau nguc lan ham", "va mo hoi lanh", "mach rat nhanh", "mach rat cham",
    # Thần kinh
    "liet nua nguoi", "yeu nua nguoi dot ngot", "meo mieng", "noi ngong dot ngot",
    "dau dau du doi nhat", "dau dau du doi nhat tu truoc toi nay",
    # Chảy máu / chấn thương
    "chay mau khong cam", "chan thuong dau kem non", "chan thuong dau kem lo mo",
    "gay xuong ho", "da chan thuong",
    # Tiêu hóa cấp
    "non ra mau", "di ngoai phan den", "dau bung du doi dot ngot", "bung cung",
    # Sản khoa cấp
    "thai phu ra mau nhieu", "vo oi", "thai may giam",
    # Khác (fever is handled separately below — it's a *combination* red flag,
    # not "sot cao" alone)
    "phan ve", "noi me day lan nhanh", "ngo doc", "y dinh tu hai", "tu tu",
)

# Numeric temperature threshold from BIZ-001 §3 ("Sốt cao ≥ 39,5°C kèm li bì").
_HIGH_FEVER_RE = re.compile(r"(3[9]\.[5-9]|4\d)\s*(?:do|°c|c\b)")


def _normalize(text: str) -> str:
    """Lowercase and strip Vietnamese diacritics for robust substring matching."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "d")


def is_emergency(text: str) -> bool:
    """Screen text for red-flag emergency keywords (BIZ-001 §3) — no LLM call.

    Pure function: no network, no database, no logging side effects — safe
    to call synchronously on the hot path before any LLM round-trip.

    Args:
        text: Raw inbound message text.

    Returns:
        True if any BIZ-001 §3 red-flag pattern matches.
    """
    normalized = _normalize(text)

    if any(phrase in normalized for phrase in _RED_FLAG_PHRASES):
        return True

    # BIZ-001 §3: high fever is a red flag only combined with lethargy, not
    # a fever mention alone.
    has_high_fever = "sot cao" in normalized or bool(_HIGH_FEVER_RE.search(normalized))
    if has_high_fever and "li bi" in normalized:
        return True

    return False
