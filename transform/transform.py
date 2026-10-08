"""
Bước 3 — Chuyển bài viết Wikipedia tiếng Việt thành RDF (Linked Data 4 sao).

Đầu vào (từ bước 2):
  ../collect/data/articles.jsonl.gz
  ../collect/data/source_categories.tsv.gz   (để phân biệt tỉnh / thành phố / tỉnh cũ)

Đầu ra (thư mục output/), chia theo loại dữ liệu giống DBpedia:
  Tầng chung — mọi bài:
    labels.nt               rdfs:label (tên bài, @vi)
    abstracts.nt            dbo:abstract (đoạn mở đầu, @vi)
    categories.nt           dct:subject -> tài nguyên thể loại
    page-links.nt           dbo:wikiPageWikiLink (liên kết giữa các bài)
    provenance.nt           foaf:isPrimaryTopicOf, prov:wasDerivedFrom, dbo:wikiPageID
    infobox-properties.nt   toàn bộ infobox ở dạng thô (vip:)
  Tầng mapping — bài có infobox được map:
    instance-types.nt       rdf:type theo mappings.yaml
    mappingbased-literals.nt  thuộc tính dữ liệu đã chuẩn hoá
    mappingbased-objects.nt   quan hệ tới tài nguyên khác
    geo-coordinates.nt      geo:lat / geo:long
  Mô tả bộ dữ liệu:
    void.ttl                metadata (VoID): nguồn, giấy phép, số triple, từ vựng sử dụng
  Báo cáo:
    reports/transform_summary.md   số liệu cho báo cáo, độ phủ từng thuộc tính

Cách chạy:
    pip install -r requirements.txt
    python transform.py
    python transform.py --articles đường/dẫn/articles.jsonl.gz --limit 50
"""
import argparse
import datetime as dt
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import mwparserfromhell
import yaml
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, FOAF, OWL, PROV, RDF, RDFS, VOID, XSD

from parsers import PARSERS, link_targets, nfc, pre_clean, to_text

HERE = Path(__file__).parent
DBO = Namespace("http://dbpedia.org/ontology/")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
WIKI = "https://vi.wikipedia.org/wiki/"
INFOBOX_PREFIXES = ("thông tin", "hộp thông tin", "infobox")
CATEGORY_RE = re.compile(r"\[\[\s*(?:Thể loại|Category)\s*:\s*([^\]|]+)", re.I)
SKIP_LINK = re.compile(r"(?i)^(tập tin|hình|file|image|thể loại|category|wikipedia|wp|bản mẫu|"
                       r"template|[a-z]{2,3}(-[a-z]+)?)\s*:")


# ---------------------------------------------------------------------------
# URI
# ---------------------------------------------------------------------------
class Namer:
    """Sinh URI theo quy ước DBpedia: dấu cách -> '_', giữ nguyên chữ tiếng Việt (IRI),
    chỉ mã hoá các ký tự không hợp lệ trong IRI."""

    def __init__(self, base):
        self.base = base.rstrip("/") + "/"
        self.VIR = Namespace(self.base + "resource/")
        self.VIP = Namespace(self.base + "property/")

    def resource(self, title):
        t = nfc(title).strip()
        t = t[:1].upper() + t[1:]
        return URIRef(self.VIR + _iri_escape(t.replace(" ", "_")))

    def category(self, name):
        return URIRef(self.VIR + _iri_escape("Thể_loại:" + nfc(name).strip().replace(" ", "_")))

    def raw_property(self, param):
        return URIRef(self.VIP + _iri_escape(re.sub(r"\s+", "_", nfc(param).strip())))


def _iri_escape(s):
    """Mã hoá phần trăm các ký tự cấm trong IRI (RFC 3987), giữ nguyên chữ Unicode."""
    out = []
    for ch in s:
        if ch in ' <>"{}|\\^`%?#[]' or ord(ch) < 0x21:
            out.append("".join(f"%{b:02X}" for b in ch.encode("utf-8")))
        else:
            out.append(ch)
    return "".join(out)


def wiki_url(title):
    return URIRef(WIKI + _iri_escape(nfc(title).replace(" ", "_")))


# ---------------------------------------------------------------------------
# Trích xuất từ wikitext
# ---------------------------------------------------------------------------
def norm_template(name):
    name = nfc(str(name)).strip()
    name = re.sub(r"(?i)^(Bản mẫu|Template)\s*:", "", name)
    name = re.sub(r"[\s_]+", " ", name).strip()
    return name[:1].upper() + name[1:] if name else name


def norm_param(name):
    return re.sub(r"\s+", " ", nfc(str(name))).strip().lower()


def infoboxes(code):
    """[(tên template, {tham số: wikitext})] của các infobox cấp ngoài cùng.
    Với template chung kiểu labelN/dataN, ghép cặp nhãn - dữ liệu."""
    out = []
    for t in code.filter_templates(recursive=False):
        name = norm_template(t.name)
        if not name.lower().startswith(INFOBOX_PREFIXES):
            continue
        params = {}
        for p in t.params:
            k = norm_param(p.name)
            if k and not k.isdigit():
                params[k] = str(p.value).strip()
        labelled = {}
        for k, v in params.items():
            m = re.fullmatch(r"label(\d+)", k)
            if m and f"data{m.group(1)}" in params:
                labelled[norm_param(to_text(v))] = params[f"data{m.group(1)}"]
        if labelled:
            params = {k: v for k, v in params.items() if not re.fullmatch(r"(label|data)\d+", k)}
            params.update(labelled)
        out.append((name, params))
    return out


def abstract(text, max_len=2000):
    """Đoạn mở đầu (trước tiêu đề mục đầu tiên), bỏ template, bảng, tập tin."""
    lead = re.split(r"\n==", text, maxsplit=1)[0]
    lead = re.sub(r"\{\|.*?\|\}", "", lead, flags=re.S)             # bảng
    code = mwparserfromhell.parse(pre_clean(lead))
    for t in code.filter_templates(recursive=False):
        try:
            code.remove(t)
        except ValueError:
            pass
    for l in code.filter_wikilinks():
        if SKIP_LINK.match(str(l.title).strip()):
            try:
                code.remove(l)
            except ValueError:
                pass
    plain = code.strip_code(normalize=True, collapse=True)
    paras = [re.sub(r"\s+", " ", p).strip() for p in plain.split("\n")]
    plain = " ".join(p for p in paras if p)
    plain = plain.replace("'''", "").replace("''", "").strip()
    return nfc(plain[:max_len].rsplit(" ", 1)[0] + "…" if len(plain) > max_len else plain)


def page_links(code):
    out = set()
    for l in code.filter_wikilinks():
        t = str(l.title).split("#")[0].strip()
        if t and not SKIP_LINK.match(t):
            out.add(nfc(t))
    return out


# ---------------------------------------------------------------------------
# Liên kết văn bản thuần tới tài nguyên (entity linking đơn giản)
# ---------------------------------------------------------------------------
GENERIC_PREFIX = re.compile(r"^(tỉnh|thành phố|tp\.?)\s+")


def norm_key(s):
    return re.sub(r"\s+", " ", nfc(s)).strip().lower()


class Resolver:
    """Từ điển 'chữ hiển thị -> bài' xây từ chính dữ liệu:
    - tiêu đề các bài đã thu thập;
    - chữ hiển thị của mọi liên kết [[Đích|chữ hiển thị]] trong các bài.
    Dùng khi tham số infobox ghi tên bằng chữ thường, không có liên kết
    (ví dụ 'Thành Phố Hồ Chí Minh', 'tỉnh Nghệ An', 'Bộ Giáo Dục và Đào Tạo')."""

    def __init__(self):
        self.titles, self.anchors = {}, defaultdict(Counter)

    def add_title(self, title):
        self.titles[norm_key(title)] = title

    def add_links(self, code):
        for l in code.filter_wikilinks():
            target = nfc(str(l.title).split("#")[0].strip())
            if not target or SKIP_LINK.match(target):
                continue
            target = target[:1].upper() + target[1:]
            shown = to_text(str(l.text)) if l.text else target
            self.anchors[norm_key(shown)][target] += 1
            self.anchors[norm_key(target)][target] += 1

    def resolve(self, text):
        key = norm_key(text)
        for k in (key, GENERIC_PREFIX.sub("", key)):
            if k in self.titles:
                return self.titles[k]
            if k in self.anchors:
                return self.anchors[k].most_common(1)[0][0]
        return None


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------
class Mapper:
    def __init__(self, cfg):
        self.cfg = cfg
        self.prefixes = {k: Namespace(v) for k, v in cfg["prefixes"].items()}
        self.templates = {norm_template(k): v for k, v in cfg["templates"].items()}
        self.skip_raw = {norm_param(p) for p in cfg.get("skip_raw_params", [])}

    def iri(self, qname):
        p, local = qname.split(":", 1)
        return self.prefixes[p][local]

    def classify(self, title, source_cats, boxes):
        """Lớp của bài theo luật đầu tiên khớp, xét lần lượt từng infobox có trong mappings."""
        low = title.lower()
        for name, _ in boxes:
            spec = self.templates.get(name)
            if not spec:
                continue
            for rule in spec.get("class_rules", []):
                ok = True
                if "source_category" in rule:
                    ok &= rule["source_category"] in source_cats
                if "title_in" in rule:
                    ok &= title in rule["title_in"]
                if "title_prefix" in rule:
                    ok &= low.startswith(rule["title_prefix"].lower())
                if "title_contains" in rule:
                    ok &= rule["title_contains"].lower() in low
                if ok:
                    return name, (self.iri(rule["class"]) if rule["class"] else None)
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--articles", default=str(HERE.parent / "collect" / "data" / "articles.jsonl.gz"))
    ap.add_argument("--source-categories",
                    default=str(HERE.parent / "collect" / "data" / "source_categories.tsv.gz"))
    ap.add_argument("--mappings", default=str(HERE / "mappings.yaml"))
    ap.add_argument("--ontology", default=str(HERE.parent / "ontology" / "vio-ontology.ttl"),
                    help="để biết lớp nào là lớp con của lớp nào (kiểm tra target_class)")
    ap.add_argument("--out", default=str(HERE / "output"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.mappings, encoding="utf-8"))
    mapper = Mapper(cfg)
    namer = Namer(cfg["base"])
    VIO = mapper.prefixes["vio"]

    # Cây lớp của ontology vio: (để biết vio:Tinh là một vio:DonViHanhChinhVietNam...)
    onto = Graph()
    if Path(args.ontology).exists():
        onto.parse(args.ontology)
    def superclasses(c):
        seen, stack = {c}, [c]
        while stack:
            for p in onto.objects(stack.pop(), RDFS.subClassOf):
                if isinstance(p, URIRef) and p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen

    source_cats = defaultdict(set)
    if Path(args.source_categories).exists():
        with gzip.open(args.source_categories, "rt", encoding="utf-8") as f:
            for line in f:
                title, _, cat = line.rstrip("\n").partition("\t")
                source_cats[nfc(title)].add(nfc(cat))
    else:
        print("[!] Không có source_categories.tsv.gz: không phân biệt được tỉnh / thành phố. "
              "Chạy lại collect_api.py (bản mới) để tạo file này.")

    # ---------------- Lượt 1: đọc bài, phân loại -------------------------------------------
    articles = []
    resolver = Resolver()
    with gzip.open(args.articles, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if args.limit and i >= args.limit:
                break
            a = json.loads(line)
            a["title"] = nfc(a["title"])
            a["code"] = mwparserfromhell.parse(a["text"])
            a["boxes"] = infoboxes(a["code"])
            a["mapped_template"], a["cls"] = mapper.classify(a["title"], source_cats[a["title"]], a["boxes"])
            resolver.add_title(a["title"])
            resolver.add_links(a["code"])
            articles.append(a)
    typed = {a["title"]: superclasses(a["cls"]) for a in articles if a["cls"] is not None}

    # ---------------- Lượt 2: sinh triple -----------------------------------------------------
    names = ["labels", "abstracts", "categories", "page-links", "provenance", "infobox-properties",
             "instance-types", "mappingbased-literals", "mappingbased-objects", "geo-coordinates"]
    G = {n: Graph() for n in names}
    cov_has, cov_ok = Counter(), Counter()      # độ phủ: (template, tham số) có mặt / chuẩn hoá được
    rejected = Counter()                        # đích bị loại do target_class / target_prefix
    class_count = Counter()
    failures = defaultdict(list)                # ví dụ giá trị không đọc được

    for a in articles:
        s = namer.resource(a["title"])
        G["labels"].add((s, RDFS.label, Literal(a["title"], lang="vi")))
        ab = abstract(a["text"])
        if ab:
            G["abstracts"].add((s, DBO.abstract, Literal(ab, lang="vi")))
        for c in sorted({nfc(c.strip()) for c in CATEGORY_RE.findall(a["text"])}):
            G["categories"].add((s, DCTERMS.subject, namer.category(c)))
        for t in page_links(a["code"]):
            G["page-links"].add((s, DBO.wikiPageWikiLink, namer.resource(t)))
        G["provenance"].add((s, FOAF.isPrimaryTopicOf, wiki_url(a["title"])))
        G["provenance"].add((s, PROV.wasDerivedFrom, wiki_url(a["title"])))
        G["provenance"].add((s, DBO.wikiPageID, Literal(a["id"], datatype=XSD.integer)))

        # Tầng thô: mọi tham số infobox
        for _, params in a["boxes"]:
            for k, v in params.items():
                if k in mapper.skip_raw or not v.strip():
                    continue
                p = namer.raw_property(k)
                links = link_targets(v)
                if links:
                    for t in links:
                        G["infobox-properties"].add((s, p, namer.resource(t)))
                else:
                    txt = to_text(v)
                    if txt:
                        G["infobox-properties"].add((s, p, Literal(txt[:500], lang="vi")))

        # Tầng mapping
        if a["cls"] is None:
            continue
        G["instance-types"].add((s, RDF.type, a["cls"]))
        class_count[a["cls"]] += 1
        spec = mapper.templates[a["mapped_template"]]
        params = dict(a["boxes"])[a["mapped_template"]]
        values = {}
        for param, m in (spec.get("properties") or {}).items():
            raw = params.get(norm_param(param), "")
            if not raw.strip():
                continue
            key = (a["mapped_template"], param)
            cov_has[key] += 1
            vals = PARSERS[m["parser"]](raw)
            if not vals and m.get("text_fallback"):
                # Không có liên kết: thử nối chữ thường với một bài đã biết
                # thử cả cụm trước ("Bộ Văn hoá, Thể thao và Du lịch"), rồi mới tách theo dấu phẩy
                whole = resolver.resolve(to_text(raw))
                vals = [whole] if whole else list(dict.fromkeys(
                    r for r in (resolver.resolve(t) for t in PARSERS["text_list"](raw)) if r))
            if not vals:
                if len(failures[key]) < 3:
                    failures[key].append(to_text(raw)[:60])
                continue
            emitted = False
            for v in vals:
                if m.get("property") == "geo":
                    G["geo-coordinates"].add((s, GEO.lat, Literal(v[0], datatype=XSD.float)))
                    G["geo-coordinates"].add((s, GEO.long, Literal(v[1], datatype=XSD.float)))
                    emitted = True
                    continue
                prop = mapper.iri(m["property"]) if "property" in m else None
                if m.get("object"):
                    if m.get("vio_individual"):
                        G["mappingbased-objects"].add((s, prop, VIO[v]))
                        emitted = True
                        continue
                    target = nfc(v)
                    if "routes" in m:                     # chọn thuộc tính theo loại đích
                        prop = next((mapper.iri(r["property"]) for r in m["routes"]
                                     if any(target.startswith(x) for x in r["target_prefix"])), None)
                        if prop is None:
                            rejected[(param, "route")] += 1
                            continue
                    if "target_prefix" in m and not any(target.startswith(x) for x in m["target_prefix"]):
                        rejected[(m.get("property", param), "prefix")] += 1
                        continue
                    if "target_class" in m and mapper.iri(m["target_class"]) not in typed.get(target, set()):
                        rejected[(m.get("property", param), "class")] += 1
                        continue
                    G["mappingbased-objects"].add((s, prop, namer.resource(target)))
                    emitted = True
                elif m.get("iri"):
                    G["mappingbased-objects"].add((s, prop, URIRef(_iri_escape(v))))
                    emitted = True
                elif m["parser"] == "date":
                    lex, kind = v
                    if kind == "date":
                        G["mappingbased-literals"].add((s, prop, Literal(lex, datatype=XSD.date)))
                    elif m.get("year_property"):          # chỉ đọc được năm -> thuộc tính năm
                        G["mappingbased-literals"].add((s, mapper.iri(m["year_property"]),
                                                        Literal(lex, datatype=XSD.gYear)))
                    else:                                  # ví dụ populationAsOf cần ngày đầy đủ
                        continue
                    emitted = True
                else:
                    dtype = mapper.iri(m["datatype"]) if m.get("datatype") else None
                    lit = Literal(v, lang=m["lang"]) if m.get("lang") else Literal(v, datatype=dtype)
                    G["mappingbased-literals"].add((s, prop, lit))
                    values[m["property"]] = v
                    emitted = True
            if emitted:
                cov_ok[key] += 1

        # Thuộc tính suy ra: mật độ dân số = dân số / diện tích (km²)
        if "dbo:populationTotal" in values and values.get("dbo:areaTotal"):
            dens = values["dbo:populationTotal"] / (values["dbo:areaTotal"] / 1e6)
            G["mappingbased-literals"].add((s, DBO.populationDensity, Literal(round(dens, 2), datatype=XSD.double)))

    # ---------------- Ghi file -----------------------------------------------------------------
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for n, g in G.items():
        g.serialize(out / f"{n}.nt", format="nt", encoding="utf-8")
        total += len(g)

    # VoID: mô tả bộ dữ liệu
    void = Graph()
    void.bind("void", VOID); void.bind("dcterms", DCTERMS)
    ds = URIRef(namer.base + "void/dataset")
    void.add((ds, RDF.type, VOID.Dataset))
    void.add((ds, DCTERMS.title, Literal("DBpedia tiếng Việt (bản thử nghiệm)", lang="vi")))
    void.add((ds, DCTERMS.source, URIRef("https://vi.wikipedia.org/")))
    void.add((ds, DCTERMS.license, URIRef("http://creativecommons.org/licenses/by-sa/3.0/")))
    void.add((ds, DCTERMS.created, Literal(dt.date.today().isoformat(), datatype=XSD.date)))
    void.add((ds, VOID.uriSpace, Literal(str(namer.VIR))))
    void.add((ds, VOID.triples, Literal(total, datatype=XSD.integer)))
    void.add((ds, VOID.entities, Literal(len(articles), datatype=XSD.integer)))
    for vocab in (str(DBO), str(VIO), str(GEO), str(FOAF), str(DCTERMS), str(PROV)):
        void.add((ds, VOID.vocabulary, URIRef(vocab)))
    for n, g in G.items():
        sub = URIRef(namer.base + f"void/{n}")
        void.add((ds, VOID.subset, sub))
        void.add((sub, RDF.type, VOID.Dataset))
        void.add((sub, VOID.dataDump, URIRef(namer.base + f"dumps/{n}.nt")))
        void.add((sub, VOID.triples, Literal(len(g), datatype=XSD.integer)))
    void.serialize(out / "void.ttl", format="turtle")

    # ---------------- Báo cáo -------------------------------------------------------------------
    rep = HERE / "reports"
    rep.mkdir(exist_ok=True)
    short = lambda u: str(u).replace(str(VIO), "vio:").replace(str(DBO), "dbo:")
    md = ["# Kết quả chuyển đổi sang RDF", "",
          f"- Số bài: **{len(articles):,}**",
          f"- Số bài được gán lớp (tầng mapping): **{sum(class_count.values()):,}**",
          f"- Tổng số triple: **{total:,}**", "",
          "## Số triple theo bộ dữ liệu", "", "| Bộ dữ liệu | Số triple |", "|---|---|",
          *[f"| {n} | {len(g):,} |" for n, g in G.items()], "",
          "## Số thực thể theo lớp", "", "| Lớp | Số thực thể |", "|---|---|",
          *[f"| `{short(c)}` | {n} |" for c, n in class_count.most_common()], "",
          "## Độ phủ mapping", "",
          "Cột *có tham số*: số bài có tham số đó; *chuẩn hoá được*: số bài đọc được giá trị hợp lệ.", "",
          "| Template | Tham số | Có tham số | Chuẩn hoá được | Tỷ lệ | Ví dụ không đọc được |",
          "|---|---|---|---|---|---|"]
    for (tpl, param), n in sorted(cov_has.items(), key=lambda x: (x[0][0], -x[1])):
        ok = cov_ok[(tpl, param)]
        ex = "; ".join(f"`{e}`" for e in failures[(tpl, param)])
        md.append(f"| {tpl} | {param} | {n} | {ok} | {ok / n:.0%} | {ex} |")
    if rejected:
        md += ["", "## Giá trị bị loại do kiểm tra đích", "",
               "Loại vì đích không có lớp yêu cầu (`class`), tiêu đề không khớp (`prefix`), "
               "hoặc không thuộc loại đích nào trong `routes` (`route`).", "",
               "| Thuộc tính | Lý do | Số lần |", "|---|---|---|",
               *[f"| `{p}` | {why} | {n} |" for (p, why), n in rejected.most_common()]]
    (rep / "transform_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:20]))
    print(f"\n... xem đầy đủ: {rep / 'transform_summary.md'}")


if __name__ == "__main__":
    main()
