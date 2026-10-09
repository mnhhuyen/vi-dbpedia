"""
Bước 5 (phần 2) — Server Linked Data cho DBpedia tiếng Việt.

Làm cho các URI https://w3id.org/vi-dbpedia/... dereference được (nguyên tắc Linked Data
số 2 và 3, điều kiện để đạt 4 sao), đồng thời là giao diện web để tra cứu và quay demo.

  /resource/<Tên>        303 See Other -> /page/<Tên> (trình duyệt) hoặc /data/<Tên>.<đuôi> (máy)
  /page/<Tên>            trang HTML mô tả thực thể; triple suy ra được tô màu riêng
  /data/<Tên>.ttl|.nt|.jsonld|.rdf    mô tả thực thể dạng RDF
  /ontology/  /ontology/<Thuật_ngữ>   ontology vio: (HTML hoặc RDF tuỳ header Accept)
  /property/<tham_số>    thuộc tính infobox thô (vip:)
  /void/..., /graph/...  metadata bộ dữ liệu, named graph
  /sparql                SPARQL endpoint (chỉ đọc) + giao diện truy vấn
  /search?q=             tìm theo tên, không cần gõ dấu
  /dumps/                tải các file dữ liệu (void:dataDump trỏ tới đây)

Chạy:
    python ld_server.py --local          # không cần Fuseki: đọc thẳng các file .nt/.ttl
    python ld_server.py                  # dùng Fuseki tại http://localhost:3030/vi-dbpedia/sparql
Rồi mở http://localhost:8000

Kiểm tra content negotiation:
    curl -i http://localhost:8000/resource/H%C3%A0_N%E1%BB%99i
    curl -iL -H "Accept: text/turtle" http://localhost:8000/resource/H%C3%A0_N%E1%BB%99i

Khi đăng ký w3id (xem w3id/README.md), https://w3id.org/vi-dbpedia/ chuyển tiếp tới server này.
"""
import argparse
import html
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, Request
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse, RedirectResponse,
                               Response)
from rdflib import Graph

import store as S

HERE = Path(__file__).parent
BASE, G = S.BASE, S.G
GRAPH_INFERRED = G + "inferred"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
DBO = "http://dbpedia.org/ontology/"
SKIP_IN_TABLE = {RDFS_LABEL, DBO + "abstract", RDF_TYPE, DBO + "wikiPageWikiLink"}
PREFIXES = {
    BASE + "resource/": "vir:", BASE + "ontology/": "vio:", BASE + "property/": "vip:",
    DBO: "dbo:", "http://dbpedia.org/resource/": "dbr:", "http://www.wikidata.org/entity/": "wd:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:", "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:", "http://www.w3.org/2001/XMLSchema#": "xsd:",
    "http://xmlns.com/foaf/0.1/": "foaf:", "http://purl.org/dc/terms/": "dct:",
    "http://www.w3.org/2003/01/geo/wgs84_pos#": "geo:", "http://www.w3.org/ns/prov#": "prov:",
    "http://schema.org/": "schema:", "http://rdfs.org/ns/void#": "void:",
    "http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#": "dul:",
}
SPARQL_PREFIXES = "".join(f"PREFIX {p} <{ns}>\n" for ns, p in PREFIXES.items())
# Nhãn tiếng Việt cho các thuộc tính chuẩn không có nhãn @vi trong ontology
EXTRA_LABELS = {
    "http://purl.org/dc/terms/subject": "thể loại Wikipedia",
    "http://xmlns.com/foaf/0.1/isPrimaryTopicOf": "bài Wikipedia",
    "http://www.w3.org/ns/prov#wasDerivedFrom": "trích xuất từ",
    "http://www.w3.org/2002/07/owl#sameAs": "cùng thực thể",
    "http://www.w3.org/2003/01/geo/wgs84_pos#lat": "vĩ độ",
    "http://www.w3.org/2003/01/geo/wgs84_pos#long": "kinh độ",
    "http://xmlns.com/foaf/0.1/homepage": "trang chủ",
    DBO + "wikiPageID": "mã trang Wikipedia",
    DBO + "wikiPageWikiLink": "liên kết trong bài",
    "http://www.w3.org/2000/01/rdf-schema#subClassOf": "lớp cha",
    "http://www.w3.org/2000/01/rdf-schema#subPropertyOf": "thuộc tính cha",
    "http://www.w3.org/2000/01/rdf-schema#domain": "áp dụng cho (domain)",
    "http://www.w3.org/2000/01/rdf-schema#range": "kiểu giá trị (range)",
    "http://www.w3.org/2002/07/owl#equivalentClass": "lớp tương đương",
    "http://www.w3.org/2002/07/owl#equivalentProperty": "thuộc tính tương đương",
    "http://www.w3.org/2002/07/owl#inverseOf": "quan hệ ngược",
    "http://www.w3.org/2002/07/owl#disjointWith": "loại trừ với",
    "http://www.w3.org/2002/07/owl#propertyChainAxiom": "chuỗi thuộc tính",
}
SAMPLES = ["Hà Nội", "Thành phố Hồ Chí Minh", "Hà Giang", "Đại học Quốc gia Hà Nội",
           "Đại học Bách khoa Hà Nội", "Trường Đại học Công nghệ, Đại học Quốc gia Hà Nội"]

app = FastAPI(title="DBpedia tiếng Việt", docs_url=None, redoc_url=None)
STORE = None          # gán trong main()
_CACHE = {}


# ------------------------------------------------------------------ URI <-> đường dẫn
def iri_escape(s):
    """Giống transform.py: mã hoá phần trăm ký tự cấm trong IRI, giữ chữ Unicode."""
    out = []
    for ch in unicodedata.normalize("NFC", s):
        if ch in ' <>"{}|\\^`%?#[]' or ord(ch) < 0x21:
            out.append("".join(f"%{b:02X}" for b in ch.encode("utf-8")))
        else:
            out.append(ch)
    return "".join(out)


def iri_for(kind, name):
    return f"{BASE}{kind}/{iri_escape(name)}"


def local_href(iri):
    """IRI trong namespace của dự án -> đường dẫn trên server này; IRI ngoài -> giữ nguyên."""
    if not iri.startswith(BASE):
        return iri
    rest = iri[len(BASE):]
    if rest.startswith("resource/"):
        rest = "page/" + rest[len("resource/"):]
    return "/" + quote(rest, safe="/:%()_,'-.!~*;=@+&$")


def short(iri):
    for ns, p in PREFIXES.items():
        if iri.startswith(ns):
            return p + iri[len(ns):]
    return iri


def fold(s):
    """Bỏ dấu để tìm kiếm: 'Hà Nội' -> 'ha noi'."""
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def num(n):
    return f"{n:,}".replace(",", ".")


def add_prefixes(query):
    """Tự thêm PREFIX chuẩn (vio:, dbo:, rdfs:...) nếu truy vấn dùng mà chưa khai báo,
    để truy vấn gõ nhanh chạy được cả trên Fuseki lẫn rdflib."""
    declared = set(re.findall(r"(?i)PREFIX\s+([\w-]*):", query))
    body = re.sub(r"(?s)<[^>]*>|\"[^\"]*\"|#[^\n]*", "", query)
    need = [(p, ns) for ns, p in PREFIXES.items()
            if p[:-1] not in declared and re.search(r"(?<![\w:/])" + re.escape(p), body)]
    return "".join(f"PREFIX {p} <{ns}>\n" for p, ns in need) + query


def esc(s):
    return html.escape(str(s), quote=True)


# ------------------------------------------------------------------ content negotiation
def negotiate(request, offers):
    """Chọn media type theo header Accept (có xét q=). offers: danh sách theo thứ tự ưu tiên."""
    accept = request.headers.get("accept", "") or "*/*"
    prefs = []
    for i, part in enumerate(accept.split(",")):
        bits = [b.strip() for b in part.split(";")]
        q = 1.0
        for b in bits[1:]:
            if b.startswith("q="):
                try:
                    q = float(b[2:])
                except ValueError:
                    q = 0
        prefs.append((-q, i, bits[0].lower()))
    for _, _, mt in sorted(prefs):
        if mt in ("*/*", "text/*"):
            return offers[0]
        if mt in offers:
            return mt
    return offers[0]


OFFERS = ["text/html"] + list(S.RDF_FORMATS)
EXT = {ext: mt for mt, (_, ext) in S.RDF_FORMATS.items()}


# ------------------------------------------------------------------ truy vấn
def describe_graph(iri):
    q = f"""CONSTRUCT {{ <{iri}> ?p ?o . ?s ?q <{iri}> }} WHERE {{
      {{ <{iri}> ?p ?o }} UNION
      {{ SELECT ?s ?q WHERE {{ ?s ?q <{iri}> FILTER(?q != <{DBO}wikiPageWikiLink>) }} LIMIT 500 }} }}"""
    return STORE.construct(q)


def rdf_response(g, mt, iri=None):
    for p, ns in ((p, ns) for ns, p in PREFIXES.items()):
        g.bind(p.rstrip(":"), ns, override=True, replace=True)
    body = g.serialize(format=S.RDF_FORMATS[mt][0])
    headers = {"Vary": "Accept", "Access-Control-Allow-Origin": "*"}
    if iri:
        # header HTTP chỉ nhận Latin-1: đổi IRI tiếng Việt sang dạng URI (mã hoá phần trăm)
        headers["Link"] = f'<{quote(iri, safe=":/%()_,-.!~*;=@+&$")}>; rel="describes"'
    return Response(body, media_type=mt + "; charset=utf-8", headers=headers)


def labels_for(iris):
    """Nhãn ưu tiên @vi, rồi @en, rồi không có ngôn ngữ."""
    iris = [i for i in dict.fromkeys(iris) if i.startswith("http")][:400]
    if not iris:
        return {}
    values = " ".join(f"<{i}>" for i in iris)
    _, rows = STORE.select(f"SELECT ?x ?l WHERE {{ VALUES ?x {{ {values} }} ?x <{RDFS_LABEL}> ?l }}")
    rank = {"vi": 0, "en": 1}
    best = {}
    for r in rows:
        x, l = r["x"]["value"], r["l"]
        k = rank.get(l.get("xml:lang"), 2)
        if x not in best or k < best[x][0]:
            best[x] = (k, l["value"])
    out = {x: v for x, (_, v) in best.items()}
    for i in iris:
        if i not in out and i in EXTRA_LABELS:
            out[i] = EXTRA_LABELS[i]
        elif i not in out and i.startswith(BASE + "resource/"):   # vd. thể loại: lấy tên từ IRI
            out[i] = i[len(BASE + "resource/"):].replace("Thể_loại:", "").replace("_", " ")
    return out


def most_specific(types):
    if len(types) < 2:
        return list(types)
    values = " ".join(f"<{t}>" for t in types)
    _, rows = STORE.select(f"""SELECT DISTINCT ?a ?b WHERE {{ VALUES ?a {{ {values} }} VALUES ?b {{ {values} }}
        ?a <http://www.w3.org/2000/01/rdf-schema#subClassOf>+ ?b FILTER(?a != ?b) }}""")
    supers = {r["b"]["value"] for r in rows}
    return [t for t in types if t not in supers]


def entity(iri):
    _, rows = STORE.select(f"SELECT ?p ?o ?g WHERE {{ GRAPH ?g {{ <{iri}> ?p ?o }} }}")
    facts = {}
    for r in rows:
        key = (r["p"]["value"], r["o"]["type"], r["o"]["value"], r["o"].get("xml:lang"))
        inferred = r["g"]["value"] == GRAPH_INFERRED
        if key not in facts or not inferred:      # cùng triple ở nhiều graph: ưu tiên graph gốc
            facts[key] = (r["p"]["value"], r["o"], inferred)
    _, inc = STORE.select(f"""SELECT DISTINCT ?s ?p WHERE {{ ?s ?p <{iri}>
        FILTER(?p != <{DBO}wikiPageWikiLink> && ?p != <http://www.w3.org/2002/07/owl#sameAs>) }} LIMIT 300""")
    return list(facts.values()), [(r["s"]["value"], r["p"]["value"]) for r in inc]


def home_stats():
    if "stats" not in _CACHE:
        _, by_graph = STORE.select("SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g")
        _, by_class = STORE.select(f"""SELECT ?c (COUNT(DISTINCT ?s) AS ?n) WHERE {{
            GRAPH <{G}data> {{ ?s a ?c }} FILTER(STRSTARTS(STR(?c), "{BASE}ontology/")) }} GROUP BY ?c ORDER BY DESC(?n)""")
        # mỗi dòng là một (thực thể, nhãn); 116 trường có thêm nhãn @en nên số dòng > số thực thể.
        # Giữ cả nhãn @en để tìm kiếm được theo tên tiếng Anh; khi đếm thì đếm thực thể khác nhau.
        _, labels = STORE.select(f"""SELECT ?s ?l (SAMPLE(?c) AS ?t) WHERE {{ GRAPH <{G}data> {{
            ?s <{RDFS_LABEL}> ?l ; <http://xmlns.com/foaf/0.1/isPrimaryTopicOf> ?w
            OPTIONAL {{ ?s a ?c }} }} }} GROUP BY ?s ?l""")
        _CACHE["stats"] = (
            {r["g"]["value"][len(G):]: int(r["n"]["value"]) for r in by_graph},
            [(r["c"]["value"], int(r["n"]["value"])) for r in by_class],
            [(r["s"]["value"], r["l"]["value"], r.get("t", {}).get("value")) for r in labels],
        )
    return _CACHE["stats"]


def search(q, limit=30):
    q = fold(q.strip())
    if not q:
        return []
    hits = []
    for s, l, t in home_stats()[2]:
        f = fold(l)
        if q in f:
            hits.append((0 if f == q else 1 if f.startswith(q) else 2, len(l), s, l, t))
    return [h[2:] for h in sorted(hits)[:limit]]


# ------------------------------------------------------------------ giao diện
CSS = """
:root{--ink:#14213D;--paper:#F7F8F6;--muted:#5B6475;--rule:#D9DDE3;--jade:#1F7A68;--lotus:#B5306B;--lotus-bg:#FBEFF4}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 "Be Vietnam Pro",system-ui,"Segoe UI",sans-serif}
a{color:var(--jade);text-decoration-thickness:1px;text-underline-offset:2px}
a:focus-visible,button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:3px solid var(--jade);outline-offset:2px}
header.site{border-bottom:1px solid var(--rule);background:#fff}
header.site div{max-width:1100px;margin:auto;padding:14px 24px;display:flex;gap:28px;align-items:baseline;flex-wrap:wrap}
header.site .brand{font-weight:700;color:var(--ink);text-decoration:none;font-size:18px}
header.site nav{display:flex;gap:20px;flex-wrap:wrap}
header.site nav a{color:var(--muted);text-decoration:none}
header.site nav a[aria-current]{color:var(--ink);font-weight:600}
main{max-width:1100px;margin:auto;padding:32px 24px 64px}
h1{font-size:40px;line-height:1.15;margin:0 0 8px;letter-spacing:-.01em}
h2{font-size:20px;margin:36px 0 12px}
.iri{font:13px/1.4 "JetBrains Mono",ui-monospace,Consolas,monospace;color:var(--muted);word-break:break-all}
.types{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
.type{padding:3px 10px;border:1px solid var(--ink);border-radius:999px;font-size:14px;text-decoration:none;color:var(--ink)}
.type.super{border-color:var(--rule);color:var(--muted)}
.type.inferred{border-color:var(--lotus);color:var(--lotus)}
.abstract{max-width:72ch;font-size:17px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:40px}
@media(max-width:860px){.grid{grid-template-columns:1fr}h1{font-size:32px}}
table{border-collapse:collapse;width:100%;font-size:15px;table-layout:fixed}
td,th{overflow-wrap:anywhere}
th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--rule)}
th{font-weight:600;width:34%}
th small{display:block;color:var(--muted);font-weight:400;font-size:12px}
td small{color:var(--muted);font-size:12px}
details.ext{margin:0;flex-basis:100%}
details.ext .types{margin:8px 0 0}
tr.inf td,tr.inf th{background:var(--lotus-bg)}
tr.inf th{box-shadow:inset 3px 0 0 var(--lotus)}
.tag{color:var(--lotus);font-size:12px;font-weight:600;margin-left:6px}
body.hide-inf tr.inf,body.hide-inf .type.inferred,body.hide-inf details.inf-ext{display:none}
.toggle{display:flex;align-items:center;gap:10px;margin:8px 0 4px;color:var(--muted);font-size:14px}
aside section{border-top:2px solid var(--ink);padding-top:10px;margin-bottom:28px}
aside h3{font-size:15px;margin:0 0 8px}
aside ul{list-style:none;padding:0;margin:0}
aside li{margin:6px 0;word-break:break-word}
iframe.map{width:100%;height:240px;border:1px solid var(--rule)}
details{margin:12px 0}
summary{cursor:pointer;color:var(--muted)}
.search{display:flex;gap:8px;max-width:640px;margin:20px 0}
.search input{flex:1;padding:12px 14px;font:inherit;border:1px solid var(--ink);border-radius:6px;background:#fff}
button,.btn{padding:10px 18px;font:inherit;font-weight:600;border:0;border-radius:6px;background:var(--ink);color:#fff;cursor:pointer;text-decoration:none}
.lede{font-size:19px;max-width:60ch;color:var(--muted);margin:0}
.facts{display:flex;flex-wrap:wrap;gap:12px 32px;margin:24px 0;color:var(--muted)}
.facts b{color:var(--ink);font-size:22px;display:block}
.cols{columns:2 280px;column-gap:40px}
.cols li{break-inside:avoid;margin:4px 0}
textarea{width:100%;min-height:260px;font:14px/1.5 "JetBrains Mono",ui-monospace,Consolas,monospace;padding:12px;border:1px solid var(--ink);border-radius:6px}
.bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:12px 0}
select{padding:9px;font:inherit;border:1px solid var(--rule);border-radius:6px;max-width:100%}
.out{overflow-x:auto;margin-top:16px}
.err{color:#9B1C1C;white-space:pre-wrap}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def layout(title, body, active="", extra_head=""):
    nav = [("/", "Trang chủ"), ("/ontology/", "Ontology"), ("/sparql", "SPARQL"), ("/dumps/", "Tải dữ liệu")]
    links = "".join(f'<a href="{h}"{" aria-current=page" if h == active else ""}>{t}</a>' for h, t in nav)
    return HTMLResponse(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} – DBpedia tiếng Việt</title>
<!-- font tải không chặn hiển thị: mất mạng khi demo thì trang vẫn hiện ngay bằng font hệ thống -->
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet" media="print" onload="this.media='all'">
<style>{CSS}</style>{extra_head}</head><body>
<header class="site"><div><a class="brand" href="/">DBpedia tiếng Việt</a><nav>{links}</nav></div></header>
<main>{body}</main></body></html>""", headers={"Vary": "Accept"})


def value_html(o, labels):
    if o["type"] == "uri":
        v = o["value"]
        text = labels.get(v) or short(v)
        ext = "" if v.startswith(BASE) else ' rel="noopener"'
        return f'<a href="{esc(local_href(v))}"{ext}>{esc(text)}</a>'
    v = esc(o["value"])
    if o.get("xml:lang"):
        return f'{v} <small>@{esc(o["xml:lang"])}</small>'
    if o.get("datatype"):
        return f'{v} <small>{esc(short(o["datatype"]))}</small>'
    return v


def entity_page(iri):
    facts, incoming = entity(iri)
    if not facts and not incoming:
        return None
    by_p = {}
    for p, o, inf in facts:
        by_p.setdefault(p, []).append((o, inf))
    objs = [o["value"] for _, o, _ in facts if o["type"] == "uri"]
    labels = labels_for([iri] + list(by_p) + objs + [s for s, _ in incoming] + [p for _, p in incoming])
    lit = lambda p: next((o["value"] for o, _ in by_p.get(p, []) if o.get("xml:lang") in ("vi", None)), None)
    title = labels.get(iri) or short(iri)
    title = title[:1].upper() + title[1:]

    types = [(o["value"], inf) for o, inf in by_p.get(RDF_TYPE, [])]
    specific = set(most_specific([t for t, _ in types if t.startswith((BASE, DBO))]))
    tlabels = labels_for([t for t, _ in types])
    chips = sorted(types, key=lambda x: (x[0] not in specific, x[1], not x[0].startswith(BASE)))
    chip = lambda t, inf: (f'<a class="type{" super" if t not in specific else ""}{" inferred" if inf else ""}" '
                           f'href="{esc(local_href(t))}" title="{esc(short(t))}{" (suy ra)" if inf else ""}">'
                           f'{esc(tlabels.get(t) or short(t))}</a>')
    own = [(t, i) for t, i in chips if t.startswith((BASE, DBO))]
    ext = [(t, i) for t, i in chips if (t, i) not in own]
    chip_html = "".join(chip(t, i) for t, i in own)
    if ext:
        chip_html += (f'<details class="ext"><summary>và {len(ext)} lớp khác (schema.org, Wikidata, DUL, OWL)</summary>'
                      f'<div class="types">{"".join(chip(t, i) for t, i in ext)}</div></details>')

    rows, raw_rows, ext_rows = [], [], []
    order = lambda p: (p.startswith(("http://www.w3.org/ns/prov", "http://xmlns.com/foaf/0.1/isPrimary",
                                     "http://purl.org/dc/terms/subject", DBO + "wikiPageID")),
                       (labels.get(p) or short(p)).lower())
    for p in sorted(by_p, key=order):
        if p in SKIP_IN_TABLE:
            continue
        for inf in (False, True):
            vals = [o for o, i in by_p[p] if i == inf]
            if not vals:
                continue
            vals.sort(key=lambda o: labels.get(o["value"], o["value"]))
            sep = "<br>" if len(vals) > 3 else ", "
            row = (f'<tr class="{"inf" if inf else ""}"><th>{esc(labels.get(p) or short(p))}'
                   f'{"<span class=tag>suy ra</span>" if inf else ""}<small>{esc(short(p))}</small></th>'
                   f'<td>{sep.join(value_html(o, labels) for o in vals)}</td></tr>')
            if p.startswith(BASE + "property/"):
                raw_rows.append(row)
            elif inf and not p.startswith((BASE, DBO, "http://www.w3.org/")):
                ext_rows.append(row)          # vd. dul:hasLocation suy ra từ DBpedia Ontology
            else:
                rows.append(row)
    n_inf = sum(1 for _, _, inf in facts if inf)

    same = [o["value"] for o, _ in by_p.get("http://www.w3.org/2002/07/owl#sameAs", [])]
    wiki = [o["value"] for o, _ in by_p.get("http://xmlns.com/foaf/0.1/isPrimaryTopicOf", [])]
    out_links = []
    for v in same:
        if v.startswith("http://dbpedia.org/resource/"):
            out_links.append(f'<li>DBpedia tiếng Anh: <a href="{esc(v.replace("/resource/", "/page/"))}">{esc(short(v))}</a></li>')
        elif "wikidata.org" in v:
            out_links.append(f'<li>Wikidata: <a href="{esc(v.replace("/entity/", "/wiki/"))}">{esc(short(v))}</a></li>')
        else:
            out_links.append(f'<li><a href="{esc(v)}">{esc(v)}</a></li>')
    out_links += [f'<li>Bài gốc: <a href="{esc(w)}">vi.wikipedia.org</a></li>' for w in wiki]

    lat, lon = lit("http://www.w3.org/2003/01/geo/wgs84_pos#lat"), lit("http://www.w3.org/2003/01/geo/wgs84_pos#long")
    map_html = ""
    if lat and lon:
        la, lo = float(lat), float(lon)
        bbox = f"{lo - .6},{la - .45},{lo + .6},{la + .45}"
        map_html = (f'<section><h3>Vị trí</h3><iframe class="map" title="Bản đồ {esc(title)}" loading="lazy" '
                    f'src="https://www.openstreetmap.org/export/embed.html?bbox={bbox}&amp;layer=mapnik&amp;marker={la},{lo}"></iframe>'
                    f'<p class="iri">{la:.4f}, {lo:.4f}</p></section>')

    name = iri.rsplit("/", 1)[-1]
    kind = iri[len(BASE):].split("/", 1)[0] if iri.startswith(BASE) else ""
    data_base = f"/data/{quote(iri[len(BASE + 'resource/'):], safe='/:%()_,-.')}" if kind == "resource" else None
    downloads = (" ".join(f'<a href="{data_base}.{ext}">{lbl}</a>' for ext, lbl in
                          (("ttl", "Turtle"), ("nt", "N-Triples"), ("jsonld", "JSON-LD"), ("rdf", "RDF/XML")))
                 if data_base else
                 " ".join(f'<a href="{esc(local_href(iri))}?format={ext}">{lbl}</a>' for ext, lbl in
                          (("ttl", "Turtle"), ("nt", "N-Triples"), ("jsonld", "JSON-LD"))))

    inc_html = "".join(f'<li><a href="{esc(local_href(s))}">{esc(labels.get(s) or short(s))}</a> '
                       f'<small class="iri">{esc(labels.get(p) or short(p))}</small></li>' for s, p in incoming[:200])
    links_out = by_p.get(DBO + "wikiPageWikiLink", [])
    wl_html = "".join(f'<li>{value_html(o, labels)}</li>' for o, _ in links_out[:400])

    instances = ""
    if kind == "ontology" and name:
        _, inst = STORE.select(f"SELECT DISTINCT ?s ?l WHERE {{ ?s a <{iri}> ; <{RDFS_LABEL}> ?l }} ORDER BY ?l LIMIT 500")
        if inst:
            inst.sort(key=lambda r: fold(r["l"]["value"]))
            items = "".join(f'<li><a href="{esc(local_href(r["s"]["value"]))}">{esc(r["l"]["value"])}</a></li>' for r in inst)
            instances = f'<h2>Thực thể thuộc lớp này ({len(inst)})</h2><ul class="cols">{items}</ul>'

    abstract = lit(DBO + "abstract") or lit(RDFS_COMMENT) or ""
    if len(abstract) > 520:
        cut = abstract.rfind(". ", 0, 520) + 1 or 520
        abstract_html = (f'<p class="abstract">{esc(abstract[:cut])}</p><details><summary>Đọc tiếp</summary>'
                         f'<p class="abstract">{esc(abstract[cut:].strip())}</p></details>')
    else:
        abstract_html = f'<p class="abstract">{esc(abstract)}</p>'
    toggle = (f'<label class="toggle"><input type="checkbox" checked onchange="document.body.classList.toggle(\'hide-inf\',!this.checked)"> '
              f'Hiện {n_inf} thông tin do reasoner suy ra (tô màu hồng)</label>') if n_inf else ""
    body = f"""<h1>{esc(title)}</h1>
<p class="iri">{esc(iri)}</p>
<div class="types">{chip_html}</div>
{toggle}
<div class="grid"><div>
{abstract_html}
<table>{"".join(rows) or '<tr><td>Không có thuộc tính nào khác.</td></tr>'}</table>
{f'<details class="inf-ext"><summary>Thuộc tính suy ra theo các ontology nền DOLCE/DUL ({len(ext_rows)})</summary><table>{"".join(ext_rows)}</table></details>' if ext_rows else ''}
{f'<details><summary>Giá trị infobox gốc chưa chuẩn hoá ({len(raw_rows)})</summary><table>{"".join(raw_rows)}</table></details>' if raw_rows else ''}
{instances}
{f'<h2>Được nhắc tới bởi ({len(incoming)})</h2><ul class="cols">{inc_html}</ul>' if incoming else ''}
{f'<details><summary>Liên kết tới {len(links_out)} bài Wikipedia khác</summary><ul class="cols">{wl_html}</ul></details>' if links_out else ''}
</div><aside>
{f'<section><h3>Cùng thực thể ở nơi khác</h3><ul>{"".join(out_links)}</ul></section>' if out_links else ''}
{map_html}
<section><h3>Dữ liệu RDF</h3><p>{downloads}</p></section>
</aside></div>"""
    return layout(title, body)


# ------------------------------------------------------------------ route: Linked Data
@app.get("/resource/{name:path}")
def resource(name: str, request: Request):
    mt = negotiate(request, OFFERS)
    path = quote(iri_escape(name), safe="/:%()_,'-.!~*;=@+&$")
    target = f"/page/{path}" if mt == "text/html" else f"/data/{path}.{S.RDF_FORMATS[mt][1]}"
    return RedirectResponse(target, status_code=303, headers={"Vary": "Accept"})


@app.get("/page/{name:path}")
def page(name: str):
    resp = entity_page(iri_for("resource", name))
    return resp or not_found(name)


@app.get("/data/{name:path}")
def data(name: str):
    stem, _, ext = name.rpartition(".")
    if ext not in EXT or not stem:
        return Response("Thiếu đuôi định dạng: .ttl, .nt, .jsonld hoặc .rdf", status_code=404)
    iri = iri_for("resource", stem)
    g = describe_graph(iri)
    if not len(g):
        return Response(f"Không có dữ liệu cho {iri}", status_code=404)
    return rdf_response(g, EXT[ext], iri)


def term_route(kind, name, request):
    """ontology/, property/, void/, graph/: trả HTML hoặc RDF tuỳ Accept (hoặc ?format=)."""
    iri = f"{BASE}{kind}/{iri_escape(name)}"
    fmt = request.query_params.get("format")
    mt = EXT.get(fmt) if fmt else negotiate(request, OFFERS)
    if mt and mt != "text/html":
        g = describe_graph(iri)
        if kind == "ontology" and not name:            # cả ontology vio:
            g = Graph().parse(HERE.parent / "ontology" / "vio-ontology.ttl")
        return rdf_response(g, mt, iri) if len(g) else Response("Không có dữ liệu", status_code=404)
    if kind == "ontology" and not name:
        return ontology_index()
    return entity_page(iri) or not_found(name)


@app.get("/ontology/{name:path}")
def ontology(name: str, request: Request):
    return term_route("ontology", name, request)


@app.get("/ontology")
def ontology_root(request: Request):
    return term_route("ontology", "", request)


@app.get("/property/{name:path}")
def prop(name: str, request: Request):
    return term_route("property", name, request)


@app.get("/void/{name:path}")
def void(name: str, request: Request):
    return term_route("void", name, request)


@app.get("/graph/{name:path}")
def graph(name: str, request: Request):
    return term_route("graph", name, request)


def ontology_index():
    _, rows = STORE.select(f"""SELECT ?t ?kind ?l ?c WHERE {{ GRAPH <{G}ontology> {{
        ?t a ?kind . FILTER(STRSTARTS(STR(?t), "{BASE}ontology/"))
        FILTER(?kind IN (<http://www.w3.org/2002/07/owl#Class>, <http://www.w3.org/2002/07/owl#ObjectProperty>,
                         <http://www.w3.org/2002/07/owl#DatatypeProperty>))
        OPTIONAL {{ ?t <{RDFS_LABEL}> ?l FILTER(LANG(?l) = "vi") }}
        OPTIONAL {{ ?t <{RDFS_COMMENT}> ?c FILTER(LANG(?c) = "vi") }} }} }} ORDER BY ?kind ?l""")
    groups = {}
    for r in rows:
        groups.setdefault(r["kind"]["value"].rsplit("#", 1)[1], []).append(r)
    names = {"Class": "Lớp", "ObjectProperty": "Quan hệ giữa các thực thể", "DatatypeProperty": "Thuộc tính giá trị"}
    body = ['<h1>Ontology vio:</h1><p class="lede">Phần mở rộng tiếng Việt của DBpedia Ontology: '
            'đơn vị hành chính và cơ sở giáo dục đại học.</p>',
            f'<p class="iri">{BASE}ontology/ · tải: <a href="/ontology/?format=ttl">Turtle</a> '
            '<a href="/ontology/?format=jsonld">JSON-LD</a></p>']
    for k in ("Class", "ObjectProperty", "DatatypeProperty"):
        items = "".join(
            f'<tr><th><a href="{esc(local_href(r["t"]["value"]))}">{esc(r.get("l", {}).get("value") or short(r["t"]["value"]))}</a>'
            f'<small>{esc(short(r["t"]["value"]))}</small></th><td>{esc(r.get("c", {}).get("value", ""))}</td></tr>'
            for r in groups.get(k, []))
        body.append(f'<h2>{names[k]} ({len(groups.get(k, []))})</h2><table>{items}</table>')
    return layout("Ontology", "".join(body), "/ontology/")


def not_found(name):
    hits = search(name.replace("_", " "), 10)
    sug = "".join(f'<li><a href="{esc(local_href(s))}">{esc(l)}</a></li>' for s, l, _ in hits)
    return HTMLResponse(layout("Không tìm thấy", f"""<h1>Chưa có thực thể này</h1>
<p class="lede">Không có dữ liệu nào cho “{esc(name)}”. Thử tìm theo tên:</p>
<form class="search" action="/search"><input name="q" value="{esc(name.replace('_', ' '))}" aria-label="Tên cần tìm"><button>Tìm</button></form>
{f'<ul>{sug}</ul>' if sug else ''}""").body, status_code=404)


# ------------------------------------------------------------------ trang chủ, tìm kiếm
@app.get("/")
def home():
    graphs, classes, labels = home_stats()
    clabels = labels_for([c for c, _ in classes])
    by_title = {l: s for s, l, _ in labels}
    samples = "".join(f'<li><a href="{esc(local_href(by_title[t]))}">{esc(t)}</a></li>' for t in SAMPLES if t in by_title)
    cls = "".join(f'<li><a href="{esc(local_href(c))}">{esc(clabels.get(c) or short(c))}</a> <small>{num(n)}</small></li>'
                  for c, n in classes)
    total = sum(graphs.values())
    body = f"""<h1>Tỉnh thành và trường đại học Việt Nam, dưới dạng dữ liệu liên kết</h1>
<p class="lede">Trích xuất từ Wikipedia tiếng Việt, mô tả bằng DBpedia Ontology và phần mở rộng vio:,
liên kết sang DBpedia tiếng Anh và Wikidata.</p>
<form class="search" action="/search" role="search"><input name="q" placeholder="Tìm theo tên, không cần dấu: ha noi, bach khoa…" aria-label="Tìm thực thể"><button>Tìm</button></form>
<div class="facts"><span><b>{num(len({s for s, _, _ in labels}))}</b>bài viết</span><span><b>{num(total)}</b>triple</span>
<span><b>{num(graphs.get('inferred', 0))}</b>triple do reasoner suy ra</span><span><b>{num(graphs.get('links', 0))}</b>liên kết sang DBpedia, Wikidata</span></div>
<div class="grid"><div><h2>Theo lớp</h2><ul class="cols">{cls}</ul></div>
<aside><section><h3>Thử xem</h3><ul>{samples}</ul></section>
<section><h3>Nguồn dữ liệu</h3><p class="iri">{esc(STORE.label)}</p></section></aside></div>"""
    return layout("Trang chủ", body, "/")


@app.get("/search")
def search_page(q: str = ""):
    hits = search(q)
    if len(hits) == 1:
        return RedirectResponse(local_href(hits[0][0]), status_code=302)
    tl = labels_for([t for _, _, t in hits if t])
    items = "".join(f'<li><a href="{esc(local_href(s))}">{esc(l)}</a> <small>{esc(tl.get(t, "") if t else "")}</small></li>'
                    for s, l, t in hits)
    body = f"""<h1>Tìm kiếm</h1><form class="search" action="/search"><input name="q" value="{esc(q)}" aria-label="Tìm thực thể"><button>Tìm</button></form>
{f'<ul class="cols">{items}</ul>' if hits else f'<p>Không có kết quả cho “{esc(q)}”. Thử một phần của tên, ví dụ “giang” hoặc “cong nghe”.</p>' if q else ''}"""
    return layout("Tìm kiếm", body)


@app.get("/search.json")
def search_json(q: str = ""):
    return JSONResponse([{"iri": s, "label": l, "type": t} for s, l, t in search(q)])


# ------------------------------------------------------------------ SPARQL
def example_queries():
    out = []
    for f in sorted((HERE / "queries").glob("*.rq")):
        text = f.read_text(encoding="utf-8")
        first = text.splitlines()[0].lstrip("# ").strip() if text else f.stem
        out.append((f.stem, first, text))
    return out


@app.api_route("/sparql", methods=["GET", "POST"])
async def sparql(request: Request):
    query = request.query_params.get("query")
    if request.method == "POST":
        ctype = request.headers.get("content-type", "")
        if "application/sparql-query" in ctype:
            query = (await request.body()).decode("utf-8")
        else:  # application/x-www-form-urlencoded (đọc tay, khỏi cần thư viện python-multipart)
            form = parse_qs((await request.body()).decode("utf-8"))
            query = form.get("query", [query])[0]
    accept = request.headers.get("accept", "")
    if not query or ("text/html" in accept and request.method == "GET"):
        return sparql_ui(query or "")
    if re.search(r"^\s*(INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|COPY|MOVE|ADD)\b", re.sub(r"(?im)^\s*(PREFIX|BASE)[^\n]*\n|#[^\n]*", "", query), re.I):
        return Response("Endpoint chỉ cho phép truy vấn đọc.", status_code=403)
    try:
        body, mt = STORE.raw(add_prefixes(query), accept or "application/sparql-results+json")
    except Exception as e:  # lỗi cú pháp hoặc lỗi endpoint: trả về để người dùng sửa truy vấn
        return Response(f"Lỗi truy vấn: {e}", status_code=400, media_type="text/plain; charset=utf-8")
    return Response(body, media_type=mt, headers={"Access-Control-Allow-Origin": "*"})


def sparql_ui(query):
    examples = example_queries()
    opts = "".join(f'<option value="{i}">{esc(t)}</option>' for i, (_, t, _) in enumerate(examples))
    start = query or (examples[0][2] if examples else "SELECT * WHERE { ?s ?p ?o } LIMIT 10")
    js_examples = json.dumps([q for _, _, q in examples], ensure_ascii=False).replace("</", "<\\/")
    body = f"""<h1>Truy vấn SPARQL</h1>
<p class="lede">Endpoint <span class="iri">/sparql</span> nhận GET hoặc POST với tham số <span class="iri">query</span>.
Các prefix vio:, vir:, dbo:, rdfs:… được tự thêm nếu bạn chưa khai báo. Ctrl+Enter để chạy.</p>
<div class="bar"><select id="ex" aria-label="Truy vấn mẫu"><option value="">Chọn truy vấn mẫu…</option>{opts}</select></div>
<textarea id="q" spellcheck="false" aria-label="Truy vấn SPARQL">{esc(start)}</textarea>
<div class="bar"><button id="run">Chạy truy vấn</button><span id="info" class="iri"></span></div>
<div class="out" id="out"></div>
<script>
const EX={js_examples}, BASE={BASE!r}, PFX={ {p: ns for ns, p in PREFIXES.items()} };
const q=document.getElementById('q'), out=document.getElementById('out'), info=document.getElementById('info');
document.getElementById('ex').onchange=e=>{{ if(e.target.value!=='') q.value=EX[+e.target.value]; }};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
const short=v=>{{for(const [p,ns] of Object.entries(PFX)) if(v.startsWith(ns)) return p+v.slice(ns.length); return v;}};
const href=v=>v.startsWith(BASE+'resource/')?'/page/'+encodeURI(v.slice(BASE.length+9)):v.startsWith(BASE)?'/'+encodeURI(v.slice(BASE.length)):v;
function cell(t){{ if(!t) return ''; if(t.type==='uri') return `<a href="${{esc(href(t.value))}}">${{esc(short(t.value))}}</a>`;
  return esc(t.value)+(t['xml:lang']?` <small>@${{t['xml:lang']}}</small>`:t.datatype?` <small>${{esc(short(t.datatype))}}</small>`:''); }}
async function run(){{
  out.innerHTML=''; info.textContent='Đang chạy…'; const t0=performance.now();
  const r=await fetch('/sparql',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded','Accept':'application/sparql-results+json, text/turtle;q=0.9'}},body:new URLSearchParams({{query:q.value}})}});
  const ms=Math.round(performance.now()-t0), ct=r.headers.get('content-type')||'', text=await r.text();
  if(!r.ok){{ info.textContent=''; out.innerHTML=`<p class="err">${{esc(text)}}</p>`; return; }}
  if(!ct.includes('json')){{ info.textContent=`${{ms}} ms`; out.innerHTML=`<pre>${{esc(text)}}</pre>`; return; }}
  const j=JSON.parse(text);
  if('boolean' in j){{ info.textContent=`${{ms}} ms`; out.innerHTML=`<p><b>${{j.boolean?'Có (true)':'Không (false)'}}</b></p>`; return; }}
  const vars=j.head.vars, rows=j.results.bindings; info.textContent=`${{rows.length}} dòng, ${{ms}} ms`;
  out.innerHTML=`<table><tr>${{vars.map(v=>`<th>${{esc(v)}}</th>`).join('')}}</tr>${{rows.map(b=>`<tr>${{vars.map(v=>`<td>${{cell(b[v])}}</td>`).join('')}}</tr>`).join('')}}</table>`;
}}
document.getElementById('run').onclick=run;
q.addEventListener('keydown',e=>{{ if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)) run(); }});
{'run();' if query else ''}
</script>"""
    return layout("SPARQL", body, "/sparql")


# ------------------------------------------------------------------ dumps
def dump_files():
    from load import plan
    files = {}
    for group in plan().values():
        for f in group:
            if f.exists():
                files[f.name] = f
    return files


@app.get("/dumps/")
@app.get("/dumps")
def dumps_index():
    files = dump_files()
    rows = "".join(f'<tr><th><a href="/dumps/{quote(n)}">{esc(n)}</a></th><td>{num(round(f.stat().st_size / 1024))} KB</td></tr>'
                   for n, f in sorted(files.items()))
    return layout("Tải dữ liệu", f"""<h1>Tải dữ liệu</h1>
<p class="lede">Các file N-Triples và Turtle của bộ dữ liệu, giấy phép CC BY-SA 4.0 (kế thừa từ Wikipedia).
Mô tả bộ dữ liệu: <a href="/void/dataset">VoID</a>.</p><table>{rows}</table>""", "/dumps/")


@app.get("/dumps/{name}")
def dump(name: str):
    f = dump_files().get(name)
    if not f:
        return Response("Không có file này", status_code=404)
    mt = "text/turtle" if f.suffix == ".ttl" else "application/n-triples"
    return FileResponse(f, media_type=mt + "; charset=utf-8", filename=name)


# ------------------------------------------------------------------ chạy
def main():
    global STORE
    ap = argparse.ArgumentParser(description="Server Linked Data cho DBpedia tiếng Việt")
    ap.add_argument("--local", action="store_true", help="đọc thẳng file, không cần Fuseki")
    ap.add_argument("--endpoint", default=S.DEFAULT_ENDPOINT)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    t0 = time.time()
    STORE = S.open_store(a.local, a.endpoint)
    print(f"Nguồn dữ liệu: {STORE.label} ({time.time() - t0:.1f}s)")
    home_stats()
    print(f"Mở http://{a.host}:{a.port}/")
    import uvicorn
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
