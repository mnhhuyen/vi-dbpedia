# Bước 4 — Liên kết sang DBpedia tiếng Anh (Linked Data 5 sao)

Đặt thư mục này cạnh `ontology/`, `collect/`, `transform/`. Cần đã chạy xong bước 3.

## Chạy

```bash
pip install -r requirements.txt
python link.py              # không cần mạng: sinh liên kết từ dữ liệu bước 2
python validate_links.py    # cần mạng: kiểm tra trên https://dbpedia.org/sparql
```

Sửa biến `USER_AGENT` trong `validate_links.py` (thêm email của bạn) trước khi chạy.

## Nguồn liên kết

| Nguồn | Liên kết sinh ra | Ghi chú |
|---|---|---|
| Liên kết liên ngôn ngữ của Wikipedia (`langlinks.tsv.gz`) | `owl:sameAs dbr:<Tên bài tiếng Anh>` | URI DBpedia sinh từ tiêu đề bài tiếng Anh, nên chính xác cao |
| Mã Wikidata (`wikidata.tsv.gz`) | `owl:sameAs wikidata:Q...` | Phủ cả bài không có bản tiếng Anh |

Không đoán URI từ tên tiếng Việt (ví dụ `dbr:Nghệ_An` không tồn tại; đúng là `dbr:Nghệ_An_province`).

## Kiểm tra (`validate_links.py`)

1. **Tồn tại:** bỏ liên kết tới tài nguyên không có trên DBpedia (bài tiếng Anh bị xoá, đổi tên...).
2. **Chuyển hướng:** `dbr:X dbo:wikiPageRedirects dbr:Y` -> thay bằng `dbr:Y`.
3. **So sánh kiểu:** lớp của ta so với kiểu cụ thể nhất bên tiếng Anh (ví dụ `vio:Tinh` ↔ `dbo:Settlement`).
4. **Liên kết đáng ngờ:** hai bên có kiểu loại trừ nhau theo ontology (ví dụ `dbo:Agent ⊥ dbo:Place`)
   -> mặc định bị bỏ (`--keep-suspicious` để giữ).
5. **Đánh giá thủ công:** 50 liên kết ngẫu nhiên (seed cố định) trong `reports/review_sample.csv`.
   Điền cột `dung` (1 đúng / 0 sai), rồi:
   ```bash
   python validate_links.py --score reports/review_sample.csv
   ```
   -> precision kèm khoảng tin cậy 95% (Wilson).

## Đầu ra

| File | Nội dung |
|---|---|
| `output/sameas-dbpedia.nt` | liên kết DBpedia chưa kiểm tra |
| `output/sameas-dbpedia.validated.nt` | **liên kết DBpedia đã kiểm tra — dùng cho bước 5** |
| `output/sameas-wikidata.nt` | liên kết Wikidata — dùng cho bước 5 |
| `reports/link_summary.md` | độ phủ liên kết theo lớp |
| `reports/link_validation.md` | trạng thái, bảng so sánh kiểu, liên kết đáng ngờ |
| `reports/review_sample.csv` | mẫu chấm tay |

## Về `owl:sameAs`

`owl:sameAs` nghĩa là hai URI chỉ **cùng một thực thể**: mọi thông tin của bên này đúng cho bên kia.
Vì vậy sau khi liên kết, Nghệ An sẽ vừa có kiểu `dbo:Province` (từ dữ liệu của ta) vừa có
`dbo:Settlement` (từ DBpedia tiếng Anh). Hai lớp này không loại trừ nhau trong DBpedia Ontology nên
không gây mâu thuẫn; nhưng nếu hai bên có kiểu loại trừ nhau thì liên kết gần như chắc chắn sai —
đó là lý do bước kiểm tra số 4 loại bỏ chúng.
