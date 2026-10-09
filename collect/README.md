# Bước 2 — Thu thập bài viết Wikipedia tiếng Việt theo thể loại

Chỉ tải các bài thuộc những thể loại đã chọn (kèm thể loại con), qua MediaWiki API
của Wikipedia. Không cần tải bản dump toàn bộ.

## Cài đặt

```bash
pip install -r requirements.txt
```

Mở `collect_api.py`, sửa biến `USER_AGENT` ở đầu file: thay email mẫu bằng email
của bạn (Wikimedia yêu cầu chương trình gọi API phải có thông tin liên hệ).

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
   python collect_api.py --depth 1
   ```
5. **Khảo sát infobox** để chuẩn bị bảng mapping cho bước 3:
   ```bash
   python profile_infoboxes.py
   ```

## Kết quả

| File | Nội dung | Dùng cho |
|---|---|---|
| `data/articles.jsonl.gz` | Mỗi dòng một bài: id, tiêu đề, wikitext | Bước 3 |
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
