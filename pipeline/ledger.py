"""The evidence ledger — the contract between Stage 1 and everything after.

The council's architecture ruling, made concrete: documents are read ONCE
into a flat ledger of evidence items; every later stage consumes the ledger,
never the documents. An item is a printed line's worth of evidence with
enough structural metadata that a deterministic join can bind it WITHOUT
inventing table geometry:

    value(s), page, statement-face tag, table id, row order, column
    binding, unit dimension, scale hint — plus provenance (the verbatim
    printed line) so every workbook cell traces back to ink.

Items that lack structure (no table_id / row_ord) are NON-JOINABLE by
Stage 2 — they exist for Stage 3's regional reads, not for code to guess
with. The ledger serializes to JSON: pinned snapshots are the validation
protocol's spine (Stage 2-4 replay locally from a committed ledger in
seconds, no vision, no LLM).

Face tagging is DETERMINISTIC CODE, not LLM judgment: statement captions
claim pages; 母公司 / company-only pages are evicted and block caption
propagation onto them (the run-98 Driver-page poisoning: a parent-company
P&L admitted as the consolidated face). The LLM's only Stage-1 job is
transcription; structure is code's job.

Pure stdlib.
"""
import json
import re
from dataclasses import dataclass, asdict

from .numerics import norm_label

LEDGER_VERSION = 1

# Statement faces Stage 2 may join against. Equity-movement and segment
# pages are tagged (identifiable, Stage-3-readable) but are not join faces.
JOIN_FACES = ("pl", "bs", "cf")

_CN_FACES = (
    ("资产负债表", "bs"),
    ("财务状况表", "bs"),
    ("利润表", "pl"),
    ("损益表", "pl"),
    ("现金流量表", "cf"),
    ("所有者权益变动表", "equity"),
    ("股东权益变动表", "equity"),
)
_EN_FACES = (
    ("balance sheet", "bs"),
    ("statement of financial position", "bs"),
    ("income statement", "pl"),
    ("statement of profit or loss", "pl"),
    ("profit and loss account", "pl"),
    ("statement of cash flows", "cf"),
    ("cash flow statement", "cf"),
    ("statement of changes in equity", "equity"),
)
# A caption line naming BOTH a statement and the parent entity marks a
# company-only (unconsolidated) page: evicted, and eviction blocks caption
# propagation onto it.
_CN_PARENT = "母公司"
_EN_PARENT = ("of the company", "company statement", "company balance sheet",
              "company income statement")

_FACE_PROPAGATION = 3   # a caption governs up to this many continuation pages


def face_of_line(line):
    """(face, is_parent) for one printed line, or (None, False)."""
    low = str(line).lower()
    face = None
    for pat, f in _CN_FACES:
        if pat in line:
            face = f
            break
    if face is None:
        for pat, f in _EN_FACES:
            if pat in low:
                face = f
                break
    if face is None:
        return None, False
    parent = _CN_PARENT in line or any(p in low for p in _EN_PARENT)
    return face, parent


def tag_faces(page_lines):
    """{page: face} + {parent pages} from one document's printed lines.

    page_lines: iterable of (page_no, line). First caption on a page tags
    it; ANY parent caption on a page evicts the whole page (a page that
    prints even part of a company-only statement must not carry face
    authority). Captions govern continuation pages, but propagation stops
    at parent pages and at pages with their own caption.
    """
    tags, parents = {}, set()
    for pn, ln in page_lines:
        face, parent = face_of_line(ln)
        if face is None:
            continue
        if parent:
            parents.add(pn)
        elif pn not in tags:
            tags[pn] = face
    out = {pn: f for pn, f in tags.items() if pn not in parents}
    for pn in sorted(tags):
        if pn in parents:
            continue
        for k in range(1, _FACE_PROPAGATION + 1):
            nxt = pn + k
            if nxt in parents or nxt in tags:
                break
            out.setdefault(nxt, tags[pn])
    return out, parents


_FACE_ROW_PATTERNS = (
    ("bs", ("资产总计", "负债合计", "所有者权益合计", "负债和所有者权益",
            "流动资产合计", "非流动资产合计", "流动负债合计", "非流动负债合计",
            "total assets", "total liabilities", "total equity",
            "total current assets", "total non-current assets",
            "total current liabilities")),
    ("pl", ("营业总收入", "营业总成本", "净利润", "利润总额", "每股收益",
            "revenue", "profit for the year", "profit before tax",
            "earnings per share")),
    ("cf", ("经营活动产生的现金流量", "投资活动产生的现金流量",
            "筹资活动产生的现金流量", "现金及现金等价物",
            "operating activities", "investing activities",
            "financing activities")),
)


def face_from_row_labels(labels):
    """A statement page identifies itself by its OWN rows even when the
    caption is cropped or printed on an earlier page (scanned pages often
    transcribe a title of just '项目'). >= 2 pattern hits on one face and
    strictly more than any other face -> that face; anything weaker -> None.
    Structure of statements, not knowledge of a company — generic across
    languages by pattern table."""
    text = " | ".join(str(x).lower() for x in labels)
    scores = {}
    for face, pats in _FACE_ROW_PATTERNS:
        scores[face] = sum(1 for p in pats if p.lower() in text)
    best = max(scores, key=lambda f: scores[f])
    n = scores[best]
    if n >= 2 and all(scores[f] < n for f in scores if f != best):
        return best
    return None


# -- scale hints --------------------------------------------------------------

# Ordered: longer/larger markers first so 百万 wins over 万, '000 over 0.
_SCALE_MARKERS = (
    ("亿元", 1e8), ("亿", 1e8),
    ("百万元", 1e6), ("百万", 1e6), ("million", 1e6), ("millions", 1e6),
    ("万元", 1e4), ("万", 1e4),
    ("千元", 1e3), ("仟元", 1e3), ("thousand", 1e3), ("'000", 1e3),
    ("’000", 1e3), ("000s", 1e3),
    ("元", 1.0),
)
_UNIT_LINE = re.compile(
    r"单位|币种|currency|amounts?\s+(?:are\s+)?(?:expressed|stated)\s+in"
    r"|expressed\s+in|in\s+(?:rmb|hk\$|us\$|usd|hkd|cny)", re.IGNORECASE)


def parse_scale_hint(line):
    """A printed unit header -> scale multiplier, or None.

    Only lines that LOOK like unit declarations are read ('单位：人民币千元',
    "(Expressed in RMB millions)", "RMB'000") — a body line mentioning
    millions in prose must not set a table's scale. Returns one of SCALES.
    """
    ln = str(line).strip()
    if len(ln) > 80 or not _UNIT_LINE.search(ln):
        return None
    low = ln.lower()
    for marker, s in _SCALE_MARKERS:
        if marker in ln or marker in low:
            return s
    return None


# -- unit dimension -----------------------------------------------------------

_DIM_PATTERNS = (
    ("per_share", re.compile(r"每股|per share|元/股|元／股|eps\b", re.IGNORECASE)),
    ("ratio", re.compile(r"[率%％]|margin|ratio|percentage|同比|比例|增减", re.IGNORECASE)),
    ("energy", re.compile(r"兆瓦|千瓦|万千瓦|瓦时|发电量|装机|上网电量|售电量"
                          r"|\bm?w\s*h?\b|megawatt|gigawatt", re.IGNORECASE)),
    ("shares", re.compile(r"万股|亿股|股数|shares outstanding|number of shares",
                          re.IGNORECASE)),
)


def unit_dim_of(label):
    """Best-effort measure family from the printed label: per_share / ratio /
    energy / shares / unknown. Conservative — 'unknown' is a legal answer;
    a WRONG dimension is not. (A megawatt item must never look like money:
    run 115.)"""
    lab = str(label or "")
    for dim, pat in _DIM_PATTERNS:
        if pat.search(lab):
            return dim
    return "unknown"


# -- items --------------------------------------------------------------------

_MIN_LABEL_ALPHA = 3


def admissible_label(label):
    """A label an item may carry: >=4 chars with >=3 letters, OR >=2 CJK
    characters (CJK packs a word into two glyphs — 水电/核能/气电 are real
    segment rows, measured excluded by the latin-length rule). Pipe
    artifacts and bare number soup are not labels."""
    lab = str(label or "")
    if "|" in lab:
        return False
    cjk = sum(1 for ch in lab if "\u4e00" <= ch <= "\u9fff")
    if cjk >= 2:
        return True
    return len(lab) >= 4 and sum(ch.isalpha() for ch in lab) >= _MIN_LABEL_ALPHA


@dataclass
class Item:
    """One printed line's evidence, in DOCUMENT units (unconverted — scale is
    proven later, at block level, never per number)."""
    doc: str            # source document filename
    page: int           # 1-based page number within doc
    table_id: int       # contiguous table block on the page (0-based)
    row_ord: int        # geometric order within the PAGE (pre-filter), not list index
    label: str          # printed line label, verbatim (trimmed)
    nums: list          # ALL numbers on the line, printed order, document units
    stmt_face: str = None       # pl|bs|cf|equity|... or None (no face authority)
    unit_dim: str = "unknown"   # per_share|ratio|energy|shares|unknown
    scale_hint: float = None    # block's printed unit header, if one was found
    channel: str = "text"       # text (deterministic parse) | vision (LLM read)
    consensus: int = 1          # extraction passes agreeing (vision channel)
    disputed: bool = False      # kept but not consensus-stable — never joinable
    source_line: str = ""       # the verbatim printed line (audit trail)

    @property
    def item_id(self):
        return f"{self.doc}#p{self.page}#t{self.table_id}#r{self.row_ord}"

    @property
    def label_norm(self):
        return norm_label(self.label)

    def joinable(self):
        """Structural admission for Stage 2: a disputed item, an item without
        table structure, or an item with fewer than two numbers (no
        current+prior pair to tie) is Stage-3 material, not join material."""
        return (not self.disputed
                and self.table_id is not None and self.row_ord is not None
                and len(self.nums) >= 2
                and admissible_label(self.label))


class Ledger:
    """The evidence ledger: items + per-page face map + per-doc metadata."""

    def __init__(self):
        self.items = []                 # [Item]
        self.faces = {}                 # (doc, page) -> face
        self.parent_pages = set()       # (doc, page) evicted company-only pages
        self.doc_meta = {}              # doc -> {"pages": n, "scale_hint": s|None, ...}

    def add(self, item):
        self.items.append(item)
        return item

    def face(self, doc, page):
        return self.faces.get((doc, page))

    def join_pool(self):
        """Items eligible to even be CONSIDERED by Stage 2: structurally
        joinable AND on a statement-face page (face authority is a pool
        property — parent pages were never admitted to the map) AND not
        from a prior-period document."""
        bad = self.noncurrent_docs()
        return [it for it in self.items
                if it.joinable() and it.doc not in bad
                and self.faces.get((it.doc, it.page)) in JOIN_FACES]

    def classify_doc_periods(self, priors, deep_priors=None):
        """{doc: 'current'|'prior'|'unknown'} — deterministic, language-free.

        VINTAGE test: in every filing, the comparative column dominates the
        second number slot of a line. The question is which YEAR fills it.
        The current-period document's comparatives are the model's PRIOR
        year; a prior-period document's comparatives are the year BEFORE
        that (the deep priors — the negative key). Whichever vintage
        dominates a doc's second slots names its period. Slot-ORDER voting
        alone fails on real filings (opening-balance notes and five-year
        tables vote both ways — measured). Without deep priors every doc is
        'unknown' (safe: nothing is excluded on a guess). Cached."""
        if getattr(self, "_doc_periods", None) is not None:
            return self._doc_periods
        import bisect
        from .numerics import SCALES, to_model_units

        def _absset(vals):
            return {abs(v) for v in vals
                    if isinstance(v, (int, float)) and abs(v) > 100}

        P, D = _absset(priors), _absset(deep_priors or [])

        def _distinct(A, B):
            """Values of one vintage NOT present in the other — unmoved
            balances and shared subtotals carry no vintage signal (measured:
            with the full sets the two counts are near-equal everywhere)."""
            sb = sorted(B)
            out = []
            for a in A:
                i = bisect.bisect_left(sb, a * 0.995)
                if not any(abs(a - b) <= max(0.6, a * 5e-3)
                           for b in sb[max(0, i - 1):i + 3]):
                    out.append(a)
            return sorted(out)

        def make_ties(sorted_abs):
            def ties(n):
                # identity-grade window (0.6 absolute / 0.05% relative) —
                # same law as the vision checksum; resemblances vote nothing
                for s in SCALES:
                    if s > 1 and abs(n) < s / 1000:
                        continue
                    a = abs(to_model_units(n, s))
                    tol_a = max(0.6, a * 5e-4)
                    i = bisect.bisect_left(sorted_abs, a - tol_a - 1.0)
                    while i < len(sorted_abs) and sorted_abs[i] <= a + tol_a + 1.0:
                        if abs(a - sorted_abs[i]) <= max(0.6, sorted_abs[i] * 5e-4):
                            return True
                        i += 1
                return False
            return ties

        p_only, d_only = _distinct(P, D), _distinct(D, P)
        out = {}
        for doc in {it.doc for it in self.items}:
            if not p_only or not d_only:
                out[doc] = "unknown"
                continue
            tie_p, tie_d = make_ties(p_only), make_ties(d_only)
            n_prior = n_deep = 0
            for it in self.items:
                if it.doc != doc or len(it.nums) < 2:
                    continue
                second = it.nums[1]
                if tie_p(second):
                    n_prior += 1
                if tie_d(second):
                    n_deep += 1
            if n_prior >= 1.5 * max(n_deep, 1) and n_prior >= 5:
                out[doc] = "current"
            elif n_deep >= 1.5 * max(n_prior, 1) and n_deep >= 5:
                out[doc] = "prior"
            else:
                out[doc] = "unknown"
        # THE SLOT-SIDE VOTE (2026-09-01: the FY24 annual report scored
        # 'unknown' on the deep-prior vote and its comparative tables
        # poisoned candidates all night). The model KNOWS last year: in
        # a prior-period document the FIRST number of a line ties the
        # model's priors (their current year IS our prior); in a
        # current-period document the SECOND does. Whichever side
        # dominates names the vintage — language-free, filename-free.
        # PRIOR-VINTAGE TABLES (2026-09-01: the current RA's own FY24
        # comparative segment table fed junk compositions all night —
        # current DOC, prior-year TABLE). Same slot-side law at table
        # granularity: a table most of whose lines carry a model PRIOR
        # as their FIRST number is printing last year, whatever document
        # it lives in. Consumers exclude these from current-year
        # evidence pools.
        tie_all = make_ties(sorted(P)) if P else None
        self._pv_tables = set()
        if tie_all is not None:
            from collections import defaultdict
            per_table = defaultdict(lambda: [0, 0])
            for it in self.items:
                if len(it.nums) < 2 or it.table_id is None:
                    continue
                k = (it.doc, it.page, it.table_id)
                per_table[k][1] += 1
                if tie_all(it.nums[0]):
                    per_table[k][0] += 1
            for k, (nt, nl) in per_table.items():
                if nt >= 4 and nt / nl >= 0.5:
                    self._pv_tables.add(k)
        if tie_all is not None:
            for doc, k in list(out.items()):
                if k != "unknown":
                    continue
                n1 = n2 = nl = 0
                for it in self.items:
                    if it.doc != doc or len(it.nums) < 2:
                        continue
                    nl += 1
                    if tie_all(it.nums[0]):
                        n1 += 1
                    if tie_all(it.nums[1]):
                        n2 += 1
                if nl >= 20:
                    f1, f2 = n1 / nl, n2 / nl
                    if f1 >= 0.15 and f1 > 1.5 * f2:
                        out[doc] = "prior"
                    elif f2 >= 0.15 and f2 > 1.5 * f1:
                        out[doc] = "current"
        self._doc_periods = out
        return out

    def prior_period_docs(self):
        return {d for d, k in (getattr(self, "_doc_periods", None) or {}).items()
                if k == "prior"}

    def noncurrent_docs(self):
        """Docs that may NOT source current-year values: 'prior' ones,
        plus 'unknown'-vintage ones whenever at least one doc PROVED
        current (2026-09-01: the restated-comparative FY24 AR defeats
        every numeric vintage vote — restatement kills its ties — and
        its comparative tables poisoned candidates all night. Unknown
        vintage is context, never evidence, once a proven-current doc
        exists)."""
        periods = getattr(self, "_doc_periods", None) or {}
        if any(k == "current" for k in periods.values()):
            return {d for d, k in periods.items() if k != "current"}
        return self.prior_period_docs()

    # -- pinned-snapshot serialization ---------------------------------------

    def to_json(self):
        return json.dumps({
            "version": LEDGER_VERSION,
            "doc_meta": self.doc_meta,
            "faces": [[d, p, f] for (d, p), f in sorted(self.faces.items())],
            "parent_pages": [[d, p] for d, p in sorted(self.parent_pages)],
            "items": [asdict(it) for it in self.items],
        }, ensure_ascii=False, indent=1)

    @classmethod
    def from_json(cls, text):
        obj = json.loads(text)
        if obj.get("version") != LEDGER_VERSION:
            raise ValueError(f"ledger version {obj.get('version')!r} != {LEDGER_VERSION}")
        led = cls()
        led.doc_meta = obj.get("doc_meta") or {}
        led.faces = {(d, p): f for d, p, f in obj.get("faces") or []}
        led.parent_pages = {(d, p) for d, p in obj.get("parent_pages") or []}
        for d in obj.get("items") or []:
            led.items.append(Item(**d))
        return led

    def save(self, path):
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path):
        from pathlib import Path
        return cls.from_json(Path(path).read_text(encoding="utf-8"))
