# Bước 1 — Ontology cho DBpedia tiếng Việt (v0.1)

Phạm vi: **đơn vị hành chính** và **cơ sở giáo dục đại học**.

## Các file

| File | Vai trò |
|---|---|
| `vio-ontology.ttl` | Ontology mở rộng `vio:` — import DBpedia Ontology và bộ nhãn tiếng Việt |
| `dbo-vi-labels.ttl` | Nhãn `@vi` cho các lớp/thuộc tính `dbo:` được dùng |
| `prepare_dbo.py` | Vá 3 lỗi của DBpedia Ontology, sinh `dbo-patched.ttl` và `dbo-patched-dl.ttl` |
| `dbo-patched.ttl` | DBpedia Ontology đã vá lỗi — nạp vào triple store ở bước 5 |
| `dbo-patched-dl.ttl` | Như trên, bỏ thêm kiểu dữ liệu ngoài OWL 2 — dùng cho reasoner |
| `catalog-v001.xml` | Cho Protégé biết lấy các file import từ thư mục này thay vì tải qua mạng |
| `tests/sample-abox.ttl` | Dữ liệu minh hoạ (Hà Nội, Cầu Giấy, Trường ĐH Công nghệ...) |
| `validate.py` | 20 kiểm tra: cú pháp, tham chiếu, nhãn, suy luận HermiT, phát hiện dữ liệu sai |

## Chạy

```bash
pip install rdflib owlready2          # owlready2 cần Java để chạy HermiT
python prepare_dbo.py ontology--DEV_type_orig.owl
python validate.py --dbo ontology--DEV_type_orig.owl
```

## Mở trong Protégé

1. Giữ nguyên các file trong cùng một thư mục (Protégé đọc `catalog-v001.xml` tự động).
2. *File → Open…* → `vio-ontology.ttl`.
3. *Reasoner → HermiT → Start reasoner*, xem cây lớp ở chế độ *Inferred*.
4. Để xem suy luận trên dữ liệu: mở `tests/sample-abox.ttl` (file này import `vio-ontology.ttl`),
   chạy HermiT, chọn individual `Trường_Đại_học_Công_nghệ_ĐHQGHN` trong tab *Individuals* —
   các dòng nền vàng là thông tin do reasoner suy ra (ví dụ: trụ sở tại Hà Nội).
