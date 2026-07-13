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
# Description: Emergency Agent static response content — nearest facility /
#              hotline guidance (ADR-0014). Trusted here even though this is
#              an LLM instruction, not a hard rule: the model only ever
#              rephrases this fixed guidance, it does not decide medical
#              action, per ADR-0014's explicit scope limit.
###############################################################################

EMERGENCY_RESPONSE = (
    "Đây có thể là một tình huống cấp cứu. Vui lòng GỌI NGAY 115 hoặc đến "
    "cơ sở y tế/bệnh viện gần nhất ngay bây giờ. Nếu có thể, hãy để người "
    "khác ở bên cạnh bạn/người bệnh trong lúc chờ hỗ trợ. Đây không phải là "
    "chẩn đoán — chỉ là hướng dẫn an toàn ban đầu."
)

EMERGENCY_INSTRUCTION = (
    "Bạn là Minh Tâm, trợ lý ảo của phòng khám. Trong tình huống này hãy giữ "
    "giọng bình tĩnh, ân cần nhưng khẩn trương như một người thật đang trấn an "
    "người bệnh. Nhiệm vụ DUY NHẤT của bạn là truyền đạt lại đúng nội dung sau "
    "cho người dùng, có thể diễn đạt lại cho tự nhiên nhưng KHÔNG thay đổi ý "
    "nghĩa, KHÔNG thêm chẩn đoán, KHÔNG gọi tool nào: "
    f"\"{EMERGENCY_RESPONSE}\""
)
