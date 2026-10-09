"""
Bước 5 (chuẩn bị) — Suy diễn trước (materialization) bằng forward chaining.

Áp dụng luật OWL 2 RL (bao gồm các luật RDFS trong bài giảng: rdfs2, rdfs3, rdfs7, rdfs9...,
cùng các luật OWL: bắc cầu, nghịch đảo, property chain, hasValue) lên ontology + dữ liệu,
rồi ghi riêng các triple MỚI được suy ra vào output/inferred.nt.

Vì sao suy diễn trước thay vì để endpoint tự suy diễn khi truy vấn?
  - Reasoner của Jena không hỗ trợ property chain (OWL 2); thư viện owlrl thì có.
  - Truy vấn nhanh hơn, và tách được "dữ liệu gốc" với "dữ liệu suy ra" thành hai named graph.

Chỉ đưa vào suy diễn: kiểu, thuộc tính đã map (bước 3). Không đưa liên kết owl:sameAs
(nếu đưa, luật của sameAs sẽ chép toàn bộ thuộc tính sang tài nguyên dbr:/wikidata:).

Cách chạy:
    pip install owlrl rdflib
    python materialize.py          # khoảng 1-3 phút
"""
import argparse
import time
from pathlib import Path

import owlrl
from itertools import combinations

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS

HERE = Path(__file__).parent
ROOT = HERE.parent
RESOURCE_NS = "https://w3id.org/vi-dbpedia/resource/"


def write_sorted_nt(g, path):
    """Ghi N-Triples theo thứ tự dòng cố định (chạy lại cho ra đúng file cũ)."""
    lines = sorted(l for l in g.serialize(format="nt").splitlines() if l.strip())
    Path(path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transform-output", default=str(ROOT / "transform" / "output"))
    ap.add_argument("--ontology-dir", default=str(ROOT / "ontology"))
    ap.add_argument("--out", default=str(HERE / "output" / "inferred.nt"))
    args = ap.parse_args()

    odir, tdir = Path(args.ontology_dir), Path(args.transform_output)
    dbo = odir / "dbo-patched.ttl"
    if not dbo.exists():
        raise SystemExit(f"Thiếu {dbo}: chạy ontology/prepare_dbo.py trước. "
                         "(Không dùng bản gốc: lỗi dbo:sourceCountry sẽ suy ra mọi thứ là dòng sông.)")
    g = Graph()
    g.parse(odir / "vio-ontology.ttl")
    g.parse(dbo)
    for n in ("instance-types", "mappingbased-literals", "mappingbased-objects"):
        g.parse(tdir / f"{n}.nt")
    asserted = set(g)
    print(f"Trước suy diễn: {len(g):,} triple (ontology + dữ liệu)")

    t = time.time()
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(g)
    print(f"Sau suy diễn: {len(g):,} triple ({time.time() - t:.0f}s)")

    # Kiểm tra mâu thuẫn SAU suy diễn: một thực thể có hai kiểu loại trừ nhau?
    # (check_quality.py ở bước 3 chỉ xét kiểu ghi trực tiếp; nhiều lỗi chỉ lộ ra sau suy diễn)
    disjoint = {frozenset(p) for p in g.subject_objects(OWL.disjointWith)}
    for ad in g.subjects(RDF.type, OWL.AllDisjointClasses):
        for a, b in combinations(list(Collection(g, g.value(ad, OWL.members))), 2):
            disjoint.add(frozenset((a, b)))
    types = {}
    for s, c in g.subject_objects(RDF.type):
        if str(s).startswith(RESOURCE_NS):
            types.setdefault(s, set()).add(c)
    conflicts = [(s, sorted(p, key=str)) for s, cs in types.items() for p in disjoint if p <= cs]
    rep = HERE / "reports"
    rep.mkdir(exist_ok=True)
    lines = ["# Mâu thuẫn sau suy diễn", "", f"Số mâu thuẫn: **{len(conflicts)}**", ""]
    lines += [f"- `{s}`: vừa là `{a}` vừa là `{b}`" for s, (a, b) in conflicts]
    (rep / "inconsistencies.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if conflicts:
        print(f"[!] {len(conflicts)} mâu thuẫn sau suy diễn, xem reports/inconsistencies.md")
        for s, (a, b) in conflicts[:5]:
            print(f"    {s.split('/')[-1]}: {a.split('/')[-1]} ⊥ {b.split('/')[-1]}")
    else:
        print("Không có mâu thuẫn sau suy diễn.")

    # Giữ triple mới về tài nguyên của ta, bỏ các triple vô ích
    inferred = Graph()
    for s, p, o in g:
        if (s, p, o) in asserted or not str(s).startswith(RESOURCE_NS):
            continue
        if isinstance(o, BNode) or o == OWL.Thing or (p == OWL.sameAs and s == o):
            continue
        inferred.add((s, p, o))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_sorted_nt(inferred, out)

    types = sum(1 for _ in inferred.triples((None, RDF.type, None)))
    print(f"Ghi {len(inferred):,} triple suy ra vào {out} ({types:,} kiểu, {len(inferred) - types:,} quan hệ/thuộc tính)")


if __name__ == "__main__":
    main()