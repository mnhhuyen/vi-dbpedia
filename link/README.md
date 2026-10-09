# Bước 4 — Liên kết sang DBpedia tiếng Anh (Linked Data 5 sao)

Đặt thư mục này cạnh `ontology/`, `collect/`, `transform/`. Cần đã chạy xong bước 3.

## Chạy

```bash
pip install -r requirements.txt
python link.py              # không cần mạng: sinh liên kết từ dữ liệu bước 2
python validate_links.py    # cần mạng: kiểm tra trên https://dbpedia.org/sparql
python match.py             # so khớp theo nội dung (kiểu Silk) + đánh giá; lần đầu cần mạng
```

Sửa biến `USER_AGENT` trong `validate_links.py` (thêm email của bạn) trước khi chạy.

## Nguồn liên kết

| Nguồn | Liên kết sinh ra | Ghi chú |
|---|---|---|
| Liên kết liên ngôn ngữ của Wikipedia (`langlinks.tsv.gz`) | `owl:sameAs dbr:<Tên bài tiếng Anh>` | URI DBpedia sinh từ tiêu đề bài tiếng Anh, nên chính xác cao |
| Mã Wikidata (`wikidata.tsv.gz`) | `owl:sameAs wikidata:Q...` | Phủ cả bài không có bản tiếng Anh |

Không đoán URI từ tên tiếng Việt (ví dụ `dbr:Nghệ_An` không tồn tại; đúng là `dbr:Nghệ_An_province`).

## So khớp theo nội dung và đánh giá (`match.py`)

Liên kết liên ngôn ngữ là "tra bảng" — chính xác nhưng không phải *link discovery*. `match.py` làm việc
của Silk: **không dùng** liên kết liên ngôn ngữ, chỉ so sánh nội dung hai bên (tên, loại, homepage, toạ độ,
năm thành lập), rồi dùng liên kết liên ngôn ngữ đã kiểm tra làm **đáp án** để đo precision / recall / F1.
Luật đầy đủ ở đầu `match.py`; bản cho Silk ở `silk/linkspec.xml` (xem `silk/README.md`).

Kết quả hiện tại (chi tiết trong `reports/match_evaluation.md`):

| | Luật ban đầu | Luật cuối |
|---|---|---|
| Precision | 87.0% | **99.4%** |
| Recall | 71.2% | **97.5%** |
| F1 | 78.4% | **98.4%** |

Các bước cải tiến (mỗi bước sửa một loại lỗi thấy trong báo cáo): tách tên chính / tên cũ → mở rộng
tập ứng viên + bảng dịch thuật ngữ Việt–Anh → so sánh loại (tỉnh vs thành phố cùng tên), homepage chỉ là
bằng chứng dương, năm thành lập chỉ cho trường → trọng số tên chuyển hướng, phạt xung đột địa danh →
lọc tên nhiễu bên DBpedia.

**Hạn chế cần nêu trong báo cáo:** luật được tinh chỉnh trên chính tập đáp án nên con số là lạc quan; và
thực thể có liên kết liên ngôn ngữ là nhóm "dễ". Với nhóm không có, bộ so khớp hay chọn nhầm ứng viên gần
nhất (khoảng một nửa trong số liên kết mới ở ngưỡng 0.75 là sai) — vì vậy liên kết mới chỉ vào
`sameas-dbpedia.final.nt` khi tên gần như trùng **và** có thêm bằng chứng độc lập.

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
| `output/sameas-dbpedia.validated.nt` | liên kết DBpedia đã kiểm tra (đáp án cho `match.py`) |
| `output/sameas-dbpedia.matched.nt` | liên kết do bộ so khớp sinh ra |
| `output/sameas-dbpedia.final.nt` | **đã kiểm tra + liên kết mới đủ tin cậy — dùng cho bước 5** |
| `output/sameas-wikidata.nt` | liên kết Wikidata — dùng cho bước 5 |
| `reports/link_summary.md` | độ phủ liên kết theo lớp |
| `reports/link_validation.md` | trạng thái, bảng so sánh kiểu, liên kết đáng ngờ |
| `reports/review_sample.csv` | mẫu chấm tay |
| `reports/match_evaluation.md` | precision / recall / F1 theo ngưỡng, theo lớp, các lỗi |
| `reports/new_links_review.csv` | liên kết mới (không có đáp án) để chấm tay |
| `cache/dbpedia_candidates.json` | ứng viên DBpedia đã tải (có ngày tải) — để chạy lại không cần mạng |

## Về `owl:sameAs`

`owl:sameAs` nghĩa là hai URI chỉ **cùng một thực thể**: mọi thông tin của bên này đúng cho bên kia.
Vì vậy sau khi liên kết, Nghệ An sẽ vừa có kiểu `dbo:Province` (từ dữ liệu của ta) vừa có
`dbo:Settlement` (từ DBpedia tiếng Anh). Hai lớp này không loại trừ nhau trong DBpedia Ontology nên
không gây mâu thuẫn; nhưng nếu hai bên có kiểu loại trừ nhau thì liên kết gần như chắc chắn sai —
đó là lý do bước kiểm tra số 4 loại bỏ chúng.
