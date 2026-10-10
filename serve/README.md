# Bước 5 — SPARQL endpoint (Apache Jena Fuseki)

Đặt thư mục này cạnh `ontology/`, `collect/`, `transform/`, `link/`. Cần đã chạy xong bước 3 và 4.

## 1. Cài đặt (một lần)

1. **Java 17 trở lên.** Kiểm tra: `java -version`. Trên macOS có thể cài bằng `brew install openjdk@21`.
2. **Apache Jena Fuseki.** Tải bản *apache-jena-fuseki* (file .zip) ở https://jena.apache.org/download/,
   giải nén vào đâu cũng được. Nhớ đường dẫn thư mục đó.
3. **Thư viện Python:** `pip install -r requirements.txt`

## 2. Chạy

```bash
# (a) Suy diễn trước: áp dụng luật OWL 2 RL, ghi triple suy ra vào output/inferred.nt (1-3 phút)
python materialize.py

# (b) Khởi động Fuseki — để cửa sổ terminal này chạy, mở terminal khác cho bước sau
FUSEKI_HOME=/đường/dẫn/apache-jena-fuseki-X.Y.Z bash start_fuseki.sh
# FUSEKI_HOME=/Users/admin/Downloads/apache-jena-fuseki-5.6.0 bash start_fuseki.sh
# (c) Nạp dữ liệu (ontology, dữ liệu, liên kết, suy diễn) vào các named graph
python load.py

# (d) Chạy bộ câu hỏi năng lực, kết quả ở reports/queries.md
python run_queries.py
```

Không cài được Fuseki? `python run_queries.py --local` chạy các truy vấn bằng rdflib trên các file
(trừ truy vấn federated) — đủ để kiểm tra kết quả, nhưng không thay thế được endpoint.

## 3. Giao diện

- **Giao diện web:** http://localhost:3030/ → chọn dataset `vi-dbpedia` → tab *query*.
  Dán nội dung một file trong `queries/` để chạy.
- **SPARQL endpoint:** `http://localhost:3030/vi-dbpedia/sparql` — dùng được từ mọi công cụ SPARQL,
  ví dụ: `curl --data-urlencode "query=SELECT * WHERE { ?s ?p ?o } LIMIT 5" http://localhost:3030/vi-dbpedia/sparql`

### Linked Data browser cục bộ

Mở terminal thứ hai trong thư mục `serve/` và chạy:

```bash
python ld_server.py
```

Giao diện chạy tại `http://127.0.0.1:8000/`; tài nguyên có trang HTML, RDF content negotiation,
và dump tải xuống. Chế độ không cần Fuseki: `python ld_server.py --local`.
Đây là demo cục bộ. Muốn `https://w3id.org/vi-dbpedia/` truy cập công khai, cần triển khai server
HTTPS và cấu hình chuyển tiếp w3id.

## 4. Tổ chức dữ liệu trong endpoint

| Named graph | Nội dung |
|---|---|
| `…/graph/ontology` | `vio-ontology.ttl` + DBpedia Ontology (bản vá) + nhãn tiếng Việt |
| `…/graph/data` | 10 bộ dữ liệu của bước 3 |
| `…/graph/links` | `owl:sameAs` sang DBpedia tiếng Anh (đã kiểm tra) và Wikidata |
| `…/graph/inferred` | triple suy ra bằng forward chaining |
| `…/graph/void` | mô tả bộ dữ liệu (VoID) |

Tiền tố chung: `https://w3id.org/vi-dbpedia/graph/`. Endpoint bật `unionDefaultGraph`, nên truy vấn
không ghi `GRAPH` thấy toàn bộ dữ liệu; ghi `GRAPH <…/graph/inferred>` để chỉ xem phần suy ra.

## 5. Bộ câu hỏi năng lực (`queries/`)

| File | Câu hỏi | Dùng tính năng |
|---|---|---|
| cq01 | 10 tỉnh/thành đông dân nhất | `FILTER NOT EXISTS`, phép tính |
| cq02 | Các tỉnh đã giải thể | `dbo:dissolutionDate\|dbo:dissolutionYear` |
| cq03 | Trường có trụ sở tại Hà Nội | lớp `vio:CoSoGiaoDucDaiHoc` **suy ra** từ lớp con |
| cq04 | Trường thành viên của mỗi đại học | `vio:coThanhVien` **suy ra** từ `owl:inverseOf` |
| cq05 | Số trường theo tỉnh | `GROUP BY` |
| cq06 | Số trường theo loại hình sở hữu | lớp liệt kê `owl:oneOf` |
| cq07 | Số thực thể theo lớp DBpedia | chỉ graph suy ra: `dbo:Province` có cá thể nhờ suy diễn |
| cq08 | Liên kết tỉnh sang DBpedia, Wikidata | `owl:sameAs` |
| cq09 | So sánh kiểu hai bên (federated) | `SERVICE <https://dbpedia.org/sparql>` |
| cq10 | So sánh dân số hai bên (federated) | `SERVICE` + phép trừ |

Truy vấn federated cần mạng và có thể chậm vì phụ thuộc endpoint công khai của DBpedia.
