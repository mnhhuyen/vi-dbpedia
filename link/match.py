"""
Bước 4 (phần 3) — So khớp thực thể với DBpedia tiếng Anh theo nội dung (kiểu Silk), có đánh giá.

link.py sinh owl:sameAs từ liên kết liên ngôn ngữ (interlanguage link) của Wikipedia — chính xác
nhưng là "tra bảng", không phải so khớp. Script này làm đúng việc của Silk Link Discovery
Framework: không dùng liên kết liên ngôn ngữ, chỉ so sánh nội dung hai bên, rồi dùng liên kết
liên ngôn ngữ làm đáp án (ground truth) để đo precision / recall / F1.

Luật liên kết (link/silk/linkspec.xml là bản rút gọn cho Silk):
  Chặn (blocking):  chỉ so tỉnh/thành với tỉnh/thành, trường với trường.
  So sánh:
    name      nhãn hai bên sau khi bỏ dấu, chữ thường, bỏ từ chung ("tỉnh", "province", "university"...):
              max(Levenshtein chuẩn hoá, Jaccard theo từ, trùng khi bỏ dấu cách). Tên trường tiếng Việt
              còn được dịch thuật ngữ sang tiếng Anh (GLOSSARY: "sư phạm" -> "education"...).
              Trọng số theo loại tên: tên bài 1.0, tên chuyển hướng 0.9, tên cũ/viết tắt 0.8, tên trường
              bỏ phần sau dấu phẩy 0.9, tên chỉ còn địa danh 0.9; hai tên trường nhắc tới hai địa danh
              khác nhau (Hà Nội vs TP.HCM) -> × 0.7.
    type      tỉnh khớp bài về tỉnh, không khớp thành phố tỉnh lỵ cùng tên (dbr:Bạc_Liêu)
    homepage  trùng tên miền -> 1; khác nhau -> bỏ qua (trường hay đổi tên miền: chỉ là bằng chứng dương)
    geo       khoảng cách: 1 nếu ≤ 2 km (trường) / 15 km (tỉnh), giảm tuyến tính về 0 ở 10× ngưỡng
    year      năm thành lập (chỉ với trường): 1 nếu lệch ≤ 1 năm, 0.5 nếu ≤ 3, ngược lại 0
  Gộp:       trung bình có trọng số các phép so sánh có giá trị (name 0.6, type 0.2, homepage 0.25,
             geo 0.1, year 0.05); thiếu dữ liệu -> bỏ khỏi trung bình. Homepage trùng: score ≥ 0.9.
  Lọc:       mỗi thực thể giữ tối đa 1 đích và mỗi đích tối đa 1 nguồn (ghép 1-1 tham lam theo điểm).
  Liên kết mới (thực thể không có đáp án) chỉ vào bộ cuối cùng khi name ≥ 0.95 và có thêm một bằng
  chứng độc lập (type / homepage / geo / year) — xem confident().

Không dùng phía DBpedia: rdfs:label@vi và owl:sameAs — hai thứ này sinh từ chính liên kết liên
ngôn ngữ, dùng sẽ là "lộ đáp án".

Đầu ra:
  cache/dbpedia_candidates.json         ứng viên đã tải (chạy lại không cần mạng; xoá để tải lại)
  output/sameas-dbpedia.matched.nt      liên kết do bộ so khớp sinh ra (ngưỡng --threshold)
  output/sameas-dbpedia.final.nt        liên kết dùng ở bước 5: interlanguage đã kiểm tra
                                        + liên kết mới do so khớp tìm được cho thực thể chưa có
  reports/match_evaluation.md           precision / recall / F1 theo ngưỡng, theo lớp, các lỗi
  reports/new_links_review.csv          liên kết mới (không có đáp án) để chấm tay

Cách chạy:
    python match.py                  # lần đầu cần mạng (tải ứng viên)
    python match.py --threshold 0.8
    python match.py --refresh        # tải lại ứng viên
"""
import argparse
import csv
import datetime as dt
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote, urlparse

from rdflib import Graph, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "transform"))
from validate_links import sparql_http, short  # noqa: E402
from transform import write_sorted_nt  # noqa: E402

DBO = "http://dbpedia.org/ontology/"
DBR = "http://dbpedia.org/resource/"
VIO = "https://w3id.org/vi-dbpedia/ontology/"
GEO = "http://www.w3.org/2003/01/geo/wgs84_pos#"

# Lớp của ta -> nhóm chặn (blocking)
BLOCK = {VIO + c: "place" for c in ("Tinh", "ThanhPhoTrucThuocTrungUong")}
BLOCK.update({VIO + c: "univ" for c in ("TruongDaiHoc", "HocVien", "DaiHoc", "DaiHocQuocGia", "DaiHocVung")})

# Lớp của ta -> loại đích mong đợi (phép so sánh "type"): tỉnh khớp bài về tỉnh, không khớp bài về
# thành phố tỉnh lỵ cùng tên (dbr:Bạc_Liêu_province chứ không phải dbr:Bạc_Liêu)
# Thành phố trực thuộc trung ương là đơn vị cấp tỉnh: bên tiếng Anh có thể là bài về thành phố
# (dbr:Hanoi) hoặc về tỉnh (dbr:Quảng_Ninh_province — Quảng Ninh mới lên thành phố năm 2026).
EXPECTED_KIND = {VIO + "Tinh": {"province"}, VIO + "ThanhPhoTrucThuocTrungUong": {"city", "province"}}

# Tập ứng viên bên DBpedia tiếng Anh: (nhóm chặn, loại, điều kiện SPARQL)
CANDIDATE_QUERIES = [
    ("place", "province", """
      { ?u dct:subject dbc:Provinces_of_Vietnam } UNION { ?u dct:subject dbc:Former_provinces_of_Vietnam }
      UNION { ?u dbo:type dbr:Provinces_of_Vietnam }
      UNION { ?u dct:subject dbc:Provinces_of_South_Vietnam } UNION { ?u dct:subject dbc:Provinces_of_French_Indochina }
      UNION { ?u dct:subject ?c . ?c skos:broader dbc:Provinces_of_Vietnam      # bài chính của thể loại cùng tên
              FILTER(STRAFTER(STR(?c), "Category:") = STRAFTER(STR(?u), "resource/")) }
    """),
    ("place", "city", """
      { ?u dct:subject dbc:Municipalities_of_Vietnam } UNION { ?u dct:subject dbc:Cities_in_Vietnam }
    """),
    ("univ", "univ", """
      { ?u dct:subject/skos:broader{0,3} dbc:Universities_and_colleges_in_Vietnam }
      UNION { ?u dct:subject/skos:broader{0,2} dbc:Universities_in_Vietnam }
      UNION { ?u a dbo:EducationalInstitution ; dbo:country dbr:Vietnam }
      UNION { ?u a dbo:EducationalInstitution ; dbo:city|dbo:state|dbo:location ?c . ?c dbo:country dbr:Vietnam }
    """),
]
# Tên chính / tên phụ (tên cũ, viết tắt): tên phụ chỉ được tính tối đa SECONDARY_WEIGHT,
# để "Bà Rịa – Vũng Tàu" (tên cũ: Phước Tuy) không khớp ngang bằng với dbr:Phước_Tuy_province
NAME_PROPS = ["rdfs:label", "foaf:name", "dbp:name", "dbp:nativeName"]
ALT_NAME_PROPS = ["dbo:formerName", "dbp:formerNames", "dbp:formerName", "dbp:acronym", "dbo:abbreviation"]
SECONDARY_WEIGHT = 0.8
REDIRECT_WEIGHT = 0.9     # tên trang chuyển hướng: "Gia Định" chuyển hướng tới dbr:Ho_Chi_Minh_City
STRIPPED_WEIGHT = 0.9     # tên trường đã bỏ phần sau dấu phẩy
PLACE_CONFLICT = 0.7      # hai tên trường nhắc tới hai địa danh khác nhau (Hà Nội vs TP.HCM)
PLACE_ONLY_WEIGHT = 0.9   # tên trường chỉ còn lại địa danh sau khi bỏ từ chung

# Liên kết MỚI (thực thể không có liên kết liên ngôn ngữ) chỉ vào bộ cuối cùng khi tên gần như trùng
# VÀ có thêm ít nhất một bằng chứng độc lập: nhóm này thường không có bài tiếng Anh, bộ so khớp dễ
# chọn nhầm "ứng viên gần nhất" (xem reports/match_evaluation.md).
NEW_LINK_MIN_NAME = 0.95
CORROBORATING = ("type", "homepage", "geo", "year")


def confident(sims):
    return sims["name"] >= NEW_LINK_MIN_NAME and any(sims.get(k) == 1.0 for k in CORROBORATING)
PREFIX_IRI = {"dbo": DBO, "dbp": "http://dbpedia.org/property/", "foaf": "http://xmlns.com/foaf/0.1/",
              "rdfs": "http://www.w3.org/2000/01/rdf-schema#"}
PREFIXES = """PREFIX dbo: <http://dbpedia.org/ontology/> PREFIX dbp: <http://dbpedia.org/property/>
PREFIX dbr: <http://dbpedia.org/resource/> PREFIX dbc: <http://dbpedia.org/resource/Category:>
PREFIX dct: <http://purl.org/dc/terms/> PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>"""

WEIGHTS = {"name": 0.6, "type": 0.2, "homepage": 0.25, "geo": 0.1, "year": 0.05}
GEO_OK_KM = {"univ": 2.0, "place": 15.0}


# ---------------------------------------------------------------------------
# Chuẩn hoá chuỗi
# ---------------------------------------------------------------------------
GENERIC = {
    "place": r"\b(tinh|thanh pho|tp|province|city|municipality|of|vietnam|viet nam)\b",
    # bỏ cả từ chỉ loại trường: "X University" và "Y University" không được giống nhau chỉ vì chữ "University"
    "univ": r"\b(the|of|in|and|va|truong|dai hoc|hoc vien|university|academy|institute|college|school|"
            r"vietnam|viet nam)\b",
}

# Bảng dịch thuật ngữ Việt -> Anh cho tên trường (sau khi bỏ dấu), cụm dài trước.
# Tương đương một chuỗi phép biến đổi "replace" trong Silk.
GLOSSARY = [
    ("thanh pho ho chi minh", "ho chi minh city"), ("ha noi", "hanoi"), ("tp hcm", "ho chi minh city"),
    ("dai hoc quoc gia", "vnu national"), ("quoc gia", "national"), ("quoc te", "international"),
    ("su pham ky thuat", "technology education"), ("su pham", "education"),
    ("bach khoa", "science technology"), ("khoa hoc tu nhien", "natural sciences"),
    ("khoa hoc xa hoi va nhan van", "social sciences humanities"), ("kinh te quoc dan", "national economics"),
    ("kinh te", "economics"), ("luat", "law"), ("y duoc", "medicine pharmacy"), ("y te cong cong", "public health"),
    ("duoc", "pharmacy"), ("ngoai ngu", "foreign languages"), ("ngoai thuong", "foreign trade"),
    ("thuong mai", "commerce"), ("xay dung", "civil engineering"), ("kien truc", "architecture"),
    ("giao thong van tai", "transport"), ("hang hai", "maritime"), ("thuy loi", "water resources thuyloi"),
    ("nong lam", "agriculture forestry"), ("nong nghiep", "agriculture"), ("lam nghiep", "forestry"),
    ("tai nguyen va moi truong", "natural resources environment"), ("the duc the thao", "sport"),
    ("san khau dien anh", "theatre cinema"), ("my thuat", "fine arts"), ("am nhac", "music"),
    ("van hoa", "culture"), ("ngan hang", "banking"), ("tai chinh", "finance"), ("marketing", "marketing"),
    ("cong nghe thong tin", "information technology"), ("cong nghiep", "industry"), ("cong nghe", "technology"),
    ("khoa hoc", "science"), ("buu chinh vien thong", "posts telecommunications"), ("mo dia chat", "mining geology"),
    ("dien luc", "electric power"), ("ngoai giao", "diplomatic"), ("bao chi va tuyen truyen", "journalism communication"),
    ("chinh tri", "politics"), ("hanh chinh", "administration"), ("an ninh", "security"), ("canh sat", "police"),
    ("quan y", "military medical"), ("ky thuat", "technical engineering"), ("mo", "open"), ("y", "medical"),
    ("viet duc", "vietnamese german"), ("viet nhat", "vietnam japan"), ("viet phap", "vietnam france"),
]
_GLOSS_RE = [(re.compile(rf"\b{vi}\b"), en) for vi, en in GLOSSARY]


def translate(key):
    for rx, en in _GLOSS_RE:
        key = rx.sub(en, key)
    return re.sub(r"\s+", " ", key).strip()


def fold(s):
    """Bỏ dấu, đ -> d, chữ thường, bỏ phần trong ngoặc và dấu câu."""
    s = unicodedata.normalize("NFD", s.replace("Đ", "D").replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_key(s, block):
    k = re.sub(GENERIC[block], " ", fold(s))
    return re.sub(r"\s+", " ", k).strip()


def name_variants(s, block, vietnamese, weight=1.0):
    """{dạng so sánh: trọng số} của một tên. Tên trường còn có bản dịch thuật ngữ và bản bỏ phần
    sau dấu phẩy ('Trường Đại học Kinh tế, Đại học Quốc gia Hà Nội' -> 'Kinh tế', trọng số thấp hơn
    vì mất thông tin trường thuộc đại học nào)."""
    s = s.strip()
    # Tên nhiễu bên DBpedia: mảnh tên ("of Science and Technology"), mã số/DOI ("10.51316")
    if not s or s[0].islower() or re.fullmatch(r"[\d.\s/-]+", s):
        return {}
    heads = [(s, weight)] + ([(s.split(",")[0], weight * STRIPPED_WEIGHT)] if block == "univ" and "," in s else [])
    out = {}
    for h, w in heads:
        keys = [name_key(h, block)]
        if vietnamese and block == "univ":
            keys.append(name_key(translate(fold(h)), block))
        for k in keys:
            # tên trường chỉ còn địa danh ("Hanoi University" -> "hanoi") phân biệt kém
            kw = w * PLACE_ONLY_WEIGHT if block == "univ" and k in PLACES else w
            if k and kw > out.get(k, 0):
                out[k] = kw
    return out


def place_mentions(s):
    """Các địa danh (tỉnh/thành của ta) xuất hiện trong một tên trường, sau khi bỏ dấu và dịch."""
    t = f" {translate(fold(s))} "
    return {p for p in PLACES if f" {p} " in t}


PLACES = set()          # điền trong load_ours: tên các tỉnh/thành đã bỏ dấu (và dạng dịch: "hanoi")


def name_sim(a, b):
    if not a or not b:
        return 0.0
    if a.replace(" ", "") == b.replace(" ", ""):        # "ha noi" ~ "hanoi", "thuy loi" ~ "thuyloi"
        return 1.0
    lev = SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()), set(b.split())
    jac = len(ta & tb) / len(ta | tb)
    return max(lev, jac)


def domain(url):
    try:
        host = urlparse(url if "//" in url else "http://" + url).hostname or ""
    except ValueError:
        return ""
    return re.sub(r"^www\d?\.", "", host.lower())


def haversine_km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = (math.sin((la2 - la1) * p / 2) ** 2
         + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def year_of(v):
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", v or "")
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Hai bên dữ liệu
# ---------------------------------------------------------------------------
def load_ours(tout):
    g = Graph()
    for f in ("labels", "instance-types", "mappingbased-literals", "mappingbased-objects", "geo-coordinates"):
        g.parse(tout / f"{f}.nt")
    ents = {}
    for s, c in g.subject_objects(RDF.type):
        if str(c) not in BLOCK:
            continue
        block = BLOCK[str(c)]
        # (tên, có phải tiếng Việt): tên bài @vi và tên tiếng Anh @en từ infobox
        names = [(str(o), o.language != "en") for o in g.objects(s, RDFS.label)]
        alt = [(str(o), True) for p in ("abbreviation", "formerName") for o in g.objects(s, URIRef(DBO + p))]
        hp = {domain(str(o)) for o in g.objects(s, FOAF.homepage)} - {""}
        lat, lon = g.value(s, URIRef(GEO + "lat")), g.value(s, URIRef(GEO + "long"))
        year = None
        for p in ("foundingDate", "foundingYear"):
            year = year or year_of(str(g.value(s, URIRef(DBO + p)) or ""))
        ents[str(s)] = {"cls": str(c), "block": block, "names": names, "alt_names": alt, "homepage": hp,
                        "geo": (float(lat), float(lon)) if lat is not None and lon is not None else None,
                        "year": year}
    PLACES.clear()
    for e in ents.values():
        if e["block"] == "place":
            for n, _ in e["names"]:
                PLACES.update({name_key(n, "place"), name_key(translate(fold(n)), "place")} - {""})
    return ents


def fetch_candidates(cache, refresh=False):
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    cands = {}
    for block, kind, where in CANDIDATE_QUERIES:
        q = f"{PREFIXES} SELECT DISTINCT ?u WHERE {{ {where} FILTER NOT EXISTS {{ ?u dbo:wikiPageRedirects ?x }} }}"
        n = 0
        for b in sparql_http(q):
            u = b["u"]["value"]
            if u.startswith(DBR) and "Category:" not in u:
                c = cands.setdefault(u, {"block": block, "kinds": [], "names": [], "alt_names": [],
                                         "homepage": [], "geo": None, "years": []})
                c["kinds"].append(kind)
                n += 1
        print(f"  {block}/{kind}: {n} ứng viên")
    uris = list(cands)
    alt_iris = {PREFIX_IRI[p.split(":")[0]] + p.split(":")[1] for p in ALT_NAME_PROPS}
    for k in range(0, len(uris), 40):
        values = " ".join(f"<{u}>" for u in uris[k:k + 40])
        q = f"""{PREFIXES} SELECT ?u ?p ?n ?r ?hp ?lat ?long ?y WHERE {{ VALUES ?u {{ {values} }}
          {{ VALUES ?p {{ {" ".join(NAME_PROPS + ALT_NAME_PROPS)} }} ?u ?p ?n
             FILTER(isLiteral(?n) && (LANG(?n) = "en" || LANG(?n) = "")) }}
          UNION {{ ?r dbo:wikiPageRedirects ?u }}
          UNION {{ ?u foaf:homepage|dbp:website ?hp }}
          UNION {{ ?u geo:lat ?lat ; geo:long ?long }}
          UNION {{ ?u dbo:foundingYear|dbo:foundingDate|dbp:established ?y }} }}"""
        for b in sparql_http(q):
            c = cands[b["u"]["value"]]
            if "n" in b:
                c["alt_names" if b["p"]["value"] in alt_iris else "names"].append(b["n"]["value"])
            if "r" in b:
                c.setdefault("redirects", []).append(unquote(b["r"]["value"][len(DBR):]).replace("_", " "))
            if "hp" in b:
                c["homepage"].append(b["hp"]["value"])
            if "lat" in b:
                c["geo"] = [float(b["lat"]["value"]), float(b["long"]["value"])]
            if "y" in b:
                c["years"].append(b["y"]["value"])
        print(f"  đã tải chi tiết {min(k + 40, len(uris))}/{len(uris)}")
    for u, c in cands.items():
        c["names"] = sorted(set([unquote(u[len(DBR):]).replace("_", " ")] + c["names"]))
        c["redirects"] = sorted(set(c.get("redirects", [])) - set(c["names"]))
        c["alt_names"] = sorted(set(c["alt_names"]) - set(c["names"]) - set(c["redirects"]))
        c["homepage"] = sorted(set(c["homepage"]))
        c["years"] = sorted(set(c["years"]))
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps({"fetched": dt.date.today().isoformat(), "candidates": cands},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    return json.loads(cache.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Luật liên kết
# ---------------------------------------------------------------------------
def compare(e, c):
    block = e["block"]

    def variants(names, w):
        out = {}
        for n, vi in names:
            for k, x in name_variants(n, block, vi, w).items():
                out[k] = max(out.get(k, 0), x)
        return out

    ours = variants(e["names"], 1.0)
    for k, w in variants(e["alt_names"], SECONDARY_WEIGHT).items():
        ours.setdefault(k, w)
    theirs = variants([(n, False) for n in c["names"]], 1.0)
    for names, w in ((c.get("redirects", []), REDIRECT_WEIGHT), (c["alt_names"], SECONDARY_WEIGHT)):
        for k, x in variants([(n, False) for n in names], w).items():
            theirs.setdefault(k, x)
    name = max((name_sim(a, b) * wa * wb for a, wa in ours.items() for b, wb in theirs.items()), default=0.0)
    if block == "univ":
        mine = set().union(*[place_mentions(n) for n, _ in e["names"]])
        their = set().union(*[place_mentions(n) for n in c["names"]])
        if mine and their and not mine & their:
            name *= PLACE_CONFLICT
    sims = {"name": name}
    if e["cls"] in EXPECTED_KIND:
        sims["type"] = 1.0 if EXPECTED_KIND[e["cls"]] & set(c["kinds"]) else 0.0
    # Homepage chỉ là bằng chứng dương: trường hay đổi tên miền (nuce.edu.vn -> huce.edu.vn),
    # nên khác nhau không có nghĩa là hai thực thể khác nhau
    if e["homepage"] & ({domain(h) for h in c["homepage"]} - {""}):
        sims["homepage"] = 1.0
    if e["geo"] and c["geo"]:
        d, ok = haversine_km(e["geo"], c["geo"]), GEO_OK_KM[block]
        sims["geo"] = 1.0 if d <= ok else max(0.0, 1 - (d - ok) / (9 * ok))
    years = [y for y in (year_of(v) for v in c["years"]) if y]
    # Năm thành lập chỉ so với trường: "thành lập" của tỉnh là lần lập/tái lập gần nhất, không nhất quán
    if block == "univ" and e["year"] and years:
        diff = min(abs(e["year"] - y) for y in years)
        sims["year"] = 1.0 if diff <= 1 else (0.5 if diff <= 3 else 0.0)
    score = sum(WEIGHTS[k] * v for k, v in sims.items()) / sum(WEIGHTS[k] for k in sims)
    if sims.get("homepage") == 1.0:
        score = max(score, 0.9)
    return score, sims


def match(ours, cands):
    """Mọi cặp cùng nhóm -> ghép 1-1 tham lam theo điểm giảm dần."""
    scored = []
    for s, e in ours.items():
        for u, c in cands.items():
            if c["block"] == e["block"]:
                score, sims = compare(e, c)
                if score >= 0.3:
                    scored.append((score, s, u, sims))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    used_s, used_u, out = set(), set(), {}
    for score, s, u, sims in scored:
        if s in used_s or u in used_u:
            continue
        used_s.add(s)
        used_u.add(u)
        out[s] = (u, score, sims)
    return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.75)
    ap.add_argument("--refresh", action="store_true", help="tải lại ứng viên từ DBpedia")
    ap.add_argument("--gold", default=str(HERE / "output" / "sameas-dbpedia.validated.nt"),
                    help="đáp án: liên kết liên ngôn ngữ đã kiểm tra (validate_links.py)")
    args = ap.parse_args()

    tout = HERE.parent / "transform" / "output"
    ours = load_ours(tout)
    data = fetch_candidates(HERE / "cache" / "dbpedia_candidates.json", args.refresh)
    cands = data["candidates"]
    gold = {str(s): str(o) for s, o in Graph().parse(args.gold).subject_objects(OWL.sameAs)}
    print(f"Thực thể của ta: {len(ours)} · ứng viên DBpedia: {len(cands)} · đáp án: "
          f"{sum(s in ours for s in gold)} cặp (trong phạm vi)")

    best = match(ours, cands)

    def evaluate(th, subset=None):
        pred = {s: u for s, (u, sc, _) in best.items() if sc >= th and (subset is None or s in subset)}
        g = {s: u for s, u in gold.items() if s in ours and (subset is None or s in subset)}
        judged = {s: u for s, u in pred.items() if s in g}      # chỉ chấm được thực thể có đáp án
        tp = sum(g[s] == u for s, u in judged.items())
        p = tp / len(judged) if judged else 0.0
        r = tp / len(g) if g else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return {"pred": len(pred), "judged": len(judged), "tp": tp, "gold": len(g), "p": p, "r": r, "f1": f,
                "new": len(pred) - len(judged)}

    # Trần recall: đáp án nằm trong tập ứng viên?
    in_scope_gold = {s: u for s, u in gold.items() if s in ours}
    reachable = sum(u in cands for u in in_scope_gold.values())

    # ---------------- Ghi liên kết ----------------------------------------------------------
    out = HERE / "output"
    gm = Graph()
    for s, (u, sc, _) in best.items():
        if sc >= args.threshold:
            gm.add((URIRef(s), OWL.sameAs, URIRef(u)))
    write_sorted_nt(gm, out / "sameas-dbpedia.matched.nt")

    final = Graph().parse(args.gold)
    linked_targets = {str(o) for o in final.objects(None, OWL.sameAs)}
    new_rows = []
    n_added = 0
    for s, (u, sc, sims) in sorted(best.items()):
        if sc >= args.threshold and s not in gold and u not in linked_targets:
            ok = confident(sims)
            if ok:
                final.add((URIRef(s), OWL.sameAs, URIRef(u)))
                n_added += 1
            new_rows.append([short(s), short(ours[s]["cls"]), u, f"{sc:.3f}",
                             " ".join(f"{k}={v:.2f}" for k, v in sims.items()), int(ok), ""])
    write_sorted_nt(final, out / "sameas-dbpedia.final.nt")
    rep = HERE / "reports"
    with open(rep / "new_links_review.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tai_nguyen_vi", "lop_cua_ta", "lien_ket_en", "diem", "chi_tiet", "vao_final", "dung"])
        w.writerows(new_rows)

    # ---------------- Báo cáo -----------------------------------------------------------------
    pct = lambda x: f"{x:.1%}"
    ev = evaluate(args.threshold)
    md = ["# Đánh giá bộ so khớp (kiểu Silk) với đáp án là liên kết liên ngôn ngữ", "",
          f"Ứng viên DBpedia tải ngày **{data['fetched']}** · ngưỡng **{args.threshold}** · "
          f"luật: xem đầu `match.py` hoặc `silk/linkspec.xml`.", "",
          "## Kết quả chính", "",
          "| Chỉ số | Giá trị |", "|---|---|",
          f"| Thực thể trong phạm vi (tỉnh/thành, cơ sở GDĐH) | {len(ours)} |",
          f"| Có đáp án (liên kết liên ngôn ngữ đã kiểm tra) | {ev['gold']} |",
          f"| Đáp án nằm trong tập ứng viên (trần recall) | {reachable} ({pct(reachable / ev['gold'])}) |",
          f"| Liên kết bộ so khớp sinh ra | {ev['pred']} |",
          f"| — chấm được (thực thể có đáp án) | {ev['judged']} |",
          f"| — đúng | {ev['tp']} |",
          f"| **Precision** | **{pct(ev['p'])}** |",
          f"| **Recall** | **{pct(ev['r'])}** |",
          f"| **F1** | **{pct(ev['f1'])}** |",
          f"| Liên kết mới (thực thể không có liên kết liên ngôn ngữ) | {ev['new']} |",
          f"| — đủ tin cậy, đưa vào `sameas-dbpedia.final.nt` | {n_added} |",
          f"| Tổng liên kết trong `sameas-dbpedia.final.nt` | {len(final)} |", "",
          "Precision chỉ tính trên thực thể có đáp án; liên kết mới cần chấm tay "
          "(`reports/new_links_review.csv`, cột `dung`).", "",
          "**Lưu ý khi đọc số liệu.** Luật được tinh chỉnh bằng cách xem lỗi trên chính tập đáp án này, "
          "nên precision/recall ở đây là ước lượng lạc quan. Thực thể có liên kết liên ngôn ngữ cũng là "
          "nhóm \"dễ\" (chắc chắn có bài tiếng Anh); với nhóm không có, bộ so khớp hay chọn nhầm ứng viên "
          f"gần nhất — vì vậy liên kết mới chỉ được nhận khi tên ≥ {NEW_LINK_MIN_NAME} và có thêm bằng chứng "
          f"độc lập ({', '.join(CORROBORATING)}).", "",
          "## Theo ngưỡng", "", "| Ngưỡng | Sinh ra | Đúng | Precision | Recall | F1 | Mới |",
          "|---|---|---|---|---|---|---|"]
    for th in (0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95):
        e = evaluate(th)
        mark = " ←" if th == args.threshold else ""
        md.append(f"| {th}{mark} | {e['pred']} | {e['tp']} | {pct(e['p'])} | {pct(e['r'])} | "
                  f"{pct(e['f1'])} | {e['new']} |")
    md += ["", "## Theo lớp", "", "| Lớp | Đáp án | Sinh ra | Đúng | Precision | Recall |", "|---|---|---|---|---|---|"]
    for c, _ in Counter(e["cls"] for e in ours.values()).most_common():
        e = evaluate(args.threshold, {s for s, x in ours.items() if x["cls"] == c})
        md.append(f"| `{short(c)}` | {e['gold']} | {e['judged']} | {e['tp']} | {pct(e['p'])} | {pct(e['r'])} |")
    md += ["", "## Đóng góp của từng phép so sánh", "",
           "Số liên kết đúng (ở ngưỡng đã chọn) có phép so sánh đó.", "",
           "| Phép so sánh | Có giá trị | Điểm = 1 |", "|---|---|---|"]
    tp_sims = [best[s][2] for s, u in gold.items()
               if s in best and best[s][1] >= args.threshold and best[s][0] == u]
    for k in WEIGHTS:
        md.append(f"| {k} | {sum(k in x for x in tp_sims)} | {sum(x.get(k) == 1.0 for x in tp_sims)} |")
    wrong = [(s, u, gold[s]) for s, (u, sc, _) in best.items() if sc >= args.threshold and s in gold and gold[s] != u]
    md += ["", f"## Liên kết sai ({len(wrong)})", "", "| Thực thể | Bộ so khớp chọn | Đáp án |", "|---|---|---|",
           *[f"| {short(s)} | {short(u)} | {short(g)} |" for s, u, g in sorted(wrong)]]
    missed = [(s, g) for s, g in in_scope_gold.items() if s not in best or best[s][1] < args.threshold]
    md += ["", f"## Bỏ sót ({len(missed)})", "",
           "Lý do: *ngoài ứng viên* = đáp án không nằm trong tập ứng viên tải về; "
           "*điểm thấp* = có nhưng điểm dưới ngưỡng hoặc bị ghép với thực thể khác.", "",
           "| Thực thể | Đáp án | Lý do |", "|---|---|---|",
           *[f"| {short(s)} | {short(g)} | {'ngoài ứng viên' if g not in cands else 'điểm thấp'} |"
             for s, g in sorted(missed)]]
    (rep / "match_evaluation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:24]))


if __name__ == "__main__":
    main()
