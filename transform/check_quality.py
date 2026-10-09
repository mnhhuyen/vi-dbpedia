"""
Kiểm tra chất lượng dữ liệu RDF sinh ra ở bước 3, dựa trên các tiên đề của ontology:

  1. Loại trừ (owl:disjointWith, owl:AllDisjointClasses): một thực thể không được thuộc
     hai lớp loại trừ nhau (tính cả lớp cha suy ra theo rdfs:subClassOf).
  2. Functional (owl:FunctionalProperty): một thực thể không được có hai giá trị khác nhau.
  3. Kiểu literal: giá trị phải đúng kiểu dữ liệu khai báo (ví dụ xsd:date hợp lệ).

Đây là kiểm tra nhanh, không thay thế reasoner đầy đủ (HermiT), nhưng chạy được
trên toàn bộ dữ liệu trong vài giây và chỉ ra chính xác thực thể nào có vấn đề.

Cách chạy:
    python check_quality.py
"""
import argparse
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from rdflib import Graph, URIRef, Literal
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS

HERE = Path(__file__).parent
XSD = "http://www.w3.org/2001/XMLSchema#"
# Các kiểu rdflib kiểm tra được giá trị (gYear... rdflib không chuyển đổi nên bỏ qua)
CHECKED_TYPES = {URIRef(XSD + t) for t in ("date", "integer", "nonNegativeInteger", "double", "float")}


def short(u):
    s = str(u)
    for p, ns in (("vio:", "https://w3id.org/vi-dbpedia/ontology/"), ("dbo:", "http://dbpedia.org/ontology/"),
                  ("vir:", "https://w3id.org/vi-dbpedia/resource/")):
        if s.startswith(ns):
            return p + s[len(ns):]
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "output"))
    ap.add_argument("--ontology-dir", default=str(HERE.parent / "ontology"))
    args = ap.parse_args()

    onto = Graph()
    odir = Path(args.ontology_dir)
    onto.parse(odir / "vio-ontology.ttl")
    dbo_file = odir / "dbo-patched.ttl"
    if dbo_file.exists():
        onto.parse(dbo_file)
    else:
        print(f"[!] Không thấy {dbo_file}: chỉ kiểm tra theo ontology vio:")

    data = Graph()
    for n in ("instance-types", "mappingbased-literals", "mappingbased-objects"):
        data.parse(Path(args.data) / f"{n}.nt")

    def supers(c, memo={}):
        if c not in memo:
            seen, stack = {c}, [c]
            while stack:
                for p in onto.objects(stack.pop(), RDFS.subClassOf):
                    if isinstance(p, URIRef) and p not in seen:
                        seen.add(p); stack.append(p)
            memo[c] = seen
        return memo[c]

    disjoint = set()
    for a, b in onto.subject_objects(OWL.disjointWith):
        disjoint.add(frozenset((a, b)))
    for ad in onto.subjects(RDF.type, OWL.AllDisjointClasses):
        for a, b in combinations(list(Collection(onto, onto.value(ad, OWL.members))), 2):
            disjoint.add(frozenset((a, b)))
    functional = set(onto.subjects(RDF.type, OWL.FunctionalProperty))

    problems = []
    types = defaultdict(set)
    for s, c in data.subject_objects(RDF.type):
        types[s] |= supers(c)
    for s, cs in types.items():
        for pair in disjoint:
            if pair <= cs:
                a, b = sorted(pair, key=str)
                problems.append(("loại trừ", s, f"vừa là {short(a)} vừa là {short(b)}"))
    for p in functional:
        vals = defaultdict(set)
        for s, o in data.subject_objects(p):
            vals[s].add(o)
        for s, os_ in vals.items():
            if len(os_) > 1:
                problems.append(("functional", s, f"{short(p)} có {len(os_)} giá trị: "
                                 + ", ".join(sorted(short(o) for o in os_))))
    for s, p, o in data:
        if isinstance(o, Literal) and o.datatype in CHECKED_TYPES and o.value is None:
            problems.append(("kiểu dữ liệu", s, f"{short(p)} = '{o}' không hợp lệ với {short(o.datatype)}"))

    print(f"Đã kiểm tra {len(types)} thực thể, {len(data)} triple, "
          f"{len(disjoint)} cặp lớp loại trừ, {len(functional)} thuộc tính functional.")
    if not problems:
        print("Không phát hiện vi phạm.")
    for kind, s, msg in sorted(problems, key=lambda x: (x[0], str(x[1]))):
        print(f"  [{kind}] {short(s)}: {msg}")

    rep = HERE / "reports"
    rep.mkdir(exist_ok=True)
    lines = ["# Kiểm tra chất lượng dữ liệu", "",
             f"Thực thể: {len(types)} · Triple: {len(data)} · Vi phạm: **{len(problems)}**", ""]
    if problems:
        lines += ["| Loại | Thực thể | Chi tiết |", "|---|---|---|",
                  *[f"| {k} | `{short(s)}` | {m} |" for k, s, m in problems]]
    (rep / "quality_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
