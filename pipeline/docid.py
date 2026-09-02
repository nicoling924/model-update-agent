"""DOCUMENT IDENTIFICATION — the first thing the agent does is say what it
is holding (owner ruling 2026-09-03, run-228 autopsy).

A person opens a filing and knows in two seconds: "this is the 2024
annual report", "this is the interim for the six months to June 2025".
The agent must do the same BEFORE any number is read, so that a mixed
bag of annual, interim and quarterly filings in one folder maps itself:

    period == the target period      -> CURRENT evidence
    an earlier period                -> PRIOR-column evidence only
                                        (restatement scan, on-demand lookup)
    a partial / later / unknown one  -> never a current-year source; listed
                                        for the analyst

Three readers, in order of authority:
  1. THE BRAIN — one bounded card per document over its first pages
     (document type, company, period end, months, comparatives).
  2. THE PRINTED PERIOD — deterministic patterns for the cover / title /
     "year ended 31 December 2024" / "截至2024年12月31日止年度" / "2024年
     年度报告" etc. The offline floor, and the check on the brain.
  3. THE NUMERIC VINTAGE VOTE (ledger.classify_doc_periods) — the
     backstop for documents that print no period the readers recognise
     (scans), and a tripwire: when it contradicts the reading, the
     document is set UNKNOWN and flagged rather than trusted.

The folder is never the authority; the document is.
"""
import re
from collections import Counter
from pathlib import Path

FIRST_PAGES = 8          # cover, contents, definitions — where a filing names itself

DOC_TYPES = ("annual report", "interim report", "quarterly report",
             "results announcement", "results presentation", "other")

_MONTHS_EN = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), 1)}
_WORD_MONTHS = {"three": 3, "six": 6, "nine": 9, "twelve": 12}
_CN_Q = {"一": 3, "1": 3, "二": 6, "2": 6, "三": 9, "3": 9, "四": 12, "4": 12}

# -- English -------------------------------------------------------------
_EN_YEAR_ENDED = re.compile(
    r"(?:financial\s+)?year\s+end(?:ed|ing)\s+(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"([A-Za-z]+),?\s+(\d{4})", re.I)
_EN_MONTHS_ENDED = re.compile(
    r"(three|six|nine|twelve)\s+months\s+end(?:ed|ing)\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"\s+([A-Za-z]+),?\s+(\d{4})", re.I)
_EN_ANNUAL = re.compile(r"\b(\d{4})\s+annual\s+report\b|\bannual\s+report\s+(\d{4})\b", re.I)
_EN_INTERIM = re.compile(r"\b(\d{4})\s+interim\s+(?:report|results)\b"
                         r"|\binterim\s+(?:report|results)\s+(\d{4})\b", re.I)
_EN_ANNUAL_RESULTS = re.compile(
    r"\b(\d{4})\s+(?:annual|final|full[\s-]year)\s+results\b"
    r"|\b(?:annual|final|full[\s-]year)\s+results\b[^.\n]{0,40}?\b(\d{4})\b", re.I)
_EN_QUARTER = re.compile(
    r"\b(first|second|third|fourth)\s+quarter(?:ly)?\s+(?:report|results)?\s*"
    r"(?:of\s+|for\s+)?(\d{4})\b|\bQ([1-4])\s+(\d{4})\s+(?:report|results)", re.I)
_EN_QWORD = {"first": 3, "second": 6, "third": 9, "fourth": 12}
_EN_FROM_TO = re.compile(
    r"from\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+to\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.I)
_EN_HIGHLIGHTS = re.compile(r"\b(\d{4})\s+(?:highlights|results\s+highlights)\b", re.I)
_EN_PRESENTATION = re.compile(r"results\s+presentation|analyst\s+(?:briefing|presentation)"
                              r"|this\s+presentation", re.I)
_EN_ANNOUNCEMENT = re.compile(r"results\s+announcement|announcement\s+of\s+(?:annual|interim|final)\s+results", re.I)

# -- Chinese -------------------------------------------------------------
_CN_ANNUAL = re.compile(r"(\d{4})\s*年\s*年度报告")
_CN_HALF = re.compile(r"(\d{4})\s*年\s*(?:半年度|中期)(?:业绩)?(?:报告|公告)")
_CN_QUARTER = re.compile(r"(\d{4})\s*年\s*第([一二三四1-4])季度(?:报告|业绩)")
_CN_PERIOD = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*至\s*"
                        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_CN_ENDED = re.compile(r"截至\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*止\s*"
                       r"(年度|十二个月|六个月|三个月|九个月)")
_CN_ENDED_MONTHS = {"年度": 12, "十二个月": 12, "六个月": 6, "三个月": 3, "九个月": 9}
_CN_ANNOUNCE = re.compile(r"业绩公告|业绩公布")
_CN_PRESENT = re.compile(r"业绩发布会|业绩推介|投资者(?:简报|演示)")


def _snip(text, m, width=70):
    a, b = max(0, m.start() - 20), min(len(text), m.end() + 20)
    return re.sub(r"\s+", " ", text[a:b])[:width]


def printed_identity(pages):
    """pages: [(page_no, text)] — the document's first text pages.
    -> {"year", "month", "day", "months", "doc_type", "evidence", "n"}
    or {} when nothing recognisable is printed. Votes across pages: the
    period named most often on the first pages is the document's own
    (comparatives are mentioned, but the filing's own year dominates its
    cover, title bar and contents)."""
    periods = Counter()          # (year, month, day, months) -> votes
    types = Counter()
    evidence = {}

    def vote(key, dtype, page, text, m, w=1):
        periods[key] += w
        if dtype:
            types[dtype] += w
        evidence.setdefault(key, (page, _snip(text, m)))

    for page, text in pages[:FIRST_PAGES]:
        t = text or ""
        for m in _EN_YEAR_ENDED.finditer(t):
            mon = _MONTHS_EN.get(m.group(2).lower())
            if mon:
                vote((int(m.group(3)), mon, int(m.group(1)), 12), None, page, t, m, 2)
        for m in _EN_MONTHS_ENDED.finditer(t):
            mon = _MONTHS_EN.get(m.group(3).lower())
            if mon:
                vote((int(m.group(4)), mon, int(m.group(2)),
                      _WORD_MONTHS[m.group(1).lower()]), None, page, t, m, 2)
        for m in _EN_FROM_TO.finditer(t):
            m1, m2 = _MONTHS_EN.get(m.group(2).lower()), _MONTHS_EN.get(m.group(5).lower())
            if m1 and m2:
                y1, y2 = int(m.group(3)), int(m.group(6))
                months = (y2 - y1) * 12 + (m2 - m1) + 1
                if 1 <= months <= 12:
                    vote((y2, m2, int(m.group(4)), months), None, page, t, m, 2)
        for m in _EN_HIGHLIGHTS.finditer(t):
            vote((int(m.group(1)), None, None, None), None, page, t, m)
        for m in _EN_ANNUAL.finditer(t):
            y = int(m.group(1) or m.group(2))
            vote((y, None, None, 12), "annual report", page, t, m)
        for m in _EN_INTERIM.finditer(t):
            y = int(m.group(1) or m.group(2))
            vote((y, None, None, 6), "interim report", page, t, m)
        for m in _EN_ANNUAL_RESULTS.finditer(t):
            y = int(m.group(1) or m.group(2))
            vote((y, None, None, 12), "results announcement", page, t, m)
        for m in _EN_QUARTER.finditer(t):
            if m.group(1):
                vote((int(m.group(2)), None, None, _EN_QWORD[m.group(1).lower()]),
                     "quarterly report", page, t, m)
            else:
                vote((int(m.group(4)), None, None, 3 * int(m.group(3))),
                     "quarterly report", page, t, m)
        for m in _CN_ANNUAL.finditer(t):
            vote((int(m.group(1)), 12, 31, 12), "annual report", page, t, m)
        for m in _CN_HALF.finditer(t):
            vote((int(m.group(1)), 6, 30, 6), "interim report", page, t, m)
        for m in _CN_QUARTER.finditer(t):
            q = _CN_Q.get(m.group(2))
            if q:
                vote((int(m.group(1)), None, None, q), "quarterly report", page, t, m)
        for m in _CN_PERIOD.finditer(t):
            y1, m1, y2, m2, d2 = (int(m.group(1)), int(m.group(2)),
                                  int(m.group(4)), int(m.group(5)), int(m.group(6)))
            months = (y2 - y1) * 12 + (m2 - m1) + 1
            if 1 <= months <= 12:
                vote((y2, m2, d2, months), None, page, t, m, 2)
        for m in _CN_ENDED.finditer(t):
            vote((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                  _CN_ENDED_MONTHS[m.group(4)]), None, page, t, m, 2)
        if _EN_PRESENTATION.search(t) or _CN_PRESENT.search(t):
            types["results presentation"] += 1
        if _EN_ANNOUNCEMENT.search(t) or _CN_ANNOUNCE.search(t):
            types["results announcement"] += 1
    if not periods:
        return {}
    # merge votes by (year, months): an exact date and a title both name
    # the same period
    by_year = Counter()
    for (y, mo, d, ms), n in periods.items():
        by_year[y] += n
    year, n = by_year.most_common(1)[0]
    by_months = Counter()
    for (y, mo, d, ms), v in periods.items():
        if y == year and ms is not None:
            by_months[ms] += v
    months = by_months.most_common(1)[0][0] if by_months else None
    dated = [(k, v) for k, v in periods.items() if k[0] == year and k[3] == months and k[1]]
    mo = day = None
    if dated:
        (_, mo, day, _), _ = max(dated, key=lambda kv: kv[1])
    dtype = types.most_common(1)[0][0] if types else (
        "annual report" if months == 12 else "interim report" if months == 6
        else "quarterly report" if months in (3, 9) else "other")
    ev = evidence.get(next((k for k in periods if k[0] == year and k[3] == months),
                           next(k for k in periods if k[0] == year)))
    return {"year": year, "month": mo, "day": day, "months": months,
            "doc_type": dtype, "evidence": ev, "n": n, "source": "printed"}


_SYSTEM = """You identify financial filings. You are shown the first pages of one document.
Answer ONLY with JSON:
{"doc_type": one of ["annual report","interim report","quarterly report","results announcement","results presentation","other"],
 "company": "<issuer name>",
 "period_end": "YYYY-MM-DD" or null,      // the END of the period this document REPORTS ON (not the publication date)
 "months": 12 | 9 | 6 | 3 | null,          // length of the period reported on
 "comparatives": ["YYYY-MM-DD", ...],      // earlier period ends it presents alongside, if visible
 "why": "<one line quoting the printed words that settle the period>"}
Rules: the document's OWN period is what its cover/title/contents name ("2024 Annual Report" = year ended 2024-12-31);
comparative years mentioned in the text are NOT the document's period. If unsure, set period_end null."""


def _validate(obj):
    errs = []
    if not isinstance(obj, dict):
        return ["not an object"]
    if obj.get("doc_type") not in DOC_TYPES:
        errs.append("doc_type must be one of " + ", ".join(DOC_TYPES))
    pe = obj.get("period_end")
    if pe is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(pe)):
        errs.append("period_end must be YYYY-MM-DD or null")
    if obj.get("months") not in (12, 9, 6, 3, None):
        errs.append("months must be 12, 9, 6, 3 or null")
    return errs


def ask_brain(client, doc, pages, max_chars=9000):
    """One bounded card: the brain names the document. Returns the
    normalised identity dict or None (no client / refusal)."""
    if client is None:
        return None
    body = []
    for page, text in pages[:FIRST_PAGES]:
        body.append(f"--- page {page} ---\n{(text or '').strip()[:1800]}")
    user = f"Document file name (may be misleading): {doc}\n\n" + "\n".join(body)
    try:
        obj = client.json(_SYSTEM, user[:max_chars], _validate, repair_retries=1)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    pe = obj.get("period_end")
    year = month = day = None
    if pe:
        year, month, day = (int(x) for x in str(pe).split("-"))
    months = obj.get("months")
    if months is None:
        months = {"annual report": 12, "interim report": 6,
                  "quarterly report": 3}.get(obj.get("doc_type"))
    return {"year": year, "month": month, "day": day, "months": months,
            "doc_type": obj.get("doc_type"), "company": obj.get("company"),
            "why": str(obj.get("why") or "")[:160], "source": "brain"}


def expected_months(period_kind):
    return {"FY": 12, "1H": 6, "2H": 6, "H1": 6, "H2": 6, "Q": 3}.get(
        str(period_kind).upper(), 12)


def classify_identity(ident, target_year, period_kind="FY"):
    """-> 'current' | 'prior' | 'partial' | 'future' | None (no period)."""
    if not ident or not ident.get("year"):
        return None
    y, months = ident["year"], ident.get("months")
    if y < target_year:
        return "prior"
    if y > target_year:
        return "future"
    exp = expected_months(period_kind)
    if months is None or months == exp:
        return "current"
    return "partial" if months < exp else "current"


_LABEL = {"current": "CURRENT — evidence for the target period",
          "prior": "PRIOR PERIOD — prior-column evidence only (restatement scan, on-demand lookup)",
          "partial": "PARTIAL PERIOD — not a current-year source; listed for the analyst",
          "future": "LATER PERIOD — not a current-year source; listed for the analyst",
          "unknown": "UNKNOWN — not a current-year source; listed for the analyst"}


def identify_documents(paths, ledger, client, target_year, period_kind, log):
    """Names every document, reconciles the three readers, and writes the
    verdict into the ledger's vintage register (which every serving stage
    obeys through vintage_ban). Returns [{doc, identity, verdict, line}]."""
    from .stage1_read import page_texts
    numeric = dict(getattr(ledger, "_doc_periods", None) or {})
    verdicts = dict(numeric)
    out = []
    for path in paths:
        doc = Path(path).name
        try:
            pages = [(pn, t) for pn, t, c in page_texts(path) if c == "text"]
        except Exception:
            pages = []
        printed = printed_identity(pages[:FIRST_PAGES]) if pages else {}
        brain = ask_brain(client, doc, pages[:FIRST_PAGES]) if pages else None
        ident = brain or printed
        readers = []
        if brain:
            readers.append("brain")
        if printed:
            readers.append(f"printed p{printed['evidence'][0]}: "
                           f"\"{printed['evidence'][1]}\"")
        disagree = []
        if brain and printed and brain.get("year") and printed.get("year") \
                and brain["year"] != printed["year"]:
            disagree.append(f"brain says {brain['year']}, print says {printed['year']}")
        read_v = classify_identity(ident, target_year, period_kind)
        num_v = numeric.get(doc, "unknown")
        if read_v is None:
            final, basis = num_v, "no printed period recognised — numeric vote"
        elif disagree:
            final, basis = "unknown", "readers disagree (" + "; ".join(disagree) + ")"
        elif num_v == "current" and read_v != "current":
            final, basis = "unknown", (f"reading says {read_v} but the numeric "
                                       "vote says current — flagged")
        elif num_v == "prior" and read_v == "current":
            final, basis = "unknown", ("reading says current but the numeric "
                                       "vote says prior — flagged")
        else:
            final = "current" if read_v == "current" else \
                    "prior" if read_v == "prior" else "unknown"
            basis = " + ".join(readers) + (f"; numeric vote {num_v}" if num_v != "unknown" else "")
        verdicts[doc] = final
        when = ""
        if ident and ident.get("year"):
            when = (f"{ident['year']}-{ident['month']:02d}-{ident['day']:02d}"
                    if ident.get("month") and ident.get("day") else str(ident["year"]))
            when = f", period end {when}, {ident.get('months') or '?'} months"
        dtype = (ident or {}).get("doc_type") or "unidentified"
        label = _LABEL.get(final if read_v in (None, "current", "prior") or final == "unknown"
                           else read_v, _LABEL["unknown"])
        if read_v in ("partial", "future") and not disagree:
            label = _LABEL[read_v]
        line = f"{doc}: {dtype}{when} -> {label} [{basis}]"
        log(f"[run] document: {line}")
        ledger.doc_meta.setdefault(doc, {})["identity"] = {
            "doc_type": dtype, "year": (ident or {}).get("year"),
            "months": (ident or {}).get("months"), "verdict": final,
            "reading": read_v, "numeric": num_v, "basis": basis}
        out.append({"doc": doc, "identity": ident, "verdict": final, "line": line})
    ledger._doc_periods = verdicts
    return out
