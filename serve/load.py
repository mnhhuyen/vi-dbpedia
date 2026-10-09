"""
Bước 5 — Nạp toàn bộ dữ liệu vào Fuseki, mỗi nhóm một named graph:

  <https://w3id.org/vi-dbpedia/graph/ontology>  vio-ontology + DBpedia Ontology (bản vá) + nhãn tiếng Việt
  <https://w3id.org/vi-dbpedia/graph/data>      dữ liệu bước 3 (10 bộ dữ liệu)
  <https://w3id.org/vi-dbpedia/graph/links>     owl:sameAs sang DBpedia tiếng Anh và Wikidata (bước 4)
  <https://w3id.org/vi-dbpedia/graph/inferred>  triple suy ra (materialize.py)
  <https://w3id.org/vi-dbpedia/graph/void>      mô tả bộ dữ liệu

Tách graph giúp truy vấn phân biệt được dữ liệu gốc và dữ liệu suy ra, ví dụ:
  SELECT ... WHERE { GRAPH <.../graph/inferred> { ?s a dbo:Province } }

Cách chạy (Fuseki phải đang chạy):
    python load.py
"""
import argparse
from pathlib import Path

import requests

HERE = Path(__file__).parent
ROOT = HERE.parent
G = "https://w3id.org/vi-dbpedia/graph/"
TYPES = {".ttl": "text/turtle; charset=utf-8", ".nt": "application/n-triples; charset=utf-8"}


def plan():
    t, l = ROOT / "transform" / "output", ROOT / "link" / "output"
    # ưu tiên: final (đã kiểm tra + liên kết mới từ match.py) > validated > chưa kiểm tra
    dbpedia = next(p for p in (l / "sameas-dbpedia.final.nt", l / "sameas-dbpedia.validated.nt",
                               l / "sameas-dbpedia.nt") if p.exists() or p.name == "sameas-dbpedia.nt")
    return {
        "ontology": [ROOT / "ontology" / f for f in ("vio-ontology.ttl", "dbo-patched.ttl", "dbo-vi-labels.ttl")],
        "data": sorted(p for p in t.glob("*.nt")),
        "links": [dbpedia, l / "sameas-wikidata.nt"],
        "inferred": [HERE / "output" / "inferred.nt"],
        "void": [t / "void.ttl"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://localhost:3030/vi-dbpedia")
    args = ap.parse_args()
    gsp = args.endpoint.rstrip("/") + "/data"

    for name, files in plan().items():
        graph = G + name
        first = True
        for f in files:
            if not f.exists():
                print(f"  [!] bỏ qua (không có file): {f}")
                continue
            body = f.read_bytes()
            # PUT = thay toàn bộ graph (lần đầu), POST = thêm vào graph
            method = requests.put if first else requests.post
            r = method(gsp, params={"graph": graph}, data=body,
                       headers={"Content-Type": TYPES[f.suffix]}, timeout=600)
            if r.status_code >= 300:
                raise SystemExit(f"Lỗi nạp {f.name} vào <{graph}>: {r.status_code} {r.text[:300]}")
            print(f"  ✓ {f.relative_to(ROOT)}  ->  <{graph}>")
            first = False

    q = "SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g ORDER BY ?g"
    r = requests.get(args.endpoint.rstrip("/") + "/sparql", params={"query": q},
                     headers={"Accept": "application/sparql-results+json"}, timeout=120)
    print("\nSố triple trong từng graph:")
    for b in r.json()["results"]["bindings"]:
        print(f"  {b['g']['value']:50} {int(b['n']['value']):>8,}")


if __name__ == "__main__":
    main()
