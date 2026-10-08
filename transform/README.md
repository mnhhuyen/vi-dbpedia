# Bước 3 — Chuyển dữ liệu sang RDF (Linked Data 4 sao)

Đặt thư mục này cạnh `ontology/` và `collect/`:

```
vi-dbpedia/
├── ontology/     bước 1
├── collect/      bước 2  (cần data/articles.jsonl.gz và data/source_categories.tsv.gz)
└── transform/    bước 3  (thư mục này)
```

## Chạy

```bash
pip install -r requirements.txt
python transform.py          # sinh output/*.nt, output/void.ttl, reports/transform_summary.md
python check_quality.py      # kiểm tra vi phạm tiên đề ontology -> reports/quality_check.md
```

Chạy thử trên dữ liệu mẫu (giả lập, có sẵn):

```bash
python transform.py --articles tests/sample-articles.jsonl.gz \
                    --source-categories tests/sample-source_categories.tsv.gz
```

## Các file

| File | Vai trò |
|---|---|
| `mappings.yaml` | **Bảng mapping** infobox → ontology. Sửa file này để thêm/bớt tham số, không cần sửa code |
| `parsers.py` | Chuẩn hoá giá trị tiếng Việt: số "1.234,5", diện tích km² → m², ngày "2/7/1976", template ngày, liên kết... |
| `transform.py` | Đọc bài viết, phân loại, sinh triple, ghi các bộ dữ liệu |
| `check_quality.py` | Kiểm tra loại trừ, functional, kiểu dữ liệu |

## Đầu ra (`output/`)

| Bộ dữ liệu | Nội dung | Áp dụng cho |
|---|---|---|
| `labels.nt` | `rdfs:label` | mọi bài |
| `abstracts.nt` | `dbo:abstract` (đoạn mở đầu) | mọi bài |
| `categories.nt` | `dct:subject` | mọi bài |
| `page-links.nt` | `dbo:wikiPageWikiLink` | mọi bài |
| `provenance.nt` | `foaf:isPrimaryTopicOf`, `prov:wasDerivedFrom`, `dbo:wikiPageID` | mọi bài |
| `infobox-properties.nt` | infobox thô (`vip:`) | mọi bài có infobox |
| `instance-types.nt` | `rdf:type` (lớp `vio:`) | bài được map |
| `mappingbased-literals.nt` | thuộc tính dữ liệu đã chuẩn hoá | bài được map |
| `mappingbased-objects.nt` | quan hệ tới tài nguyên khác | bài được map |
| `geo-coordinates.nt` | `geo:lat`, `geo:long` | bài được map có toạ độ |
| `void.ttl` | mô tả bộ dữ liệu (VoID) | — |

## Quyết định thiết kế đáng ghi vào báo cáo

- **URI:** `https://w3id.org/vi-dbpedia/resource/<Tiêu_đề_bài>`, giữ nguyên chữ tiếng Việt (IRI),
  chuẩn hoá Unicode NFC.
- **Mapping có điều kiện:** tỉnh, thành phố trực thuộc trung ương và tỉnh cũ dùng chung một
  template; lớp được quyết định theo thể loại nơi tìm thấy bài. Trường đại học / học viện được
  phân loại theo tiêu đề (template "Thông tin trường học" dùng chung cho mọi loại trường).
- **Kiểm tra đích trước khi tạo quan hệ:** `vio:truSoTai` chỉ trỏ tới thực thể đã được xác định là
  đơn vị hành chính; `vio:laThanhVienCua` chỉ trỏ tới "Đại học ..."; `vio:coQuanChuQuan` chỉ trỏ tới
  "Bộ ...". Tránh để luật rdfs3 (range) suy ra kiểu sai cho đích.
- **Chọn thuộc tính theo loại đích (`routes`):** tham số "thành viên của" có khi là một đại học
  (`vio:laThanhVienCua`), có khi là bộ chủ quản (`vio:coQuanChuQuan`), có khi là tập đoàn sở hữu
  (`dbo:owningOrganisation`).
- **Nối chữ thường với tài nguyên (`text_fallback`):** khi tham số ghi tên mà không có liên kết
  ("Thành Phố Hồ Chí Minh", "tỉnh Nghệ An"), dùng từ điển xây từ tiêu đề bài và chữ hiển thị của
  liên kết trong toàn bộ dữ liệu. Không áp dụng cho tên người (dễ trùng tên).
- **Không dùng `dbo:isoCodeRegion`** (domain `dbo:Settlement` sẽ suy ra tỉnh là khu dân cư).
- **Không map tỉnh thời Việt Nam Cộng hòa** (template "Infobox" chung): ngoài phạm vi, vì
  ontology suy ra mọi `vio:DonViHanhChinhVietNam` có `dbo:country dbr:Vietnam`. Dữ liệu thô vẫn giữ.
- **Học hàm không phải người:** liên kết `[[TS]]`, `[[PGS]]`... trong tham số hiệu trưởng bị bỏ qua.
- **Mật độ dân số** được tính lại từ dân số và diện tích (giá trị trong infobox là biểu thức `#expr`).
