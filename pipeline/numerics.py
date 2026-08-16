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

# Number tokens as filings print them: optional parens (negative), thousands
# commas, decimals. Fullwidth forms are translated before matching.
_NUMTOK = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")

_FULLWIDTH = str.maketrans("０１２３４５６７８９，．（）－", "0123456789,.()-")


def parse_number(token):
    """One printed token -> float, or None.

    Handles thousands commas, parenthesised negatives, leading minus,
    fullwidth digits/punctuation. Returns None for anything that is not a
    single printed number ('-', 'n/a', '', years are NOT filtered here —
    that is line_numbers' job, which has the context to know).
    """
    if isinstance(token, (int, float)):
        return float(token)
    if token is None:
        return None
    t = str(token).translate(_FULLWIDTH).strip()
    neg = (t.startswith("(") and t.endswith(")")) or t.startswith("-")
    t = t.strip("()").lstrip("-").replace(",", "")
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
    for m in _NUMTOK.finditer(str(line).translate(_FULLWIDTH)):
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
    ln = str(line).translate(_FULLWIDTH)
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
    return max(a * 5e-3, base if a >= 10 else 0.01)


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


def norm_label(s):
    """Script-aware normalizer: lowercase, keep latin + digits + CJK, collapse
    everything else to single spaces. CJK kept because CN filings ARE the
    primary corpus."""
    return re.sub(r"[^a-z0-9一-鿿]+", " ", str(s or "").lower()).strip()


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
    wa = {w for w in na.split() if w not in STOPWORDS and len(w) > 2}
    wb = {w for w in nb.split() if w not in STOPWORDS and len(w) > 2}
    if wa and wb:
        return bool(wa & wb)
    sa, sb = na.replace(" ", ""), nb.replace(" ", "")
    if len(sa) < 2 or len(sb) < 2:
        return False
    return sa in sb or sb in sa
