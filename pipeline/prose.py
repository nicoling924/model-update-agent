"""PROSE FIGURES (owner ruling 2026-09-08): a figure stated in a sentence —
"2025年，公司新生效订单1172.51亿元，同比增长15.93%", "order intake of
RMB117.3bn, up 16%" — is evidence like any table line. The reader turns
such sentences into ledger lines so the generic map applies unchanged:
last year's figure (stated, or implied by the growth rate) ties the
model's prior, the name confirms, this year's figure lands. Where no tie
exists the line reaches the brain's serve card as a label candidate with
the sentence printed on it; the brain judges the item and the unit, code
checks the result against the model's previous period.

This is a wide net, deliberately: "noun phrase + amount + unit word", the
growth rate or a stated prior when present. It decides only which
sentences are worth showing; it is not a rulebook of formats.

Currency amounts are normalised to the base unit (yuan / dollar) so the
existing scale machinery converts them to the model's units exactly as it
converts a statement line. Non-currency amounts (MW, 台, kWh, cents) keep
their printed value and carry the unit word — the brain converts those.
"""
import re

from .ledger import Item

# unit word -> multiplier to the base currency unit (None = not currency)
_UNITS = [
    (r"亿元", 1e8), (r"亿美元", 1e8), (r"亿港元", 1e8), (r"亿", 1e8),
    (r"千万元", 1e7), (r"百万元", 1e6), (r"万元", 1e4), (r"千元", 1e3), (r"元", 1.0),
    (r"billion|bn\b", 1e9), (r"million|mn\b|\bm\b", 1e6), (r"thousand|\bk\b", 1e3),
    (r"MW|GW|kW|MWh|GWh|kWh|TWh|TJ|GJ|吨|万吨|台|套|人|户|units?|tonnes?|MT|cents?|%", None),
]
_UNIT_RE = re.compile(
    r"(?P<cur>RMB|HK\$|HKD|US\$|USD|人民币|港元|港币|美元|\$|€|£)?\s*"
    r"(?P<num>-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*"
    r"(?P<unit>" + "|".join(u for u, _m in _UNITS) + r")", re.I)
_GROWTH = re.compile(
    r"(?:同比|较上年|按年|year[- ]on[- ]year|yoy|y/y|versus last year|compared with (?:last|the prior) year)"
    r"[^0-9%]{0,12}?(?P<dir>增长|增加|上升|提高|下降|减少|下跌|up|down|increase|decrease|rise|fall|grew|fell|higher|lower)?"
    r"[^0-9%]{0,8}?(?P<pct>-?\d+(?:\.\d+)?)\s*%", re.I)
_GROWTH_EN = re.compile(r"(?P<dir>up|down|increase[ds]?|decrease[ds]?|rose|fell|grew|declined)\s+(?:by\s+)?(?P<pct>-?\d+(?:\.\d+)?)\s*%", re.I)
_STATED_PRIOR = re.compile(
    r"(?:去年同期|上年同期|上年|去年|last year|prior year|previous year|20\d\d\s*年?[:：]?)\s*[:：为是]?\s*"
    r"(?P<cur>RMB|HK\$|US\$|人民币|港元|美元|\$)?\s*(?P<num>-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*(?P<unit>亿元|万元|元|billion|bn|million|mn|m)\b", re.I)
_DOWN = ("下降", "减少", "下跌", "down", "decrease", "decreased", "decreases", "fell", "declined", "lower", "fall")
_STOP_LABEL = re.compile(r"^(?:公司|本公司|集团|本集团|我们|the group|the company|we|it|which|its|of|for|in|at|to|and|with)\s*", re.I)
_MIN_LABEL, _MAX_LABEL = 2, 40


def _sentences(text):
    """Join wrapped lines into paragraphs, then split on sentence ends."""
    lines = [l.strip() for l in str(text or "").splitlines()]
    para, out = "", []
    for l in lines:
        if not l:
            if para:
                out.append(para)
            para = ""
            continue
        joiner = "" if (para and (re.search(r"[一-鿿]$", para) or re.match(r"^[一-鿿，,%）)]", l))) else " "
        para = (para + joiner + l) if para else l
    if para:
        out.append(para)
    sents = []
    for p in out:
        sents += [s.strip() for s in re.split(r"(?<=[。；;!?！？])|(?<=[.])\s+(?=[A-Z])", p) if s.strip()]
    return sents


def _unit_mult(word):
    for pat, mult in _UNITS:
        if re.fullmatch(pat, word, re.I):
            return mult
    return None


def _noun_phrase(before):
    """The item's name: the words before the amount, after the last clause
    break — '2025年，公司新生效订单' -> '新生效订单'; 'order intake of' ->
    'order intake'."""
    seg = re.split(r"[，,。；;：:（）()、]|\s{2,}", before)[-1]
    seg = re.sub(r"^(?:20\d\d\s*年?[,，]?\s*|\d{4}\s*)", "", seg)
    seg = _STOP_LABEL.sub("", seg.strip())
    seg = re.sub(r"(?:实现|达到|为|达|完成|录得|录入|实现了|of|was|were|reached|totalled|totaled|amounted to|at|approximately|about|approx\.?)\s*$", "", seg.strip(), flags=re.I).strip()
    seg = re.sub(r"^(?:实现|完成|录得|达到)", "", seg)
    if len(seg) < _MIN_LABEL:
        return ""
    return seg[-_MAX_LABEL:] if len(seg) > _MAX_LABEL else seg


def harvest_prose(doc, page_no, text):
    """One text page -> prose Items. nums = [current] or [current,
    implied/stated prior], in BASE currency units for money (so the page
    scale converts them like a statement line) or the printed value with
    its unit word in unit_dim otherwise. table_id 900+ marks the channel;
    row_ord keeps sentence order."""
    items = []
    for i, sent in enumerate(_sentences(text)):
        if len(sent) < 6 or not re.search(r"\d", sent):
            continue
        for m in _UNIT_RE.finditer(sent):
            unit = m.group("unit")
            mult = _unit_mult(unit)
            if unit == "%":
                continue                    # a rate is not an amount
            before = sent[:m.start()]
            label = _noun_phrase(before)
            if not label:
                continue
            try:
                amt = float(m.group("num").replace(",", ""))
            except ValueError:
                continue
            if abs(amt) < 1e-9:
                continue
            tail = sent[m.end():m.end() + 80]
            growth, prior = None, None
            g = _GROWTH.search(tail) or _GROWTH_EN.search(tail)
            if g:
                pct = float(g.group("pct")) / 100.0
                d = (g.group("dir") or "").lower()
                if any(k in d for k in _DOWN) or pct < 0:
                    pct = -abs(pct)
                growth = pct
            sp = _STATED_PRIOR.search(tail)
            if sp:
                pm = _unit_mult(sp.group("unit"))
                try:
                    prior = float(sp.group("num").replace(",", "")) * (pm or 1.0)
                except ValueError:
                    prior = None
            if mult is not None:            # money -> base currency unit
                cur = amt * mult
                if prior is None and growth is not None and abs(1 + growth) > 1e-9:
                    prior = cur / (1 + growth)
                nums = [cur] + ([prior] if prior is not None else [])
                udim = "money"
            else:
                cur = amt
                if prior is None and growth is not None and abs(1 + growth) > 1e-9:
                    prior = cur / (1 + growth)
                nums = [cur] + ([prior] if prior is not None else [])
                udim = f"unit:{unit}"
            items.append(Item(
                doc=doc, page=page_no, table_id=900 + i, row_ord=i,
                label=label, nums=nums, unit_dim=udim, scale_hint=None,
                channel="prose", consensus=1,
                source_line=sent[:200]))
    return items
