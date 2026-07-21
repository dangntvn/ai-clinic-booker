# TODO — dịch sang tiếng Nhật (jp)

Thư mục này hiện là **bản copy nguyên văn của `eval/fixtures/vn/`** (tiếng Việt),
chỉ để giữ đúng cấu trúc file cho `SEED_LANG=jp` chạy được ngay — nội dung
CHƯA được dịch sang tiếng Nhật.

Cần dịch trước khi dùng `SEED_LANG=jp` cho mục đích thật (demo/eval bằng tiếng Nhật):

- `doctors.yaml` — `full_name`, `title`, `specialty`, `bio` (giữ nguyên cấu trúc field,
  `specialty` phải map đúng 1 trong 14 giá trị enum SPECIALTIES phía backend — kiểm tra
  xem enum có cần bản dịch riêng hay giữ nguyên tiếng Việt/tiếng Anh nội bộ trước khi dịch).
- `knowledge_base/clinic_info/*.md`, `knowledge_base/medical_guide/*.md`,
  `knowledge_base/policy/*.md` — toàn bộ `title` (frontmatter) + nội dung markdown.

Danh tính phòng khám giả định (giữ nguyên khi dịch, chỉ dịch câu chữ xung quanh):
tên "Phòng khám Đa khoa Tâm An", địa chỉ "45 Đường Nguyễn Chí Thanh, Phường Láng
Thượng, Quận Đống Đa, Hà Nội", SĐT "0888 999 000", email "lienhe@tamanclinic.vn".

Xoá file TODO này sau khi đã dịch xong.
