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
        issuers = printed_issuers(pages[:FIRST_PAGES])
        issuer = (brain or {}).get("company") or (issuers[0] if issuers else None)
        if issuer:
            line += f" | issuer: {issuer}"
        ledger.doc_meta.setdefault(doc, {})["identity"] = {
            "doc_type": dtype, "year": (ident or {}).get("year"),
            "months": (ident or {}).get("months"), "verdict": final,
            "reading": read_v, "numeric": num_v, "basis": basis,
            "issuer": issuer}
        out.append({"doc": doc, "identity": ident, "verdict": final,
                    "line": line, "printed_issuer": issuer, "issuers": issuers})
    company = issuer_check(out, log)
    for e in out:
        verdicts[e["doc"]] = e["verdict"]
        ledger.doc_meta[e["doc"]]["identity"]["verdict"] = e["verdict"]
    if company:
        log(f"[run] company per the documents: {company}")
    ledger._doc_periods = verdicts
    ledger.stamp_vintages()
    return out


# -- the issuer: every current document must name the same company ---------
_EN_ISSUER = re.compile(
    r"([A-Z][A-Za-z&.,'\- ]{2,60}?\s+(?:Limited|Ltd\.?|Holdings(?:\s+Limited)?|"
    r"Corporation|Corp\.?|Inc\.?|plc|PLC|Company\s+Limited|Group(?:\s+Limited)?))\b")
_CN_ISSUER = re.compile(r"([一-鿿]{2,20}?(?:股份有限公司|有限公司|集团))")
_STOP = {"the", "of", "and", "limited", "ltd", "holdings", "company", "group",
         "corporation", "corp", "inc", "plc", "co"}


def printed_issuers(pages):
    """Every company name printed on the first pages, most-named first.
    A cover names the exchange, the auditor and the issuer; which one is
    the issuer is settled ACROSS documents (issuer_check), never here."""
    c = Counter()
    for _pn, text in pages[:FIRST_PAGES]:
        t = text or ""
        for m in _EN_ISSUER.finditer(t):
            c[m.group(1).strip()] += 1
        for m in _CN_ISSUER.finditer(t):
            c[m.group(1)] += 1
    return [n for n, _k in c.most_common()]


def printed_issuer(pages):
    """Most-named issuer on the first pages, or None."""
    names = printed_issuers(pages)
    return names[0] if names else None


def _issuer_tokens(name):
    s = str(name or "").lower()
    cn = set(re.findall(r"[一-鿿]{2,}", s))
    en = {w for w in re.findall(r"[a-z]{2,}", s) if w not in _STOP}
    # Chinese names: compare on 2-character shingles so 东方电气 ~ 东方电气股份
    sh = set()
    for w in cn:
        sh |= {w[i:i + 2] for i in range(len(w) - 1)}
    return en | sh


def same_issuer(a, b):
    ta, tb = _issuer_tokens(a), _issuer_tokens(b)
    if not ta or not tb:
        return True          # nothing to compare — never a false alarm
    return bool(ta & tb)


def issuer_check(entries, log):
    """entries: the identify_documents output (mutated in place).
    Among CURRENT documents the majority issuer is the company; a current
    document naming a different issuer is set UNKNOWN and flagged — a
    wrong company's report must never serve a number."""
    cur = [e for e in entries if e["verdict"] == "current"
           and (e.get("issuers") or (e.get("identity") or {}).get("company"))]
    if len(cur) < 2:
        return None
    # the company = the name (token group) named by the MOST documents; a
    # document whose names ALL miss that group is another company's
    groups = []          # [representative, set(doc)]
    for e in cur:
        names = list(e.get("issuers") or [])
        b = (e.get("identity") or {}).get("company")
        if b and e["identity"].get("source") == "brain":
            names = [b] + names
        for n in names:
            for g in groups:
                if same_issuer(g[0], n):
                    g[1].add(e["doc"])
                    break
            else:
                groups.append([n, {e["doc"]}])
    groups.sort(key=lambda g: -len(g[1]))
    company = groups[0][0]
    for e in cur:
        names = list(e.get("issuers") or [])
        b = (e.get("identity") or {}).get("company")
        if b:
            names = [b] + names
        if not any(same_issuer(company, n) for n in names):
            e["verdict"] = "unknown"
            e["line"] += (f" | ISSUER MISMATCH: names {names[:2]}, the other "
                          f"documents name '{company}' — not used, review")
            log(f"[run] document: {e['doc']}: ISSUER MISMATCH {names[:2]} vs "
                f"'{company}' — set UNKNOWN, flagged")
    return company


# -- the primary statements: which pages are they? ------------------------
_FACES_SYSTEM = """You are shown the first pages (cover, contents) of one financial filing, plus a list of
candidate pages that a scanner flagged as statement-like. Name the pages of the CONSOLIDATED primary
statements and the segment note. Answer ONLY with JSON:
{"pl": [page numbers of the consolidated income statement / statement of profit or loss],
 "bs": [pages of the consolidated balance sheet / statement of financial position],
 "cf": [pages of the consolidated cash flow statement],
 "segment": [pages of the segment information note],
 "parent_only": [pages that are COMPANY-ONLY (parent) statements, not consolidated],
 "why": "<one line: where the contents page says these are>"}
Use the filing's own printed page numbers as they appear in the text. Empty lists are fine."""


def _faces_validate(obj):
    errs = []
    if not isinstance(obj, dict):
        return ["not an object"]
    for k in ("pl", "bs", "cf", "segment", "parent_only"):
        v = obj.get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, int) for x in v):
            errs.append(f"{k} must be a list of integers")
    return errs


def identify_statement_pages(paths, ledger, client, priors, log):
    """THE READING STEP for statement pages (owner ruling 2026-09-03): the
    brain names the consolidated P&L / BS / CF / segment pages from the
    contents; code RATIFIES each named page by its numbers (the page must
    tie the model's prior year at a proven scale) before the face is
    used; a named page that does not ratify is refused and logged; pages
    the brain calls parent-only lose face authority. Without a brain the
    deterministic caption tagger stands (the floor)."""
    from .stage2_join import ratify_page_scales
    banned = set(getattr(ledger, "noncurrent_docs", lambda: set())())
    # A PAGE THAT PROVES ITSELF IS A STATEMENT FACE (DFE run 235): the
    # consolidated cash flow statement (PDF p101) read as 'cf' by its own
    # rows and ratified the prior year at one scale, yet no caption had
    # tagged it and the brain's page list did not resolve to it — so the
    # whole statement was never walked and the share placement was
    # missed. Code's own evidence (rows + ties) adopts such a page before
    # the brain is asked; the brain can still add, never lose, a face.
    from .ledger import face_from_row_labels
    for path in paths:
        doc = Path(path).name
        if doc in banned:
            continue
        items = [it for it in ledger.items if it.doc == doc]
        if not items:
            continue
        labels_by_page = {}
        for it in items:
            labels_by_page.setdefault(it.page, []).append(str(it.label or ""))
        try:
            ratified = ratify_page_scales(items, priors)
        except Exception:
            ratified = {}
        promoted = []
        # A PARENT-COMPANY STATEMENT MUST NOT PASS AS THE CONSOLIDATED ONE
        # (DFE 1H25: the parent balance sheet two pages after the
        # consolidated one ties a few shared lines — share capital,
        # reserves — and would ratify). Per face kind, a page adopts
        # only when it ties at least a third as many distinct priors as
        # the best page of that kind, and never fewer than 3.
        from .numerics import to_model_units as _tmu
        _pri = sorted({abs(float(p)) for p in priors
                       if isinstance(p, (int, float)) and abs(p) > 100})

        def _ties(pn, scale):
            hit = set()
            for it in items:
                if it.page != pn:
                    continue
                for n in (it.nums or [])[1:]:
                    if scale > 1 and abs(n) < scale / 1000:
                        continue
                    a = abs(_tmu(n, scale))
                    for p in _pri:
                        if abs(a - p) <= max(1.0, p * 0.01):
                            hit.add(p)
                            break
            return len(hit)
        face_of = {}
        ties_of = {}
        for (d, pn), scale in ratified.items():
            f = face_from_row_labels(labels_by_page.get(pn) or [])
            if f in ("pl", "bs", "cf"):
                face_of[pn] = f
                ties_of[pn] = _ties(pn, scale)
        best = {}
        for pn, f in face_of.items():
            best[f] = max(best.get(f, 0), ties_of[pn])
        for (d, pn) in ratified:
            if ledger.faces.get((d, pn)) in ("pl", "bs", "cf"):
                continue
            face = face_of.get(pn)
            if face and ties_of.get(pn, 0) < max(3, best.get(face, 0) / 3.0):
                log(f"[run] statement pages ({doc}): p{pn} reads as {face} but ties "
                    f"only {ties_of.get(pn, 0)} prior(s) vs {best.get(face, 0)} on the "
                    "best page of that kind — parent-company or note page, not adopted")
                continue
            if face in ("pl", "bs", "cf"):
                ledger.faces[(d, pn)] = face
                if hasattr(ledger, "parent_pages"):
                    ledger.parent_pages.discard((d, pn))
                promoted.append(f"p{pn}={face}")
        if promoted:
            log(f"[run] statement pages ({doc}): {len(promoted)} page(s) adopted "
                f"on their own rows + prior-year ties: {promoted[:8]}")
    if client is None:
        return {}
    from .stage1_read import page_texts
    out = {}
    for path in paths:
        doc = Path(path).name
        if doc in banned:
            continue
        try:
            pages = [(pn, t) for pn, t, c in page_texts(path) if c == "text"]
        except Exception:
            continue
        cands = sorted(pn for (d, pn), f in ledger.faces.items() if d == doc)
        body = [f"--- page {pn} ---\n{(t or '').strip()[:1500]}"
                for pn, t in pages[:FIRST_PAGES]]
        user = (f"Document: {doc}\nScanner's candidate statement pages: {cands}\n\n"
                + "\n".join(body))[:12000]
        try:
            obj = client.json(_FACES_SYSTEM, user, _faces_validate, repair_retries=1)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        items = [it for it in ledger.items if it.doc == doc]
        ratified = ratify_page_scales(items, priors)
        adopted, refused = [], []
        # THE PAGE-SPACE LAW (run-230 autopsy): the brain names PRINTED
        # page numbers; the ledger counts PDF pages. A named page is
        # accepted only where its OWN ROWS identify that statement
        # (face_from_row_labels) AND its numbers ratify; when the PDF
        # page of that number fails, the printed number is looked up
        # in page footers and the self-identifying page wins. Note
        # pages ratify too — ratification alone adopted the wrong pages
        # and demoted the real statements in run 230.
        from .ledger import face_from_row_labels
        labels_by_page = {}
        for it in items:
            labels_by_page.setdefault(it.page, []).append(str(it.label or ""))
        text_by_page = {pn: (t or "") for pn, t in pages}

        def self_face(pn):
            labs = labels_by_page.get(pn) or []
            return face_from_row_labels(labs) if labs else None

        def resolve(pn, face):
            """-> the PDF page that carries `face` for printed/PDF number pn, or None."""
            if self_face(pn) == face and (doc, pn) in ratified:
                return pn
            tok = re.compile(rf"(?m)^\s*{pn}\s*$|\bpage\s+{pn}\b", re.I)
            for q, t in text_by_page.items():
                if q != pn and tok.search(t) and self_face(q) == face and (doc, q) in ratified:
                    return q
            return None

        confirmed = set()
        for face in ("pl", "bs", "cf"):
            for pn in obj.get(face) or []:
                q = resolve(pn, face)
                if q is None:
                    refused.append(f"p{pn}={face} (no page with that number both "
                                   "reads as that statement by its rows and ties the prior year)")
                    continue
                if (doc, q) in ledger.parent_pages:
                    ledger.parent_pages.discard((doc, q))
                ledger.faces[(doc, q)] = face
                confirmed.add(q)
                adopted.append(f"p{pn}->pdf{q}={face}" if q != pn else f"p{q}={face}")
        for pn in obj.get("segment") or []:
            q = pn if pn in labels_by_page else None
            if q is not None:
                ledger.faces.setdefault((doc, q), "segment")
                adopted.append(f"p{q}=segment")
        for pn in obj.get("parent_only") or []:
            # CODE OUTRANKS THE NAME (DFE run 238): the brain names
            # parent-company pages in PRINTED numbers; PDF p101 — the
            # consolidated cash flow statement, self-identified and tied
            # to the model's priors at one scale — was deleted as
            # 'parent-only' and never walked. A parent-company statement
            # cannot ratify against consolidated priors, so a page that
            # ratifies is kept whatever it was called.
            if (doc, pn) in ratified and self_face(pn) in ("pl", "bs", "cf"):
                refused.append(f"p{pn}=parent-only refused (the page ties the "
                               "model's prior year at one scale: consolidated)")
                continue
            if ledger.faces.get((doc, pn)) in ("pl", "bs", "cf"):
                del ledger.faces[(doc, pn)]
            ledger.parent_pages.add((doc, pn))
            adopted.append(f"p{pn}=parent-only (face removed)")
        # THE BRAIN'S MAP IS THE AUTHORITY (run-229 autopsy): once the
        # brain has named the primary statements and they ratified,
        # caption-propagated face tags on OTHER pages of this document
        # (a fixed-asset note tagged 'cf' by a caption three pages
        # earlier) lose statement authority — kept only within one page
        # of a named statement (a statement that runs over the page).
        named = confirmed
        demoted = []
        if named:
            for (d, pn), face in list(ledger.faces.items()):
                if d != doc or face not in ("pl", "bs", "cf"):
                    continue
                if pn in named or any(abs(pn - q) <= 1 for q in named):
                    continue
                if self_face(pn) is not None:
                    continue        # its own rows say it is a statement page
                del ledger.faces[(d, pn)]
                demoted.append(pn)
        if demoted:
            adopted.append(f"{len(demoted)} caption-tagged page(s) demoted: "
                           f"{sorted(demoted)[:8]}")
        out[doc] = {"adopted": adopted, "refused": refused,
                    "why": str(obj.get("why") or "")[:160]}
        log(f"[run] statement pages ({doc}): brain named {len(adopted)} "
            f"ratified; {len(refused)} refused — {obj.get('why', '')!s:.100}"
            + (f"; refused: {refused[:3]}" if refused else ""))
    return out


# -- the model's key rows: which rows are the headline outputs? ----------
# THE BALANCE SHEET'S OWN FOUR (owner 2026-09-17): a balance check that closes
# proves the two SIDES agree, not that either side is right — the perpetuals
# plugged into a liability row leave total liabilities and equity tying the
# print while non-current liabilities is off it. Each side's halves are keys in
# their own right, measured on the MODEL's computed total row against the
# printed one, exactly like every other key.
KEY_NAMES = ("revenue", "gross profit", "operating profit", "net profit",
             "recurring net profit", "eps", "dps", "total assets",
             "current assets", "non-current assets",
             "current liabilities", "non-current liabilities",
             "total liabilities and equity", "total liabilities",
             "non-controlling interests",
             "total equity", "operating cash flow", "investing cash flow",
             "financing cash flow", "cash year end")

_KEYS_SYSTEM = """You are shown the row labels of an equity analyst's financial model (one sheet at a time,
"row: label"). Name the rows that carry the headline outputs. Answer ONLY with JSON:
{"key_rows": [{"row": <int>, "name": <one of %s>}, ...],
 "why": "<one line>"}
Pick at most one row per name, the CONSOLIDATED / total line (not a segment), the reported
figure unless the name says recurring. Omit names this sheet does not carry.""" % ", ".join(
    f'"{n}"' for n in KEY_NAMES)


def _keys_validate(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get("key_rows"), list):
        return ["key_rows must be a list"]
    errs = []
    for e in obj["key_rows"]:
        if not isinstance(e, dict) or not isinstance(e.get("row"), int) \
                or e.get("name") not in KEY_NAMES:
            errs.append(f"bad entry {e!r}: row int + name in the allowed list")
    return errs


def identify_key_rows(wb_values, spec, client, log, max_rows=260,
                      panel_path=None, target_year=None):
    """THE READING STEP for the model (owner ruling 2026-09-03): the brain
    reads each sheet's labels and names the headline rows; code VERIFIES
    each named row carries numbers in the year axis before it replaces
    the pattern-matched pick of the same name. Unverifiable picks are
    logged and dropped. Without a brain the synonym patterns stand."""
    if client is None:
        return []
    axis = spec.get("year_axis") or {}
    panel = {}
    if panel_path is not None:
        try:
            import json as _json
            panel = _json.loads(Path(panel_path).read_text())
        except Exception:
            panel = {}
    from .checks import prior_column as _pcol

    def _prior_ties(sheet, row, name):
        """Numeric verification (run-230: the brain named EBIT as
        'operating profit'): when the pinned panel knows the key's PRIOR,
        the named row's prior-year value must tie it."""
        want = (panel.get(name) or {}).get("prior")
        if not isinstance(want, (int, float)) or target_year is None:
            return True
        pc = _pcol(spec, sheet, target_year)
        if not pc:
            return True
        v = wb_values[sheet][f"{pc}{row}"].value
        if isinstance(v, str) and v.startswith("="):
            try:
                from .evaluator import Evaluator
                v = Evaluator(wb_values).cell(sheet, f"{pc}{row}")
            except Exception:
                return False
        return isinstance(v, (int, float)) and abs(v - want) <= max(1.0, abs(want) * 0.002)
    found, dropped = [], []
    for sheet, ax in axis.items():
        if sheet not in wb_values.sheetnames:
            continue
        ws = wb_values[sheet]
        cols = list((ax.get("columns") or ax.get("cols") or {}).values()) \
            if isinstance(ax, dict) else []
        if not cols:
            cols = [c for c in ("B", "C", "D", "E", "F", "G", "H", "I", "J", "K")]
        lines, numeric_rows = [], set()
        for r in range(1, min(ws.max_row, max_rows) + 1):
            lab = ws.cell(r, 1).value
            if lab is None or not str(lab).strip():
                continue
            # a manual-calc model caches nothing: a FORMULA row carries
            # numbers as much as a typed one (run-229: the brain's correct
            # picks Final!15/27/31 were dropped as "no numbers")
            has_num = any(isinstance(ws[f"{c}{r}"].value, (int, float))
                          or (isinstance(ws[f"{c}{r}"].value, str)
                              and ws[f"{c}{r}"].value.startswith("="))
                          for c in cols[:12])
            if has_num:
                numeric_rows.add(r)
            lines.append(f"{r}: {str(lab).strip()[:60]}")
        if len(lines) < 5:
            continue
        user = f"Sheet: {sheet}\n" + "\n".join(lines)
        try:
            obj = client.json(_KEYS_SYSTEM, user[:14000], _keys_validate,
                              repair_retries=1)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        for e in obj.get("key_rows") or []:
            if e["row"] not in numeric_rows:
                dropped.append(f"{sheet}!{e['row']} as {e['name']} (no numbers on the row)")
            elif not _prior_ties(sheet, e["row"], e["name"]):
                dropped.append(f"{sheet}!{e['row']} as {e['name']} (its prior-year value "
                               "does not tie the pinned prior for that key)")
            else:
                found.append({"name": e["name"], "sheet": sheet, "row": e["row"],
                              "source": "brain"})
    if not found and not dropped:
        return []
    by_name = {}
    for k in found:
        by_name.setdefault(k["name"], k)      # first sheet wins per name
    old = spec.get("key_rows") or []
    # A VERIFIED EXISTING PICK IS NOT DISPLACED by a brain pick from another
    # sheet (run 232: 'operating profit' moved from Final!15 to Driver!28 —
    # both tie the pinned prior, but the report reads the primary sheet)
    keep_old = {}
    for k in old:
        nm = k.get("name")
        b = by_name.get(nm)
        if b and b["sheet"] != k.get("sheet") and k.get("sheet") in wb_values.sheetnames \
                and _prior_ties(k["sheet"], int(k["row"]), nm):
            keep_old[nm] = k
    for nm in keep_old:
        dropped.append(f"{by_name[nm]['sheet']}!{by_name[nm]['row']} as {nm} "
                       f"(the existing {keep_old[nm]['sheet']}!{keep_old[nm]['row']} verifies and stays)")
        by_name.pop(nm)
    kept = [k for k in old if k.get("name") not in by_name]
    spec["key_rows"] = kept + list(by_name.values())
    log(f"[run] key rows: brain named {len(by_name)} verified "
        f"({', '.join(sorted(by_name))}); {len(kept)} pattern picks kept"
        + (f"; dropped {dropped[:3]}" if dropped else ""))
    return list(by_name.values())
