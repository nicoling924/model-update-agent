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


def kinship(a, b):
    """Non-vacuous label kinship: POSITIVE evidence required.

    Languages with spaces: content-word overlap (stopwords and <=2-char
    tokens carry no identity). CJK / short labels: normalized substring
    containment, both sides >= 2 chars. An empty content-word set confirms
    NOTHING — vacuous truth is how every hint-path poison got in.

    Kinship RANKS and CORROBORATES; it never creates a match on its own
    (kinship-only matches belong to Stage 3, not Stage 2).
    """
    na, nb = norm_label(a), norm_label(b)
    if not na or not nb:
        return False
    import re as _re
    cjk = bool(_re.search(r"[\u4e00-\u9fff]", na + nb))
    if not cjk:
        wa = {w for w in na.split() if w not in STOPWORDS and len(w) > 2}
        wb = {w for w in nb.split() if w not in STOPWORDS and len(w) > 2}
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
    for pat, mult in ((r"亿", 1e8), (r"千万", 1e7), (r"百万", 1e6), (r"万", 1e4), (r"千元|thousand|\bk\b|'000|000s", 1e3),
                      (r"billion|\bbn\b", 1e9), (r"million|\bmn\b|\bm\b|\bmm\b", 1e6)):
        if _re.search(pat, t):
            return mult
    return None


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
