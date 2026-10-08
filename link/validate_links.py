"""
Bước 4 (phần 2) — Kiểm tra và đánh giá liên kết sang DBpedia tiếng Anh.

Truy vấn SPARQL endpoint của DBpedia (https://dbpedia.org/sparql) để:
  1. Kiểm tra tồn tại: tài nguyên dbr: có thật không?
  2. Xử lý chuyển hướng: nếu dbr:X chỉ là trang chuyển hướng (dbo:wikiPageRedirects -> dbr:Y),
     thay liên kết bằng dbr:Y.
  3. So sánh kiểu: lớp của ta (ví dụ vio:Tinh) so với kiểu cụ thể nhất bên DBpedia tiếng Anh.
  4. Phát hiện liên kết đáng ngờ: hai bên có kiểu loại trừ nhau (ví dụ một bên là tổ chức,
     một bên là địa điểm; dbo:Agent ⊥ dbo:Place) -> nhiều khả năng liên kết sai.
  5. Lấy mẫu ngẫu nhiên để đánh giá thủ công độ chính xác (precision).

Đầu ra:
  output/sameas-dbpedia.validated.nt   liên kết đã sửa chuyển hướng, bỏ tài nguyên không tồn tại
  reports/link_validation.md           thống kê, bảng so sánh kiểu, liên kết đáng ngờ
  reports/review_sample.csv            mẫu để chấm tay (cột "dung": điền 1 = đúng, 0 = sai)

Cách chạy:
    python validate_links.py                          # cần mạng
    python validate_links.py --score reports/review_sample.csv   # tính precision sau khi chấm tay
"""
import argparse
import csv
import json
import math
import random
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS

HERE = Path(__file__).parent
ENDPOINT = "https://dbpedia.org/sparql"
USER_AGENT = "ViDBpediaCourseProject/0.1 (sinh vien; email-cua-ban@example.com)"
DBO = "http://dbpedia.org/ontology/"
VIO = "https://w3id.org/vi-dbpedia/ontology/"


def short(u):
    s = str(u)
    for p, ns in (("dbo:", DBO), ("vio:", VIO), ("dbr:", "http://dbpedia.org/resource/"),
                  ("vir:", "https://w3id.org/vi-dbpedia/resource/")):
        if s.startswith(ns):
            return p + s[len(ns):]
    return s


# ---------------------------------------------------------------------------
# SPARQL
# ---------------------------------------------------------------------------
def sparql_http(query):
    import requests
    for attempt in range(6):
        try:
            r = requests.get(ENDPOINT, params={"query": query, "format": "application/sparql-results+json"},
                             headers={"User-Agent": USER_AGENT}, timeout=120)
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except Exception as e:                       # mạng, quá tải, phản hồi lỗi
            wait = 2 ** attempt
            print(f"    lỗi truy vấn ({type(e).__name__}), thử lại sau {wait}s...")
            time.sleep(wait)
    raise RuntimeError("Không truy vấn được DBpedia sau nhiều lần thử.")


def describe(iris, sparql, batch=40):
    """Với mỗi IRI: nhãn tiếng Anh, các kiểu dbo:, đích chuyển hướng (nếu có)."""
    info = {i: {"label": None, "types": set(), "redirect": None, "exists": False} for i in iris}
    iris = list(iris)
    for k in range(0, len(iris), batch):
        chunk = iris[k:k + batch]
        values = " ".join(f"<{i}>" for i in chunk)
        q = f"""
        PREFIX dbo: <{DBO}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?r ?label ?type ?redir WHERE {{
          VALUES ?r {{ {values} }}
          {{ ?r rdfs:label ?label . FILTER(LANG(?label) = "en") }}
          UNION {{ ?r a ?type . FILTER(STRSTARTS(STR(?type), "{DBO}")) }}
          UNION {{ ?r dbo:wikiPageRedirects ?redir }}
        }}"""
        for b in sparql(q):
            r = b["r"]["value"]
            d = info.setdefault(r, {"label": None, "types": set(), "redirect": None, "exists": False})
            d["exists"] = True
            if "label" in b:
                d["label"] = b["label"]["value"]
            if "type" in b:
                d["types"].add(URIRef(b["type"]["value"]))
            if "redir" in b:
                d["redirect"] = b["redir"]["value"]
        print(f"  đã kiểm tra {min(k + batch, len(iris))}/{len(iris)}")
        time.sleep(0.5)
    return info


# ---------------------------------------------------------------------------
# Ontology: cây lớp + loại trừ
# ---------------------------------------------------------------------------
class Onto:
    def __init__(self, ontology_dir):
        self.g = Graph()
        d = Path(ontology_dir)
        for f in ("vio-ontology.ttl", "dbo-patched.ttl"):
            if (d / f).exists():
                self.g.parse(d / f)
        self.disjoint = {frozenset(p) for p in self.g.subject_objects(OWL.disjointWith)}
        for ad in self.g.subjects(RDF.type, OWL.AllDisjointClasses):
            for a, b in combinations(list(Collection(self.g, self.g.value(ad, OWL.members))), 2):
                self.disjoint.add(frozenset((a, b)))
        self._memo = {}

    def supers(self, c):
        if c not in self._memo:
            seen, stack = {c}, [c]
            while stack:
                for p in self.g.objects(stack.pop(), RDFS.subClassOf):
                    if isinstance(p, URIRef) and p not in seen:
                        seen.add(p)
                        stack.append(p)
            self._memo[c] = seen
        return self._memo[c]

    def most_specific(self, types):
        types = set(types)
        return sorted((t for t in types if not any(t != u and t in self.supers(u) for u in types)), key=str)

    def conflicts(self, a_types, b_types):
        A = set().union(*(self.supers(t) for t in a_types)) if a_types else set()
        B = set().union(*(self.supers(t) for t in b_types)) if b_types else set()
        return [tuple(sorted(p, key=str)) for p in self.disjoint
                if len(p) == 2 and (lambda x, y: (x in A and y in B) or (y in A and x in B))(*p)]


# ---------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def score(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    judged = [r for r in rows if r.get("dung", "").strip() in ("0", "1")]
    k = sum(r["dung"].strip() == "1" for r in judged)
    n = len(judged)
    if not n:
        print("Chưa có dòng nào được chấm (cột 'dung' điền 1 hoặc 0).")
        return
    lo, hi = wilson(k, n)
    print(f"Đã chấm {n}/{len(rows)} liên kết: {k} đúng.")
    print(f"Precision = {k / n:.1%}  (khoảng tin cậy 95%: {lo:.1%} – {hi:.1%})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", default=str(HERE / "output" / "sameas-dbpedia.nt"))
    ap.add_argument("--types", default=str(HERE.parent / "transform" / "output" / "instance-types.nt"))
    ap.add_argument("--ontology-dir", default=str(HERE.parent / "ontology"))
    ap.add_argument("--sample", type=int, default=50, help="số liên kết lấy mẫu để chấm tay")
    ap.add_argument("--keep-suspicious", action="store_true",
                    help="giữ cả liên kết đáng ngờ trong file kết quả (mặc định: bỏ)")
    ap.add_argument("--score", metavar="CSV", help="tính precision từ file mẫu đã chấm rồi thoát")
    args = ap.parse_args()
    if args.score:
        return score(args.score)
    run(args, sparql_http)


def run(args, sparql):
    links = Graph().parse(args.links)
    pairs = sorted((s, o) for s, o in links.subject_objects(OWL.sameAs))
    ours = {s: o for s, o in Graph().parse(args.types).subject_objects(RDF.type)}
    onto = Onto(args.ontology_dir)
    print(f"Kiểm tra {len(pairs)} liên kết trên {ENDPOINT} ...")

    info = describe({str(o) for _, o in pairs}, sparql)
    redirect_targets = {d["redirect"] for d in info.values() if d["redirect"]}
    if redirect_targets:
        print(f"  {len(redirect_targets)} liên kết là trang chuyển hướng, kiểm tra đích...")
        info.update(describe(redirect_targets, sparql))

    status = Counter()
    validated = Graph()
    rows = []
    type_table = defaultdict(Counter)
    suspicious = []
    for s, o in pairs:
        d = info.get(str(o), {})
        final = str(o)
        if d.get("redirect"):
            final = d["redirect"]
            status["chuyển hướng (đã sửa)"] += 1
        elif not d.get("exists") or (not d.get("label") and not d.get("types")):
            status["không tồn tại (đã bỏ)"] += 1
            continue
        else:
            status["tồn tại"] += 1
        fd = info.get(final, {})
        en_types = onto.most_specific(fd.get("types", set()))
        our = ours.get(s)
        if our is not None:
            type_table[our][", ".join(short(t) for t in en_types) or "(không có kiểu dbo:)"] += 1
            bad = onto.conflicts({our}, fd.get("types", set()))
            if bad:
                suspicious.append((s, final, our, en_types, bad))
                if not args.keep_suspicious:
                    status["đáng ngờ: kiểu loại trừ nhau (đã bỏ)"] += 1
                    continue
        validated.add((s, OWL.sameAs, URIRef(final)))
        rows.append({"tai_nguyen_vi": short(s), "lop_cua_ta": short(our) if our else "",
                     "lien_ket_en": final, "nhan_en": fd.get("label") or "",
                     "kieu_en": " ".join(short(t) for t in en_types)})

    out = Path(args.links).parent
    validated.serialize(out / "sameas-dbpedia.validated.nt", format="nt", encoding="utf-8")

    rep = HERE / "reports"
    rep.mkdir(exist_ok=True)
    random.seed(42)                                   # cố định để tái lập được
    sample = random.sample(rows, min(args.sample, len(rows)))
    with open(rep / "review_sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["tai_nguyen_vi", "lop_cua_ta", "lien_ket_en", "nhan_en", "kieu_en", "dung"])
        w.writeheader()
        for r in sample:
            w.writerow({**r, "dung": ""})

    md = ["# Kiểm tra liên kết sang DBpedia tiếng Anh", "",
          f"Endpoint: {ENDPOINT} · Số liên kết: **{len(pairs)}** · "
          f"Giữ lại sau kiểm tra: **{len(validated)}**", "",
          "Ghi chú: dòng 'đáng ngờ' được tính trong số 'tồn tại' hoặc 'chuyển hướng' (liên kết có thật nhưng bị bỏ vì kiểu hai bên loại trừ nhau).", "",
          "## Trạng thái", "", "| Trạng thái | Số liên kết |", "|---|---|",
          *[f"| {k} | {v} |" for k, v in status.most_common()], "",
          "## So sánh kiểu: lớp của ta và kiểu cụ thể nhất bên DBpedia tiếng Anh", "",
          "| Lớp của ta | Kiểu bên tiếng Anh | Số thực thể |", "|---|---|---|"]
    for our, cnt in sorted(type_table.items(), key=lambda x: -sum(x[1].values())):
        for en_t, n in cnt.most_common():
            md.append(f"| `{short(our)}` | {en_t} | {n} |")
    md += ["", "## Liên kết đáng ngờ (hai bên có kiểu loại trừ nhau)", ""]
    if suspicious:
        md += ["| Tài nguyên | Liên kết | Lớp của ta | Kiểu bên tiếng Anh | Cặp loại trừ |", "|---|---|---|---|---|"]
        for s, final, our, en_types, bad in suspicious:
            md.append(f"| `{short(s)}` | `{short(final)}` | `{short(our)}` | "
                      f"{', '.join(short(t) for t in en_types)} | "
                      f"{'; '.join(f'{short(a)} ⊥ {short(b)}' for a, b in bad)} |")
    else:
        md.append("Không có.")
    md += ["", "## Đánh giá thủ công", "",
           f"Đã lấy ngẫu nhiên {len(sample)} liên kết vào `reports/review_sample.csv`. Mở file, điền cột "
           "`dung` (1 = đúng, 0 = sai), rồi chạy `python validate_links.py --score reports/review_sample.csv`."]
    (rep / "link_validation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()