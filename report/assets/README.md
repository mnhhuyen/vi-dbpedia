# Hình minh họa của báo cáo

- `kien_truc.png`: luồng thu thập, mapping, RDF, kiểm định/liên kết/suy luận và truy vấn.
- `ontology.png`: phân cấp lớp giáo dục, địa giới và ba quan hệ đối tượng tiêu biểu.
- `snapshot_statistics.png`: số liệu snapshot thu thập; sinh từ `collect/reports/collect_summary.json`, `collect/data/articles.jsonl.gz`, `collect/reports/profile_summary.md` và `collect/reports/infobox_templates.csv`.

Các hình được vẽ riêng cho project, không lấy từ tài liệu bên ngoài. Tạo lại bằng lệnh `python report/generate_assets.py` sau khi cài các phụ thuộc trong `report/requirements.txt`. File nguồn là `report/generate_assets.py`; lớp và thuộc tính ontology được đối chiếu với `ontology/vio-ontology.ttl`.
