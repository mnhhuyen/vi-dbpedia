# DBpedia tiếng Việt (bản thu nhỏ)

Chuyển một phần Wikipedia tiếng Việt thành Linked Data 5 sao: thu thập → ontology → RDF → liên kết sang
DBpedia tiếng Anh → SPARQL endpoint.

**Phạm vi:** đơn vị hành chính cấp tỉnh (hiện hành và đã giải thể) và cơ sở giáo dục đại học.
Giới hạn phạm vi là có chủ đích: Wikipedia tiếng Việt có hơn 1 triệu bài, phần lớn là bài sơ khai do bot
tạo; hai nhóm này có infobox đầy đủ, nối được với nhau (trường — trụ sở tại — tỉnh) và có bài tương ứng
bên tiếng Anh để đánh giá liên kết.

**Dữ liệu:** thu thập qua MediaWiki API khoảng ngày **2026-10-09** (theo lịch sử commit; từ nay
`collect/reports/collect_summary.json` ghi `collected_at`). Ứng viên DBpedia cho bước so khớp tải ngày
ghi trong `link/cache/dbpedia_candidates.json`.

## Các bước

| Bước | Thư mục | Chạy | Đầu ra chính |
|---|---|---|---|
| 1. Ontology | [ontology/](ontology/) | `python validate.py --dbo "ontology--DEV_type=orig.owl"` | `vio-ontology.ttl` |
| 2. Thu thập | [collect/](collect/) | `python collect_api.py --depth 1` | `data/articles.jsonl.gz` |
| 3. Chuyển sang RDF | [transform/](transform/) | `python transform.py && python check_quality.py` | `output/*.nt` |
| 4. Liên kết | [link/](link/) | `python link.py && python validate_links.py && python match.py` | `output/sameas-dbpedia.final.nt` |
| 5. Endpoint | [serve/](serve/) | `python materialize.py`, `bash start_fuseki.sh`, `python load.py`, `python run_queries.py` | Fuseki tại `localhost:3030/vi-dbpedia` |

Mỗi thư mục có README riêng. Cài thư viện: `pip install -r <thư mục>/requirements.txt`. HermiT
(bước 1), Fuseki (bước 5) và Silk (tuỳ chọn, bước 4) cần **Java 17+**.

## Số liệu chính

| Chỉ số | Giá trị | Nguồn |
|---|---|---|
| Bài thu thập | 496 | `collect/reports/collect_summary.json` |
| Thực thể được gán lớp | 332 | `transform/reports/transform_summary.md` |
| Triple (dữ liệu bước 3) | 56,748 (40,674 là page-links) | như trên |
| Triple suy ra (OWL 2 RL) | 8,330 · 0 mâu thuẫn | `serve/output/inferred.nt` |
| Vi phạm tiên đề ontology | 0 | `transform/reports/quality_check.md` |
| Liên kết `owl:sameAs` → DBpedia tiếng Anh | 200 | `link/output/sameas-dbpedia.final.nt` |
| Liên kết `owl:sameAs` → Wikidata | 477 | `link/output/sameas-wikidata.nt` |
| Bộ so khớp: precision / recall / F1 | 99.4% / 97.5% / 98.4% (đáp án: liên kết liên ngôn ngữ) | `link/reports/match_evaluation.md` |
| Câu hỏi năng lực (SPARQL) | 10, trong đó 2 federated | `serve/reports/queries.md` |

## Hạn chế đã biết

- Luật so khớp được tinh chỉnh trên chính tập đáp án → precision/recall lạc quan; thực thể không có liên
  kết liên ngôn ngữ khó hơn nhiều (xem `link/README.md`).
- 66 bài tỉnh cũ (thời Pháp thuộc, Việt Nam Cộng hòa...) chưa được gán lớp: `vio:DonViHanhChinhVietNam` suy
  ra `dbo:country dbr:Vietnam`, chưa mô hình hoá được đơn vị hành chính của các chính thể trước đây.
- Toạ độ: 78 tỉnh/thành nhưng chỉ 24 trường (phần lớn infobox trường không ghi toạ độ).
- Kết quả phụ thuộc thời điểm thu thập: Wikipedia và DBpedia đều thay đổi (ví dụ sáp nhập tỉnh 2025).
