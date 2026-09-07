"""Cell notes for the ANALYST, not for the agent (owner rulings, run 233,
2026-09-07):

1. Notes only on highlighted cells. A plain updated input carries no
   note — 144 provenance notes on ordinary inputs buried the ones that
   matter. The provenance stays in the run log and provenance.json.
2. Notes are short and in plain words. "Backed out from the annual
   report p214." / "Not found in the documents. Kept last period's
   figure." An analyst has no time for, and no meaning in, 'tier-3',
   'stage-2.5 bound-table join' or 'QUEUE-DOCUMENTED'.

`plain_note` turns the agent's working note into that sentence.
`hygiene` applies both rules to a workbook at delivery: strips the
agent's notes from un-highlighted cells and rewrites the rest. The
analyst's own notes (other authors) are never touched.
"""
import re

AUTHOR = "Model Update Agent"
RED = "FFC7CE"
ORANGE = "FFC000"
BLUE = "BDD7EE"      # frozen / held forecast input (the forecast-year colour)
MAX_LEN = 160

_SRC = re.compile(r"([A-Za-z0-9_][^()/:;]*?\.pdf)\S*\s+p(\d+)")
_PAGE = re.compile(r"\bp(\d{1,4})\b")
_NUM = re.compile(r"[+-]?\d[\d,]*(?:\.\d+)?")


def _kind(doc):
    d = doc.lower()
    if "annual report" in d or "annual_report" in d:
        return "annual report"
    if "announce" in d:
        return "results announcement"
    if "present" in d or "results pres" in d:
        return "results presentation"
    if "interim" in d:
        return "interim report"
    return ""


def _source(text):
    """'(e_2025 Annual Report.pdf p214)' -> 'annual report p214'."""
    m = _SRC.search(text)
    if m:
        kind = _kind(m.group(1)) or re.sub(r"\.pdf$", "", m.group(1)).strip()[:24]
        return f"{kind} p{m.group(2)}"
    # 'p37: ... (CLP 2025 Annual Results Pres)' — a page and a document
    # kind named apart
    pm = _PAGE.search(text)
    kind = _kind(text)
    if pm and kind:
        return f"{kind} p{pm.group(1)}"
    return ""


def _nums(text, n=2):
    out = []
    for m in _NUM.finditer(text):
        s = m.group(0).replace(",", "")
        try:
            v = float(s)
        except ValueError:
            continue
        out.append(v)
        if len(out) >= n:
            break
    return out


def _fmt(v):
    if isinstance(v, (int, float)):
        return f"{v:,.1f}" if abs(v) < 100 and v != int(v) else f"{v:,.0f}"
    return str(v)


def _cut(s):
    s = " ".join(str(s).split())
    return s if len(s) <= MAX_LEN else s[:MAX_LEN - 1].rstrip() + "…"


def plain_note(text):
    """The agent's working note -> one short sentence for the analyst."""
    t = " ".join(str(text or "").split())
    low = t.lower()
    src = _source(t)
    where = f" ({src})" if src else ""

    if low.startswith("tier-3 back-out"):
        return "Backed out: not found in the documents; held at the group's growth rate. True up when disclosed."
    if low.startswith(("queue-documented", "card rendered with zero candidates",
                       "card-adjudicated not proven", "stale input")):
        return "Not found in the documents. Kept last period's figure."
    if low.startswith(("guard revert", "not confirmed", "backed out", "new line this year",
                       "updated per the disclosure", "two readings",
                       "least confident", "one of ")):
        return _cut(t)                     # already written for the analyst
    if low.startswith("embedded hardcode"):
        m = re.search(r"constant\(s\) ([\d.,\s]+?) from", t)
        consts = m.group(1).strip() if m else "last period's constants"
        return _cut(f"Formula still carries last period's constants ({consts}). Check they still hold.")
    if low.startswith("roll-base mismatch"):
        m = re.search(r"gap ([+-]?[\d,\.]+)", t)
        gap = m.group(1) if m else "a gap"
        return _cut(f"Forecast base is off this year's actual by {gap}. Check the inputs this row rolls forward from.")
    if low.startswith("roll-base anchor"):
        m = re.search(r"Anchored ([\-\d,\.]+) \+ ([\-\d,\.]+)", t)
        adj = f" ({m.group(2)})" if m else ""
        return _cut(f"Backed out{adj} so the roll reproduces the disclosed closing. Reconcile the components.")
    if low.startswith(("stale roll base", "stale twin")):
        return "Still holds last period's figure while a linked cell was updated. Re-anchor it."
    if low.startswith("collapsed forecast"):
        ns = _nums(t.split("computed", 1)[1] if "computed" in t else t, 2)
        if len(ns) == 2:
            return _cut(f"Forecast moved from {_fmt(ns[0])} to {_fmt(ns[1])} after the update. Check the actual-year inputs it uses.")
        return "Forecast moved sharply after the update. Check the actual-year inputs it uses."
    if low.startswith("sign-flip unresolved"):
        return "Forecast flips sign against both actual years. Check the actual-year inputs it uses."
    if low.startswith("composite rewrite"):
        pairs = re.findall(r"(\d[\d.]*)->(\d[\d.]*)", t)
        chg = ", ".join(f"{a}→{b}" for a, b in pairs[:3] if a != b)
        return _cut(f"Backed out from the disclosure{where}: {chg}." if chg
                    else f"Backed out from the disclosure{where}.")
    if low.startswith("recomposed"):
        return _cut(f"Backed out from the disclosure{where}; new items added to the sum.")
    if low.startswith("key-tie back-out"):
        m = re.search(r"'([^']+)' computed ([\d,\.\-]+) vs disclosed ([\d,\.\-]+)", t)
        if m:
            return _cut(f"Backed out so {m.group(1)} ties the disclosed {m.group(3)}.")
        return "Backed out so the key figure ties the disclosure."
    if low.startswith("twin back-out"):
        return "Backed out so the total ties. Awaiting the detailed split."
    if low.startswith("plug meter"):
        ns = _nums(t.split("computed", 1)[1] if "computed" in t else t, 2)
        if len(ns) == 2:
            return _cut(f"The model's own residual moved from {_fmt(ns[0])} to {_fmt(ns[1])}. Check the inputs feeding its total.")
        return "The model's own residual moved sharply. Check the inputs feeding its total."
    if low.startswith("plug:"):
        return _cut(t)                     # written for the analyst already
    if low.startswith("one-off not propagated"):
        return "Held at zero: last year's one-off is not carried into the forecast."
    if low.startswith(("plug over proven value", "plug ")):
        m = re.search(r"residual ([\-\d,\.]+)", t)
        amt = f" {m.group(1)}" if m else ""
        return _cut(f"Plug: absorbed{amt} to close the check. Please rule.")
    if low.startswith("auto-probe hold"):
        return "Held at your pre-update value; it closes the balance check."
    if low.startswith("rollover"):
        return "Kept last period's figure: the new value moved the forecast out of proportion. Please confirm."
    if low.startswith("definition question"):
        ns = _nums(t.split("computes", 1)[1] if "computes" in t else t, 2)
        if len(ns) == 2:
            return _cut(f"Computes {_fmt(ns[0])} vs printed {_fmt(ns[1])}. The definition differs from the disclosure. Your ruling.")
        return "The definition differs from the disclosure. Your ruling."
    if low.startswith("disclosure prints nil"):
        return _cut(f"Disclosure prints '–' for this period{where}.")
    if low.startswith("objective loop"):
        return _cut(f"Updated per the disclosure{where}. Please confirm." if src
                    else "Updated on the agent's review. Please confirm.")
    if low.startswith(("stage-2", "stage-3", "reconciliation")):
        return _cut(f"Read from the disclosure{where}.")
    # default: the first sentence, jargon stripped
    first = re.split(r"(?<=[.;])\s|\s—\s", t, 1)[0]
    first = re.sub(r"\b(ANALYST (REVIEW|MUST RULE|RULING)|nothing forced)\b\.?", "", first).strip(" .;:—")
    return _cut(first + ".") if first else ""


def _fill_code(cell):
    try:
        rgb = str(cell.fill.fgColor.rgb or "")
    except Exception:
        return ""
    return rgb[-6:].upper()


def hygiene(wb, author=AUTHOR, log=None):
    """Apply the two rules to every sheet the analyst reads (sheets not
    starting with '_'). -> {"stripped": n, "rewritten": n}."""
    from openpyxl.comments import Comment
    stripped = rewritten = 0
    for ws in wb.worksheets:
        if ws.title.startswith("_"):
            continue
        for row in ws.iter_rows():
            for cell in row:
                cm = cell.comment
                if cm is None or (cm.author or "") != author:
                    continue
                code = _fill_code(cell)
                if code not in (RED, ORANGE, BLUE):
                    cell.comment = None
                    stripped += 1
                    continue
                short = plain_note(cm.text)
                if short and short != cm.text:
                    cell.comment = Comment(short, author)
                    rewritten += 1
    if log:
        log(f"[run] note hygiene: {stripped} notes removed from plain "
            f"cells, {rewritten} flagged-cell notes rewritten in plain words")
    return {"stripped": stripped, "rewritten": rewritten}
