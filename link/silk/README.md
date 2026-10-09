# Chạy luật liên kết bằng Silk

`linkspec.xml` là luật liên kết ở định dạng LSL của Silk Link Discovery Framework. Đây là bản rút gọn
của `../match.py`: bản Python có thêm bảng dịch thuật ngữ đầy đủ, trọng số theo loại tên, phạt xung đột
địa danh và ghép 1-1. Số liệu đánh giá trong báo cáo lấy từ `match.py`.

> File này **chưa được chạy thử** (máy phát triển không có Java). Kiểm tra lại tên các phép biến đổi
> (`normalizeChars`, `tokenize`...) theo phiên bản Silk bạn dùng.

## Chạy

Cần Java 8+ và `silk.jar` (Silk Single Machine, https://github.com/silk-framework/silk/releases).

```bash
# Gộp dữ liệu bước 3 thành một file
cat ../../transform/output/{labels,instance-types,mappingbased-literals,mappingbased-objects,geo-coordinates}.nt \
    > ../../transform/output/all.nt

java -DconfigFile=linkspec.xml -jar silk.jar
```

Kết quả nằm ở `../output/sameas-dbpedia.silk-tinh.nt` và `../output/sameas-dbpedia.silk-truong.nt`.

## Silk Workbench (giao diện web)

```bash
docker run -d -p 9000:80 silkframework/silk-workbench
```

Mở http://localhost:9000, tạo project và nhập các nguồn dữ liệu như trong `linkspec.xml`. Workbench có
chế độ *learning* (học luật từ các cặp đúng/sai). Có thể dùng `../output/sameas-dbpedia.validated.nt` làm
tập ví dụ đúng.
