# Đánh giá bộ so khớp (kiểu Silk) với đáp án là liên kết liên ngôn ngữ

Ứng viên DBpedia tải ngày **2026-10-09** · ngưỡng **0.75** · luật: xem đầu `match.py` hoặc `silk/linkspec.xml`.

## Kết quả chính

| Chỉ số | Giá trị |
|---|---|
| Thực thể trong phạm vi (tỉnh/thành, cơ sở GDĐH) | 332 |
| Có đáp án (liên kết liên ngôn ngữ đã kiểm tra) | 160 |
| Đáp án nằm trong tập ứng viên (trần recall) | 157 (98.1%) |
| Liên kết bộ so khớp sinh ra | 181 |
| — chấm được (thực thể có đáp án) | 157 |
| — đúng | 156 |
| **Precision** | **99.4%** |
| **Recall** | **97.5%** |
| **F1** | **98.4%** |
| Liên kết mới (thực thể không có liên kết liên ngôn ngữ) | 24 |
| — đủ tin cậy, đưa vào `sameas-dbpedia.final.nt` | 6 |
| Tổng liên kết trong `sameas-dbpedia.final.nt` | 200 |

Precision chỉ tính trên thực thể có đáp án; liên kết mới cần chấm tay (`reports/new_links_review.csv`, cột `dung`).

**Lưu ý khi đọc số liệu.** Luật được tinh chỉnh bằng cách xem lỗi trên chính tập đáp án này, nên precision/recall ở đây là ước lượng lạc quan. Thực thể có liên kết liên ngôn ngữ cũng là nhóm "dễ" (chắc chắn có bài tiếng Anh); với nhóm không có, bộ so khớp hay chọn nhầm ứng viên gần nhất — vì vậy liên kết mới chỉ được nhận khi tên ≥ 0.95 và có thêm bằng chứng độc lập (type, homepage, geo, year).

## Theo ngưỡng

| Ngưỡng | Sinh ra | Đúng | Precision | Recall | F1 | Mới |
|---|---|---|---|---|---|---|
| 0.5 | 245 | 156 | 98.1% | 97.5% | 97.8% | 86 |
| 0.6 | 213 | 156 | 98.1% | 97.5% | 97.8% | 54 |
| 0.65 | 199 | 156 | 98.7% | 97.5% | 98.1% | 41 |
| 0.7 | 190 | 156 | 98.7% | 97.5% | 98.1% | 32 |
| 0.75 ← | 181 | 156 | 99.4% | 97.5% | 98.4% | 24 |
| 0.8 | 178 | 156 | 99.4% | 97.5% | 98.4% | 21 |
| 0.85 | 166 | 155 | 99.4% | 96.9% | 98.1% | 10 |
| 0.9 | 166 | 155 | 99.4% | 96.9% | 98.1% | 10 |
| 0.95 | 148 | 140 | 99.3% | 87.5% | 93.0% | 7 |

## Theo lớp

| Lớp | Đáp án | Sinh ra | Đúng | Precision | Recall |
|---|---|---|---|---|---|
| `vio:TruongDaiHoc` | 71 | 69 | 69 | 100.0% | 97.2% |
| `vio:Tinh` | 65 | 64 | 64 | 100.0% | 98.5% |
| `vio:HocVien` | 7 | 7 | 7 | 100.0% | 100.0% |
| `vio:ThanhPhoTrucThuocTrungUong` | 9 | 9 | 8 | 88.9% | 88.9% |
| `vio:DaiHoc` | 4 | 4 | 4 | 100.0% | 100.0% |
| `vio:DaiHocVung` | 2 | 2 | 2 | 100.0% | 100.0% |
| `vio:DaiHocQuocGia` | 2 | 2 | 2 | 100.0% | 100.0% |

## Đóng góp của từng phép so sánh

Số liên kết đúng (ở ngưỡng đã chọn) có phép so sánh đó.

| Phép so sánh | Có giá trị | Điểm = 1 |
|---|---|---|
| name | 156 | 145 |
| type | 72 | 72 |
| homepage | 86 | 86 |
| geo | 73 | 43 |
| year | 51 | 45 |

## Liên kết sai (1)

| Thực thể | Bộ so khớp chọn | Đáp án |
|---|---|---|
| vir:Huế | dbr:Thừa_Thiên_Huế_province | dbr:Huế |

## Bỏ sót (3)

Lý do: *ngoài ứng viên* = đáp án không nằm trong tập ứng viên tải về; *điểm thấp* = có nhưng điểm dưới ngưỡng hoặc bị ghép với thực thể khác.

| Thực thể | Đáp án | Lý do |
|---|---|---|
| vir:Thừa_Thiên_Huế | dbr:Thừa_Thiên_Huế_province | điểm thấp |
| vir:Trường_Đại_học_Hải_Phòng | dbr:Hai_Phong_University | ngoài ứng viên |
| vir:Trường_Đại_học_Kinh_tế,_Đại_học_Quốc_gia_Hà_Nội | dbr:College_of_Economics,_Vietnam_National_University | ngoài ứng viên |
