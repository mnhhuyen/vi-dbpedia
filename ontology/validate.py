"""
Kiểm tra ontology vio: (bước 1 của project DBpedia tiếng Việt).

  1. Cú pháp: các file Turtle parse được.
  2. Tham chiếu: mọi IRI dbo: được dùng đều tồn tại trong DBpedia Ontology.
  3. Nhãn: mọi lớp/thuộc tính vio: có rdfs:label @vi và @en.
  4. Suy luận (HermiT): ontology nhất quán với dữ liệu mẫu, và các suy luận mong đợi xảy ra.
  5. Phát hiện lỗi: các tình huống dữ liệu sai bị reasoner phát hiện là mâu thuẫn.

Cách chạy:
    pip install rdflib owlready2
    python validate.py --dbo ontology--DEV_type_orig.owl
(owlready2 cần Java để chạy HermiT.)
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

from rdflib import Graph, Namespace, URIRef, RDF, RDFS, OWL

from prepare_dbo import fix_dul_equivalences, strip_non_owl2_datatypes

HERE = Path(__file__).parent
VIO = Namespace("https://w3id.org/vi-dbpedia/ontology/")
VIR = Namespace("https://w3id.org/vi-dbpedia/resource/")
DBO = Namespace("http://dbpedia.org/ontology/")
DBR = Namespace("http://dbpedia.org/resource/")

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def load(*paths, fmt=None):
    g = Graph()
    for p in paths:
        g.parse(str(p), format=fmt)
    return g


# ---------------------------------------------------------------- 1-3
def static_checks(dbo):
    print("\n1. Cú pháp")
    vio = load(HERE / "vio-ontology.ttl")
    labels = load(HERE / "dbo-vi-labels.ttl")
    check("vio-ontology.ttl parse được", True, f"{len(vio)} triple")
    check("dbo-vi-labels.ttl parse được", True, f"{len(labels)} triple")

    print("\n2. Tham chiếu tới DBpedia Ontology")
    dbo_terms = set(dbo.subjects())
    used = {t for g in (vio, labels) for t in g.all_nodes()
            if isinstance(t, URIRef) and str(t).startswith(str(DBO))}
    missing = sorted(str(t) for t in used if t not in dbo_terms)
    check(f"{len(used)} IRI dbo: được dùng đều tồn tại", not missing,
          ", ".join(missing))

    print("\n3. Nhãn song ngữ")
    terms = {s for s in vio.subjects(RDF.type, None)
             if isinstance(s, URIRef) and str(s).startswith(str(VIO)) and s != URIRef(str(VIO))}
    for lang in ("vi", "en"):
        lacking = sorted(str(t).split("/")[-1] for t in terms
                         if not any(l.language == lang for l in vio.objects(t, RDFS.label)))
        check(f"{len(terms)} thuật ngữ vio: đều có nhãn @{lang}", not lacking, ", ".join(lacking))
    no_vi = [t for t in used if not any(l.language == "vi" for l in labels.objects(t, RDFS.label))
             and (t, RDF.type, OWL.Class) in dbo]
    check("mọi lớp dbo: được tham chiếu đều có nhãn @vi", not no_vi,
          ", ".join(str(t).split("/")[-1] for t in no_vi))
    return vio, labels


# ---------------------------------------------------------------- 4-5
def reason(dbo, vio, extra_ttl=""):
    """Gộp dbo + vio + dữ liệu, chạy HermiT. Trả về (consistent, world)."""
    import owlready2
    g = Graph()
    g += dbo
    g += vio
    g.parse(HERE / "tests" / "sample-abox.ttl")
    if extra_ttl:
        g.parse(data=PREFIXES + extra_ttl, format="turtle")
    g.remove((None, OWL.imports, None))  # đã gộp thủ công, không tải qua mạng
    # HermiT không nhận rdf:langString làm range. Language-tagged literals vẫn
    # giữ nguyên trong dữ liệu; chỉ bỏ range khỏi bản ontology dùng cho reasoner.
    strip_non_owl2_datatypes(g)
    fd, path = tempfile.mkstemp(suffix=".nt")
    os.close(fd)
    g.serialize(path, format="nt")
    world = owlready2.World()
    world.get_ontology("file://" + path).load()
    try:
        with world.get_ontology("http://test/inferred"):
            owlready2.sync_reasoner_hermit(world, infer_property_values=True, debug=0)
        return True, world
    except owlready2.OwlReadyInconsistentOntologyError:
        return False, world
    finally:
        os.remove(path)


PREFIXES = """
@prefix vio: <https://w3id.org/vi-dbpedia/ontology/> .
@prefix vir: <https://w3id.org/vi-dbpedia/resource/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
"""


def holds(world, s, p, o):
    """Kiểm tra triple (kể cả đã suy luận) trong world của owlready2."""
    # owlready2 chỉ lưu kiểu cụ thể nhất và giá trị của thuộc tính hẹp nhất,
    # nên phải hỏi các giá trị "gián tiếp" (theo cây lớp / cây thuộc tính).
    ind = world[str(s)]
    if p == RDF.type:
        return world[str(o)] in ind.INDIRECT_is_a
    values = world[str(p)]._get_indirect_values_for_individual(ind)
    return any(getattr(v, "iri", None) == str(o) for v in values)


def reasoning_checks(dbo_raw, vio):
    print("\n4. Suy luận trên dữ liệu mẫu (HermiT)")
    # Bản DBpedia Ontology chỉ bỏ kiểu dữ liệu ngoài OWL 2 (để HermiT chạy được),
    # CHƯA vá lỗi equivalentProperty -> phải mâu thuẫn, chứng minh lỗi là có thật.
    unpatched = Graph(); unpatched += dbo_raw
    strip_non_owl2_datatypes(unpatched)
    ok, _ = reason(unpatched, vio)
    check("với dbo GỐC chưa vá: dữ liệu mẫu bị mâu thuẫn (tái hiện lỗi của DBpedia)", not ok)

    dbo = Graph(); dbo += dbo_raw
    fix_dul_equivalences(dbo)
    strip_non_owl2_datatypes(dbo)
    ok, w = reason(dbo, vio)
    check("ontology + dữ liệu mẫu nhất quán", ok)
    if not ok:
        return
    uet, hn = VIR["Trường_Đại_học_Công_nghệ_ĐHQGHN"], VIR["Hà_Nội"]
    expectations = [
        ("thuocDonViHanhChinh bắc cầu: Dịch Vọng Hậu thuộc Hà Nội",
         VIR["Dịch_Vọng_Hậu"], VIO.thuocDonViHanhChinh, hn),
        ("property chain: trường có trụ sở tại Hà Nội",
         uet, VIO.truSoTai, hn),
        ("subPropertyOf: trụ sở tại => dbo:location",
         uet, DBO.location, VIR["Dịch_Vọng_Hậu"]),
        ("owl:hasValue: Hà Nội dbo:country dbr:Vietnam",
         hn, DBO.country, DBR.Vietnam),
        ("owl:inverseOf: ĐHQGHN có thành viên là trường",
         VIR["Đại_học_Quốc_gia_Hà_Nội"], VIO.coThanhVien, uet),
        ("neo vào dbo: Hà Nội là dbo:City",
         hn, RDF.type, DBO.City),
        ("neo vào dbo: trường là dbo:University",
         uet, RDF.type, DBO.University),
        ("neo vào dbo: Cầu Giấy là dbo:District",
         VIR["Cầu_Giấy"], RDF.type, DBO.District),
    ]
    for name, s, p, o in expectations:
        check(name, holds(w, s, p, o))

    print("\n5. Phát hiện dữ liệu sai")
    bad_cases = [
        ("một đơn vị vừa là tỉnh vừa là phường (AllDisjointClasses)",
         "vir:Cầu_Giấy a vio:Tinh .", False),
        ("một trường vừa là tổ chức vừa là đơn vị hành chính (dbo:Agent ⊥ dbo:Place)",
         "vir:Trường_Đại_học_Công_nghệ_ĐHQGHN a vio:Phuong .", False),
        ("trường thuộc 2 đại học KHÔNG được khai báo khác nhau "
         "-> vẫn nhất quán, reasoner suy ra owl:sameAs (không có Unique Name Assumption)",
         "vir:Trường_Đại_học_Công_nghệ_ĐHQGHN vio:laThanhVienCua vir:ĐHQG_X .", True),
        ("trường thuộc 2 đại học đã khai báo khác nhau (FunctionalProperty)",
         "vir:Trường_Đại_học_Công_nghệ_ĐHQGHN vio:laThanhVienCua vir:ĐHQG_X .\n"
         "vir:ĐHQG_X owl:differentFrom vir:Đại_học_Quốc_gia_Hà_Nội .", False),
    ]
    for name, ttl, expect_consistent in bad_cases:
        consistent, _ = reason(dbo, vio, ttl)
        verdict = "nhất quán" if consistent else "mâu thuẫn"
        check(name, consistent == expect_consistent, f"reasoner: {verdict}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dbo", required=True, help="đường dẫn tới ontology--DEV_type_orig.owl")
    ap.add_argument("--no-reasoner", action="store_true", help="bỏ qua bước 4-5 (không cần Java)")
    args = ap.parse_args()

    print("Đang nạp DBpedia Ontology...")
    dbo = load(args.dbo, fmt="xml")
    vio, _ = static_checks(dbo)
    if not args.no_reasoner:
        reasoning_checks(dbo, vio)

    passed = sum(results)
    print(f"\nKết quả: {passed}/{len(results)} kiểm tra đạt")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
