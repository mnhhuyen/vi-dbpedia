"""
Bước 4 (phần 1) — Sinh liên kết owl:sameAs sang DBpedia tiếng Anh và Wikidata.

Nguồn liên kết (đã thu thập ở bước 2, không cần mạng):
  - liên kết liên ngôn ngữ của Wikipedia: bài tiếng Việt -> bài tiếng Anh
    => owl:sameAs <http://dbpedia.org/resource/Tên_bài_tiếng_Anh>
    (URI của DBpedia tiếng Anh sinh trực tiếp từ tiêu đề bài Wikipedia tiếng Anh)
  - mã Wikidata của bài: => owl:sameAs <http://www.wikidata.org/entity/Q...>

Đầu ra:
  output/sameas-dbpedia.nt    liên kết sang DBpedia tiếng Anh (chưa kiểm tra)
  output/sameas-wikidata.nt   liên kết sang Wikidata
  reports/link_summary.md     độ phủ liên kết, theo từng lớp

Bước tiếp theo: validate_links.py kiểm tra các liên kết DBpedia trên endpoint thật.

Cách chạy:
    python link.py
"""
import argparse
import gzip
import sys
from collections import Counter
from pathlib import Path

import yaml
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "transform"))
from transform import Namer, _iri_escape  # noqa: E402  (dùng chung quy tắc sinh URI với bước 3)
from parsers import nfc  # noqa: E402

DBR = "http://dbpedia.org/resource/"
WD = "http://www.wikidata.org/entity/"


def dbpedia_iri(en_title):
    t = nfc(en_title).strip().replace(" ", "_")
    return URIRef(DBR + _iri_escape(t[:1].upper() + t[1:]))


def read_tsv(path):
    out = {}
    if Path(path).exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                a, _, b = line.rstrip("\n").partition("\t")
                if a and b:
                    out[nfc(a)] = b.strip()
    else:
        print(f"[!] Không thấy {path}")
    return out


def main():
    ap = argparse.ArgumentParser()
    data = HERE.parent / "collect" / "data"
    tout = HERE.parent / "transform" / "output"
    ap.add_argument("--langlinks", default=str(data / "langlinks.tsv.gz"))
    ap.add_argument("--wikidata", default=str(data / "wikidata.tsv.gz"))
    ap.add_argument("--labels", default=str(tout / "labels.nt"))
    ap.add_argument("--types", default=str(tout / "instance-types.nt"))
    ap.add_argument("--mappings", default=str(HERE.parent / "transform" / "mappings.yaml"))
    ap.add_argument("--out", default=str(HERE / "output"))
    args = ap.parse_args()

    namer = Namer(yaml.safe_load(open(args.mappings, encoding="utf-8"))["base"])
    labels = Graph().parse(args.labels)
    ours = {URIRef(s) for s in labels.subjects()}
    types = Graph().parse(args.types)
    cls_of = {s: o for s, o in types.subject_objects(RDF.type)}

    en, wd = read_tsv(args.langlinks), read_tsv(args.wikidata)
    g_db, g_wd = Graph(), Graph()
    missing_subject = 0
    for title, en_title in en.items():
        s = namer.resource(title)
        if s not in ours:
            missing_subject += 1
            continue
        g_db.add((s, OWL.sameAs, dbpedia_iri(en_title)))
    for title, qid in wd.items():
        s = namer.resource(title)
        if s in ours and qid.startswith("Q"):
            g_wd.add((s, OWL.sameAs, URIRef(WD + qid)))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    g_db.serialize(out / "sameas-dbpedia.nt", format="nt", encoding="utf-8")
    g_wd.serialize(out / "sameas-wikidata.nt", format="nt", encoding="utf-8")

    # Báo cáo độ phủ
    has_db, has_wd = set(g_db.subjects()), set(g_wd.subjects())
    by_cls = Counter(cls_of.values())
    short = lambda u: str(u).rsplit("/", 1)[-1]
    rows = []
    for c, n in by_cls.most_common():
        members = [s for s, k in cls_of.items() if k == c]
        a = sum(s in has_db for s in members)
        b = sum(s in has_wd for s in members)
        rows.append(f"| `vio:{short(c)}` | {n} | {a} ({a / n:.0%}) | {b} ({b / n:.0%}) |")
    untyped = [s for s in ours if s not in cls_of]
    a = sum(s in has_db for s in untyped)
    b = sum(s in has_wd for s in untyped)
    if untyped:
        rows.append(f"| (không gán lớp) | {len(untyped)} | {a} ({a / len(untyped):.0%}) | "
                    f"{b} ({b / len(untyped):.0%}) |")
    md = ["# Liên kết sang DBpedia tiếng Anh và Wikidata", "",
          f"- Số tài nguyên: **{len(ours):,}**",
          f"- Có liên kết DBpedia tiếng Anh: **{len(has_db):,}** ({len(has_db) / len(ours):.1%})",
          f"- Có liên kết Wikidata: **{len(has_wd):,}** ({len(has_wd) / len(ours):.1%})",
          f"- Có ít nhất một liên kết ra ngoài: **{len(has_db | has_wd):,}** "
          f"({len(has_db | has_wd) / len(ours):.1%})", "",
          "## Theo lớp", "", "| Lớp | Số thực thể | Có DBpedia | Có Wikidata |", "|---|---|---|---|", *rows]
    if missing_subject:
        md += ["", f"_{missing_subject} liên kết bị bỏ vì bài không có trong dữ liệu bước 3._"]
    rep = HERE / "reports"
    rep.mkdir(exist_ok=True)
    (rep / "link_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
