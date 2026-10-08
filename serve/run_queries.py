"""
Bước 5 — Chạy bộ câu hỏi năng lực (queries/*.rq) và ghi kết quả ra reports/queries.md.

Hai chế độ:
  python run_queries.py                    # gửi tới Fuseki (http://localhost:3030/vi-dbpedia/sparql)
  python run_queries.py --local            # không cần Fuseki: nạp các file vào rdflib rồi truy vấn
                                           # (bỏ qua truy vấn federated, vì chậm và cần mạng)

Kết quả mỗi câu hỏi: tiêu đề (dòng chú thích đầu file), số dòng, 15 dòng đầu.
"""
import argparse
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
G = "https://w3id.org/vi-dbpedia/graph/"


def short(v):
    s = str(v)
    for p, ns in (("vir:", "https://w3id.org/vi-dbpedia/resource/"), ("vio:", "https://w3id.org/vi-dbpedia/ontology/"),
                  ("dbo:", "http://dbpedia.org/ontology/"), ("dbr:", "http://dbpedia.org/resource/"),
                  ("wd:", "http://www.wikidata.org/entity/")):
        if s.startswith(ns):
            return p + s[len(ns):]
    return s


def run_endpoint(endpoint, query):
    import requests
    r = requests.get(endpoint, params={"query": query}, timeout=300,
                     headers={"Accept": "application/sparql-results+json"})
    r.raise_for_status()
    data = r.json()
    cols = data["head"]["vars"]
    rows = [[b.get(c, {}).get("value", "") for c in cols] for b in data["results"]["bindings"]]
    return cols, rows


def local_dataset():
    from rdflib import Dataset, URIRef
    ds = Dataset(default_union=True)
    files = {
        "ontology": [ROOT / "ontology" / f for f in ("vio-ontology.ttl", "dbo-vi-labels.ttl")],
        "data": [p for p in (ROOT / "transform" / "output").glob("*.nt") if p.name != "page-links.nt"],
        "links": [ROOT / "link" / "output" / "sameas-dbpedia.validated.nt", ROOT / "link" / "output" / "sameas-wikidata.nt"],
        "inferred": [HERE / "output" / "inferred.nt"],
    }
    for name, fs in files.items():
        g = ds.graph(URIRef(G + name))
        for f in fs:
            if f.exists():
                g.parse(f)
    return ds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://localhost:3030/vi-dbpedia/sparql")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--only", help="chỉ chạy truy vấn có tên chứa chuỗi này, ví dụ cq03")
    args = ap.parse_args()

    ds = local_dataset() if args.local else None
    out = ["# Kết quả các câu hỏi năng lực", "",
           f"Nguồn: {'rdflib (cục bộ)' if args.local else args.endpoint}", ""]
    for f in sorted((HERE / "queries").glob("*.rq")):
        if args.only and args.only not in f.name:
            continue
        query = f.read_text(encoding="utf-8")
        title = query.splitlines()[0].lstrip("# ").strip()
        federated = "SERVICE" in query
        print(f"- {f.name}: {title}")
        out += [f"## {title}", "", f"`queries/{f.name}`", ""]
        if federated and args.local:
            out += ["_Bỏ qua ở chế độ --local (truy vấn federated)._", ""]
            continue
        t = time.time()
        try:
            if args.local:
                res = ds.query(query)
                cols = [str(v) for v in res.vars]
                rows = [[("" if x is None else str(x)) for x in r] for r in res]
            else:
                cols, rows = run_endpoint(args.endpoint, query)
        except Exception as e:
            out += [f"**Lỗi:** `{type(e).__name__}: {str(e)[:300]}`", ""]
            print(f"    lỗi: {e}")
            continue
        print(f"    {len(rows)} dòng ({time.time() - t:.1f}s)")
        out += [f"{len(rows)} dòng.", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        out += ["| " + " | ".join(short(c).replace("|", "\\|")[:80] for c in r) + " |" for r in rows[:15]]
        if len(rows) > 15:
            out.append(f"| … ({len(rows) - 15} dòng nữa) |" + " |" * (len(cols) - 1))
        out.append("")
    rep = HERE / "reports"
    rep.mkdir(exist_ok=True)
    (rep / "queries.md").write_text("\n".join(out), encoding="utf-8")
    print(f"\nĐã ghi {rep / 'queries.md'}")


if __name__ == "__main__":
    main()
