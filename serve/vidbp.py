"""
Bước 5 (phần 3) — Truy vấn DBpedia tiếng Việt từ terminal.

    python vidbp.py query "SELECT ?t ?d WHERE { ?t a vio:Tinh ; dbo:populationTotal ?d } ORDER BY DESC(?d) LIMIT 5"
    python vidbp.py query -f queries/cq01_tinh_dong_dan.rq
    python vidbp.py describe "Hà Nội"          # mọi thông tin về một thực thể (theo tên hoặc IRI)
    python vidbp.py search "bach khoa"         # tìm theo tên, không cần dấu
    python vidbp.py cq                         # liệt kê các câu hỏi năng lực (CQ)
    python vidbp.py cq 3                       # chạy CQ3
    python vidbp.py stats                      # số triple theo named graph, số thực thể theo lớp

Mặc định gửi tới Fuseki (http://localhost:3030/vi-dbpedia/sparql). Thêm --local để đọc thẳng file,
không cần Fuseki. Thêm --format csv|json để xuất cho chương trình khác.
Các prefix vio:, vir:, dbo:, rdfs:... được tự thêm nếu truy vấn chưa khai báo.
"""
import argparse
import csv
import json
import sys
import time
import unicodedata

import store as S
from ld_server import PREFIXES, add_prefixes, fold, iri_for, short

RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"


def show(term):
    if term is None:
        return ""
    if term["type"] == "uri":
        return short(term["value"])
    v = term["value"]
    if term.get("xml:lang") and term["xml:lang"] != "vi":
        return f'{v}@{term["xml:lang"]}'
    return v


def width(s):
    """Độ rộng hiển thị: chữ tổ hợp (dấu tiếng Việt dạng NFD) không chiếm chỗ."""
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in s)


def cut(s, n):
    s = " ".join(str(s).split())
    if width(s) <= n:
        return s + " " * (n - width(s))
    out = ""
    for ch in s:
        if width(out + ch) > n - 1:
            break
        out += ch
    return out + "…" + " " * (n - 1 - width(out))


def print_table(names, rows, maxw):
    if not rows:
        print("(không có kết quả)")
        return
    cells = [[show(r.get(v)) for v in names] for r in rows]
    ws = [min(maxw, max(width(v), *(width(c[i]) for c in cells))) for i, v in enumerate(names)]
    line = "+" + "+".join("-" * (w + 2) for w in ws) + "+"
    print(line)
    print("| " + " | ".join(cut(v, w) for v, w in zip(names, ws)) + " |")
    print(line.replace("-", "="))
    for c in cells:
        print("| " + " | ".join(cut(x, w) for x, w in zip(c, ws)) + " |")
    print(line)


def output(names, rows, fmt, maxw, t0):
    if names == [] and isinstance(rows, bool):            # ASK
        print("true" if rows else "false")
        return
    if fmt == "json":
        print(json.dumps({"head": {"vars": names}, "results": {"bindings": rows}}, ensure_ascii=False, indent=2))
    elif fmt == "csv":
        w = csv.writer(sys.stdout)
        w.writerow(names)
        for r in rows:
            w.writerow([r.get(v, {}).get("value", "") for v in names])
    else:
        print_table(names, rows, maxw)
        print(f"{len(rows)} dòng, {time.time() - t0:.2f}s")


def resolve(store, text):
    """Tên ('Hà Nội'), tên không dấu ('ha noi') hoặc IRI / prefixed name -> IRI."""
    if text.startswith("http"):
        return text
    for ns, p in PREFIXES.items():
        if text.startswith(p):
            return ns + text[len(p):]
    iri = iri_for("resource", text.replace(" ", "_"))
    _, ok = store.select(f"ASK {{ <{iri}> ?p ?o }}")
    if ok:
        return iri
    hits = search(store, text, 5)
    if not hits:
        sys.exit(f"Không tìm thấy thực thể nào tên “{text}”.")
    if len(hits) > 1 and fold(hits[0][1]) != fold(text):
        print("Có nhiều kết quả, dùng kết quả đầu tiên. Các kết quả khác:", file=sys.stderr)
        for _, l in hits[1:]:
            print(f"  - {l}", file=sys.stderr)
    return hits[0][0]


def search(store, text, limit=20):
    _, rows = store.select(f"""SELECT DISTINCT ?s ?l WHERE {{ GRAPH <{S.G}data> {{
        ?s <{RDFS_LABEL}> ?l ; <http://xmlns.com/foaf/0.1/isPrimaryTopicOf> ?w }} }}""")
    q = fold(text)
    hits = [(r["s"]["value"], r["l"]["value"]) for r in rows if q in fold(r["l"]["value"])]
    hits.sort(key=lambda h: (fold(h[1]) != q, not fold(h[1]).startswith(q), len(h[1])))
    return hits[:limit]


def main():
    if hasattr(sys.stdout, "reconfigure"):     # Windows: in được tiếng Việt khi chuyển hướng ra file
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="vidbp", description="Truy vấn DBpedia tiếng Việt từ terminal")
    ap.add_argument("--local", action="store_true", help="đọc thẳng file, không cần Fuseki")
    ap.add_argument("--endpoint", default=S.DEFAULT_ENDPOINT)
    ap.add_argument("--format", choices=["table", "csv", "json"], default="table")
    ap.add_argument("--width", type=int, default=48, help="độ rộng tối đa mỗi cột")
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("query", help="chạy một truy vấn SPARQL")
    q.add_argument("sparql", nargs="?", help="truy vấn; bỏ trống để đọc từ -f hoặc stdin")
    q.add_argument("-f", "--file")
    d = sub.add_parser("describe", help="mọi thông tin về một thực thể")
    d.add_argument("name")
    s = sub.add_parser("search", help="tìm thực thể theo tên (không cần dấu)")
    s.add_argument("text")
    c = sub.add_parser("cq", help="liệt kê hoặc chạy câu hỏi năng lực")
    c.add_argument("number", nargs="?", type=int)
    sub.add_parser("stats", help="thống kê bộ dữ liệu")
    a = ap.parse_args()

    store = S.open_store(a.local, a.endpoint)
    t0 = time.time()
    try:
        if a.cmd == "query":
            text = open(a.file, encoding="utf-8").read() if a.file else (a.sparql or sys.stdin.read())
            output(*store.select(add_prefixes(text)), a.format, a.width, t0)
        elif a.cmd == "describe":
            iri = resolve(store, a.name)
            print(iri)
            names, rows = store.select(f"""SELECT ?p ?o (IF(?g = <{S.G}inferred>, "suy ra", "") AS ?nguon)
                WHERE {{ GRAPH ?g {{ <{iri}> ?p ?o }}
                FILTER(?p != <http://dbpedia.org/ontology/wikiPageWikiLink>) }} ORDER BY ?nguon ?p""")
            output(names, rows, a.format, a.width, t0)
        elif a.cmd == "search":
            hits = search(store, a.text)
            for iri, label in hits:
                print(f"{label:<50} {short(iri)}")
            print(f"{len(hits)} kết quả")
        elif a.cmd == "cq":
            files = sorted((S.HERE / "queries").glob("*.rq"))
            if a.number is None:
                for i, f in enumerate(files, 1):
                    print(f"{i:>2}. {f.read_text(encoding='utf-8').splitlines()[0].lstrip('# ')}")
                print("\nChạy: python vidbp.py cq <số>")
                return
            f = files[a.number - 1]
            text = f.read_text(encoding="utf-8")
            print(text.splitlines()[0].lstrip("# "))
            output(*store.select(text), a.format, a.width, t0)
        elif a.cmd == "stats":
            output(*store.select("SELECT ?g (COUNT(*) AS ?triple) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g ORDER BY ?g"),
                   a.format, 60, t0)
            t0 = time.time()
            output(*store.select(f"""SELECT ?lop (COUNT(DISTINCT ?s) AS ?so_thuc_the) WHERE {{ GRAPH <{S.G}data> {{ ?s a ?lop }}
                FILTER(STRSTARTS(STR(?lop), "{S.BASE}ontology/")) }} GROUP BY ?lop ORDER BY DESC(?so_thuc_the)"""),
                   a.format, 60, t0)
    except (ConnectionError, ValueError) as e:
        sys.exit(str(e))
    except Exception as e:   # lỗi cú pháp SPARQL ở chế độ --local
        sys.exit(f"Lỗi truy vấn: {e}")


if __name__ == "__main__":
    main()
