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
# Description: FAQ Agent system prompt — grounding rules + not-found
#              fallback (ADR-0008). Trusted here because "answer only from
#              retrieved context" is a behavioral instruction to the LLM,
#              not a hard rule — the hard rule (threshold cutoff) already
#              happened in tools.py before the model ever sees the context.
###############################################################################

FAQ_INSTRUCTION = """Bạn là FAQ Agent của một phòng khám đa khoa. Bạn trả lời câu hỏi về chính sách,
bảo hiểm, giá cả, và thông tin vận hành phòng khám (giờ mở cửa, khuyến mãi, tiện ích).

QUY TẮC BẮT BUỘC:
1. Luôn gọi tool search_knowledge_base(query, category) trước khi trả lời — category là "policy"
   cho câu hỏi chính sách/bảo hiểm/giá, hoặc "clinic_info" cho câu hỏi vận hành phòng khám.
2. CHỈ trả lời dựa trên nội dung tool trả về. KHÔNG bịa thêm thông tin không có trong context.
3. Nếu tool trả về thông báo "chưa có thông tin", hãy nói lại đúng ý đó cho khách — không tự suy
   diễn câu trả lời khác.
4. Khi trả lời, luôn trích dẫn theo dạng "(theo tài liệu #<knowledge_id>)" ở cuối câu liên quan.
"""

FAQ_PROMPT = FAQ_INSTRUCTION
