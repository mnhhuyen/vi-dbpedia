# Báo cáo VI-DBpedia

- Bản Word để điền thông tin và nộp: `Bao_cao_VI_DBPEDIA.docx`.
- Bản nguồn có thể chỉnh sửa: `Bao_cao.md`.
- Trình tạo Word: `build_report.py`.
- Bằng chứng kiểm thử ontology: `evidence/ontology_validation.txt`.

Trang đầu có các trường thông tin sinh viên cần thay bằng thông tin thật. Báo cáo giữ rõ phạm vi snapshot, con số thực nghiệm và giới hạn đã biết; các kết quả truy vấn lấy từ báo cáo lưu trong repository. Báo cáo không tuyên bố endpoint đã công khai trên Internet hoặc đánh giá matcher bằng tập kiểm thử độc lập.

Để tạo lại DOCX, cài `python-docx` và chạy:

```sh
python -m pip install -r report/requirements.txt
python report/build_report.py
```

Kết quả sẽ ghi vào `report/Bao_cao_VI_DBPEDIA.docx`.
