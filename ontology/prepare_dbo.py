"""
Chuẩn bị DBpedia Ontology để dùng trong project.

Bản gốc (ontology--DEV_type_orig.owl) có hai loại vấn đề:

(1) LỖI MÔ HÌNH: ba thuộc tính dbo: được khai báo owl:equivalentProperty với
    các thuộc tính tổng quát của DOLCE+DUL. Vì hàng trăm thuộc tính dbo: là
    sub-property của các thuộc tính DUL này, các khai báo domain/range hẹp
    "lan" lên toàn bộ ontology (luật rdfs7 + rdfs2/rdfs3):

    - dbo:sourceCountry ≡ dul:hasLocation, domain dbo:Stream, range dbo:Country
        => mọi thứ có dbo:location / dbo:country / dbo:birthPlace... bị suy ra
           là SÔNG, và mọi địa điểm bị suy ra là QUỐC GIA.
    - dbo:firstPopularVote ≡ dul:sameSettingAs, range dbo:Person
        => đối tượng của dbo:successor / dbo:predecessor / dbo:parentOrganisation...
           bị suy ra là NGƯỜI.
    - dbo:simcCode ≡ dul:isClassifiedBy, domain dbo:PopulatedPlace
        => mọi thứ có dbo:type bị suy ra là NƠI CÓ DÂN CƯ.

    Kết hợp với dbo:Agent owl:disjointWith dbo:Place, mọi tổ chức có vị trí
    đều trở thành mâu thuẫn. File output loại bỏ ba tiên đề này.

(1b) LIÊN KẾT TƯƠNG ĐƯƠNG MƠ HỒ: nhiều thuộc tính/lớp dbo: khác nhau cùng được khai báo
    owl:equivalentProperty / owl:equivalentClass với MỘT thuật ngữ bên ngoài (thường là
    Wikidata). Vì "tương đương" có tính bắc cầu, các thuật ngữ dbo: đó bị suy ra là tương
    đương NHAU. Ví dụ:
      dbo:foundingDate ≡ wikidata:P571 ≡ dbo:formationDate (domain dbo:Organisation)
        => mọi tỉnh có ngày thành lập bị suy ra là TỔ CHỨC, mâu thuẫn với dbo:Agent ⊥ dbo:Place.
      dbo:foundingYear ≡ bag:oorspronkelijkBouwjaar ≡ dbo:yearOfConstruction (domain dbo:Place)
        => mọi trường đại học có năm thành lập bị suy ra là ĐỊA ĐIỂM.
    File output bỏ các liên kết tới những thuật ngữ bên ngoài bị dùng chung như vậy.

(2) KIỂU DỮ LIỆU NGOÀI OWL 2: nhiều datatype property có range là kiểu riêng
    của DBpedia (dbt:hour, dbt:kilometre...) hoặc xsd:date, xsd:gYear,
    rdf:langString. Các reasoner OWL 2 DL như HermiT từ chối chạy.
    Chỉ bản "-dl" bỏ các range này; bản thường giữ nguyên.

Output:
    dbo-patched.ttl     sửa (1). Dùng để nạp vào triple store (bước 5).
    dbo-patched-dl.ttl  sửa (1) + (2). Dùng cho reasoner (Protégé + HermiT, validate.py).

Cách chạy:
    python prepare_dbo.py ontology--DEV_type_orig.owl
"""
import sys
from pathlib import Path

from rdflib import Graph, URIRef, RDF, RDFS, OWL

HERE = Path(__file__).parent
DUL = "http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#"
DBO = "http://dbpedia.org/ontology/"
XSD = "http://www.w3.org/2001/XMLSchema#"

OWL2_DATATYPES = {URIRef(XSD + n) for n in (
    "decimal integer nonNegativeInteger nonPositiveInteger positiveInteger negativeInteger "
    "long int short byte unsignedLong unsignedInt unsignedShort unsignedByte double float "
    "string normalizedString token language Name NCName NMTOKEN boolean hexBinary "
    "base64Binary anyURI dateTime dateTimeStamp").split()} | {
    RDFS.Literal, OWL.real, OWL.rational,
    URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#PlainLiteral"),
    URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#XMLLiteral")}


def fix_dul_equivalences(g):
    """Bỏ mọi owl:equivalentProperty giữa một thuộc tính dbo: và một thuộc tính DUL."""
    bad = [(s, o) for s, o in g.subject_objects(OWL.equivalentProperty)
           if (str(s).startswith(DBO) and str(o).startswith(DUL))
           or (str(s).startswith(DUL) and str(o).startswith(DBO))]
    for s, o in bad:
        g.remove((s, OWL.equivalentProperty, o))
    return bad


def fix_shared_external_equivalences(g):
    """Bỏ owl:equivalentProperty/equivalentClass giữa thuật ngữ dbo: và một thuật ngữ bên ngoài
    khi thuật ngữ bên ngoài đó được nối với từ 2 thuật ngữ dbo: trở lên."""
    removed = []
    for pred in (OWL.equivalentProperty, OWL.equivalentClass):
        links = {}
        for s, o in g.subject_objects(pred):
            if str(s).startswith(DBO) and not str(o).startswith(DBO):
                links.setdefault(o, []).append((s, o))
            elif str(o).startswith(DBO) and not str(s).startswith(DBO):
                links.setdefault(s, []).append((s, o))
        for ext, pairs in links.items():
            dbo_terms = {a if str(a).startswith(DBO) else b for a, b in pairs}
            if len(dbo_terms) > 1:
                for a, b in pairs:
                    g.remove((a, pred, b))
                    removed.append((a, pred, b))
    return removed


def strip_non_owl2_datatypes(g):
    """Bỏ rdfs:range của datatype property khi range không thuộc OWL 2 datatype map."""
    bad = [(p, d) for p, d in g.subject_objects(RDFS.range)
           if (p, RDF.type, OWL.DatatypeProperty) in g and d not in OWL2_DATATYPES]
    for p, d in bad:
        g.remove((p, RDFS.range, d))
    return bad


def main(src):
    g = Graph()
    g.parse(src, format="xml")
    n0 = len(g)

    removed = fix_dul_equivalences(g)
    print(f"Đã bỏ {len(removed)} tiên đề owl:equivalentProperty lỗi:")
    for s, o in removed:
        print(f"  - {s.n3(g.namespace_manager)} ≡ {o.n3(g.namespace_manager)}")
    shared = fix_shared_external_equivalences(g)
    print(f"\nĐã bỏ {len(shared)} liên kết tương đương tới thuật ngữ bên ngoài bị dùng chung, ví dụ:")
    for a, p, b in shared[:6]:
        print(f"  - {a.n3(g.namespace_manager)} {p.n3(g.namespace_manager)} {b.n3(g.namespace_manager)}")
    g.serialize(HERE / "dbo-patched.ttl", format="turtle")
    print(f"=> dbo-patched.ttl ({len(g)} triple, gốc {n0})")

    stripped = strip_non_owl2_datatypes(g)
    print(f"\nĐã bỏ {len(stripped)} rdfs:range dùng kiểu dữ liệu ngoài OWL 2")
    g.serialize(HERE / "dbo-patched-dl.ttl", format="turtle")
    print(f"=> dbo-patched-dl.ttl ({len(g)} triple)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Cách dùng: python prepare_dbo.py <ontology--DEV_type_orig.owl>")
    main(sys.argv[1])