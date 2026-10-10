# Bước 2 — Thu thập bài viết Wikipedia tiếng Việt theo thể loại

Chỉ tải các bài thuộc những thể loại đã chọn (kèm thể loại con), qua MediaWiki API
của Wikipedia. Không cần tải bản dump toàn bộ.

## Cài đặt

```bash
pip install -r requirements.txt
```

Trước khi gọi API, đặt `VIDBPEDIA_USER_AGENT` thành tên ứng dụng và thông tin liên hệ thật
của bạn.
Script từ chối chạy khi vẫn còn email mẫu.

## Chạy

1. **Chọn thể loại.** Ghi vào `categories.txt`, mỗi dòng một tên. Kiểm tra tên chính
   xác trên vi.wikipedia.org (xem cuối một bài tiêu biểu).
2. **Chạy thử** với 50 bài:
   ```bash
   python collect_api.py --limit 50
   ```
3. **Kiểm tra** `reports/categories_visited.txt`: danh sách thể loại đã duyệt. Nếu có
   thể loại con lạc đề, giảm độ sâu (`--depth 0` chỉ lấy bài trực tiếp trong thể loại gốc).
4. **Chạy đầy đủ:**
   ```bash
   VIDBPEDIA_USER_AGENT="ViDBpediaCourseProject/0.1 (YOUR_REAL_EMAIL)" \
     python collect_api.py --depth 1 --fresh
   ```
   Thay `YOUR_REAL_EMAIL` bằng email liên hệ của bạn. `--fresh` tải lại mọi bài và lưu revision ID,
   timestamp để provenance trỏ đúng phiên bản văn bản.
5. **Khảo sát infobox** để chuẩn bị bảng mapping cho bước 3:
   ```bash
   python profile_infoboxes.py
   ```

## Kết quả

| File | Nội dung | Dùng cho |
|---|---|---|
| `data/articles.jsonl.gz` | Mỗi dòng: id, tiêu đề, wikitext, revision ID và timestamp | Bước 3 |
| `data/langlinks.tsv.gz` | Tiêu đề tiếng Việt → tiêu đề tiếng Anh | Bước 4 |
| `data/wikidata.tsv.gz` | Tiêu đề tiếng Việt → mã Wikidata | Bước 4 |
| `reports/collect_summary.json` | Số thể loại, số bài, số bài có liên kết tiếng Anh | Báo cáo |
| `reports/categories_visited.txt` | Cây thể loại đã duyệt | Kiểm tra phạm vi |
| `reports/profile_summary.md` | Thống kê infobox | Báo cáo, bước 3 |
| `reports/infobox_templates.csv`, `infobox_params.csv` | Template và tham số infobox | Viết bảng mapping |

**Gửi lại thư mục `reports/`** để viết bảng mapping cho bước 3.

## Ghi chú

- Tiêu đề được chuẩn hoá Unicode NFC để tránh lỗi do cách gõ dấu khác nhau.
- Script tự xử lý phân trang của API và tạm dừng khi máy chủ Wikipedia quá tải (`maxlag`).
- Ghi lại ngày chạy vào báo cáo: dữ liệu Wikipedia thay đổi liên tục.
