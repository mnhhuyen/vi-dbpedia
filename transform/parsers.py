"""
Bộ chuẩn hoá giá trị infobox tiếng Việt -> giá trị RDF.

Giá trị trong infobox là wikitext "bẩn": có chú thích <ref>, liên kết [[...]],
template {{...}}, chú thích HTML <!-- -->, thẻ <br>, chữ đậm '''...'''.
Mỗi hàm parse_* nhận wikitext thô của MỘT tham số và trả về:
  - danh sách giá trị đã chuẩn hoá, hoặc
  - danh sách rỗng nếu không đọc được (giá trị thô vẫn được giữ ở tầng vip:).
"""
import re
import unicodedata

import mwparserfromhell

# ---------------------------------------------------------------------------
# Làm sạch chung
# ---------------------------------------------------------------------------
REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
BR_RE = re.compile(r"<br\s*/?>", re.I)

# Template mang nội dung cần giữ: tên (chữ thường) -> hàm lấy nội dung
DATE_TEMPLATES = ("ngày thành lập và tuổi", "start date and age", "start date", "ngày bắt đầu",
                  "ngày sinh", "ngày sinh và tuổi", "birth date", "birth date and age")
TEXT_TEMPLATES = {"màu chữ": 1, "color": 1, "nowrap": 0, "lang": 1, "langx": 1}  # vị trí tham số giữ lại
URL_TEMPLATES = ("url", "official website", "trang web chính thức", "website")
COUNTRY_TEMPLATES = {"vie": "Việt Nam", "vnm": "Việt Nam"}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def pre_clean(text):
    """Bỏ ref, chú thích HTML; <br> -> xuống dòng."""
    text = COMMENT_RE.sub("", text)
    text = REF_RE.sub("", text)
    return BR_RE.sub("\n", text)


def _tpl_name(t):
    return str(t.name).strip().lower().replace("_", " ")


def expand_templates(code):
    """Thay các template quen thuộc bằng nội dung văn bản, xoá các template còn lại."""
    for t in code.filter_templates(recursive=False):
        name = _tpl_name(t)
        repl = ""
        pos = [str(p.value).strip() for p in t.params if not p.showkey]
        if name in TEXT_TEMPLATES and len(pos) > TEXT_TEMPLATES[name]:
            repl = pos[TEXT_TEMPLATES[name]]
        elif name in COUNTRY_TEMPLATES:
            repl = COUNTRY_TEMPLATES[name]
        elif name in URL_TEMPLATES and pos:
            repl = pos[0]
        elif name.startswith(DATE_TEMPLATES) and len(pos) >= 1:
            repl = "/".join(reversed(pos[:3]))              # y|m|d -> d/m/y
        try:
            code.replace(t, repl)
        except ValueError:
            pass
    return code


def to_text(wikitext):
    """Wikitext -> văn bản thuần (liên kết lấy phần hiển thị)."""
    code = expand_templates(mwparserfromhell.parse(pre_clean(wikitext)))
    text = code.strip_code(normalize=True, collapse=True)
    text = text.replace("'''", "").replace("''", "")
    return nfc(re.sub(r"[ \t]+", " ", text).strip())


TITLE_WORDS = {  # liên kết trỏ tới học hàm/học vị, không phải tới người
    "ts", "pgs", "gs", "ths", "pgs.ts", "gs.ts", "tskh", "gs.tskh", "pgs.tskh", "tiến sĩ",
    "phó giáo sư", "giáo sư", "thạc sĩ", "cử nhân", "bác sĩ", "nhà giáo nhân dân",
    "nhà giáo ưu tú", "ngnd", "ngưt", "tiến sĩ khoa học", "kỹ sư",
}


# Học hàm, học vị, danh hiệu, chức danh đứng trước tên người: "PGS.TS.KTS.", "NGND,", "Đại tá"...
HONORIFIC_RE = re.compile(
    r"^(?:(?:g\.?s|p\.?g\.?s|t\.?s|tskh|th\.?s|kts|bs|bsck(?:ii|i|1|2)?|gvcc|ksvcc|ks|cn|ds|"
    r"ngnd|ngưt|ngut|nsưt|nsnd|ttnd|ttưt|"
    r"phó giáo sư(?: \(việt nam\))?|giáo sư|tiến sĩ khoa học|tiến sĩ|thạc sĩ|cử nhân|bác sĩ|kỹ sư|"
    r"nhà giáo nhân dân|nhà giáo ưu tú|thầy thuốc nhân dân|thầy thuốc ưu tú|nghệ sĩ ưu tú|"
    r"nhà thơ|nhà báo|đại tá|thượng tá|thiếu tướng|trung tướng|hòa thượng|giuse|bà)"
    r"(?![a-zà-ỹđ])[\s.,:\-]*)+", re.I)


def _is_honorific(s):
    s = s.strip()
    m = HONORIFIC_RE.match(s)
    return bool(s) and m is not None and m.end() == len(s)


def link_targets(wikitext):
    """Đích của các liên kết nội bộ [[Đích|chữ]], bỏ liên kết tới tập tin và học vị."""
    code = mwparserfromhell.parse(pre_clean(wikitext))
    out = []
    for l in code.filter_wikilinks():
        target = nfc(str(l.title).split("#")[0].strip())
        if not target or re.match(r"(?i)(tập tin|hình|file|image|thể loại|category)\s*:", target):
            continue
        if target.lower() in TITLE_WORDS or _is_honorific(target):
            continue
        out.append(target[:1].upper() + target[1:])
    return out


# ---------------------------------------------------------------------------
# Số
# ---------------------------------------------------------------------------
# Kiểu Việt Nam: dấu chấm phân cách hàng nghìn, dấu phẩy là dấu thập phân.
NUM_VI = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _vi_number(s):
    return float(s.replace(".", "").replace(",", "."))


EN_THOUSANDS = re.compile(r"\b\d{1,3}(?:,\d{3})+\b(?![.,]\d)")


def parse_int(wikitext):
    text = to_text(wikitext)
    # Số viết kiểu tiếng Anh "2,830" (dấu phẩy phân cách hàng nghìn) -> đổi về kiểu Việt
    text = EN_THOUSANDS.sub(lambda m: m.group().replace(",", "."), text)
    m = NUM_VI.search(text)
    if not m:
        return []
    v = _vi_number(m.group())
    return [int(v)] if v == int(v) and v >= 0 else []


UNIT_TO_M2 = [("km²", 1e6), ("km2", 1e6), ("ha", 1e4), ("hecta", 1e4), ("m²", 1.0), ("m2", 1.0)]


def parse_area_m2(wikitext, default_unit="km²"):
    """Diện tích -> mét vuông (quy ước của DBpedia cho dbo:areaTotal)."""
    text = to_text(wikitext)
    m = NUM_VI.search(text)
    if not m:
        return []
    rest = text[m.end():].strip().lower()
    factor = dict(UNIT_TO_M2)[default_unit]
    for unit, f in UNIT_TO_M2:
        if rest.startswith(unit):
            factor = f
            break
    return [_vi_number(m.group()) * factor]


def parse_decimal_point(wikitext):
    """Số thực viết theo kiểu quốc tế (dấu chấm thập phân), dùng cho toạ độ."""
    m = re.search(r"-?\d+(?:\.\d+)?", to_text(wikitext))
    return [float(m.group())] if m else []


DMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*°\s*(?:(\d+(?:\.\d+)?)\s*['′]\s*)?(?:(\d+(?:\.\d+)?)\s*[\"″]\s*)?([NSEWBĐTnsew])")
DEC_PAIR_RE = re.compile(r"(-?\d{1,2}\.\d+)\s*[,;]\s*(-?\d{1,3}\.\d+)")


def _valid(lat, lon):
    return [(lat, lon)] if -90 <= lat <= 90 and -180 <= lon <= 180 else []


def parse_coord(wikitext):
    """Toạ độ -> (vĩ, kinh). Hỗ trợ:
    {{Coord|10.37|105.43}} · {{Coord|10|52|6.5|N|106|47|46.4|E}} ·
    10°52'06.5"N 106°47'46.4"E · 10.8276, 106.7000"""
    code = mwparserfromhell.parse(pre_clean(wikitext))
    for t in code.filter_templates():
        if _tpl_name(t) == "coord":
            pos = [str(p.value).strip() for p in t.params if not p.showkey]
            try:
                hemi = [i for i, x in enumerate(pos) if x.upper() in ("N", "S", "E", "W")]
                if len(hemi) >= 2:                       # dạng độ|phút|giây|N|độ|phút|giây|E
                    a, b = hemi[0], hemi[1]
                    lat = sum(float(x) / 60 ** i for i, x in enumerate(pos[:a]))
                    lon = sum(float(x) / 60 ** i for i, x in enumerate(pos[a + 1:b]))
                    lat *= -1 if pos[a].upper() == "S" else 1
                    lon *= -1 if pos[b].upper() == "W" else 1
                    return _valid(lat, lon)
                return _valid(float(pos[0]), float(pos[1]))
            except (ValueError, IndexError):
                return []
    text = pre_clean(wikitext)
    dms = DMS_RE.findall(text)
    if len(dms) >= 2:
        vals = []
        for d, m, sec, h in dms[:2]:
            v = float(d) + float(m or 0) / 60 + float(sec or 0) / 3600
            vals.append(-v if h.upper() in ("S", "W") else v)
        return _valid(vals[0], vals[1])
    m = DEC_PAIR_RE.search(text)
    if m:
        return _valid(float(m.group(1)), float(m.group(2)))
    return []


# ---------------------------------------------------------------------------
# Ngày tháng
# ---------------------------------------------------------------------------
def _ymd(y, m, d):
    y, m, d = int(y), int(m), int(d)
    if 1 <= m <= 12 and 1 <= d <= 31 and 1 <= y <= 2100:
        return [(f"{y:04d}-{m:02d}-{d:02d}", "date")]
    return []


def parse_date(wikitext):
    """Trả về [(chuỗi, 'date')] hoặc [(năm, 'gYear')].

    Hỗ trợ: 2/7/1976 · 8-8-1966 · ngày 10 tháng 6 năm 1957 · 28 tháng 6, 1976 ·
    {{ngày thành lập và tuổi|1999|12|30}} · {{start date and age|1924|10|27}} · 1029
    """
    text = to_text(wikitext).lower()
    m = re.search(r"(\d{1,2})\s*tháng\s*(\d{1,2})\s*(?:năm|,)?\s*(\d{3,4})", text)
    if m:
        return _ymd(m.group(3), m.group(2), m.group(1))
    m = re.search(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{3,4})\b", text)
    if m:
        return _ymd(m.group(3), m.group(2), m.group(1))
    m = re.search(r"\b(\d{3,4})\b", text)
    if m and 1 <= int(m.group(1)) <= 2100:
        return [(f"{int(m.group(1)):04d}", "gYear")]
    return []


# ---------------------------------------------------------------------------
# Chuỗi, danh sách, URL, mã
# ---------------------------------------------------------------------------
def parse_text(wikitext, max_len=300):
    t = to_text(wikitext).strip(' "“”')
    return [t[:max_len]] if t else []


def parse_text_list(wikitext):
    """Tách nhiều giá trị (xuống dòng, dấu phẩy, dấu chấm phẩy, gạch đầu dòng)."""
    text = to_text(wikitext)
    parts = re.split(r"[\n;]|,(?!\d)|^\s*\*", text, flags=re.M)
    return [p.strip(" *•-") for p in parts if p.strip(" *•-")]


def parse_code(wikitext):
    """Mã ngắn: '38<ref..>' -> '38'; '{{Màu chữ|green|''DMT''}}' -> 'DMT'."""
    t = to_text(wikitext)
    m = re.match(r"[A-Za-z0-9ĐđÀ-ỹ\-]+", t)
    return [m.group()] if m else []


def parse_code_list(wikitext):
    return [c for c in parse_text_list(wikitext) if len(c) <= 30]


def parse_url(wikitext):
    # Liên kết ngoài dạng [https://... Trang chủ]: lấy địa chỉ, không lấy chữ hiển thị
    for el in mwparserfromhell.parse(pre_clean(wikitext)).filter_external_links():
        url = str(el.url).strip()
        if url.lower().startswith("http"):
            return [url]
    text = to_text(wikitext)
    m = re.search(r"(https?://[^\s\]|<>\"]+)|((?:www\.)?[a-z0-9\-]+(?:\.[a-z0-9\-]+)+(?:/[^\s\]|<>\"]*)?)",
                  text, re.I)
    if not m:
        return []
    url = m.group(0).rstrip(".,;)")
    return [url if url.lower().startswith("http") else "http://" + url]


def parse_links(wikitext):
    return link_targets(wikitext)


def parse_first_link(wikitext):
    return link_targets(wikitext)[:1]


NAME_WORD = r"[A-ZÀ-ỸĐ][a-zà-ỹđA-ZÀ-ỸĐ]*"


def parse_person_name(wikitext):
    """Tên người, bỏ học hàm/học vị/danh hiệu và ghi chú:
    'PGS.TS.KTS. Phạm Trọng Thuật' -> 'Phạm Trọng Thuật';
    '[[Giáo sư|GS]]. [[Tiến sĩ|TS]]. [[Nguyễn Hữu Tú]]' -> 'Nguyễn Hữu Tú';
    'TS. Đoàn Hoài Sơn<br>Quyền Hiệu trưởng' -> 'Đoàn Hoài Sơn'."""
    text = to_text(wikitext).replace("­", "")              # bỏ dấu gạch nối mềm
    for line in text.split("\n"):
        line = re.sub(r"\(.*?\)|\(.*$", "", line).strip(" .,;:-–")
        line = HONORIFIC_RE.sub("", line).strip(" .,;:-–")
        line = re.sub(r"(?i)[\s.,]+(tiến sĩ|ts)$", "", line)       # 'Nguyễn Văn Khải Tiến sĩ'
        if re.fullmatch(rf"{NAME_WORD}(?: {NAME_WORD}){{1,5}}", line):
            return [line]
    return []


def parse_person_link(wikitext):
    """Liên kết tới bài về người: chỉ nhận liên kết có đích trùng tên đã tách được,
    để bỏ liên kết tới học hàm ('[[GS. TS.]]'), cấp bậc ('[[Đại tá Quân đội...|Đại tá]]')
    hay đích viết dính học vị ('[[PGS.TS.Lê Tuấn Anh]]')."""
    name = parse_person_name(wikitext)
    links = [t.replace("­", "") for t in link_targets(wikitext)]
    return [t for t in links if name and t == name[0]][:1]


def parse_ownership(wikitext):
    """Loại hình -> một trong ba cá thể của vio:LoaiHinhSoHuu."""
    t = to_text(wikitext).lower() + " " + " ".join(link_targets(wikitext)).lower()
    if "vốn nước ngoài" in t or "vốn đầu tư nước ngoài" in t or "100% vốn" in t:
        return ["CoVonDauTuNuocNgoai"]
    if "tư thục" in t or "dân lập" in t or "private" in t:
        return ["TuThuc"]
    if "công lập" in t or "public" in t:
        return ["CongLap"]
    return []


PARSERS = {
    "int": parse_int, "area_m2": parse_area_m2, "float": parse_decimal_point, "coord": parse_coord,
    "date": parse_date, "text": parse_text, "text_list": parse_text_list, "code": parse_code,
    "code_list": parse_code_list, "url": parse_url, "links": parse_links,
    "first_link": parse_first_link, "ownership": parse_ownership, "person_name": parse_person_name,
    "person_link": parse_person_link,
}
