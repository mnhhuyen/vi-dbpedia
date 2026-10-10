# Kết quả các câu hỏi năng lực

Nguồn: http://localhost:3030/vi-dbpedia/sparql

## CQ1: 10 tỉnh/thành hiện hành đông dân nhất (dân số, diện tích km², mật độ)

`queries/cq01_tinh_dong_dan.rq`

10 dòng.

| ten | danSo | dienTichKm2 | matDo |
|---|---|---|---|
| Thành phố Hồ Chí Minh | 14052713 | 6773 | 2074.94 |
| Hà Nội | 8807523 | 3360 | 2621.43 |
| An Giang | 4952238 | 9889 | 500.79 |
| Đồng Nai | 4836798 | 12737 | 379.74 |
| Hải Phòng | 4664124 | 3195 | 1459.95 |
| Ninh Bình | 4412264 | 3943 | 1119.12 |
| Đồng Tháp | 4403800 | 5939 | 741.56 |
| Lâm Đồng | 4356400 | 24239 | 179.73 |
| Thanh Hóa | 4320947 | 11115 | 388.76 |
| Cần Thơ | 4257581 | 6361 | 669.34 |

## CQ2: Các tỉnh đã giải thể, thời gian tồn tại (sắp theo ngày giải thể)

`queries/cq02_tinh_da_giai_the.rq`

63 dòng.

| ten | thanhLap | giaiThe |
|---|---|---|
| Bình Trị | 1890-05-03 | 1896-01-23 |
| Hưng Hóa | 1831 | 1903-05-05 |
| Vĩnh Yên (tỉnh) | 1890-10-20 | 1950-02-12 |
| Long Xuyên (tỉnh) | 1900-01-01 | 1956-10-22 |
| Kiến An (tỉnh) | 1887-09-11 | 1962-10-27 |
| Hải Ninh (tỉnh) | 1906 | 1963 |
| Quảng Yên (tỉnh) | 1831 | 1963-10-30 |
| Hà Đông (tỉnh) | 1902-05-03 | 1965-04-21 |
| Sơn Tây (tỉnh Việt Nam) | 1466 | 1965-04-21 |
| Nam Hà (tỉnh) | 1965 | 1975 |
| Gia Định (tỉnh) | 1833 | 1975-05-03 |
| Nghĩa Lộ (tỉnh) | 1962-10-27 | 1975-12-27 |
| Cao Lạng | 1975-12-27 | 1978-12-29 |
| Nghĩa Bình | 1975 | 1989 |
| Phú Khánh | 1975 | 1989 |
| … (48 dòng nữa) | | |

## CQ3: Các cơ sở giáo dục đại học có trụ sở tại Hà Nội

`queries/cq03_truong_tai_ha_noi.rq`

53 dòng.

| ten | loai |
|---|---|
| Đại học Kinh tế Quốc dân | vio:DaiHoc |
| Đại học Phenikaa | vio:DaiHoc |
| Đại học Quốc gia Hà Nội | vio:DaiHocQuocGia |
| Học viện Báo chí và Tuyên truyền | vio:HocVien |
| Học viện Chính sách và Phát triển | vio:HocVien |
| Học viện Chính trị Quốc gia Hồ Chí Minh | vio:HocVien |
| Học viện Công nghệ Bưu chính Viễn thông | vio:HocVien |
| Học viện Múa Việt Nam | vio:HocVien |
| Học viện Nông nghiệp Việt Nam | vio:HocVien |
| Học viện Phụ nữ Việt Nam | vio:HocVien |
| Học viện Quản lý giáo dục | vio:HocVien |
| Học viện Thanh thiếu niên Việt Nam | vio:HocVien |
| Học viện Tài chính (Việt Nam) | vio:HocVien |
| Học viện Tư pháp (Việt Nam) | vio:HocVien |
| Học viện Y – Dược học cổ truyền Việt Nam | vio:HocVien |
| … (38 dòng nữa) | |

## CQ4: Các trường thành viên của mỗi đại học quốc gia / đại học vùng (vio:coThanhVien được suy ra từ nghịch đảo)

`queries/cq04_thanh_vien_dhqg.rq`

4 dòng.

| daiHoc | soThanhVien | danhSach |
|---|---|---|
| Đại học Huế | 8 | Trường Đại học Khoa học, Đại học Huế \| Trường Đại học Kinh tế, Đại học Huế \| T |
| Đại học Quốc gia Thành phố Hồ Chí Minh | 7 | Trường Đại học An Giang, Đại học Quốc gia Thành phố Hồ Chí Minh \| Trường Đại họ |
| Đại học Quốc gia Hà Nội | 7 | Trường Đại học Công nghệ, Đại học Quốc gia Hà Nội \| Trường Đại học Giáo dục, Đạ |
| Đại học Đà Nẵng | 6 | Trường Đại học Bách khoa, Đại học Đà Nẵng \| Trường Đại học Công nghệ Thông tin  |

## CQ5: Số cơ sở giáo dục đại học theo tỉnh/thành

`queries/cq05_so_truong_theo_tinh.rq`

23 dòng.

| tinh | soTruong |
|---|---|
| Hà Nội | 53 |
| Thành phố Hồ Chí Minh | 32 |
| Đà Nẵng | 12 |
| Huế | 10 |
| Thái Nguyên | 7 |
| Cần Thơ | 4 |
| Nghệ An | 4 |
| Hưng Yên | 3 |
| Hải Phòng | 3 |
| Khánh Hòa | 3 |
| Lâm Đồng | 3 |
| Ninh Bình | 3 |
| Vĩnh Long | 3 |
| Đồng Nai | 3 |
| An Giang | 2 |
| … (8 dòng nữa) | |

## CQ6: Số cơ sở giáo dục đại học theo loại hình sở hữu

`queries/cq06_loai_hinh_so_huu.rq`

2 dòng.

| loaiHinh | so |
|---|---|
| công lập | 128 |
| tư thục | 42 |

## CQ7: Lợi ích của suy diễn — số thực thể theo lớp DBpedia (chỉ có trong graph suy ra, dữ liệu gốc chỉ ghi lớp vio:)

`queries/cq07_suy_dien_province.rq`

6 dòng.

| lop | so |
|---|---|
| dbo:Organisation | 260 |
| dbo:University | 237 |
| dbo:AdministrativeRegion | 171 |
| dbo:Place | 171 |
| dbo:Province | 88 |
| dbo:City | 9 |

## CQ8: Tỉnh của ta và tài nguyên tương ứng trên DBpedia tiếng Anh, Wikidata

`queries/cq08_lien_ket_dbpedia.rq`

25 dòng.

| ten | dbpedia | wikidata |
|---|---|---|
| An Giang | dbr:An_Giang_province | wd:Q36592 |
| Cao Bằng | dbr:Cao_Bằng_province | wd:Q36865 |
| Cà Mau | dbr:Cà_Mau_province | wd:Q33354 |
| Gia Lai | dbr:Gia_Lai_province | wd:Q36662 |
| Hà Tĩnh | dbr:Hà_Tĩnh_province | wd:Q33351 |
| Hưng Yên | dbr:Hưng_Yên_province | wd:Q36235 |
| Khánh Hòa | dbr:Khánh_Hòa_province | wd:Q33369 |
| Lai Châu | dbr:Lai_Châu_province | wd:Q36409 |
| Lào Cai | dbr:Lào_Cai_province | wd:Q36446 |
| Lâm Đồng | dbr:Lâm_Đồng_province | wd:Q36721 |
| Lạng Sơn | dbr:Lạng_Sơn_province | wd:Q33403 |
| Nghệ An | dbr:Nghệ_An_province | wd:Q36587 |
| Ninh Bình | dbr:Ninh_Bình_province | wd:Q36900 |
| Phú Thọ | dbr:Phú_Thọ_province | wd:Q36610 |
| Quảng Ngãi | dbr:Quảng_Ngãi_province | wd:Q33304 |
| … (10 dòng nữa) | | |

## CQ9 (federated, cần mạng): So sánh kiểu hai bên — tỉnh của ta là dbo:Province, bên DBpedia tiếng Anh là gì?

`queries/cq09_federated_kieu.rq`

20 dòng.

| ten | enResource | kieuTiengAnh |
|---|---|---|
| An Giang | dbr:An_Giang_province | Place, Location, PopulatedPlace, Settlement |
| Cao Bằng | dbr:Cao_Bằng_province | Place, Location, PopulatedPlace, Settlement |
| Cà Mau | dbr:Cà_Mau_province | Place, Location, PopulatedPlace, Settlement |
| Gia Lai | dbr:Gia_Lai_province | Place, Location, PopulatedPlace, Settlement |
| Hà Tĩnh | dbr:Hà_Tĩnh_province | Place, Location, PopulatedPlace, Settlement |
| Hưng Yên | dbr:Hưng_Yên_province | Place, Location, PopulatedPlace, Settlement |
| Khánh Hòa | dbr:Khánh_Hòa_province | Place, Location, PopulatedPlace, Settlement |
| Lai Châu | dbr:Lai_Châu_province | Place, Location, PopulatedPlace, Settlement |
| Lào Cai | dbr:Lào_Cai_province | Place, Location, PopulatedPlace, Settlement |
| Lâm Đồng | dbr:Lâm_Đồng_province | Place, Location, PopulatedPlace, Settlement |
| Lạng Sơn | dbr:Lạng_Sơn_province | Place, Location, PopulatedPlace, Settlement |
| Nghệ An | dbr:Nghệ_An_province | Place, Location, PopulatedPlace, Settlement |
| Ninh Bình | dbr:Ninh_Bình_province | Place, Location, PopulatedPlace, Settlement |
| Phú Thọ | dbr:Phú_Thọ_province | Place, Location, PopulatedPlace, Settlement |
| Quảng Ngãi | dbr:Quảng_Ngãi_province | Place, Location, PopulatedPlace, Settlement |
| … (5 dòng nữa) | | |

## CQ10 (federated, cần mạng): Dân số theo bản tiếng Việt so với DBpedia tiếng Anh

`queries/cq10_federated_dan_so.rq`

20 dòng.

| ten | danSoVi | danSoEn | chenhLech |
|---|---|---|---|
| Thành phố Hồ Chí Minh | 14052713 | 14002598 | 50115 |
| Hà Nội | 8807523 | 8807523 | 0 |
| An Giang | 4952238 | 4952238 | 0 |
| Đồng Nai | 4836798 | 4576125 | 260673 |
| Hải Phòng | 4664124 | 4664124 | 0 |
| Ninh Bình | 4412264 | 4412264 | 0 |
| Đồng Tháp | 4403800 | 4370046 | 33754 |
| Lâm Đồng | 4356400 | 3872999 | 483401 |
| Thanh Hóa | 4320947 | 4764200 | -443253 |
| Cần Thơ | 4257581 | 4199824 | 57757 |
| Vĩnh Long | 4257580 | 4257581 | -1 |
| Gia Lai | 4182700 | 3583693 | 599007 |
| Phú Thọ | 4022638 | 4022638 | 0 |
| Bắc Ninh | 3989623 | 287658 | 3701965 |
| Nghệ An | 3831694 | 4472300 | -640606 |
| … (5 dòng nữa) | | | |
