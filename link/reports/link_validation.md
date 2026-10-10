# Kiểm tra liên kết sang DBpedia tiếng Anh

Endpoint: https://dbpedia.org/sparql · Số liên kết: **200** · Giữ lại sau kiểm tra: **193**

Ghi chú: dòng 'đáng ngờ' được tính trong số 'tồn tại' hoặc 'chuyển hướng' (liên kết có thật nhưng bị bỏ vì kiểu hai bên loại trừ nhau).

## Trạng thái

| Trạng thái | Số liên kết |
|---|---|
| tồn tại | 185 |
| chuyển hướng (đã sửa) | 8 |
| không tồn tại (đã bỏ) | 7 |

## So sánh kiểu: lớp của ta và kiểu cụ thể nhất bên DBpedia tiếng Anh

| Lớp của ta | Kiểu bên tiếng Anh | Số thực thể |
|---|---|---|
| `vio:TruongDaiHoc` | dbo:University | 65 |
| `vio:TruongDaiHoc` | dbo:School, dbo:University | 3 |
| `vio:TruongDaiHoc` | dbo:School | 2 |
| `vio:TruongDaiHoc` | (không có kiểu dbo:) | 1 |
| `vio:Tinh` | dbo:Location, dbo:Settlement | 50 |
| `vio:Tinh` | (không có kiểu dbo:) | 7 |
| `vio:Tinh` | dbo:AdministrativeRegion, dbo:Location | 6 |
| `vio:Tinh` | dbo:Settlement | 1 |
| `vio:Tinh` | dbo:City, dbo:Location, dbo:Town | 1 |
| `vio:ThanhPhoTrucThuocTrungUong` | dbo:City, dbo:Location, dbo:Town | 5 |
| `vio:ThanhPhoTrucThuocTrungUong` | dbo:City, dbo:Location | 1 |
| `vio:ThanhPhoTrucThuocTrungUong` | dbo:City | 1 |
| `vio:ThanhPhoTrucThuocTrungUong` | (không có kiểu dbo:) | 1 |
| `vio:ThanhPhoTrucThuocTrungUong` | dbo:Location, dbo:Settlement | 1 |
| `vio:HocVien` | dbo:University | 6 |
| `vio:HocVien` | dbo:School | 1 |
| `vio:DaiHoc` | dbo:University | 4 |
| `vio:DaiHocVung` | dbo:University | 2 |
| `vio:DaiHocQuocGia` | dbo:University | 2 |

## Liên kết đáng ngờ (hai bên có kiểu loại trừ nhau)

Không có.

## Đánh giá thủ công

Đã lấy ngẫu nhiên 50 liên kết vào `reports/review_sample.csv`. Mở file, điền cột `dung` (1 = đúng, 0 = sai), rồi chạy `python validate_links.py --score reports/review_sample.csv`.
