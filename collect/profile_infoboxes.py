"""
Bước 2 — Khảo sát dữ liệu đã thu thập, làm cơ sở cho bảng mapping ở bước 3.

Trả lời các câu hỏi:
  - Bao nhiêu bài viết có infobox?
  - Những template infobox nào được dùng nhiều nhất?
  - Mỗi template có những tham số nào, mỗi tham số xuất hiện trong bao nhiêu bài,
    giá trị ví dụ trông như thế nào?
  - Có bao nhiêu bài thuộc các thể loại chứa từ khoá quan tâm (ví dụ "Chùa", "Đình")?
    -> giúp quyết định phạm vi dựa trên dữ liệu thật.

Output (thư mục reports/):
  profile_summary.md         tóm tắt, dùng trực tiếp cho báo cáo
  infobox_templates.csv      template, số bài, tỷ lệ
  infobox_params.csv         template, tham số, số bài có tham số, tỷ lệ, giá trị ví dụ
  all_templates_top.csv      200 template phổ biến nhất (kể cả không phải infobox),
                             để phát hiện infobox có tên không theo quy ước
  category_keywords.csv      từ khoá, số bài, các thể loại khớp nhiều nhất

Cách chạy:
    python profile_infoboxes.py
    python profile_infoboxes.py --limit 20000 --workers 4
    python profile_infoboxes.py --keywords Chùa Đình Đền Miếu "Trường đại học" Tỉnh
"""
import argparse
import csv
import gzip
import json
import re
import unicodedata
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

import mwparserfromhell

HERE = Path(__file__).parent

# Tiền tố thường gặp của template infobox trên Wikipedia tiếng Việt.
# Danh sách chỉ mang tính khởi đầu: xem all_templates_top.csv để bổ sung.
INFOBOX_PREFIXES = ("thông tin", "hộp thông tin", "infobox")
CATEGORY_RE = re.compile(r"\[\[\s*(?:Thể loại|Category)\s*:\s*([^\]|]+)", re.IGNORECASE)


def norm_template(name):
    """Chuẩn hoá tên template theo quy tắc của MediaWiki:
    bỏ tiền tố không gian tên, '_' = ' ', gộp khoảng trắng, chữ cái đầu không phân biệt hoa thường."""
    name = unicodedata.normalize("NFC", str(name)).strip()
    name = re.sub(r"^(Bản mẫu|Template)\s*:", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[\s_]+", " ", name).strip()
    return name[:1].upper() + name[1:] if name else name


def is_infobox(name):
    return name.lower().startswith(INFOBOX_PREFIXES)


def analyse(line):
    """Phân tích một bài viết (chạy trong tiến trình con)."""
    art = json.loads(line)
    try:
        code = mwparserfromhell.parse(art["text"])
        templates = code.filter_templates(recursive=False)
    except Exception:
        templates = []
    infoboxes, all_names = [], set()
    for t in templates:
        name = norm_template(t.name)
        if not name:
            continue
        all_names.add(name)
        if is_infobox(name):
            params = {}
            for p in t.params:
                key = re.sub(r"\s+", " ", str(p.name)).strip().lower()
                if key and not key.isdigit():
                    params[key] = str(p.value).strip()[:80]
            infoboxes.append((name, params))
    cats = [unicodedata.normalize("NFC", c).strip() for c in CATEGORY_RE.findall(art["text"])]
    return art["title"], infoboxes, sorted(all_names), cats


def read_lines(path, limit):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            yield line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--articles", default=str(HERE / "data" / "articles.jsonl.gz"))
    ap.add_argument("--limit", type=int, default=0, help="chỉ phân tích N bài đầu (để chạy thử)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--keywords", nargs="*",
                    default=["Tỉnh", "Huyện", "Xã", "Phường", "Trường đại học", "Học viện",
                             "Chùa", "Đình", "Đền", "Miếu", "Di tích"])
    args = ap.parse_args()

    n_articles = n_with_infobox = 0
    tpl_pages = Counter()                       # template -> số bài dùng nó
    param_pages = defaultdict(Counter)          # template -> tham số -> số bài
    param_example = defaultdict(dict)           # template -> tham số -> giá trị ví dụ
    tpl_example_title = {}
    all_tpl = Counter()
    kw_pages = Counter()
    kw_cats = defaultdict(Counter)

    with Pool(args.workers) as pool:
        for title, infoboxes, names, cats in pool.imap_unordered(
                analyse, read_lines(args.articles, args.limit), chunksize=200):
            n_articles += 1
            if infoboxes:
                n_with_infobox += 1
            for name in names:
                all_tpl[name] += 1
            for name, params in {n: p for n, p in infoboxes}.items():
                tpl_pages[name] += 1
                tpl_example_title.setdefault(name, title)
                for k, v in params.items():
                    param_pages[name][k] += 1
                    if v and k not in param_example[name]:
                        param_example[name][k] = v
            for kw in args.keywords:
                # Khớp ở ĐẦU tên thể loại, phân biệt hoa thường: "Đình tại Hà Nội" khớp "Đình",
                # còn "Gia đình Việt Nam" thì không. Vẫn có thể lẫn (ví dụ "Xã hội..." khớp "Xã"):
                # xem cột the_loai_khop_nhieu_nhat để đánh giá.
                matched = [c for c in cats if c == kw or c.startswith(kw + " ")]
                if matched:
                    kw_pages[kw] += 1
                    kw_cats[kw].update(matched)
            if n_articles % 50_000 == 0:
                print(f"  đã phân tích {n_articles:,} bài")

    rep = HERE / "reports"
    rep.mkdir(exist_ok=True)
    with open(rep / "infobox_templates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template", "so_bai", "ty_le_tren_bai_co_infobox", "bai_vi_du"])
        for name, n in tpl_pages.most_common():
            w.writerow([name, n, f"{n / max(n_with_infobox, 1):.2%}", tpl_example_title[name]])
    with open(rep / "infobox_params.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template", "tham_so", "so_bai", "ty_le_trong_template", "gia_tri_vi_du"])
        for name, n in tpl_pages.most_common():
            for k, c in param_pages[name].most_common():
                w.writerow([name, k, c, f"{c / n:.0%}", param_example[name].get(k, "")])
    with open(rep / "all_templates_top.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template", "so_bai", "nhan_dien_la_infobox"])
        for name, n in all_tpl.most_common(200):
            w.writerow([name, n, "có" if is_infobox(name) else ""])
    with open(rep / "category_keywords.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tu_khoa", "so_bai", "the_loai_khop_nhieu_nhat"])
        for kw in args.keywords:
            top = "; ".join(f"{c} ({n})" for c, n in kw_cats[kw].most_common(5))
            w.writerow([kw, kw_pages[kw], top])

    # Tóm tắt Markdown cho báo cáo
    cum, lines, ranked = 0, [], tpl_pages.most_common()
    for i, (name, n) in enumerate(ranked, 1):
        cum += n
        if i in (10, 20, 50, 100) or i == len(ranked):
            lines.append(f"| top {i} template | {cum / max(sum(tpl_pages.values()), 1):.1%} |")
    md = [
        "# Khảo sát dữ liệu Wikipedia tiếng Việt", "",
        f"- Số bài viết phân tích: **{n_articles:,}**",
        f"- Số bài có infobox: **{n_with_infobox:,}** ({n_with_infobox / max(n_articles, 1):.1%})",
        f"- Số template infobox khác nhau: **{len(tpl_pages):,}**", "",
        "## Độ phủ tích luỹ của các template phổ biến nhất", "",
        "| Nhóm | Tỷ lệ lượt dùng infobox được phủ |", "|---|---|", *lines, "",
        "## 20 template infobox phổ biến nhất", "",
        "| # | Template | Số bài | Bài ví dụ |", "|---|---|---|---|",
        *[f"| {i} | {name} | {n:,} | {tpl_example_title[name]} |"
          for i, (name, n) in enumerate(tpl_pages.most_common(20), 1)], "",
        "## Số bài theo từ khoá trong thể loại", "",
        "| Từ khoá | Số bài |", "|---|---|",
        *[f"| {kw} | {kw_pages[kw]:,} |" for kw in args.keywords], "",
    ]
    (rep / "profile_summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
