"""
Bước 2 (cách nhẹ) — Thu thập bài viết theo THỂ LOẠI qua MediaWiki API,
thay vì tải toàn bộ bản dump.

Chỉ tải những bài thuộc các thể loại bạn chọn (kèm thể loại con tới độ sâu cho
trước). Đầu ra cùng định dạng với collect_articles.py, nên các bước sau dùng chung:

  data/articles.jsonl.gz    {"id", "title", "text"}         -> bước 3
  data/langlinks.tsv.gz     tiêu đề tiếng Việt <TAB> tiêu đề tiếng Anh  -> bước 4
  data/wikidata.tsv.gz      tiêu đề tiếng Việt <TAB> mã Wikidata (Q...) -> bước 4
  data/source_categories.tsv.gz  tiêu đề <TAB> thể loại nơi tìm thấy bài -> bước 3
  reports/collect_summary.json, reports/categories_visited.txt

Cách chạy:
    pip install -r requirements.txt
    python collect_api.py                         # đọc danh sách thể loại từ categories.txt
    python collect_api.py --limit 50              # chạy thử với 50 bài
    python collect_api.py "Tỉnh của Việt Nam" --depth 0   # hoặc ghi thể loại trực tiếp

Trong categories.txt có thể ghi độ sâu riêng cho từng thể loại:  Tên thể loại | 0

Lưu ý:
  - Tên thể loại viết KHÔNG kèm tiền tố "Thể loại:". Kiểm tra tên chính xác trên
    vi.wikipedia.org trước khi chạy.
  - Thể loại con có thể "trôi" sang chủ đề khác (ví dụ thể loại về một tỉnh có thể
    chứa thể loại con về người). Xem reports/categories_visited.txt để kiểm tra,
    và giữ --depth nhỏ.
  - Wikimedia yêu cầu User-Agent có thông tin liên hệ: sửa biến USER_AGENT bên dưới.
"""
import argparse
import gzip
import json
import time
import unicodedata
from pathlib import Path

import requests

HERE = Path(__file__).parent
API = "https://vi.wikipedia.org/w/api.php"
USER_AGENT = "ViDBpediaCourseProject/0.1 (sinh vien; email-cua-ban@example.com)"
CAT_PREFIX = "Thể loại:"


def nfc(s):
    return unicodedata.normalize("NFC", s)


class Wiki:
    def __init__(self, session=None, pause=0.2):
        self.s = session or requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.pause = pause

    def query(self, **params):
        """Gọi action=query, tự xử lý 'continue', trả về từng trang kết quả."""
        params = {"action": "query", "format": "json", "formatversion": 2, "maxlag": 5, **params}
        cont = {}
        while True:
            data = None
            for attempt in range(6):
                try:
                    r = self.s.get(API, params={**params, **cont}, timeout=90)
                    data = r.json()
                except (requests.RequestException, ValueError) as e:
                    # Lỗi mạng tạm thời (mất kết nối, phản hồi bị cắt ngang...): chờ rồi thử lại
                    wait = 2 ** attempt
                    print(f"    lỗi mạng ({type(e).__name__}), thử lại sau {wait}s...")
                    time.sleep(wait)
                    continue
                if data.get("error", {}).get("code") == "maxlag":
                    time.sleep(5 * (attempt + 1))
                    continue
                break
            if data is None:
                raise RuntimeError("Không kết nối được tới Wikipedia sau nhiều lần thử. "
                                   "Chạy lại lệnh: script sẽ tải tiếp từ chỗ dừng.")
            if "error" in data:
                raise RuntimeError(data["error"])
            yield data.get("query", {})
            time.sleep(self.pause)
            if "continue" not in data:
                return
            cont = data["continue"]

    def category_members(self, category):
        """Trả về (bài viết, thể loại con) trực tiếp của một thể loại."""
        pages, subcats = [], []
        for q in self.query(list="categorymembers", cmtitle=CAT_PREFIX + category,
                            cmtype="page|subcat", cmnamespace="0|14", cmlimit="max"):
            for m in q.get("categorymembers", []):
                if m["ns"] == 14:
                    subcats.append(nfc(m["title"])[len(CAT_PREFIX):])
                else:
                    pages.append((m["pageid"], nfc(m["title"])))
        return pages, subcats

    def category_info(self, category):
        """Kiểm tra thể loại có tồn tại không, và có bao nhiêu bài / thể loại con."""
        for q in self.query(titles=CAT_PREFIX + category, prop="categoryinfo"):
            for p in q.get("pages", []):
                if p.get("missing"):
                    return None
                return p.get("categoryinfo", {"pages": 0, "subcats": 0})
        return None

    def search_categories(self, text, limit=10):
        """Tìm tên thể loại gần đúng (dùng khi không biết tên chính xác)."""
        for q in self.query(list="search", srsearch=text, srnamespace=14, srlimit=limit):
            return [nfc(r["title"])[len(CAT_PREFIX):] for r in q.get("search", [])]
        return []

    def categories_of(self, title):
        """Các thể loại (không ẩn) của một bài viết."""
        cats = []
        for q in self.query(titles=title, prop="categories", clshow="!hidden", cllimit="max"):
            for p in q.get("pages", []):
                cats += [nfc(c["title"])[len(CAT_PREFIX):] for c in p.get("categories", [])]
        return cats

    def fetch(self, pageids):
        """Lấy wikitext, liên kết sang tiếng Anh và mã Wikidata cho tối đa 50 trang."""
        result = {}
        for q in self.query(pageids="|".join(map(str, pageids)),
                            prop="revisions|langlinks|pageprops", rvprop="content", rvslots="main",
                            lllang="en", lllimit="max", ppprop="wikibase_item"):
            for p in q.get("pages", []):
                rec = result.setdefault(p["pageid"], {"id": p["pageid"], "title": nfc(p["title"]),
                                                      "text": None, "en": None, "qid": None})
                revs = p.get("revisions")
                if revs:
                    rec["text"] = revs[0]["slots"]["main"].get("content", "")
                for ll in p.get("langlinks", []):
                    rec["en"] = nfc(ll["title"])
                if "pageprops" in p:
                    rec["qid"] = p["pageprops"].get("wikibase_item")
        return list(result.values())


def crawl(wiki, roots, depth, log):
    """Duyệt thể loại theo chiều rộng, gom các bài viết.
    roots: danh sách (tên thể loại, độ sâu tối đa riêng hoặc None = dùng depth chung)."""
    seen_cats, pages, found_in = set(), {}, {}
    frontier = [(c, 0, depth if d is None else d) for c, d in roots]
    while frontier:
        cat, d, maxd = frontier.pop(0)
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        members, subcats = wiki.category_members(cat)
        log.write(f"{'  ' * d}{cat}  ({len(members)} bài, {len(subcats)} thể loại con)\n")
        for pid, title in members:
            pages.setdefault(pid, title)
            found_in.setdefault(pid, set()).add(cat)
        if d < maxd:
            frontier += [(s, d + 1, maxd) for s in subcats]
    crawl.found_in = found_in          # thể loại nơi tìm thấy mỗi bài (dùng ở bước 3)
    return pages, seen_cats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("categories", nargs="*",
                    help='tên thể loại, ví dụ "Tỉnh Việt Nam"; bỏ trống để đọc từ --file')
    ap.add_argument("--file", default=str(HERE / "categories.txt"),
                    help="file danh sách thể loại, mỗi dòng một tên, dòng bắt đầu bằng # là chú thích")
    ap.add_argument("--find", metavar="TỪ_KHOÁ",
                    help="tìm tên thể loại chứa từ khoá rồi thoát, ví dụ --find \"tỉnh Việt Nam\"")
    ap.add_argument("--categories-of", metavar="TÊN_BÀI",
                    help="in các thể loại của một bài rồi thoát, ví dụ --categories-of \"Thái Nguyên\"")
    ap.add_argument("--depth", type=int, default=1, help="độ sâu thể loại con (mặc định 1)")
    ap.add_argument("--limit", type=int, default=0, help="chỉ tải N bài đầu (để chạy thử)")
    ap.add_argument("--out", default=str(HERE / "data"))
    ap.add_argument("--batch", type=int, default=20, help="số bài mỗi lần gọi API (tối đa 50)")
    ap.add_argument("--fresh", action="store_true",
                    help="tải lại từ đầu (mặc định: giữ các bài đã tải, chỉ tải phần còn thiếu)")
    args = ap.parse_args()

    out, rep = Path(args.out), HERE / "reports"
    out.mkdir(parents=True, exist_ok=True)
    rep.mkdir(exist_ok=True)
    if args.find or args.categories_of:
        wiki = Wiki()
        if args.find:
            print(f"Thể loại khớp với '{args.find}':")
            for c in wiki.search_categories(args.find, 20):
                info = wiki.category_info(c) or {}
                print(f"  {c}  ({info.get('pages', 0)} bài, {info.get('subcats', 0)} thể loại con)")
        if args.categories_of:
            print(f"Thể loại của bài '{args.categories_of}':")
            for c in wiki.categories_of(nfc(args.categories_of)):
                print("  " + c)
        return

    lines = args.categories or [
        l.strip() for l in Path(args.file).read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")]
    roots = []                                   # (tên, độ sâu riêng hoặc None)
    for l in lines:
        name, _, d = l.partition("|")
        roots.append((nfc(name.strip().removeprefix(CAT_PREFIX)), int(d) if d.strip() else None))
    if not roots:
        ap.error("chưa có thể loại nào: ghi trong categories.txt hoặc truyền trên dòng lệnh")
    print("Thể loại gốc:", ", ".join(c for c, _ in roots))
    wiki = Wiki()

    valid = []
    for c, d in roots:
        info = wiki.category_info(c)
        if info is None or (info.get("pages", 0) == 0 and info.get("subcats", 0) == 0):
            why = "không tồn tại" if info is None else "trống"
            print(f"\n[!] Thể loại '{c}' {why} trên Wikipedia tiếng Việt. Một số tên gần đúng:")
            for sug in wiki.search_categories(c, 8):
                print(f"      {sug}")
        else:
            dd = args.depth if d is None else d
            print(f"  ✓ {c}: {info.get('pages', 0)} bài, {info.get('subcats', 0)} thể loại con (độ sâu {dd})")
            valid.append((c, d))
    if not valid:
        print("\nKhông có thể loại hợp lệ. Sửa categories.txt rồi chạy lại.")
        return
    roots = valid

    with open(rep / "categories_visited.txt", "w", encoding="utf-8") as log:
        pages, cats = crawl(wiki, roots, args.depth, log)
    ids = sorted(pages)[: args.limit or None]
    # Ghi lại bài nào được tìm thấy trong thể loại nào: bước 3 dùng để phân biệt
    # tỉnh / thành phố trực thuộc trung ương / tỉnh cũ (cùng dùng một template infobox).
    with gzip.open(out / "source_categories.tsv.gz", "wt", encoding="utf-8") as fsc:
        for pid in ids:
            for c in sorted(crawl.found_in.get(pid, ())):
                fsc.write(f"{pages[pid]}\t{c}\n")
    print(f"{len(cats)} thể loại, {len(pages)} bài; sẽ tải {len(ids)} bài")

    # Trong lúc tải, ghi ra file văn bản thường (*.part) theo từng đợt, để nếu bị ngắt
    # giữa chừng thì lần chạy sau tải tiếp được. Tải xong mới nén thành .gz.
    names = ["articles.jsonl", "langlinks.tsv", "wikidata.tsv"]
    parts = {n: out / (n + ".part") for n in names}
    if args.fresh:
        for p in parts.values():
            p.unlink(missing_ok=True)
    else:
        for n, p in parts.items():                     # tiếp tục từ bản .gz của lần chạy trước
            gz = out / (n + ".gz")
            if gz.exists() and not p.exists():
                with gzip.open(gz, "rt", encoding="utf-8") as fi, open(p, "w", encoding="utf-8") as fo:
                    fo.write(fi.read())

    done = set()
    if parts["articles.jsonl"].exists():
        good = []
        for line in parts["articles.jsonl"].read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
                good.append(line)
            except (json.JSONDecodeError, KeyError):
                pass                                    # dòng cuối bị cắt dở khi lỗi: bỏ
        parts["articles.jsonl"].write_text("".join(l + "\n" for l in good), encoding="utf-8")
    todo = [i for i in ids if i not in done]
    if done:
        print(f"  đã có {len(done)} bài từ lần chạy trước, còn {len(todo)} bài cần tải")
    batch = max(1, min(args.batch, 50))

    missing = 0
    with open(parts["articles.jsonl"], "a", encoding="utf-8") as fa, \
         open(parts["langlinks.tsv"], "a", encoding="utf-8") as fl, \
         open(parts["wikidata.tsv"], "a", encoding="utf-8") as fw:
        for i in range(0, len(todo), batch):
            recs = wiki.fetch(todo[i:i + batch])        # tải xong cả đợt rồi mới ghi
            for rec in recs:
                if not rec["text"]:
                    missing += 1
                    continue
                fa.write(json.dumps({"id": rec["id"], "title": rec["title"], "text": rec["text"]},
                                    ensure_ascii=False) + "\n")
                if rec["en"]:
                    fl.write(f"{rec['title']}\t{rec['en']}\n")
                if rec["qid"]:
                    fw.write(f"{rec['title']}\t{rec['qid']}\n")
            fa.flush(); fl.flush(); fw.flush()
            print(f"  đã tải {len(done) + min(i + batch, len(todo))}/{len(ids)}")

    # Nén thành .gz (bỏ dòng trùng nếu có) và xoá file tạm
    counts = {}
    for n, p in parts.items():
        lines = list(dict.fromkeys(l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()))
        with gzip.open(out / (n + ".gz"), "wt", encoding="utf-8") as fo:
            fo.write("".join(l + "\n" for l in lines))
        counts[n] = len(lines)
        p.unlink()

    stats = {"categories": len(cats), "articles": counts["articles.jsonl"],
             "with_en_link": counts["langlinks.tsv"], "with_wikidata": counts["wikidata.tsv"],
             "missing_text_this_run": missing}
    stats["root_categories"] = [{"category": c, "depth": args.depth if d is None else d} for c, d in roots]
    stats["depth"] = args.depth
    (rep / "collect_summary.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()