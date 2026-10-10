from pathlib import Path
import csv
import gzip
import json
import re
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
NAVY = "#1F4E79"
BLUE = "#DCEAF7"
TEAL = "#DDF1ED"
GOLD = "#FFF0CF"
INK = "#243447"
MUTED = "#526477"
WHITE = "#FFFFFF"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def rounded(draw, box, fill, outline=NAVY, radius=24, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def centered(draw, box, lines, face, fill=INK, gap=8):
    x0, y0, x1, y1 = box
    sizes = [draw.textbbox((0, 0), line, font=face) for line in lines]
    total = sum(b[3] - b[1] for b in sizes) + gap * (len(lines) - 1)
    y = y0 + ((y1 - y0) - total) / 2
    for line, bounds in zip(lines, sizes):
        height = bounds[3] - bounds[1]
        width = bounds[2] - bounds[0]
        draw.text((x0 + ((x1 - x0) - width) / 2, y), line, font=face, fill=fill)
        y += height + gap


def arrow(draw, start, end, color=NAVY, width=6, head=18):
    draw.line((start, end), fill=color, width=width)
    import math
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    left = (end[0] - head * math.cos(angle - 0.55), end[1] - head * math.sin(angle - 0.55))
    right = (end[0] - head * math.cos(angle + 0.55), end[1] - head * math.sin(angle + 0.55))
    draw.polygon((end, left, right), fill=color)


def architecture():
    image = Image.new("RGB", (1800, 1040), "#F7F9FC")
    draw = ImageDraw.Draw(image)
    draw.text((90, 45), "KIẾN TRÚC XỬ LÝ DỮ LIỆU VI-DBPEDIA", font=font(42, True), fill=NAVY)
    nodes = [
        (80, 220, 380, 410, "Wikipedia tiếng Việt", "bài · infobox · revision", BLUE),
        (510, 220, 810, 410, "Thu thập", "MediaWiki API · snapshot", BLUE),
        (940, 220, 1240, 410, "Chuẩn hóa & mapping", "parsers.py · mappings.yaml", TEAL),
        (1370, 220, 1670, 410, "Sinh RDF", "labels · types · properties", TEAL),
    ]
    for x0, y0, x1, y1, title, sub, color in nodes:
        rounded(draw, (x0, y0, x1, y1), color)
        centered(draw, (x0 + 12, y0 + 20, x1 - 12, y0 + 115), [title], font(27, True))
        centered(draw, (x0 + 12, y0 + 112, x1 - 12, y1 - 12), [sub], font(21), MUTED)
    for x in (395, 825, 1255):
        arrow(draw, (x, 315), (x + 100, 315))
    lower = [
        (140, 620, 500, 825, "Ontology + SHACL", "mô hình và kiểm tra", GOLD),
        (720, 620, 1080, 825, "Liên kết + suy luận", "DBpedia · Wikidata · OWL RL", GOLD),
        (1300, 620, 1660, 825, "Fuseki + ứng dụng", "SPARQL · competency questions", BLUE),
    ]
    for x0, y0, x1, y1, title, sub, color in lower:
        rounded(draw, (x0, y0, x1, y1), color)
        centered(draw, (x0 + 10, y0 + 18, x1 - 10, y0 + 105), [title], font(26, True))
        centered(draw, (x0 + 10, y0 + 110, x1 - 10, y1 - 8), [sub], font(19), MUTED)
    arrow(draw, (1470, 430), (980, 590))
    arrow(draw, (520, 720), (700, 720))
    arrow(draw, (1100, 720), (1280, 720))
    draw.text((90, 940), "Luồng chính: thu thập → chuyển đổi → RDF → kiểm tra, liên kết, suy luận → truy vấn", font=font(23), fill=MUTED)
    image.save(ASSETS / "kien_truc.png", optimize=True)


def ontology():
    # Overview follows vio-ontology.ttl; it shows both class trees and the
    # declared domain relations without implying omitted classes do not exist.
    image = Image.new("RGB", (2200, 1780), "#F7F9FC")
    draw = ImageDraw.Draw(image)
    draw.text((80, 35), "ONTOLOGY VIO: GIÁO DỤC ĐẠI HỌC VÀ ĐƠN VỊ HÀNH CHÍNH",
              font=font(38, True), fill=NAVY)
    draw.text((95, 115), "Lớp và quan hệ chính khai báo trong vio-ontology.ttl",
              font=font(22), fill=MUTED)

    def node(box, label, color=TEAL, size=18):
        rounded(draw, box, color, radius=18, width=2)
        centered(draw, box, [label], font(size, True))

    # Education hierarchy: DBpedia anchor and Vietnamese specializations.
    draw.text((80, 185), "CƠ SỞ GIÁO DỤC ĐẠI HỌC", font=font(25, True), fill=NAVY)
    node((80, 250, 590, 330), "dbo:University", GOLD, 20)
    node((80, 385, 590, 465), "vio:CoSoGiaoDucDaiHoc", BLUE, 20)
    arrow(draw, (335, 335), (335, 378), color="#72869A", width=4, head=13)
    edu_x = [55, 350, 645]
    edu_names = ["vio:DaiHoc", "vio:TruongDaiHoc", "vio:HocVien"]
    for x, name in zip(edu_x, edu_names):
        node((x, 545, x + 270, 625), name)
        arrow(draw, (335, 470), (x + 135, 538), color="#72869A", width=4, head=13)
    for x, name in zip((55, 350), ("vio:DaiHocQuocGia", "vio:DaiHocVung")):
        node((x, 705, x + 270, 785), name, BLUE, 17)
        arrow(draw, (190, 630), (x + 135, 698), color="#72869A", width=4, head=13)
    draw.text((80, 815), "DaiHoc / TruongDaiHoc / HocVien: AllDisjointClasses",
              font=font(16), fill=MUTED)
    draw.text((80, 845), "DaiHocQuocGia / DaiHocVung: AllDisjointClasses",
              font=font(16), fill=MUTED)

    # Administrative hierarchy. Dashed semantic notes summarize union classes.
    draw.text((1100, 185), "ĐƠN VỊ HÀNH CHÍNH VIỆT NAM", font=font(25, True), fill=NAVY)
    node((1090, 250, 1640, 330), "dbo:GovernmentalAdministrativeRegion", GOLD, 17)
    node((1090, 385, 1640, 465), "vio:DonViHanhChinhVietNam", BLUE, 19)
    arrow(draw, (1365, 335), (1365, 378), color="#72869A", width=4, head=13)
    levels = [
        (1010, 535, "vio:DonViHanhChinhCapTinh", "vio:Tinh · vio:ThanhPhoTrucThuocTrungUong"),
        (1370, 535, "vio:DonViHanhChinhCapHuyen", "vio:Quan · vio:Huyen · vio:ThiXa · vio:ThanhPhoCapHuyen"),
        (1730, 535, "vio:DonViHanhChinhCapXa", "vio:Xa · vio:Phuong · vio:ThiTran · vio:DacKhu"),
    ]
    for x, y, parent, children in levels:
        node((x, y, x + 330, y + 90), parent, TEAL, 14)
        arrow(draw, (1365, 470), (x + 165, y - 8), color="#72869A", width=4, head=13)
        centered(draw, (x - 5, y + 100, x + 335, y + 155), [children], font(13), INK)
        centered(draw, (x - 5, y + 156, x + 335, y + 184), ["equivalentClass = unionOf"], font(12), MUTED)
    draw.text((1090, 755), "CapTinh / CapHuyen / CapXa: AllDisjointClasses",
              font=font(15), fill=MUTED)
    draw.text((1090, 785), "Mỗi tập union bên trên cũng khai báo disjoint classes",
              font=font(15), fill=MUTED)
    draw.text((1090, 815), "CapHuyen rdfs:subClassOf dbo:District",
              font=font(15), fill=MUTED)
    draw.text((1090, 850), "DonViHanhChinhVietNam: hasValue dbo:country dbr:Vietnam",
              font=font(15), fill=MUTED)
    draw.text((1090, 880), "CapHuyen / CapXa: someValuesFrom CapTinh qua thuocDonViHanhChinh",
              font=font(15), fill=MUTED)
    draw.text((1090, 910), "Tinh → dbo:Province · Thành phố / thành phố cấp huyện → dbo:City",
              font=font(15), fill=MUTED)
    draw.text((1090, 940), "Thị xã / thị trấn → dbo:Town; các datatype và ownership cũng được khai báo",
              font=font(15), fill=MUTED)

    # Cross-tree object properties and their declared semantics.
    draw.line((70, 1220, 2130, 1220), fill="#C7D1DB", width=2)
    draw.text((80, 1245), "CÁC QUAN HỆ ĐỐI TƯỢNG ĐÁNG CHÚ Ý", font=font(24, True), fill=NAVY)
    relation_rows = [
        (1285, "vio:laThanhVienCua", "CoSoGiaoDucDaiHoc → DaiHoc", "inverse: vio:coThanhVien · Functional · subPropertyOf dbo:parentOrganisation"),
        (1365, "vio:truSoTai", "dbo:Organisation → DonViHanhChinhVietNam", "subPropertyOf dbo:location · property chain: truSoTai / thuocDonViHanhChinh"),
        (1445, "vio:thuocDonViHanhChinh", "DonViHanhChinhVietNam → DonViHanhChinhVietNam", "Transitive · inverse: vio:coDonViTrucThuoc · subPropertyOf dbo:isPartOf"),
        (1525, "vio:duocSapNhapVao", "DonViHanhChinhVietNam → DonViHanhChinhVietNam", "inverse: vio:hinhThanhTuSapNhap · subPropertyOf dbo:successor"),
        (1605, "vio:trungTamHanhChinh", "DonViHanhChinhVietNam → DonViHanhChinhVietNam", "Quan hệ trung tâm hành chính; không dùng dbo:capital"),
    ]
    for y, prop, domain_range, semantics in relation_rows:
        rounded(draw, (80, y, 2120, y + 62), WHITE, outline="#C5D0DA", radius=12, width=2)
        draw.text((100, y + 8), prop, font=font(17, True), fill="#176B67")
        draw.text((650, y + 8), domain_range, font=font(16, True), fill=INK)
        draw.text((650, y + 34), semantics, font=font(14), fill=MUTED)
    draw.text((80, 1695), "Mũi tên xám liền: rdfs:subClassOf. Sơ đồ tóm lược các lớp; danh sách con thể hiện unionOf.",
              font=font(17), fill=MUTED)
    image.save(ASSETS / "ontology.png", optimize=True)

def snapshot_statistics():
    """Build a snapshot infographic from the collection and profiling reports."""
    collect = ROOT.parent / "collect"
    summary = json.loads((collect / "reports/collect_summary.json").read_text(encoding="utf-8"))
    records = [json.loads(line) for line in gzip.open(collect / "data/articles.jsonl.gz", "rt", encoding="utf-8")]
    with_infobox = int(re.search(r"Số bài có infobox: \*\*(\d+)\*", (collect / "reports/profile_summary.md").read_text(encoding="utf-8")).group(1))
    with (collect / "reports/infobox_templates.csv").open(encoding="utf-8-sig", newline="") as f:
        templates = list(csv.DictReader(f))
    n_articles = len(records)
    revision_complete = sum(bool(r.get("revision_id") and r.get("revision_timestamp")) for r in records)
    wikidata = int(summary["with_wikidata"])
    collected_date = summary["collected_at"][:10]

    image = Image.new("RGB", (1800, 1200), "#F5F8FC")
    draw = ImageDraw.Draw(image)
    draw.text((85, 55), "VI-DBPEDIA · SNAPSHOT THU THẬP", font=font(42, True), fill=NAVY)
    draw.text((88, 120), f"Dữ liệu Wikipedia tiếng Việt · ngày {collected_date} (UTC)", font=font(23), fill=MUTED)

    # Large headline total and four supporting metrics.
    rounded(draw, (80, 205, 820, 500), NAVY, outline=NAVY, radius=30, width=2)
    draw.text((130, 250), f"{n_articles:,}", font=font(112, True), fill=WHITE)
    draw.text((140, 390), "bài viết được thu thập", font=font(31, True), fill=WHITE)
    draw.text((140, 445), f"từ {summary['categories']} category đã duyệt", font=font(23), fill="#DCEAF7")

    cards = [
        (890, 205, 1660, 335, f"{summary['categories']}", "category đã duyệt"),
        (890, 365, 1660, 495, f"{revision_complete}/{n_articles}", "bài có revision ID và timestamp"),
        (80, 570, 820, 700, f"{with_infobox}/{n_articles}  ·  {with_infobox/n_articles:.1%}", "bài phát hiện có infobox"),
        (890, 570, 1660, 700, f"{len(templates)}", "tên template infobox khác nhau"),
        (80, 730, 820, 860, f"{wikidata}/{n_articles}  ·  {wikidata/n_articles:.1%}", "bài có Wikidata ID"),
    ]
    for x0, y0, x1, y1, value, label in cards:
        rounded(draw, (x0, y0, x1, y1), WHITE, outline="#C5D0DA", radius=22, width=2)
        draw.text((x0 + 28, y0 + 15), value, font=font(36, True), fill="#176B67")
        draw.text((x0 + 30, y0 + 78), label, font=font(21), fill=INK)

    # Compact visual comparison of infobox presence and Wikidata coverage.
    draw.text((90, 930), "ĐỘ PHỦ TRÊN 495 BÀI", font=font(23, True), fill=NAVY)
    bars = [("Có infobox", with_infobox, "#39A99A"), ("Có Wikidata ID", wikidata, "#5B8FC4")]
    for i, (label, value, color) in enumerate(bars):
        y = 985 + i * 60
        draw.text((95, y), label, font=font(19), fill=INK)
        x0, x1 = 330, 1330
        rounded(draw, (x0, y + 2, x1, y + 30), "#E1E8EF", outline="#E1E8EF", radius=13, width=1)
        width = int((x1 - x0) * value / n_articles)
        rounded(draw, (x0, y + 2, x0 + width, y + 30), color, outline=color, radius=13, width=1)
        draw.text((1360, y - 2), f"{value}/{n_articles}  ({value/n_articles:.1%})", font=font(18, True), fill=INK)

    draw.text((90, 1130), "Nguồn: collect_summary.json · articles.jsonl.gz · profile_summary.md · infobox_templates.csv",
              font=font(16), fill=MUTED)
    image.save(ASSETS / "snapshot_statistics.png", optimize=True)


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    architecture()
    ontology()
    snapshot_statistics()
    print("Generated report/assets/kien_truc.png, ontology.png and snapshot_statistics.png")
