"""The numeric doctrine — shared foundation for every pipeline stage.

Everything here is a law learned from a shipped disease (RUNLOG has the
autopsies); the functions encode the lesson, the museum tests pin it:

- ROW-WORLD TOLERANCE (run 112): the tolerance for tying a value to a row is
  the row's OWN world. An absolute 1.0 let "prior 1.15" corroborate a 0.94
  EPS row and net profit 3,831.3 was swapped in. Small rows tie at 0.5% or
  a cent; aggregate rows get an absolute base that absorbs statement
  rounding.
- YEAR-TOKEN FILTER (run 60): a financial value >= 1000 is printed WITH a
  thousands separator ('2,025'); a bare 4-digit 19xx/20xx token is a YEAR —
  column header or date — and poisons every prior-triangulation downstream
  if treated as data.
- NON-VACUOUS KINSHIP (run-B hardening): label kinship requires POSITIVE
  evidence. An empty content-word set confirms nothing — the vacuous-truth
  clause produced every hint-path poison measured. Short CJK labels compare
  by normalized substring containment.
- SCALE IS A SET, NEVER A GUESS (run 116): the only legal scale multipliers
  are the ones filings actually print (units, thousands, 万, millions, 亿).
  Scale is a property of a BLOCK, proven by reconciliation — never inferred
  from one number's magnitude.

Pure stdlib. No LLM, no I/O, importable anywhere (including local Python
3.9 with nothing installed).
"""
import re

# The only scale multipliers a CN/HK/US filing prints: units, thousands,
# 万 (1e4), millions, 亿 (1e8). Anything else is not a scale, it is an error.
SCALES = (1.0, 1e3, 1e4, 1e6, 1e8)

# Words that carry no identity on their own: overlap on these confirms nothing.
STOPWORDS = {"and", "of", "in", "the", "net", "total", "other", "for"}
# Their CJK cousins: structural words that name a POSITION in a table, not a
# thing — '其他' kinship-matched a payables row by substring and a bare
# '合计' line served a tier-2 join (both measured live, both poison).
CJK_STRUCTURAL = {"其他", "合计", "小计", "总计", "其中", "本期", "上期", "项目"}

# Number tokens as filings print them: optional parens (negative), thousands
# commas, decimals. Fullwidth forms are translated before matching.
_NUMTOK = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")
# A LINE'S ENUMERATOR IS NOT A NUMBER (DFE 2026-09-10: the fixed-asset note's
# '（1）上年年末余额 17,915,996.06 …' lost its label because '(1)' tokenised as
# a negative one and the label became empty — the opening and closing rows
# of every movement table were dropped). '(1)', '1.', '1、' before a label
# are the print's own numbering.
_ENUM = re.compile(r"^\s*(?:\(\s*\d{1,2}\s*\)|\d{1,2}\s*[.、．])\s*(?=[^\d\s(])")

_FULLWIDTH = str.maketrans("０１２３４５６７８９，．（）－", "0123456789,.()-")


_SPACES = "\u0020\u00a0\u2009\u202f"   # space, nbsp, thin space, narrow nbsp
_SPACE_GROUPED = re.compile("^\\d{1,3}(?:[" + _SPACES + ",]\\d{3})*(?:\\.\\d+)?$")


def parse_number(token):
    """One printed token -> float, or None.

    Handles thousands commas, parenthesised negatives, leading minus,
    fullwidth digits/punctuation, and SPACE-GROUPED digits ('48 168 255
    333.72' — scanned statements print thin-space grouping and the vision
    reader copies it verbatim; refusing it silently deleted a whole 2025
    equity block and left a 58.5 balance gap, measured live). Space
    merging happens only when every group is exactly 3 digits — the
    thousands invariant — and only HERE, on a single cell's token; text
    lines with several adjacent numbers go through line_numbers, which
    never merges across spaces. Returns None for anything that is not a
    single printed number.
    """
    if isinstance(token, (int, float)):
        return float(token)
    if token is None:
        return None
    t = str(token).translate(_FULLWIDTH).strip()
    neg = (t.startswith("(") and t.endswith(")")) or t.startswith("-")
    t = t.strip("()").lstrip("-").strip()
    if _SPACE_GROUPED.match(t):
        t = re.sub("[" + _SPACES + ",]", "", t)
    else:
        t = t.replace(",", "")
    if not t or not any(ch.isdigit() for ch in t):
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def line_numbers(line, skip_years=True):
    """All numbers on a printed line, in printed order.

    Year-token filter (run-60 law): a bare 4-digit 1990-2100 integer with no
    comma and no decimal point is a header/date, not data — real values that
    size are printed '2,025'. Parenthesised tokens come back negative.
    """
    out = []
    for m in _NUMTOK.finditer(_ENUM.sub("", str(line).translate(_FULLWIDTH), count=1)):
        tok = m.group(0)
        raw = tok.strip("()")
        if skip_years and "," not in raw and "." not in raw:
            bare = raw.lstrip("-")
            if bare.isdigit() and 1990 <= int(bare) <= 2100:
                continue
        v = parse_number(tok)
        if v is not None:
            out.append(v)
    return out


# A nil mark: a standalone dash with nothing after it but more nil marks.
# (A dash BETWEEN two printed numbers is ambiguous — 'Interest 1,234 - 200'
# is a nil column in a table and a subtraction in a sentence, and the text
# layer carries no column geometry to tell them apart — so only the
# unambiguous trailing nils are read. Reviewer 2026-09-16: reading every
# dash cost '88,018 — up 11% from 79,000' a phantom zero.)
_DASH_NIL = re.compile(r"(?<![0-9A-Za-z)])[-\u2013\u2014](?=(?:\s+[-\u2013\u2014])*\s*$)")


def line_cells(line, skip_years=True):
    """The printed numbers of a line WITH the nils that keep the columns
    aligned: a standalone dash (or en/em dash) printed after the line's
    figures, with nothing but further dashes behind it, is that column's
    nil and reads 0 — 'Other gain 5 460 -' prints 460 this year and nothing
    last year, and dropping the dash shifted every later column left. A dash
    before the first figure is punctuation in the label ('Hong Kong -
    electricity'), never a nil."""
    s = _ENUM.sub("", str(line).translate(_FULLWIDTH), count=1)
    toks = [(m.start(), m.group(0), True) for m in _NUMTOK.finditer(s)]
    toks += [(m.start(), m.group(0), False) for m in _DASH_NIL.finditer(s)]
    out, seen = [], False
    for _pos, tok, is_num in sorted(toks):
        if not is_num:
            if seen:
                out.append(0.0)
            continue
        raw = tok.strip("()")
        if skip_years and "," not in raw and "." not in raw:
            bare = raw.lstrip("-")
            if bare.isdigit() and 1990 <= int(bare) <= 2100:
                continue
        v = parse_number(tok)
        if v is not None:
            out.append(v)
            seen = True
    return out


def label_of(line):
    """The text before the first number token — the printed line label."""
    ln = _ENUM.sub("", str(line).translate(_FULLWIDTH), count=1)
    m = _NUMTOK.search(ln)
    lab = ln[:m.start()] if m else ln
    return lab.strip(" .|:–—-　")


def row_tol(prior_value, base=0.6):
    """Tolerance for tying a value to a row with this prior: the row's own
    world (run-112 law). Aggregate rows (|pv| >= 10) get `base` absolute to
    absorb statement rounding; per-share/ratio rows tie at 0.5% or a cent —
    an absolute 1.0 there accepts anything.
    """
    a = abs(prior_value) if isinstance(prior_value, (int, float)) else 0.0
    # a RATIO (|prior| < 1: a margin, a rate) ties relative-only — "a cent"
    # on 0.15 would be 6.7% of it (owner 2026-09-10: the tolerance must
    # never be wider on a percentage than on an amount)
    return max(a * 5e-3, base if a >= 10 else (0.01 if a >= 1 else 0.0))


def to_model_units(n, scale):
    """A printed number -> the model's units, at a PROVEN block scale.

    At scale 1 this is identity. At other scales only aggregate values
    convert: a CN statement page printing yuan (scale 1e6 to a millions
    model) prints every real aggregate >= scale/1000, while per-share
    figures, ratios and FX rates print small and are ALREADY in model units
    (EPS 1.15 is 1.15 in both worlds — dividing it by a million is a
    poison, not a conversion).
    """
    if not isinstance(n, (int, float)) or not scale or scale == 1:
        return n
    return n / scale if abs(n) >= scale / 1000 else n


_NOTE_REF = re.compile(r"[（(]?\s*(?:附注\s*)?[五六七八九十]\s*[（(]\s*[一二三四五六七八九十百]+\s*[)）]\s*[)）]?"
                       r"|\b(?:note|notes)\s*\d+[a-z]?\b", re.I)


# THE HOUSE GLOSSARY (CLAUDE.md, "Line-item mapping — the cascade"; owner
# ruling 2026-09-17). Synonyms are the FIRST rung of the cascade, and the
# coincidence gate must know them or it calls the department's own vocabulary a
# coincidence: 'Other jointly controlled entities' read off a line printed
# 'Joint ventures' is the same item, not a number that happened to match.
# Groups only — a pair is kin when BOTH labels land in the same group. Members
# are normalised phrases; extend as names recur (that is what the glossary is
# for). Associates is deliberately NOT in the JCE group: CLAUDE.md says watch
# that split, and a synonym that merges two different items is the dangerous
# mapping error the gate exists to catch.
SYNONYM_GROUPS = [
    {"revenue", "revenues", "turnover", "sales", "net sales", "营业收入", "营业总收入"},
    {"finance costs", "finance cost", "interest expense", "borrowing costs",
     "finance charges", "财务费用"},
    {"finance income", "interest income", "interest received"},
    {"joint ventures", "joint venture", "jointly controlled entities",
     "jointly controlled entity", "jces", "jce", "合营企业"},
    {"property plant and equipment", "ppe", "pp e", "fixed assets", "tangible fixed assets",
     "固定资产"},
    {"profit attributable to shareholders", "net profit attributable to owners",
     "profit for the year attributable to equity holders",
     "profit attributable to owners of the company", "归母净利润"},
    {"depreciation and amortisation", "depreciation and amortization", "d a", "da",
     "折旧和摊销", "折旧与摊销"},
    {"cash and cash equivalents", "cash and equivalents", "cash and bank balances",
     "货币资金"},
    {"effect of exchange rate changes", "currency adjustments", "exchange differences",
     "foreign exchange translation", "汇率变动影响"},
]


def synonymous(a, b):
    """Do these two labels name the same item in the HOUSE GLOSSARY? Both must
    land in the same group; a label that lands in none says nothing."""
    na, nb = norm_label(a), norm_label(b)
    if not na or not nb or na == nb:
        return bool(na) and na == nb
    for g in SYNONYM_GROUPS:
        if any(m in na for m in g) and any(m in nb for m in g):
            return True
    return False


def norm_label(s):
    """Script-aware normalizer: lowercase, keep latin + digits + CJK, collapse
    everything else to single spaces. CJK kept because CN filings ARE the
    primary corpus. PDF furniture is removed first (owner 2026-09-08 — the
    label map must survive formatting): full-width letters/digits become
    ASCII (NFKC), and a note reference glued to the label ('五（二十一）',
    'note 12') is not part of the item's name."""
    import unicodedata
    t = unicodedata.normalize("NFKC", str(s or ""))
    t = _NOTE_REF.sub(" ", t)
    return re.sub(r"[^a-z0-9一-鿿]+", " ", t.lower()).strip()


# WORDS THAT TELL TWO LINES APART (owner ruling 2026-09-17). Within a family
# the members are mutually exclusive: two labels that each carry a member, and
# carry DIFFERENT ones, name opposite things however much else they share --
# 'net cash from operating activities' and 'net cash from investing activities'
# share every other word, and kinship called them kin.
DISTINGUISHERS = [
    {"operating": ("operating", "operations", "经营"),
     "investing": ("investing", "investment", "投资"),
     "financing": ("financing", "筹资", "融资")},
    {"current": ("current", "流动"),
     "noncurrent": ("non current", "noncurrent", "non-current", "长期", "非流动")},
    {"receivable": ("receivable", "receivables", "应收"),
     "payable": ("payable", "payables", "应付")},
]


def _distinguished(na, nb):
    """Do these two labels carry DIFFERENT members of the same family? Then
    they are not kin, whatever else they share. A label carrying none of a
    family's words says nothing about that family."""
    for fam in DISTINGUISHERS:
        ha = {k for k, words in fam.items() if any(w in na for w in words)}
        hb = {k for k, words in fam.items() if any(w in nb for w in words)}
        # 'non current' contains 'current': the longer member owns its label
        if "noncurrent" in ha:
            ha.discard("current")
        if "noncurrent" in hb:
            hb.discard("current")
        if ha and hb and not (ha & hb):
            return True
    return False


def _stem(w):
    """A word's stem, for matching: the plural forms only. A stemmer that
    reaches further starts inventing kinship."""
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ses", "xes", "ches", "shes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def kinship(a, b):
    """Non-vacuous label kinship: POSITIVE evidence required.

    THE HOUSE GLOSSARY IS THE FIRST RUNG (owner ruling 2026-09-17): 'turnover'
    and 'revenue' share no word and are the same line, and CLAUDE.md's cascade
    says so -- a kinship that does not read the glossary calls the department's
    own vocabulary a coincidence. Words match on their STEMS, so 'revenues' is
    'revenue'. And the activity and direction words TELL LINES APART: operating
    / investing / financing, current / non-current, receivable / payable. Two
    labels carrying different members of one family are not kin however many
    other words they share.

    Languages with spaces: content-word overlap on stems (stopwords and <=2-char
    tokens carry no identity). CJK / short labels: normalized substring
    containment, both sides >= 2 chars. An empty content-word set confirms
    NOTHING — vacuous truth is how every hint-path poison got in.

    Kinship RANKS and CORROBORATES; it never creates a match on its own
    (kinship-only matches belong to Stage 3, not Stage 2).
    """
    na, nb = norm_label(a), norm_label(b)
    if not na or not nb:
        return False
    if _distinguished(na, nb):
        return False                      # opposite members of one family
    if synonymous(na, nb):
        return True                       # the house glossary, cascade rung 1
    import re as _re
    cjk = bool(_re.search(r"[\u4e00-\u9fff]", na + nb))
    if not cjk:
        wa = {_stem(w) for w in na.split() if w not in STOPWORDS and len(w) > 2}
        wb = {_stem(w) for w in nb.split() if w not in STOPWORDS and len(w) > 2}
        if wa and wb:
            return bool(wa & wb)
    sa, sb = na.replace(" ", ""), nb.replace(" ", "")
    if len(sa) < 2 or len(sb) < 2:
        return False
    if sa in CJK_STRUCTURAL or sb in CJK_STRUCTURAL:
        return False
    if sa in sb or sb in sa:
        return True
    # (the stem rule below was unreachable behind a bare return until
    # 2026-09-08 — bilingual model labels ('Dividend 现金分红') never
    # reached it)
    # CJK labels are one token: kinship is a shared stem of >= 4
    # characters (DFE 2026-09-08: '汇率变动对现金的影响' vs
    # '四、汇率变动对现金及现金等价物的影响'; '应收票据及应收账款' vs
    # '应收票据' — the word-overlap path never reached containment)
    short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    for n in range(len(short), 3, -1):
        for i in range(0, len(short) - n + 1):
            seg = short[i:i + n]
            if seg in CJK_STRUCTURAL:
                continue
            if seg in long_:
                return True
    return False


def model_unit_mult(units_text):
    """The model's stated units -> base-currency multiplier ('HK$ millions'
    -> 1e6; 'RMB 万元' -> 1e4). None when the text names no unit word."""
    import re as _re
    t = str(units_text or "").lower()
    hits = []
    for pat, mult in ((r"亿", 1e8), (r"千万", 1e7), (r"百万", 1e6), (r"万", 1e4), (r"千元|thousand|\bk\b|'000|000s", 1e3),
                      (r"billion|\bbn\b", 1e9), (r"million|\bmn\b|\bm\b|\bmm\b", 1e6)):
        m = _re.search(pat, t)
        if m:
            hits.append((m.start(), mult))
    # the model's unit is the first named ('HK$ million; shares in thousands' is a million model)
    return min(hits)[1] if hits else None


def prose_money_value(n, spec, page_scale=None):
    """A prose money figure (harvested in BASE currency units: 'HK$390
    million' -> 390,000,000) in the MODEL's units (owner 2026-09-15, CLP:
    390,000,000 landed in a HK$-million model as a one-off gain). The
    model's stated units convert it; without them the page's ratified
    scale is the fallback."""
    mult = model_unit_mult((spec or {}).get("units")) if isinstance(spec, dict) else None
    if isinstance(n, (int, float)) and mult:
        return n / mult
    return to_model_units(n, page_scale) if page_scale else n
