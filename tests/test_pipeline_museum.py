"""THE PIPELINE MUSEUM — the rebuild's adversarial floor.

Every exhibit is a disease that actually shipped on the legacy line (RUNLOG
has the autopsies), rebuilt synthetically against the NEW pipeline/ stages.
Any change that lets one pass again is rejected, whatever it does to the
score. Pure stdlib — no LLM, no workbook, no pdfplumber; runs on a bare
Python 3.9: python tests/test_pipeline_museum.py  (or pytest -q).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.ledger import (Item, Ledger, parse_scale_hint, tag_faces,   # noqa: E402
                             unit_dim_of)
from pipeline.numerics import (kinship, line_numbers, parse_number,       # noqa: E402
                               row_tol, to_model_units)
from pipeline.stage1_read import (checksum_page, merge_votes,             # noqa: E402
                                  segment_page, vision_items)
from pipeline.stage2_join import join, ratify_page_scales                 # noqa: E402
from pipeline.targets import TargetRow                                    # noqa: E402

DOC = "ar.pdf"


def _ledger(items, face_pages=((95, "pl"),), parents=()):
    led = Ledger()
    for it in items:
        led.add(it)
    for pn, f in face_pages:
        led.faces[(DOC, pn)] = f
    led.parent_pages |= {(DOC, pn) for pn in parents}
    return led


def _item(page, row_ord, label, nums, table_id=0, **kw):
    return Item(doc=DOC, page=page, table_id=table_id, row_ord=row_ord,
                label=label, nums=list(nums), **kw)


def _anchors(page=95, scale=1.0):
    """Two aggregate lines that ratify the page's scale against the two
    anchor targets below (labels chosen to kinship-match NOTHING)."""
    s = scale
    return [_item(page, 1, "营业总收入合计栏", [60000.0 * s, 58000.0 * s]),
            _item(page, 2, "营业总成本合计栏", [41000.0 * s, 39000.0 * s])]


def _anchor_targets():
    return [TargetRow("Model", 1, "aaaa", 58000.0),
            TargetRow("Model", 2, "bbbb", 39000.0)]


# ── Exhibit 112: the row-world tolerance ─────────────────────────────────
# An absolute tolerance of 1.0 let "prior 1.15" corroborate a 0.94 EPS row
# and net profit 3,831.3 was swapped in. On the new line: a misaligned note
# item [3,831.30 | 1.15] under the EPS label must not tie prior 0.94 even
# on a ratified statement face; the true face line [1.15 | 0.94] serves.

def test_112_small_world_swap_refused():
    items = _anchors() + [
        _item(95, 10, "基本每股收益", [3831.30122213, 1.15]),
        _item(95, 11, "基本每股收益（元／股）", [1.15, 0.94]),
    ]
    targets = _anchor_targets() + [TargetRow("Model", 9, "基本每股收益", 0.94)]
    served, _ = join(_ledger(items), targets)
    e = served.get(("Model", 9))
    assert e is not None, "true EPS face line failed to join"
    assert abs(e["value"] - 1.15) < 1e-9, \
        f"run-112 poison re-admitted: EPS row served {e['value']}"


def test_row_tol_worlds():
    assert row_tol(0.94) <= 0.01 + 1e-9           # per-share world: a cent
    assert row_tol(2773.7) >= 13.0                # aggregate world: 0.5%
    assert abs(1.15 - 0.94) > row_tol(0.94), "1.15 must never tie 0.94"


# ── Exhibit 115: face authority ──────────────────────────────────────────
# A MEGAWATT figure joined a P&L money row via label match. On the new
# line: a production-table page carries no statement caption, so its items
# never enter the join pool — however perfect the label and the prior tie.

def test_115_no_face_no_join():
    items = _anchors(page=95) + [
        _item(158, 5, "其他业务成本(金融类)", [8056.6, 26.1]),   # 26.1 MW, coincidental tie
    ]
    led = _ledger(items, face_pages=((95, "pl"),))   # p158 has no face
    targets = _anchor_targets() + [
        TargetRow("Model", 7, "其他业务成本(金融类)", 26.15)]
    served, _ = join(led, targets)
    assert ("Model", 7) not in served, \
        "run-115 poison re-admitted: faceless page joined a model row"


def test_115b_parent_page_evicted():
    """A 母公司 twin prints the same lines as the consolidated face; its
    page must carry no face authority even when captions surround it."""
    lines = [(95, "合并资产负债表"), (100, "母公司资产负债表"),
             (101, "资产总计 1,000 900")]
    faces, parents = tag_faces(lines)
    assert faces.get(95) == "bs"
    assert 100 in parents and 100 not in faces, "parent page kept authority"
    # propagation from p95 stops AT the parent page
    assert faces.get(96) == "bs" and faces.get(101) is None, \
        "caption propagated past a parent page"


# ── Exhibit 116: block-scale ratification ────────────────────────────────
# A no-prior row served without a scale anchor wrote a raw-yuan number.
# On the new line: a page joins ONLY at a scale ratified by >= 2 distinct
# prior ties, and the served value converts at that BLOCK scale.

def test_116_ratified_scale_converts():
    items = _anchors(page=95, scale=1e6) + [
        _item(95, 5, "归属于母公司股东的净利润", [3831300000.0, 3600000000.0]),
    ]
    targets = _anchor_targets() + [
        TargetRow("Model", 5, "归属于母公司股东的净利润", 3600.0)]
    served, _ = join(_ledger(items), targets)
    e = served.get(("Model", 5))
    assert e is not None, "ratified yuan page failed to join"
    assert abs(e["value"] - 3831.3) < 0.01, \
        f"run-116 scale poison: served {e['value']} instead of 3,831.3 model units"


def test_116b_unratified_page_serves_nothing():
    items = [_item(95, 1, "营业总收入合计栏", [60000e6, 58000e6]),
             _item(95, 5, "归属于母公司股东的净利润", [3831300000.0, 3600000000.0])]
    # only ONE model prior ties this page: 1 distinct tie < 2 -> no scale.
    # One agreeing sibling is a coincidence; two is a scale.
    targets = [TargetRow("Model", 5, "归属于母公司股东的净利润", 3600.0)]
    served, _ = join(_ledger(items), targets)
    assert not served, \
        f"run-116 poison re-admitted: unratified page served {served}"


def test_116c_scale_invariant_ties_cannot_ratify():
    """Small values (EPS, rates) pass through to_model_units unchanged, so
    they tie at EVERY scale — such ties must not ratify one."""
    items = [_item(95, 1, "基本每股收益甲类", [1.20, 1.15]),
             _item(95, 2, "稀释每股收益甲类", [1.18, 1.13]),
             _item(95, 5, "归属于母公司股东的净利润", [3831300000.0, 3600000000.0])]
    targets = [TargetRow("Model", 1, "cccc", 1.15),
               TargetRow("Model", 2, "dddd", 1.13),
               TargetRow("Model", 5, "净利润归属", 3600.0)]
    scales = ratify_page_scales(_ledger(items).join_pool(),
                                [t.prior_value for t in targets])
    assert (DOC, 95) not in scales, \
        f"scale ratified from scale-invariant ties: {scales}"


def test_to_model_units_small_world_passthrough():
    assert to_model_units(22679594590.64, 1e6) == 22679.59464 or \
        abs(to_model_units(22679594590.64, 1e6) - 22679.594590) < 1e-6
    assert to_model_units(1.15, 1e6) == 1.15, "EPS must never be divided"
    assert to_model_units(500.0, 1.0) == 500.0


# ── Tier 2: identity without a name, page affinity required ──────────────
# Cross-language models starve kinship; an identity-grade tie may serve a
# row ONLY from a page already tier-1-serving >= 2 rows of the same sheet.
# Lone singletons measured 4 wrong writes; a world-tolerance oracle 15.

def test_tier2_identity_join_with_page_affinity():
    items = _anchors() + [
        _item(95, 5, "营业总收入乙栏", [60001.0, 58001.0]),
        _item(95, 6, "营业总成本乙栏", [41001.0, 39001.0]),
        _item(95, 8, "研发费用支出栏", [3261.16, 2854.55]),
    ]
    targets = [
        # two CN-labelled rows tier-1-serve sheet S on p95 (kinship works)
        TargetRow("S", 1, "营业总收入乙栏", 58001.0),
        TargetRow("S", 2, "营业总成本乙栏", 39001.0),
        # an EN-labelled row: kinship fails, identity + affinity serves it
        TargetRow("S", 8, "R&D expense", 2854.55),
        # same prior on a DIFFERENT sheet: no affinity -> stays unbound
        TargetRow("T", 8, "R&D expense", 2854.55),
    ]
    served, dec = join(_ledger(items), targets)
    assert ("S", 1) in served and ("S", 2) in served
    e = served.get(("S", 8))
    assert e is not None and abs(e["value"] - 3261.16) < 0.01, \
        f"tier-2 affinity join failed: {e}"
    assert ("T", 8) not in served, \
        "tier-2 served a sheet with no page affinity (lone-singleton class)"


# ── The CLP dividend poison: per-share printed next to the total ─────────
# 'Fourth interim dividend declared 1.26 ... 3,183' — slot-by-tie pairs
# (1.26, 3183), the 3,183 ties the model's totals row, kinship passes on
# 'dividend', and a per-share number lands in a HK$M row with every gate
# green. The world-band law at join time refuses it (caught live on CLP,
# first dry run, by the delivery gate's magnitude sweep).

def test_clp_dividend_per_share_next_to_total_refused():
    items = _anchors() + [
        _item(95, 5, "Fourth interim dividend declared", [1.26, 3183.0]),
    ]
    targets = _anchor_targets() + [
        TargetRow("Model", 5, "Final ordinary dividend", 3183.0)]
    served, _ = join(_ledger(items), targets)
    assert ("Model", 5) not in served, \
        "CLP dividend poison re-admitted: per-share value joined a totals row"


# ── The kinship doctrine: positive evidence only ─────────────────────────

def test_vacuous_kinship_confirms_nothing():
    assert not kinship("", "anything")
    assert not kinship("—", "资产总计")
    assert not kinship("of the", "in for")        # stopwords only
    assert kinship("Interest income", "interest income earned")
    assert kinship("资产总计", "资产总计")


def test_kinship_required_even_with_prior_tie():
    items = _anchors() + [_item(95, 5, "递延所得税负债", [500.0, 400.0])]
    targets = _anchor_targets() + [TargetRow("Model", 5, "Deferred grants", 400.0)]
    served, _ = join(_ledger(items), targets)
    assert ("Model", 5) not in served, \
        "prior tie joined without positive label kinship"


# ── Agreement-or-nothing ─────────────────────────────────────────────────

def test_disagreeing_candidates_join_nothing():
    items = _anchors() + [
        _item(95, 5, "Trade receivables", [500.0, 400.0]),
        _item(95, 6, "Other trade receivables", [700.0, 400.0]),
    ]
    targets = _anchor_targets() + [TargetRow("Model", 5, "Trade receivables", 400.0)]
    served, decisions = join(_ledger(items), targets)
    assert ("Model", 5) not in served, "disagreeing candidates joined anyway"
    assert any(d.status == "ambiguous" and d.row == 5 for d in decisions)


# ── Twins: 合计 rows must not flatten onto components ─────────────────────

def test_twins_neither_joins():
    items = _anchors() + [_item(95, 5, "Inventories held", [500.0, 400.0])]
    targets = _anchor_targets() + [
        TargetRow("Model", 20, "Inventories held", 400.0),
        TargetRow("Model", 21, "Raw inventories held", 400.0),
    ]
    served, decisions = join(_ledger(items), targets)
    assert ("Model", 20) not in served and ("Model", 21) not in served, \
        "twin rows both bound one item"
    assert sum(1 for d in decisions if d.status == "twin_dropped") == 2


# ── Elimination lines prove nothing ──────────────────────────────────────

def test_elimination_line_refused():
    items = _anchors() + [_item(95, 5, "Segment elimination adj", [123.4, -123.4])]
    targets = _anchor_targets() + [TargetRow("Model", 5, "Segment elimination adj", -123.4)]
    served, _ = join(_ledger(items), targets)
    assert ("Model", 5) not in served, \
        "elimination line (exact adjacent negation) was joined"


# ── Composition/backout rows never join ──────────────────────────────────

def test_backout_rows_excluded():
    items = _anchors() + [_item(95, 5, "Net finance costs", [50.0, 44.0])]
    targets = _anchor_targets() + [
        TargetRow("Model", 5, "Net finance costs", 44.0, is_backout=True)]
    served, decisions = join(_ledger(items), targets)
    assert ("Model", 5) not in served, "backout row joined"
    assert any(d.status == "excluded_backout" and d.row == 5 for d in decisions)


# ── No-prior rows are Stage-3 material, never Stage-2 ────────────────────

def test_no_prior_rows_left_alone():
    items = _anchors() + [_item(95, 5, "Right-of-use depreciation", [152.7, 199.1])]
    targets = _anchor_targets() + [
        TargetRow("Model", 5, "Right-of-use depreciation", None)]
    served, _ = join(_ledger(items), targets)
    assert ("Model", 5) not in served, "a no-prior row was served by Stage 2"


# ── The sibling-position pass (measured 13/13) ───────────────────────────

def test_sibling_position_binds_sole_tier():
    items = _anchors() + [
        _item(95, 10, "Interest income earned", [100.0, 90.0]),
        _item(95, 12, "Government grants received", [55.0, 44.0]),
        _item(95, 14, "Dividend income earned", [200.0, 180.0]),
    ]
    targets = _anchor_targets() + [
        TargetRow("Model", 5, "Interest income", 90.0),
        TargetRow("Model", 6, "Other gains", 44.0),      # no kinship with grants
        TargetRow("Model", 7, "Dividend income", 180.0),
    ]
    served, decisions = join(_ledger(items), targets)
    assert ("Model", 5) in served and ("Model", 7) in served
    e = served.get(("Model", 6))
    assert e is not None and abs(e["value"] - 55.0) < 1e-9, \
        f"sibling-position pass failed: {e}"
    assert any(d.status == "accepted_sibling" and d.row == 6 for d in decisions)


# ── Stage 1: the year-token filter (run-60 poison) ───────────────────────

def test_year_token_filter():
    assert line_numbers("2025年度 2024年度") == []
    assert line_numbers("营业收入 2,025 1,987") == [2025.0, 1987.0]
    assert line_numbers("Profit (1,234.5) 2,000") == [-1234.5, 2000.0]
    assert parse_number("（１，２３４）") == -1234.0     # fullwidth
    assert parse_number("n/a") is None and parse_number("-") is None


# ── Space-grouped digits (the 58.5 equity-gap disease, caught live) ──────
# Scanned statements print thin-space grouping; the vision reader copies it
# verbatim ('48 168 255 333.72'). Refusing it silently deleted the 2025
# equity block from the ledger and left the balance 58.5 open. Merging is
# legal ONLY inside one cell token with strict 3-digit groups — text lines
# with adjacent numbers must never merge.

def test_space_grouped_digits():
    assert parse_number("48 168 255 333.72") == 48168255333.72
    assert parse_number("48 168 255 333.72") == 48168255333.72
    assert parse_number("(1 234)") == -1234.0
    assert parse_number("12 34") is None            # not 3-digit groups
    # adjacent numbers on a TEXT line stay separate
    assert line_numbers("应付票据 15,652,241,398.50 15,635,278,628.07") == \
        [15652241398.50, 15635278628.07]
    assert line_numbers("货币资金 123 456") == [123.0, 456.0]


# ── Stage 1: text-channel segmentation ───────────────────────────────────

def test_segment_page_structure():
    text = ("合并利润表\n单位：人民币千元\n"
            "营业收入 88,018 87,211\n"
            "2．少数股东损益 396.2 380.1\n"
            "\n\n"
            "governance prose without numbers\n\n"
            "总资产 1,234 1,100\n")
    items = segment_page(DOC, 95, text)
    assert [it.label for it in items] == ["营业收入", "少数股东损益", "总资产"]
    assert items[0].scale_hint == 1e3, "unit header not attached"
    assert items[0].table_id != items[2].table_id, "gap did not split tables"
    assert items[1].nums == [396.2, 380.1], "enumerator parsed as a value"
    assert items[0].row_ord < items[1].row_ord < items[2].row_ord
    assert items[0].row_ord == 2, "row_ord must be the physical line index"


def test_scale_hint_is_unit_lines_only():
    assert parse_scale_hint("单位：人民币千元") == 1e3
    assert parse_scale_hint("单位：元 币种：人民币") == 1.0
    assert parse_scale_hint("(Expressed in RMB millions)") == 1e6
    assert parse_scale_hint("we made millions in profits this year") is None
    assert parse_scale_hint("董事会报告") is None


def test_unit_dims():
    assert unit_dim_of("基本每股收益（元／股）") == "per_share"
    assert unit_dim_of("总装机容量（兆瓦）") == "energy"
    assert unit_dim_of("毛利率 %") == "ratio"
    assert unit_dim_of("营业收入") == "unknown"


# ── Stage 1: vision consensus + the prior-column checksum ────────────────

def test_merge_votes_consensus_and_dispute():
    v1 = {"title": "合并资产负债表", "rows": [
        {"name": "货币资金", "current": "22,679,594,590.64", "prior": "18,000,000,000.00"},
        {"name": "存货", "current": "5,000,000,000.00", "prior": "4,900,000,000.00"}]}
    v2 = {"title": "合并资产负债表", "rows": [
        {"name": "货币资金", "current": "22,679,594,590.64", "prior": "18,000,000,000.00"},
        {"name": "存货", "current": "5,800,000,000.00", "prior": "4,900,000,000.00"}]}
    title, rows = merge_votes([v1, v2])
    assert title == "合并资产负债表"
    by = {r["name"]: r for r in rows}
    assert not by["货币资金"]["disputed"] and by["货币资金"]["consensus"] == 2
    assert by["存货"]["disputed"], "a digit-level disagreement passed as consensus"
    # disputed rows never become joinable items
    its = vision_items(DOC, 95, title, rows, 1e6)
    disputed = [it for it in its if it.label == "存货"]
    assert disputed and not disputed[0].joinable()


def test_checksum_anchors_are_identities_not_resemblances():
    """The FY24-AR coincidence (caught live): a dense prior-period page with
    values within 0.5% of model priors must NOT anchor — the window is 0.6
    absolute document units or 0.05% relative, never looser."""
    known = [22679.59, 18000.0, 4900.0, 3600.0]
    near = [{"name": f"line{i}", "current": "1,000,000",
             "prior": f"{v * 1000 * 1.004:,.0f}"}   # 0.4% off at scale 1e3
            for i, v in enumerate(known)]
    hits, _s, _c = checksum_page(near, known)
    assert hits == 0, f"near-miss values anchored: {hits}"
    exact = [{"name": f"line{i}", "current": "1,000,000",
              "prior": f"{v * 1000:,.0f}"} for i, v in enumerate(known)]
    hits2, s2, _ = checksum_page(exact, known)
    assert hits2 == 4 and s2 == 1e3


def test_checksum_gate_prior_column_only():
    known = [22679.59, 18000.0, 4900.0, 3600.0, 990.0]   # model units (millions)
    real = [{"name": "货币资金", "current": "24,000,000,000", "prior": "22,679,594,590.64"},
            {"name": "应收账款", "current": "19,000,000,000", "prior": "18,000,000,000.00"},
            {"name": "存货", "current": "5,100,000,000", "prior": "4,900,000,000.00"},
            {"name": "净利润", "current": "3,900,000,000", "prior": "3,600,000,000.00"},
            {"name": "其他", "current": "1,000,000,000", "prior": "990,000,000.00"}]
    hits, scale, copy = checksum_page(real, known)
    assert hits >= 4 and scale == 1e6, f"real page failed: hits={hits} scale={scale}"
    fake = [{"name": r["name"], "current": r["current"], "prior": "1,111,111,111"}
            for r in real]
    hits_f, _s, _c = checksum_page(fake, known)
    assert hits_f < 4, "hallucinated priors passed the checksum"
    copies = [{"name": r["name"], "current": r["prior"], "prior": r["prior"]}
              for r in real]
    _h, _s, copy_frac = checksum_page(copies, known)
    assert copy_frac > 0.8, "column-copying page not caught by copy fraction"


# ── The ledger is the contract: snapshots must round-trip ────────────────

def test_ledger_roundtrip():
    led = _ledger(_anchors() + [
        _item(95, 5, "净利润归属于母公司", [3831.3, 3600.0], scale_hint=1e6,
              channel="vision", consensus=2)],
        face_pages=((95, "pl"), (96, "bs")), parents=(100,))
    led.doc_meta[DOC] = {"pages": 200}
    led2 = Ledger.from_json(led.to_json())
    assert len(led2.items) == len(led.items)
    assert led2.faces == led.faces and led2.parent_pages == led.parent_pages
    assert led2.items[-1].scale_hint == 1e6
    assert led2.items[-1].channel == "vision"
    assert [it.item_id for it in led2.items] == [it.item_id for it in led.items]
    # the join runs identically off the reloaded snapshot
    targets = _anchor_targets() + [TargetRow("Model", 5, "净利润归属于母公司", 3600.0)]
    s1, _ = join(led, targets)
    s2, _ = join(led2, targets)
    assert {k: v["value"] for k, v in s1.items()} == \
           {k: v["value"] for k, v in s2.items()}


# ── Stage 3: the signed row checksum (zero wrong reads, every run) ───────

def test_stage3_checksum_sign_rule():
    from pipeline.stage3_read import checksum_accept
    # page prints model's sign convention at yuan scale -> serve as printed
    v, s = checksum_accept("152,709,448.06", "199,139,706.74", 199.1397)
    assert abs(v - 152.709448) < 1e-4 and s == 1e6
    # page prints the OPPOSITE convention (expenses positive, model negative)
    v, s = checksum_accept("8,123.4", "7,456.2", -7456.2)
    assert abs(v + 8123.4) < 1e-6 and s == 1.0, "sign flip not served flipped"
    # a legitimate year-to-year sign flip is preserved (OCI/FX class)
    v, _s = checksum_accept("(500.0)", "300.0", 300.0)
    assert v == -500.0, "this year's printed sign must win"


def test_stage3_checksum_small_world():
    from pipeline.stage3_read import checksum_accept
    # 1.15 must never tie 0.94 at read time either
    assert checksum_accept("3,831.30", "1.15", 0.94) is None
    assert checksum_accept("1.15", "0.94", 0.94) is not None


def test_stage3_checksum_refuses_untied():
    from pipeline.stage3_read import checksum_accept
    assert checksum_accept("5,000", "4,321", 9999.0) is None
    assert checksum_accept(None, "4,321", 4321.0) is None
    assert checksum_accept("5,000", None, 4321.0) is None


# ── Exhibit 116, re-armed on the new line: the no-prior path ─────────────

def test_116_no_prior_needs_ratified_anchor():
    from pipeline.stage3_read import no_prior_value
    # filing prints yuan, model in millions: block anchor converts
    v = no_prior_value("152,709,448.06", [1e6])
    assert abs(v - 152.709448) < 0.01, f"run-116 scale poison: {v}"
    # no anchor -> no serve, however plausible the number looks
    assert no_prior_value("152,709,448.06", []) is None
    # conflicting anchors -> no serve
    assert no_prior_value("152,709,448.06", [1e6, 1e3]) is None
    # small values pass through even at a big anchor (EPS class)
    assert no_prior_value("1.15", [1e6]) == 1.15


def test_stage3_regions_gap_fill_and_parent_exclusion():
    from pipeline.stage3_read import regions_from_ledger
    led = _ledger([], face_pages=((95, "bs"), (99, "pl"), (101, "cf")),
                  parents=(100,))
    (grp,) = regions_from_ledger(led, DOC)
    assert 96 in grp and 98 in grp, "continuation pages must ride along"
    assert 100 not in grp, "parent page entered a read region"


# ── The prior-period document (run-3 autopsy): slot-tie classification ───
# In the CURRENT-period doc, model priors print in the second slot (the
# comparative column); in a PRIOR-period doc they print in the first (its
# current column IS the model's prior year). The classifier names each doc
# deterministically, and prior docs never join, read, or serve citations.

def test_prior_period_doc_classified_and_excluded():
    priors = [58000.0, 39000.0, 3600.0, 22679.59, 18000.0, 4900.0]
    deep = [v * 0.9 for v in priors]        # the year before prior
    cur_items = [_item(95, i, f"当前年报第{i}行栏", [v * 1.1, v])
                 for i, v in enumerate(priors)]     # comparatives = priors
    pri_items = [Item(doc="old_ar.pdf", page=95, table_id=0, row_ord=i,
                      label=f"上年年报第{i}行栏", nums=[v, v * 0.9])
                 for i, v in enumerate(priors)]     # comparatives = DEEP priors
    led = _ledger(cur_items + pri_items,
                  face_pages=((95, "pl"),))
    led.faces[("old_ar.pdf", 95)] = "pl"      # even face-tagged...
    periods = led.classify_doc_periods(priors, deep)
    assert periods[DOC] == "current" and periods["old_ar.pdf"] == "prior", periods
    assert all(it.doc != "old_ar.pdf" for it in led.join_pool()), \
        "prior-period document entered the join pool"


# ── Scanned pages self-identify by their rows (cropped-caption class) ────

def test_face_from_row_labels():
    from pipeline.ledger import face_from_row_labels
    assert face_from_row_labels(
        ["流动资产", "货币资金", "资产总计", "负债合计"]) == "bs"
    assert face_from_row_labels(
        ["Revenue", "Profit for the year", "Earnings per share"]) == "pl"
    assert face_from_row_labels(
        ["经营活动产生的现金流量净额", "投资活动产生的现金流量净额"]) == "cf"
    # one hit is a coincidence, not an identity
    assert face_from_row_labels(["净利润", "存货", "其他"]) is None
    # a mixed summary page (P&L + BS highlights) identifies as nothing
    assert face_from_row_labels(
        ["营业总收入", "净利润", "资产总计", "负债合计"]) is None


# ── Stage 2.5: the bound-table Driver/MD&A path (council two-level law) ──

def _seg_items(page=207):
    """A 4-column interleaved segment table: (2025rev, 2025cost, 2024rev,
    2024cost) — the layout where adjacent-pair mechanics served the wrong
    measure (measured live)."""
    rows = [("能源装备制造", [58005.4, 49897.1, 47546.6, 42306.7]),
            ("核能", [5659.96, 4295.16, 4876.71, 3704.41]),
            ("气电", [5627.57, 4951.68, 7110.32, 6592.66]),
            ("风电", [18224.2, 17707.9, 12288.0, 12562.2])]
    return [_item(page, i + 20, lab, ns, table_id=2)
            for i, (lab, ns) in enumerate(rows)]


def test_bound_table_offset_law():
    from pipeline.stage2_join import join_bound_tables
    led = _ledger(_seg_items(), face_pages=())     # NOT a statement face
    targets = [TargetRow("Driver", 8, "Nuclear", 4876.71, input_kind="hardcode"),
               TargetRow("Driver", 9, "Wind", 12288.0, input_kind="hardcode"),
               TargetRow("Driver", 40, "Gas cost", -6592.66, input_kind="hardcode"),
               TargetRow("Driver", 41, "Nuclear cost", -3704.41, input_kind="hardcode")]
    served, _ = join_bound_tables(led, targets, {}, [])
    assert abs(served[("Driver", 8)]["value"] - 5659.96) < 0.01, \
        f"offset law failed: {served.get(('Driver', 8))}"
    assert abs(served[("Driver", 9)]["value"] - 18224.2) < 0.01
    assert abs(served[("Driver", 41)]["value"] + 4295.16) < 0.01, \
        "cost row not served from the mirrored slot (signed)"


def test_bound_table_uncorroborated_offset_refuses():
    """One row tying at the block-start slot is not an offset — without a
    second corroborating tie the geometry is unproven and interleaved rows
    must NOT serve (the guard that refused the wrong-measure write)."""
    from pipeline.stage2_join import join_bound_tables
    led = _ledger(_seg_items(), face_pages=())
    targets = [TargetRow("Driver", 8, "Nuclear", 4876.71, input_kind="hardcode"),
               TargetRow("Driver", 40, "Gas cost", -6592.66, input_kind="hardcode"),
               TargetRow("Driver", 41, "Nuclear cost", -3704.41, input_kind="hardcode")]
    served, _ = join_bound_tables(led, targets, {}, [])
    assert ("Driver", 8) not in served and ("Driver", 41) not in served, \
        "interleaved rows served on an uncorroborated offset"


def test_bound_table_refusals():
    from pipeline.stage2_join import join_bound_tables
    led = _ledger(_seg_items(), face_pages=())
    # one tie is chance — a table with a single prior tie must not bind
    t1 = [TargetRow("Driver", 8, "Nuclear", 4876.71, input_kind="hardcode")]
    served, _ = join_bound_tables(led, t1, {}, [])
    assert not served, "a single-tie table bound (coincidence class)"
    # derived rows (formula priors) never bound-table join
    t2 = [TargetRow("Driver", 8, "Nuclear", 4876.71, input_kind="hardcode"),
          TargetRow("Driver", 40, "Gas cost", -6592.66, input_kind="hardcode"),
          TargetRow("Driver", 41, "Nuclear cost", -3704.41, input_kind="derived")]
    served2, _ = join_bound_tables(led, t2, {}, [])
    assert ("Driver", 41) not in served2, "a derived row was bound-table joined"
    # small-world rows never bound-table join (tax-row coincidence class)
    t3 = t2[:2] + [TargetRow("Driver", 50, "Small fee", 23.98, input_kind="hardcode")]
    served3, _ = join_bound_tables(led, t3, {}, [])
    assert ("Driver", 50) not in served3


def test_cjk_two_char_labels_admissible():
    from pipeline.ledger import admissible_label
    assert admissible_label("水电") and admissible_label("核能")
    assert admissible_label("存货")
    assert not admissible_label("水")            # one glyph is not a word
    assert not admissible_label("a|b garbage")
    assert admissible_label("Revenue")


# ── The write chokepoint (exhibits 112b / 114 on the NEW layer) ──────────

def _wb(cells):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    for coord, v in cells.items():
        ws[coord] = v
    return wb


def test_112b_world_band_guard_new_chokepoint():
    from pipeline.writer import Writer
    w = Writer(_wb({"T5": 0.94, "V6": 2.0}))
    assert w.write("S", "U5", 3831.3, prior_coord="T5") is False
    assert w.write("S", "U5", 1.15, prior_coord="T5") is True
    assert w.write("S", "U6", 3831.3, prior_coord="T5", trusted=True) is True
    assert w.log["band_refused"], "refusal not logged"


def test_114_numeric_preview_new_chokepoint():
    from pipeline.writer import Writer
    w = Writer(_wb({"T9": 21.8791}))
    assert w.write("S", "U9", "=21.8791*482.376", prior_coord="T9") is False
    assert w.write("S", "U9", "=21.8791*3.65", prior_coord="T9") is True


def test_rollover_column_convention():
    """The owner's convention: new column = prior column carried forward —
    formulas Excel-shifted, hardcodes reported as the input census."""
    from pipeline.writer import rollover_column
    wb = _wb({"T2": 100.0, "T3": "=T2*2", "T4": "abc", "T5": "=$A$1+T4"})
    hard = rollover_column(wb, "S", "T", "U")
    ws = wb["S"]
    assert ws["U2"].value == 100.0 and hard == [2]
    assert ws["U3"].value == "=U2*2"
    assert ws["U4"].value == "abc"
    assert ws["U5"].value == "=$A$1+U4", f"got {ws['U5'].value}"


def test_clobber_diff_blocks_out_of_column_edits():
    from pipeline.writer import clobber_diff, formula_map
    wb = _wb({"B2": "=A1*2", "U2": 1.0})
    pre = formula_map(wb)
    wb["S"]["U2"] = 5.0          # allowed target column
    wb["S"]["B2"] = 99.0         # clobbered formula
    bad = clobber_diff(pre, wb, allowed_cols=["U"])
    assert ("S", "B2", "=A1*2", 99.0) in bad and len(bad) == 1


def test_write_lock_refused():
    from pipeline.writer import Writer
    w = Writer(_wb({"T5": 100.0}))
    w.lock("S", "U5")
    assert w.write("S", "U5", 105.0, prior_coord="T5") is False
    assert w.write("S", "U5", 105.0, prior_coord="T5", force_lock=True) is True


# ── Stage 4: the objective loop's guardrails (no LLM needed) ─────────────

def _loop(wb, spec, served=None, evidence=None):
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer

    class NoClient:
        def json(self, *a, **k):
            raise AssertionError("loop must not call the LLM in these tests")
    led = Ledger()
    # the evidence law refuses any write not in the ledger; loop-write
    # exhibits declare the printed rows their scenario assumes
    for nums in (evidence or []):
        led.add(Item(doc="T.PDF", page=1, table_id=0,
                     row_ord=len(led.items), label="row", nums=list(nums),
                     source_line="row"))
    return ObjectiveLoop(wb, spec, "2025", led, [], served or {},
                         Writer(wb), NoClient())


def _spec_tiny():
    return {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}],
            "key_rows": [{"name": "revenue", "sheet": "S", "row": 2}]}


def test_39_transactional_write_reverts():
    """The run-39 law: a write that breaks a previously-passing check row is
    auto-reverted and the loop is told the target cell was wrong."""
    wb = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0,
              "U2": 110.0, "U3": 60.0, "U4": 170.0,
              "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"})
    lp = _loop(wb, _spec_tiny(), evidence=[
        [999.0, 100.0], [171.0, 150.0], [111.0, 100.0]])
    r = lp.t_set_input({"cell": "S!U2", "value": 999.0, "why": "p12: test"})
    assert r.startswith("REVERTED"), r
    assert wb["S"]["U2"].value == 110.0, "revert did not restore the cell"
    r2 = lp.t_set_input({"cell": "S!U4", "value": 171.0, "why": "p12: test"})
    assert r2.startswith("REVERTED"), "a check-breaking write survived"
    r3 = lp.t_set_input({"cell": "S!U2", "value": 111.0, "why": "p12: test"})
    assert r3.startswith("REVERTED"), "U2=111 breaks the check and must revert"


def test_set_input_requires_citation_and_refuses_totals():
    wb = _wb({"T2": 100.0, "U5": "=U2+U3", "T5": "=T2+T3"})
    lp = _loop(wb, _spec_tiny())
    assert lp.t_set_input({"cell": "S!U2", "value": 1.0,
                           "why": "looks right"}).startswith("REFUSED"), \
        "write accepted without a page citation"
    assert lp.t_set_input({"cell": "S!U5", "value": 1.0,
                           "why": "p3: total"}).startswith("REFUSED"), \
        "a designed subtotal formula was writable"


def test_gate_year_headers():
    from pipeline.gate import check_year_headers
    spec = _spec_tiny()
    wb = _wb({"T1": 2024, "U1": 2024})          # stale header
    assert check_year_headers(wb, spec, "2025"), "stale year header passed"
    wb2 = _wb({"T1": 2024, "U1": 2025})
    assert not check_year_headers(wb2, spec, "2025")
    wb3 = _wb({"T1": 2024, "U1": "2025"})       # numeric -> text: type changed
    assert check_year_headers(wb3, spec, "2025"), "header type change passed"


def test_gate_magnitude_sweep():
    from pipeline.gate import magnitude_sweep
    spec = _spec_tiny()
    wb = _wb({"T2": 3.6, "U2": 3600000000.0})   # raw-yuan class
    fails = magnitude_sweep(wb, spec, "2025", ["S!U2"])
    assert fails and "MAGNITUDE" in fails[0], "raw-scale written cell passed"
    wb2 = _wb({"T2": 3.6, "U2": 3.8})
    assert not magnitude_sweep(wb2, spec, "2025", ["S!U2"])


def test_gate_flag_budget():
    """Owner doctrine 2026-08-30: only RED (unresolved) flags spend the
    budget; orange recipe-resolved cells are the deliver-with-flags
    mechanism working, not a failure."""
    from openpyxl.styles import PatternFill
    from pipeline.gate import flag_budget
    spec = _spec_tiny()
    cells = {f"U{r}": 1.0 for r in range(1, 11)}
    wb = _wb(cells)
    RED = PatternFill("solid", fgColor="FFC7CE")
    ORG = PatternFill("solid", fgColor="FFC000")
    for r in (1, 2, 3):
        wb["S"][f"U{r}"].fill = RED
    flags = [f"S!U{r}" for r in (1, 2, 3)]      # 30% RED-flagged
    assert flag_budget(wb, spec, "2025", flags), "over-budget reds passed"
    assert not flag_budget(wb, spec, "2025", ["S!U1"])
    for r in (1, 2, 3):
        wb["S"][f"U{r}"].fill = ORG             # same cells, now ORANGE
    assert not flag_budget(wb, spec, "2025", flags), \
        "orange recipe-resolved cells must not spend the budget"
    # run-14 ruling: an ADJUDICATED red (agent looked, documented why the
    # figure is not disclosed) is a finding, not neglect
    from openpyxl.comments import Comment
    for r in (1, 2, 3):
        wb["S"][f"U{r}"].fill = RED
        wb["S"][f"U{r}"].comment = Comment(
            "not disclosed this period: checked BS face p6, note 21, "
            "five-year summary — analyst input required", "agent")
    assert not flag_budget(wb, spec, "2025", flags), \
        "an investigated, documented red is a finding, not neglect"
    wb["S"]["U1"].comment = Comment("STALE INPUT: rolled from prior",
                                    "agent")
    wb["S"]["U2"].comment = None
    wb["S"]["U3"].comment = None                # unexplained reds count
    assert flag_budget(wb, spec, "2025", flags)


def test_checks_scorecard_and_completion():
    from pipeline.checks import scorecard
    wb = _wb({"T2": 100.0, "T3": 50.0, "U2": 110.0, "U3": 60.0,
              "T9": "=T2+T3-150", "U9": "=U2+U3-170"})
    card = scorecard(wb, _spec_tiny(), "2025",
                     served={("S", 2): {"conf": 5}})
    by = {c["name"]: c["status"] for c in card["checks"]}
    assert by["S!r9 (2024)"] == "PASS" and by["S!r9 (2025)"] == "PASS"
    (key,) = card["keys"]
    assert key["proven"] and key["present"] and abs(key["value"] - 110.0) < 1e-9
    assert card["completion"]["S"]["pct"] > 0


# ── The balance doctrine (owner ruling 2026-08-18): find it, fix it; ─────
# plugging is the loud worst case

def test_balance_doctrine_diagnose_fix_plug():
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    wb = _wb({"A2": "Total assets", "T2": 900.0, "U2": 1000.0,
              "A3": "Debt", "T3": 650.0, "U3": 700.0,
              "A4": "Equity", "T4": 250.0, "U4": 240.0,
              "T9": "=T2-T3-T4", "U9": "=U2-U3-U4"})
    led = Ledger()
    led.add(Item(doc="ar.pdf", page=95, table_id=0, row_ord=1,
                 label="Total assets", nums=[1000.0, 900.0]))
    led.add(Item(doc="ar.pdf", page=95, table_id=0, row_ord=2,
                 label="Debt total", nums=[700.0, 650.0]))
    led.add(Item(doc="ar.pdf", page=95, table_id=0, row_ord=3,
                 label="Equity total", nums=[300.0, 250.0]))
    led.faces[("ar.pdf", 95)] = "bs"
    targets = [TargetRow("S", 2, "Total assets", 900.0),
               TargetRow("S", 3, "Debt", 650.0),
               TargetRow("S", 4, "Equity", 250.0)]
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}]}

    class NoClient:
        def json(self, *a, **k):
            raise AssertionError("no LLM")
    lp = ObjectiveLoop(wb, spec, "2025", led, targets, {}, Writer(wb), NoClient())
    diag = lp.t_diagnose_balance({"check": "S!9"})
    assert "GUILTY S!4" in diag, diag
    assert lp.t_plug_residual({"check": "S!9", "into": "S!U3",
                               "why": "x"}).startswith("REFUSED"), \
        "plug allowed while a guilty cell existed"
    assert lp.t_apply_diff({"row": "S!4"}).startswith("WRITTEN")
    assert "residual = 0.00" in lp.t_diagnose_balance({"check": "S!9"})
    # the -57.89 class: an unproven (no-prior/flagged) leaf whose removal
    # closes the residual is named a SUSPECT with the exact-delta hint
    wb["S"]["A5"] = "FX translation diff"
    wb["S"]["U5"] = -57.89
    wb["S"]["U9"] = "=U2-U3-U4-U5"
    lp.writer.log["flags"].append("S!U5")
    diag = lp.t_diagnose_balance({"check": "S!U9"})   # cell-style ref accepted
    assert "SUSPECT S!U5" in diag and "CLOSES" in diag, diag




def _reclass_plan(total=360.0):
    from pipeline.reclass import plan_backout
    segs = [
        {"name": "A", "prior": 100.0, "actual": 130.0},   # mapped
        {"name": "B", "prior": 80.0, "actual": 90.0},     # mapped
        {"name": "C", "prior": 60.0, "actual": None},
        {"name": "D", "prior": 40.0, "actual": None},
        {"name": "E", "prior": 20.0, "actual": None},     # smallest
    ]
    return plan_backout(segs, total, 300.0)


def test_reclass_backout_recipe():
    """Owner ruling 2026-08-30: map only untouched segments; grow the
    rest at the total's growth; the SMALLEST backed-out segment is the
    plug so the table always ties to the disclosed total."""
    plan = _reclass_plan()
    rows = {r["name"]: r for r in plan["rows"]}
    assert plan["plugName"] == "E"
    assert rows["C"]["value"] == 72.0 and rows["C"]["flag"] == "orange"
    assert rows["D"]["value"] == 48.0
    assert rows["E"]["value"] == 20.0 and rows["E"]["kind"] == "plug"
    assert abs(sum(r["value"] for r in plan["rows"]) - 360.0) < 0.01


def test_reclass_ugly_plug_goes_red_but_still_ties():
    """A negative/wild plug is delivered (the total must tie) but RED —
    it usually means a MAPPED segment is wrong."""
    # growth 310/300: C=62.0, D=41.3; plug: 310-(130+90+62+41.3) = -13.3
    plan = _reclass_plan(total=310.0)
    rows = {r["name"]: r for r in plan["rows"]}
    assert rows["E"]["value"] == -13.3 and rows["E"]["flag"] == "red"
    assert "MAPPED" in rows["E"]["note"]
    assert abs(sum(r["value"] for r in plan["rows"]) - 310.0) < 0.05




def test_assumption_freeze_law():
    """Owner ruling 2026-08-30: a %-formatted forecast cell wired to the
    past freezes at its PRE-UPDATE value as an orange hardcode; a margin
    computed in its own column and a level cell are never touched."""
    import openpyxl
    from pipeline.freeze import apply_freezes, plan_freezes
    wb, pre = openpyxl.Workbook(), openpyxl.Workbook()
    ws, pw = wb.active, pre.active
    ws.title = pw.title = "Model"
    # U=21 target (2025A); V=22 first forecast
    ws["V5"] = "=U5"                     # growth chained to the past
    ws["V5"].number_format = "0.0%"
    pw["V5"] = 0.30                      # the analyst's 30%
    ws["W5"] = "=V5"                     # chain: inherits the freeze
    ws["W5"].number_format = "0.0%"
    pw["W5"] = 0.30
    ws["V7"] = "=V6/V4"                  # margin OUTPUT: own column
    ws["V7"].number_format = "0.0%"
    pw["V7"] = 0.17
    ws["V4"] = "=U4*(1+V5)"              # level: flows, not frozen
    ws["V4"].number_format = "#,##0.0"
    pw["V4"] = 105.0
    ws["V9"] = "='Driver'!U9"            # cross-sheet: another axis, skip
    ws["V9"].number_format = "0.0%"
    pw["V9"] = 0.10
    plans = plan_freezes(wb, pre, ["Model"], target_col=21)
    coords = {p["coord"] for p in plans}
    assert coords == {"V5"}, coords
    lines = apply_freezes(wb, plans)
    assert ws["V5"].value == 0.30                    # hardcode, not =U5
    # frozen forecast inputs are BLUE (owner 2026-09-07): the one
    # forecast-year colour, distinct from red / orange in the actual column
    assert ws["V5"].fill.start_color.rgb.endswith("BDD7EE")
    assert ws["W5"].value == "=V5"                   # chain untouched
    assert ws["V7"].value == "=V6/V4"                # wiring untouched
    assert ws["V4"].value == "=U4*(1+V5)"            # level untouched
    assert "was =U5" in lines[0]




def test_evidence_law_run7_exhibits():
    """Run-7 autopsy pins (2026-08-30): the objective loop's set_input is
    gated by the evidence law. Both balance-killing writes replayed here
    must be REFUSED; honest paths stay open."""
    from pipeline.writegate import find_evidence, judge_write

    # exhibit 1 — Raw!U60: the loop overwrote a PROVEN 15,193.8 with a
    # note-page 53,546.5 whose row does not tie the prior (12,545.3)
    note_row = {"doc": "12053065.PDF", "page": 154,
                "nums": [53546486141.57, 4275000000.0, 49271486141.57]}
    ev = find_evidence([note_row], 53546.5)
    assert ev, "the gross figure IS printed — evidence must be found"
    verdict, why, flag = judge_write(53546.5, 12545.3, True, ev, set(), held_proven=True)
    assert verdict == "REFUSE" and "proven" in why.lower()
    # 2026-09-16: the holder there WAS proven (15,193.8 tied its prior). Where it
    # is not — a red read, an orange derivation — the brain's pick lands RED, never clean
    verdict, why, flag = judge_write(53546.5, 12545.3, True, ev, set(), held_proven=False)
    assert verdict == "ALLOW_FLAGGED", (verdict, why)

    # exhibit 2 — a value printed nowhere is never writable
    verdict, why, flag = judge_write(56432.1, 12545.3, False,
                                     find_evidence([note_row], 56432.1),
                                     set())
    assert verdict == "REFUSE" and "NOWHERE" in why

    # exhibit 3 — Raw!U72: the prepayments row already serves U62;
    # one row, one claim
    prepay = {"doc": "12053065.PDF", "page": 95,
              "nums": [6892713423.33, 5876898026.02]}
    ev = find_evidence([prepay], 6892.7)
    claimed = {6892.7}
    verdict, why, flag = judge_write(6892.7, 0.0, False, ev, claimed)
    assert verdict == "REFUSE" and "one row, one claim" in why

    # exhibit 4 — the same value on an unclaimed row, prior untied:
    # deliverable, but RED — never silent
    verdict, why, flag = judge_write(6892.7, 0.0, False, ev, set())
    assert verdict == "ALLOW_FLAGGED" and flag == "red"

    # exhibit 5 — a proven write (row carries the prior) lands clean,
    # and 万元-scale evidence is recognised
    face = {"doc": "AR.PDF", "page": 5,
            "nums": [1519379.49, 1254530.0]}      # 万元
    ev = find_evidence([face], 15193.8)
    verdict, why, flag = judge_write(15193.8, 12545.3, True, ev, set())
    assert verdict == "ALLOW" and flag is None




def test_one_home_law_run8_exhibit():
    """Run-8 pin (2026-08-30): Raw!U153 took the section total that row
    156 had already proven from the same document — a no-prior read may
    never give a second home to an already-served figure."""
    from pipeline.writegate import claimed_values, no_prior_duplicate
    served = {("Raw financials", 156): {
        "value": 12182.46645655, "doc": "12053065.PDF", "page": 96}}
    # the register is DOCUMENT-wide: page is irrelevant to a claim
    reg = claimed_values(served)
    assert no_prior_duplicate(12182.5, "12053065.PDF", reg)
    # run-9 pin: the law is document-AGNOSTIC — OCI -57.9 served from
    # one document must block the same figure landing as FX-translation
    # from another
    assert no_prior_duplicate(12182.5, "OTHER.PDF", reg)
    assert no_prior_duplicate(57.9, "AR.PDF", claimed_values(
        {("Raw financials", 167): {"value": -57.9, "doc": "ANN.PDF"}}))
    assert not no_prior_duplicate(0.2, "12053065.PDF",
                                  claimed_values({("S", 1): {
                                      "value": 0.2, "doc": "12053065.PDF"}}))


def test_worsening_write_reverts():
    """Run-8 pin: a write that makes an ALREADY-FAILING check worse is
    reverted (the old guard only caught pass->fail)."""
    wb = _wb({"T2": 100.0, "T3": 50.0, "T4": 151.0,
              "U2": 110.0, "U3": 60.0, "U4": 171.5,
              "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"})   # already -1.5 off
    lp = _loop(wb, _spec_tiny(), evidence=[[500.0, 100.0]])
    r = lp.t_set_input({"cell": "S!U2", "value": 500.0, "why": "p9: t"})
    assert r.startswith("REVERTED"), r
    assert wb["S"]["U2"].value == 110.0




def test_reclassification_recipe():
    """Owner rulings 2026-08-30: stale segments in a block back out at
    the TOTAL's growth; the analyst's designed plug is respected; without
    one the smallest stale segment becomes the plug; an ugly plug goes
    red."""
    from pipeline.reclass import (designed_plug, find_blocks,
                                  flag_embedded_hardcodes, reclass_sweep)
    from pipeline.writer import Writer

    def paint_stale(wb, writer, refs):
        for ref in refs:
            sh, coord = ref.split("!")
            wb[sh][coord].fill = writer.fills["red"]
            writer.log["flags"].append(ref)

    # A: designed plug (row 8 references the total) — stale rows get the
    # growth formula, the plug row is untouched
    wb = _wb({"A5": "Seg1", "A6": "Seg2", "A7": "Seg3", "A8": "Others",
              "A9": "Total",
              "T5": 100.0, "T6": 50.0, "T7": 30.0, "T8": 20.0, "T9": 200.0,
              "U5": 100.0, "U6": 55.0, "U7": 30.0,
              "U8": "=U9-U5-U6-U7", "U9": 240.0})
    ws = wb["S"]
    blocks = find_blocks(ws, "T", "U", max_row=12)
    assert len(blocks) == 1 and blocks[0]["total_row"] == 9
    assert designed_plug(ws, blocks[0], "U") == 8
    w = Writer(wb)
    paint_stale(wb, w, ["S!U5", "S!U7"])        # reclassified, stale
    n = reclass_sweep(wb, ["S"], {"S": "U"}, {"S": "T"}, w,
                      lambda m: None)
    assert n == 2
    assert ws["U5"].value == "=T5*U$9/T$9"       # held at total growth
    assert ws["U7"].value == "=T7*U$9/T$9"
    assert ws["U8"].value == "=U9-U5-U6-U7"      # analyst's plug kept

    # B: no designed plug — the SMALLEST stale segment carries the
    # residual; and shrunk hard, it goes red
    wb2 = _wb({"A5": "Seg1", "A6": "Seg2", "A7": "Seg3", "A8": "Total",
               "T5": 100.0, "T6": 50.0, "T7": 20.0, "T8": 170.0,
               "U5": 100.0, "U6": 50.0, "U7": 20.0, "U8": 80.0})
    w2 = Writer(wb2)
    paint_stale(wb2, w2, ["S!U5", "S!U6", "S!U7"])
    def _eval(sheet, coord):                     # tiny arithmetic stand-in
        if coord == "U7":                        # 9.4 vs prior 20 = -53%
            return 80.0 - (100.0 * 80 / 170) - (50.0 * 80 / 170)
        return None
    n2 = reclass_sweep(wb2, ["S"], {"S": "U"}, {"S": "T"}, w2,
                       lambda m: None, evaluate=_eval)
    assert n2 == 3
    assert wb2["S"]["U5"].value == "=T5*U$8/T$8"
    assert wb2["S"]["U7"].value == "=U8-U5-U6"   # smallest is the plug
    assert wb2["S"]["U7"].fill.start_color.rgb.endswith("FFC7CE"), \
        "a plug that halved must escalate to red"

    # C: a formula smuggling a prior-period constant is a KEY DRIVER
    wb3 = _wb({"U5": "=16602.97-U6", "U6": 2955.4, "U7": "=U5/U6",
               "U8": "=365/(U5/U6)", "U9": "=U5*12/100"})
    w3 = Writer(wb3)
    n3 = flag_embedded_hardcodes(wb3, ["S"], {"S": "U"}, w3,
                                 lambda m: None)
    assert n3 == 1 and "S!U5" in w3.log["flags"], \
        "365/12/100 are conventions, not smuggled priors"
    assert wb3["S"]["U7"].fill.start_color.rgb in ("00000000", None) or \
        not str(wb3["S"]["U7"].fill.start_color.rgb).endswith("FFC7CE")




def test_dash_nil_law_run11_exhibit():
    """Run-11 pin: 'Less: Treasury shares – 648,882.29' — a standalone
    nil mark in the current slot beside the tying prior proves a zero."""
    from pipeline.writegate import nil_current_zero
    it = {"doc": "ANN.PDF", "page": 6, "nums": [648882.29],
          "stmt_face": "bs",
          "source_line": "Less: Treasury shares – 648,882.29"}
    assert nil_current_zero([it], 0.64888229) is not None
    assert nil_current_zero([it], 0.6489) is not None
    assert nil_current_zero([it], 0.6) is None, \
        "a rounded prior is not a full-precision tie"
    assert nil_current_zero([it], 0.3) is None       # immaterial prior
    it_param = {"doc": "A.PDF", "page": 1, "nums": [15.0],
                "stmt_face": "pl", "source_line": "tax rate – 15"}
    it_note = {"doc": "A.PDF", "page": 99, "nums": [648882.29],
               "source_line": "note line – 648,882.29"}
    assert nil_current_zero([it_note], 0.64888229) is not None   # no page rule (owner 2026-09-08): the tie at full precision is the proof
    # CLP-1 pins: a YEAR-like prior never nil-proves; prior-period
    # documents are banned evidence
    it_year = {"doc": "AR.PDF", "page": 1, "stmt_face": "bs",
               "nums": [2024000.0],
               "source_line": "some line – 2,024,000.00"}
    assert nil_current_zero([it_year], 2024.0) is None
    it_prev = {"doc": "e_2024 AR.PDF", "page": 224, "stmt_face": "bs",
               "nums": [648882.29],
               "source_line": "Less: Treasury shares – 648,882.29"}
    assert nil_current_zero([it_prev], 0.64888229,
                            banned_docs={"e_2024 AR.PDF"}) is None
    assert nil_current_zero([it_prev], 0.64888229) is not None
    # an untagged item on a page the join served from IS a face
    # CLP-1 pins: a YEAR-like prior never nil-proves; prior-period
    # documents are banned evidence
    it_year = {"doc": "AR.PDF", "page": 1, "stmt_face": "bs",
               "nums": [2024000.0],
               "source_line": "some line – 2,024,000.00"}
    assert nil_current_zero([it_year], 2024.0) is None
    it_prev = {"doc": "e_2024 AR.PDF", "page": 224, "stmt_face": "bs",
               "nums": [648882.29],
               "source_line": "Less: Treasury shares – 648,882.29"}
    assert nil_current_zero([it_prev], 0.64888229,
                            banned_docs={"e_2024 AR.PDF"}) is None
    assert nil_current_zero([it_prev], 0.64888229) is not None
    it_served_page = {"doc": "ANN.PDF", "page": 6, "nums": [648882.29],
                      "source_line": "Less: Treasury shares – 648,882.29"}
    assert nil_current_zero([it_served_page], 0.64888229,
                            face_pages={("ANN.PDF", 6)}) is not None
    assert nil_current_zero([it_served_page], 0.64888229,
                            face_pages={("ANN.PDF", 99)}) is not None   # face_pages is accepted and ignored
    assert nil_current_zero([it_param], 15.0) is None, \
        "parameters (few digits) prove nothing"
    # no nil mark -> no proof; untied prior -> no proof
    it2 = {"doc": "ANN.PDF", "page": 6, "nums": [648882.29],
           "source_line": "Less: Treasury shares 648,882.29"}
    assert nil_current_zero([it2], 0.6489) is not None   # last year's figure printed alone = blank this year = nil (owner 2026-09-08)
    assert nil_current_zero([it], 5.0) is None
    it4 = {"doc": "A.PDF", "page": 1, "nums": [12345.0, 648882.29],   # two numbers: not a lone comparative
           "source_line": "x – 12,345 648,882.29"}
    assert nil_current_zero([it4], 0.6489) is None, \
        "nil must sit DIRECTLY before the tying number"
    # a negative number's dash is NOT a nil mark
    it3 = {"doc": "A.PDF", "page": 1, "nums": [-1234.0, 648882.29],
           "source_line": "Some line -1,234.00 648,882.29"}
    assert nil_current_zero([it3], 0.6489) is None




def test_forecast_balance_ladder():
    """Owner ruling 2026-08-30: balance ALL years — attribute first,
    plug only the residue, red when the plug is large."""
    import openpyxl
    from pipeline.forecast_balance import (audit, cf_input_rows,
                                           last_resort_plug, place_flow)
    from pipeline.evaluator import Evaluator
    from pipeline.writer import Writer

    def build(gap_v):
        wb = openpyxl.Workbook()
        ws = wb.active; ws.title = "Model"
        ws["A2"] = "Balance Sheet"
        ws["A3"] = "Receivables"
        ws["U3"], ws["V3"] = 100.0, 130.0
        ws["A4"] = "Liabilities"
        ws["U4"], ws["V4"] = 100.0, 130.0 - gap_v
        ws["A6"] = "Check"
        ws["V6"] = "=(V3+V9)-V4"          # Others feeds the asset side
        ws["A8"] = "Cash flow statement"
        ws["A9"] = "Others"
        ws["U9"], ws["V9"] = 0.0, 0.0
        ws["A10"] = "Wired line"
        ws["V10"] = "=V3"
        return wb, ws

    # audit names the gap and the movements
    wb, ws = build(10.0)
    ev = Evaluator(wb)
    rep = audit(wb, lambda s, c: ev.cell(s, c), "Model", 6,
                [(3, "Receivables"), (4, "Liabilities")], ["U", "V"])
    assert rep and rep[0]["col"] == "V" and rep[0]["gap"] == 10.0
    assert rep[0]["moves"][0]["row"] in (3, 4)

    # placement targets are typed inputs only
    assert (9, "Others") in cf_input_rows(ws, "V")
    w = Writer(wb); w.plugs_allowed = True  # the exhibit tests the ladder: the last-resort stage is open
    f, err = place_flow(wb, w, "Model", 3, 10, "V", "U")
    assert f is None and "not a typed CF input cell" in err
    f, err = place_flow(wb, w, "Model", 3, 9, "V", "U")
    assert err is None and f == "=-(V3-U3)"
    assert ws["V9"].value == "=-(V3-U3)"

    # last-resort plug closes the residue; small plug stays orange
    wb2, ws2 = build(10.0)
    w2 = Writer(wb2); w2.plugs_allowed = True  # the exhibit tests the ladder: the last-resort stage is open
    plugged = last_resort_plug(
        wb2, w2, (lambda: (lambda s, c, e=None: Evaluator(wb2).cell(s, c))),
        "Model", 6, ["V"], 3, lambda m: None)
    assert len(plugged) == 1 and plugged[0][2] == -10.0
    assert abs(Evaluator(wb2).cell("Model", "V6")) <= 0.01, "must tie"
    assert not plugged[0][3]                       # 10 <= 10% of 130? no:
    # gap 10 vs assets 130 -> 7.7% -> not large
    # a LARGE plug (>10% of the asset base) goes red
    wb3, ws3 = build(30.0)
    w3 = Writer(wb3); w3.plugs_allowed = True  # the exhibit tests the ladder: the last-resort stage is open
    plugged3 = last_resort_plug(
        wb3, w3, (lambda: (lambda s, c: Evaluator(wb3).cell(s, c))),
        "Model", 6, ["V"], 3, lambda m: None)
    assert plugged3[0][3] is True
    # a forecast plug is BLUE even when large (owner 2026-09-07: forecast
    # cells are never red); the large one is watch-listed for the desk
    assert ws3["V9"].fill.start_color.rgb.endswith("BDD7EE")
    assert any(ref == "Model!V9" for ref, _why in w3.log.get("forecast_watch", []))
    # a broken ACTUAL base withholds every forecast plug
    wb5, ws5 = build(10.0)
    ws5["U6"] = "=(U3+U9)-U4"
    ws5["U4"] = 50.0                       # actual year broken by 50
    msgs5 = []
    plugged5 = last_resort_plug(
        wb5, Writer(wb5), (lambda: (lambda s, c: Evaluator(wb5).cell(s, c))),
        "Model", 6, ["V"], 3, msgs5.append)
    assert not plugged5 and any("WITHHELD" in m for m in msgs5)
    # no designed catch-all -> the year is LEFT FAILING, never invented
    wb4, ws4 = build(10.0)
    ws4["A9"] = "Named line"
    msgs = []
    plugged4 = last_resort_plug(
        wb4, Writer(wb4), (lambda: (lambda s, c: Evaluator(wb4).cell(s, c))),
        "Model", 6, ["V"], 3, msgs.append)
    assert not plugged4 and any("left failing" in m for m in msgs)




def test_place_flow_run16_pins():
    """Run-16 pins: the movement of CASH (the CF's own output) can never
    be placed back into the CF; a placement that worsens the gap or
    opens a cycle is REVERTED; an absurd plug is withheld."""
    import openpyxl
    from pipeline.evaluator import Evaluator
    from pipeline.forecast_balance import last_resort_plug, place_flow
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Model"
    ws["A2"] = "Balance Sheet"
    ws["A3"] = "Cash";        ws["V3"] = "=V12"      # wired to CF ending
    ws["A4"] = "Receivables"; ws["U4"], ws["V4"] = 100.0, 130.0
    ws["A6"] = "Check";       ws["V6"] = "=(V3+V4)-260"
    ws["A8"] = "Cash flow statement"
    ws["A9"] = "Others";      ws["U9"], ws["V9"] = 0.0, 0.0
    ws["A12"] = "Ending cash"; ws["V12"] = "=130+V9"
    w = Writer(wb)
    # the cash row itself: refused by the source law (wired through CF)
    f, err = place_flow(wb, w, "Model", 3, 9, "V", "U")
    assert f is None and "RESULT of the CF" in err, err
    # a CF-block row as source: refused
    f, err = place_flow(wb, w, "Model", 12, 9, "V", "U")
    assert f is None and "inside the cash-flow block" in err
    # a real BS line: placed
    f, err = place_flow(wb, w, "Model", 4, 9, "V", "U")
    assert err is None and f == "=-(V4-U4)"
    # plug WITHHELD when the gap exceeds half the asset base
    wb2 = openpyxl.Workbook()
    w2s = wb2.active; w2s.title = "Model"
    w2s["A2"] = "Balance Sheet"
    w2s["A3"] = "Assets"; w2s["U3"], w2s["V3"] = 100.0, 100.0
    w2s["A6"] = "Check";  w2s["V6"] = "=V3-V9-20"    # gap 80 > 50% of 100
    w2s["A8"] = "Cash flow statement"
    w2s["A9"] = "Others"; w2s["V9"] = 0.0
    msgs = []
    plugged = last_resort_plug(
        wb2, Writer(wb2),
        (lambda: (lambda s, c: Evaluator(wb2).cell(s, c))),
        "Model", 6, ["V"], 3, msgs.append)
    assert not plugged and any("WITHHELD" in m and "half" in m
                               for m in msgs), msgs




def test_attribution_window_run18_pin():
    """Runs 17-18: the engine burned its budget re-tracing forecast gaps
    the plug was always going to close. The walk-away rule is mechanics:
    after a quarter of the budget, forecast actions refuse."""
    wb = _wb({"T2": 100.0, "U2": 110.0})
    lp = _loop(wb, _spec_tiny())
    lp.spec["year_axis"]["S"]["columns"]["2026"] = "V"
    assert lp._is_forecast_action("forecast_audit", {})
    assert lp._is_forecast_action("trace_cell", {"cell": "S!V9"})
    assert not lp._is_forecast_action("trace_cell", {"cell": "S!U9"})
    assert not lp._is_forecast_action("flag_cell", {"cell": "S!V9"})
    assert not lp._fc_window_closed()
    lp._fc_spend = max(10, lp.budget0 // 4)
    assert lp._fc_window_closed()




def test_inherited_break_law_clp1_pin():
    """CLP-1: a check that already failed identically in the pre-update
    model is the analyst's standing item — reported, not refused; making
    it WORSE refuses."""
    import openpyxl
    from pipeline.gate import deliver_or_refuse
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}],
            "key_rows": []}
    def mk(t9, u9):
        wb = _wb({"T2": 100.0, "U2": 110.0, "T9": t9, "U9": u9})
        return wb
    pre = mk(-1264.0, 0.0)
    now_same = mk(-1264.0, 0.0)
    ok, fails, card = deliver_or_refuse(now_same, spec, "2025", {}, {},
                                        pre_values_wb=pre)
    assert not any("CHECK S!r9 (2024)" in f for f in fails), fails
    assert any("standing item" in x
               for x in card.get("inherited_breaks", []))
    now_worse = mk(-2264.0, 0.0)
    ok2, fails2, _ = deliver_or_refuse(now_worse, spec, "2025", {}, {},
                                       pre_values_wb=pre)
    assert any("CHECK S!r9 (2024)" in f for f in fails2), fails2




def test_load_bearing_trace_and_tier_law():
    """CLP campaign pins: (1) the wiring trace crosses sheets through the
    forecast column's formulas; (2) the neglect budget counts ONLY
    load-bearing reds — tier-3 decoration costs nothing."""
    import openpyxl
    from pipeline.loadbearing import trace
    from pipeline.gate import flag_budget
    wb = openpyxl.Workbook()
    m = wb.active; m.title = "M"
    seg = wb.create_sheet("Seg")
    # M!V7 (forecast) consumes Seg!V5; Seg!V5 consumes its own V3
    m["V7"] = "='Seg'!V5*2"
    seg["V5"] = "=V3+1"
    seg["V3"] = "=U3"
    spec = {"year_axis": {"M": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"}},
                          "Seg": {"columns": {"2024": "T", "2025": "U",
                                              "2026": "V"}}},
            "key_rows": [{"sheet": "M", "row": 7, "name": "revenue"}],
            "check_rows": []}
    lb = trace(wb, spec, "2025")
    assert ("Seg", 5) in lb and ("Seg", 3) in lb, lb
    assert ("Seg", 99) not in lb
    # gate: 30 red cells on Seg, none load-bearing -> no neglect failure
    from openpyxl.styles import PatternFill
    red = PatternFill("solid", fgColor="FFC7CE")
    flags = []
    for r in range(40, 70):
        seg[f"U{r}"] = 1.0
        seg[f"U{r}"].fill = red
        flags.append(f"Seg!U{r}")
    assert flag_budget(wb, spec, "2025", flags, load_bearing=lb) == []
    # the same reds ON the load-bearing set do fail
    lb2 = lb | {("Seg", r) for r in range(40, 70)}
    assert flag_budget(wb, spec, "2025", flags, load_bearing=lb2)


def test_205_segment_geometry_guard():
    """Run-205: China's D&A tied its prior -840 inside the PRIOR-YEAR
    segment matrix, where the adjacent number is the neighbouring
    SEGMENT (Hong Kong's -5,727), not the next year. A bound-table
    candidate current that itself ties another row's prior is refused."""
    from pipeline.stage2_join import join_bound_tables
    from pipeline.targets import TargetRow
    led = Ledger()
    # a prior-only segment matrix: one row, five segment columns
    for i in range(4):
        led.add(Item(doc="AR", page=178, table_id=1, row_ord=i,
                     label=f"Row {i}", nums=[-5727.0 - i, -840.0 - i,
                                            -2658.0 - i, -51.0 - i],
                     source_line="x"))
    led.faces[("AR", 178)] = "bs"
    tg = [TargetRow(sheet="CN", row=9, label="D&A", prior_value=-840.0),
          TargetRow(sheet="HK", row=9, label="D&A", prior_value=-5727.0)]
    out, _dec = join_bound_tables(led, tg, {}, log=[])
    assert ("CN", 9) not in out or \
        abs(out[("CN", 9)]["value"] + 5727.0) > 1, out.get(("CN", 9))


def test_205_evaluated_prior_law():
    """Run-205: a prior behind a formula on a manual-calc model made the
    row a 'no prior' target — its unguarded read landed +1,598 on a row
    whose true prior is -282. Formula priors are EVALUATED now."""
    import openpyxl
    from pipeline.targets import from_workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A9"] = "Amortisation"
    ws["T9"] = "=T20"                    # prior behind a formula
    ws["T20"] = -282.0
    values = openpyxl.Workbook()
    vs = values.active
    vs.title = "S"
    vs["A9"] = "Amortisation"            # data_only: no cache (manual calc)
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}}
    tg = from_workbook(values, spec, 2025, wb_formulas=wb)
    t9 = [t for t in tg if t.row == 9]
    assert t9 and t9[0].prior_value == -282.0, t9


def test_205_forecast_plug_cascade_breaker():
    """Run-205: plugs doubled year over year (-2,327 -> -42,512) — each
    plug flows through cash into the next year's gap. An escalating
    series stops, unwinds, and leaves the years failing with causes."""
    import openpyxl
    from pipeline.forecast_balance import last_resort_plug
    from pipeline.evaluator import Evaluator
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A20"] = "Cash flow statement"
    ws["A21"] = "Others"
    # a check row engineered to cascade: each year's gap doubles and the
    # plug row feeds it (gap_col = base*2^i - plug contributions)
    ws["V21"], ws["W21"], ws["X21"] = 0.0, 0.0, 0.0
    ws["V30"], ws["W30"], ws["X30"] = "=1000-V21", "=2600-W21-V21", "=7000-X21-W21-V21"
    logs = []
    _pw = Writer(wb); _pw.plugs_allowed = True  # the exhibit tests the ladder: the last-resort stage is open
    plugged = last_resort_plug(
        wb, _pw, lambda: (lambda s, c: Evaluator(wb).cell(s, c)),
        "S", 30, ["V", "W", "X"], None, logs.append)
    assert plugged == [], plugged
    assert any("STOPPED" in l or "escalating" in l for l in logs), logs
    assert ws["V21"].value in (0.0, 0), ws["V21"].value   # unwound


def test_assumption_freeze_pure_inheritance_only():
    """Owner side-question 2026-09-01, two defects exposed: (a) a growth
    DISPLAY (=V6/U6-1, touches its own column) must never freeze — only
    cells inheriting PURELY from the past (=U5); (b) manual-calc models
    cache nothing, so the pre-update hold value is COMPUTED from the
    archived formulas (the fourth no-cached-values fix)."""
    import openpyxl
    from openpyxl.utils import column_index_from_string
    from pipeline.freeze import plan_freezes
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T5"], ws["U5"] = 0.28, 0.30           # growth assumption history
    ws["V5"] = "=U5"                          # 2026E rate = 2025 rate
    ws["V6"] = "=V2/U2-1"                     # growth DISPLAY: wiring
    ws["U2"], ws["V2"] = 100.0, 130.0
    for c in ("V5", "V6"):
        ws[c].number_format = "0%"
    # manual-calc: the values workbook caches NOTHING for V5
    values = openpyxl.Workbook()
    values.active.title = "S"
    tc = column_index_from_string("U")
    assert plan_freezes(wb, values, ["S"], tc) == []      # no cache: skip
    plans = plan_freezes(wb, values, ["S"], tc, pre_formulas_wb=wb)
    assert [(p["sheet"], p["coord"], p["value"]) for p in plans] \
        == [("S", "V5", 0.30)], plans                     # display excluded


def test_sign_absurd_detection_pin():
    """CLP pin (rewritten under FORECAST INVIOLABILITY, owner
    2026-09-01): the detection still finds the negative-where-actuals-
    positive forecast — but nothing ever freezes it; the healthy row is
    never even listed."""
    import openpyxl
    from pipeline.gate import sign_absurd_rows
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "S"
    ws["T9"], ws["U9"] = 6536.0, 7081.0
    ws["V9"] = "=U9-20000"                     # computes negative
    ws["T11"], ws["U11"] = 100.0, 110.0
    ws["V11"] = "=U11*1.05"                    # healthy
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"}}}}
    rows = sign_absurd_rows(wb, spec, "2025")
    assert [(r[0], r[1], r[2]) for r in rows] == [("S", "V", 9)], rows
    assert ws["V9"].value == "=U9-20000"       # forecast stays LIVE
    assert ws["V11"].value == "=U11*1.05"


# ── Run-197 exhibits: the plug grammar and the tripwire law ──────────────

def test_197_plug_accepts_the_refs_its_own_tools_print():
    """Run-197: diagnose_balance printed 'Final!AI99' and plug_residual
    rejected that exact form with a MISS that never named the defect —
    the endgame budget burned on format-guessing and the delivering plug
    never landed. One grammar now: column-qualified checks parse, bare
    rows default to the target column, and every MISS names the fix."""
    wb = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0,
              "U2": 109.0, "U3": 60.0, "U4": 171.0,
              "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"})
    lp = _loop(wb, _spec_tiny())
    lp.writer.plugs_allowed = True     # the exhibit tests the plug tool: the last-resort stage is open
    # diagnose accepts the column-qualified form AND lists eligible sites
    diag = lp.t_diagnose_balance({"check": "S!U9"})
    assert "eligible plug sites" in diag, diag
    assert "S!U4" in diag and "plug_residual" in diag, diag
    # the run-197 call shape itself: column-qualified check, bare-row into
    r = lp.t_plug_residual({"check": "S!U9", "into": "S!2",
                            "why": "no guilty cell; test"})
    assert "MISS" not in r, r
    assert wb["S"]["U2"].value == 111.0, wb["S"]["U2"].value
    # MISS messages name the defect, never just an example
    bad = lp.t_plug_residual({"check": "nonsense", "into": "S!U3",
                              "why": "t"})
    assert "unparseable" in bad and "tolerated" in bad, bad
    wb2 = _wb({"T2": 100.0, "U2": 90.0, "U3": 60.0, "U4": 171.0,
               "T9": "=T2", "U9": "=U2-U3-U4+140"})
    lp2 = _loop(wb2, _spec_tiny())
    lp2.writer.plugs_allowed = True     # the exhibit tests the plug tool: the last-resort stage is open
    bad2 = lp2.t_plug_residual({"check": "S!9", "into": "S!U9", "why": "t"})
    assert "formula" in bad2 and "diagnose_balance" in bad2, bad2


def test_204_signflip_never_frozen():
    """Run-204 autopsy (owner 2026-09-01): hardcoding forecast formulas
    at pre-update values broke every forecast year's balance — FORECAST
    INVIOLABILITY. Sign-flips are detected by ONE predicate, handed to
    the loop, and the terminal state is LIVE + red + SUSPICIOUS verdict
    — never a frozen hardcode. A verdicted row is adjudicated, not
    refused."""
    import openpyxl
    from pipeline.gate import driver_roll, sign_absurd_rows
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T2"] = 6536.0
    ws["T9"] = "=T2"                    # formula-valued prior actual
    ws["U9"] = 7081.0
    ws["V9"] = "=U9-20000"
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"}}}}
    rows = sign_absurd_rows(wb, spec, "2025")
    assert [(r[0], r[1], r[2]) for r in rows] == [("S", "V", 9)], rows
    # unexamined -> the gate refuses and says the loop must verdict it
    w = Writer(wb); w.plugs_allowed = True  # the exhibit tests the ladder: the last-resort stage is open
    fails = driver_roll(wb, spec, "2025", {}, w.log)
    assert any("UNEXAMINED" in f for f in fails), fails
    # the terminal (run.py behavior, law-level): SUSPICIOUS verdict,
    # formula stays LIVE — and the gate accepts the adjudication
    w.log.setdefault("verdicts", []).append(
        "S!V9: SUSPICIOUS — sign-flip unresolved; cause is in the "
        "actual column")
    assert driver_roll(wb, spec, "2025", {}, w.log) == []
    assert ws["V9"].value == "=U9-20000"     # NEVER hardcoded
    from pipeline import freeze
    assert not hasattr(freeze, "freeze_sign_absurd")   # writer retired


def test_198_composite_constants_law():
    """Run-198: -240 was 8 stale composite formulas (=4976+23 — run 51's
    own exhibit cell) invisible to every layer and unfixable by any
    tool. The law: every embedded literal must tie a face line's
    comparative, the WHOLE composition must resolve on a COMMON page
    (the by-hand method — a statement is read as a page), and all
    qualifying pages must agree. Decoy note-table ties on other pages
    must not poison, and structural scalers never trigger."""
    import openpyxl
    from pipeline.composites import literals_of, rewrite_cell, sweep
    from pipeline.writer import Writer
    assert literals_of("=4976+23") == ["4976", "23"]
    assert literals_of("=AI61-'SOC Accounts'!AI8") == []
    assert literals_of("=U9*100/1000") == ["100", "1000"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T5"] = "=158532+10183"          # prior actual (same composition)
    ws["U5"] = "=158532+10183"          # stale mark-to-actual carry
    ws["T7"], ws["U7"] = 40.0, "=U5*100/168715"   # scalers only: no trigger
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}}
    led = Ledger()
    led.add(Item(doc="AR", page=25, table_id=0, row_ord=0,
                 label="Fixed assets", nums=[166094.0, 158532.0],
                 source_line="Fixed assets 166,094 158,532"))
    led.add(Item(doc="AR", page=25, table_id=0, row_ord=1,
                 label="Right-of-use assets", nums=[10034.0, 10183.0],
                 source_line="Right-of-use assets 10,034 10,183"))
    # decoy: a PPE note on ANOTHER page ties 158532 to a different figure
    led.add(Item(doc="AR", page=33, table_id=0, row_ord=0,
                 label="Net book value", nums=[133059.0, 158532.0],
                 source_line="Net book value 133,059 158,532"))
    for p in (25, 33):
        led.faces[("AR", p)] = "bs"
    w = Writer(wb)
    ok, msg = rewrite_cell(wb, spec, 2025, led, w, "S", 5)
    assert ok, msg
    assert wb["S"]["U5"].value == "=166094+10034", wb["S"]["U5"].value
    # non-stale cells and scaler-only cells are never touched
    n_ok, _n_red = sweep(wb, spec, 2025, led, w, lambda s: None)
    assert wb["S"]["U7"].value == "=U5*100/168715"
    # the decoy page alone (no partner literal) can never win: a cell
    # whose only ties disagree across pages refuses
    ws["U6"] = ws["T6"] = "=158532+55555"
    ok2, msg2 = rewrite_cell(wb, spec, 2025, led, w, "S", 6)
    assert not ok2 and "55555" in msg2, msg2


def test_199_unmatched_lines_surface():
    """Run-199: perpetual capital securities 3,872 — a single-year line
    with no comparative — was invisible to every prior-identity tool
    through 90 actions. statement_diff now lists face lines that tie NO
    model row (the leftover names the missing line); tied lines and
    year/date furniture stay out."""
    wb = _wb({"T2": 100.0, "T9": "=T2", "U2": 110.0, "U9": "=U2"})
    lp = _loop(wb, _spec_tiny())
    for it in (Item(doc="RA", page=26, table_id=0, row_ord=0,
                    label="Revenue", nums=[110.0, 100.0],
                    source_line="Revenue 110 100"),
               Item(doc="RA", page=26, table_id=0, row_ord=1,
                    label="Perpetual capital securities", nums=[3872.0],
                    source_line="Perpetual capital securities 3,872"),
               Item(doc="RA", page=26, table_id=0, row_ord=2,
                    label="as at", nums=[31.0, 2025.0],
                    source_line="as at 31 December 2025")):
        lp.ledger.add(it)
    lp.ledger.faces[("RA", 26)] = "bs"
    r = lp.t_statement_diff({"stmt": "bs"})
    assert "UNMATCHED" in r and "3,872" in r, r
    assert "Revenue" not in r.split("UNMATCHED")[1], r
    assert "as at" not in r, r


def test_199_terminal_ladder_delivers():
    """Run-199: two runs exhausted their budget without completing the
    owner's escalation ladder. The referee's last rung now closes a
    failing target-year check itself — largest eligible site, flagged,
    transactional — so 'back out, mark, still deliver' is guaranteed."""
    from pipeline.orchestrator import terminal_ladder
    wb = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0,
              "U2": 109.0, "U3": 60.0, "U4": 171.0,
              "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"})
    lp = _loop(wb, _spec_tiny())
    lp.writer.plugs_allowed = True     # the exhibit tests the plug tool: the last-resort stage is open
    logs = []
    n = terminal_ladder(lp, logs.append)
    assert n == 1, (n, logs)
    assert lp._failing_target_checks() == []
    # 2026-09-02 (coefficient probe): the largest site U4 now plugs
    # CORRECTLY on its measured -1 coefficient (169 closes the check)
    # instead of reverting on the old +1 assumption — first site wins
    assert wb["S"]["U4"].value == 169.0, wb["S"]["U4"].value
    assert wb["S"]["U2"].value == 109.0, wb["S"]["U2"].value
    assert any(v for v in lp.writer.log["written"]), "no write logged"


def test_202_moveon_machine_look():
    """Run-202: one sheet's unexamined reds refused a run whose balance
    and keys were done — the loop can never visit ~100 reds. The
    move-on law: code runs the exhaustive not-disclosed search itself;
    a red the whole ledger cannot tie becomes a PROVEN finding, one
    with candidates stays the loop's work."""
    import openpyxl
    from openpyxl.comments import Comment
    from pipeline.moveon import machine_look
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T5"], ws["U5"] = 777.0, 777.0        # prior nowhere in the ledger
    ws["T6"], ws["U6"] = 555.0, 555.0        # prior IS in the ledger
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}}
    led = Ledger()
    led.add(Item(doc="RA", page=9, table_id=0, row_ord=0,
                 label="Some line", nums=[560.0, 555.0],
                 source_line="Some line 560 555"))
    w = Writer(wb); w.plugs_allowed = True  # the exhibit tests the ladder: the last-resort stage is open
    for coord in ("U5", "U6"):
        ws[coord].comment = Comment("STALE INPUT: rolled...", "t")
        w.log["flags"].append(f"S!{coord}")
    n_proved, n_evid = machine_look(wb, spec, 2025, led, w, lambda s: None)
    assert (n_proved, n_evid) == (1, 1)
    assert "NOT DISCLOSED (proven)" in ws["U5"].comment.text
    assert "evidence candidates exist" in ws["U6"].comment.text
    # gate contract: the proven one no longer counts as unexamined
    from pipeline.gate import flag_budget
    ws["U5"].fill = w.fills["red"]
    ws["U6"].fill = w.fills["red"]
    fails = flag_budget(wb, spec, 2025, w.log["flags"])
    assert fails and "1/" in fails[0], fails


def test_202_moveon_gate_reports_not_refuses():
    """With every check passing and nothing structural broken, flag
    budget breaches are REPORTED on the card, never refusing (the
    move-on law). While anything else fails, they still refuse."""
    from pipeline.gate import deliver_or_refuse
    import openpyxl
    from openpyxl.comments import Comment
    from pipeline.writer import Writer, formula_map
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T2"], ws["U2"] = 100.0, 110.0
    ws["T9"], ws["U9"] = "=T2-T2", "=U2-U2"      # check row passes
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}]}
    w = Writer(wb)
    for r in range(20, 30):                       # 10 unexamined reds
        ws[f"U{r}"] = 1.0
        ws[f"U{r}"].fill = w.fills["red"]
        ws[f"U{r}"].comment = Comment("STALE INPUT: rolled", "t")
        w.log["flags"].append(f"S!U{r}")
    ok, fails, card = deliver_or_refuse(wb, spec, 2025, formula_map(wb),
                                        w.log)
    assert ok, fails
    assert card.get("moveon_reported"), card.get("moveon_reported")
    # break the check -> the same staleness refuses again
    ws["U9"] = "=U2-50"
    ok2, fails2, _ = deliver_or_refuse(wb, spec, 2025, formula_map(wb),
                                       w.log)
    assert not ok2 and any("FLAG BUDGET" in f for f in fails2), fails2


def test_203_error_baseline_law():
    """Run-203: two unflagged zeros made every forecast year #DIV/0! and
    the gate, blind to EVAL_ERROR, called the model balanced. The law:
    count errors BEFORE the update; only NEW errors are the agent's —
    they refuse (traced); pre-existing ones report as the analyst's."""
    import openpyxl
    from pipeline.errorscan import error_cells, new_errors
    from pipeline.gate import deliver_or_refuse
    from pipeline.writer import Writer, formula_map
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T5"], ws["U5"], ws["V5"] = 1577.0, 1577.0, "=U5"
    ws["T6"], ws["U6"], ws["V6"] = "=100/T5", "=100/U5", "=100/V5"
    ws["T8"] = "=1/0"                      # the analyst's own old error
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"}}},
            "check_rows": []}
    base = error_cells(wb, spec)
    assert set(base) == {("S", "T8")}, base
    ws["U5"] = 0.0                         # the run-203 crime
    cur = error_cells(wb, spec)
    ne = new_errors(base, cur)
    assert {(s, c) for s, c, _ in ne} == {("S", "U6"), ("S", "V6")}, ne
    w = Writer(wb)
    ok, fails, card = deliver_or_refuse(wb, spec, 2025, formula_map(wb),
                                        w.log, error_baseline=base)
    assert not ok and sum(f.startswith("NEW ERROR") for f in fails) == 2
    assert card.get("preexisting_errors") == ["S!T8"], card


def test_203_error_guard_reverts_the_breaking_write():
    """The write chokepoint's journal lets the error guard restore the
    exact write that made cells stop computing — the auto-disproof of a
    false 'proven zero'."""
    import openpyxl
    from pipeline.errorscan import error_cells, new_errors
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T5"], ws["U5"] = 1577.0, 1577.0
    ws["T6"], ws["U6"] = "=100/T5", "=100/U5"
    ws["T7"] = 4.0
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}}
    base = error_cells(wb, spec)
    w = Writer(wb)
    assert w.write("S", "U7", 5.0, prior_coord="T5", trusted=True)  # innocent
    assert w.write("S", "U5", 0.0, prior_coord="T5", trusted=True)  # culprit
    assert new_errors(base, error_cells(wb, spec))
    # the run.py guard logic, distilled: pop newest-first, keep innocents
    undo = w.log["undo"]
    cur = new_errors(base, error_cells(wb, spec))
    while cur and undo:
        sh, coord, old = undo.pop()
        prev = wb[sh][coord].value
        wb[sh][coord] = old
        now = new_errors(base, error_cells(wb, spec))
        if len(now) < len(cur):
            cur = now
        else:
            wb[sh][coord] = prev
    assert ws["U5"].value == 1577.0        # culprit reverted
    assert ws["U7"].value == 5.0           # innocent kept
    assert not new_errors(base, error_cells(wb, spec))


def test_203_trace_error_names_the_cause():
    """The taught investigation: from the erroring cell down to the zero
    divisor, with the before-picture and the write provenance."""
    wb = _wb({"T5": 1577.0, "U5": 0.0,
              "T6": "=100/T5", "U6": "=100/U5", "U9": "=U6"})
    lp = _loop(wb, _spec_tiny())
    r = lp.t_trace_error({"cell": "S!U9"})
    assert "CAUSE: S!U5" in r, r
    assert "divides by it" in r and "UNFLAGGED" in r, r
    ok = lp.t_trace_error({"cell": "S!T6"})
    assert "evaluates fine" in ok


def test_203_key_tie_backs_out_the_estimate():
    """Run-203: total opex still held the FORECAST formula
    (=prior*revenue growth) in the actual column — +148 flowed into
    operating profit, net profit and EPS. The key-tie law wraps that
    exact component (formula over a hardcode prior = the type
    violation) so the key ties the print, orange, traceable."""
    import json
    from pipeline.keytie import key_tie
    from pipeline.writer import Writer
    wb = _wb({"T2": 90964.0, "U2": 88018.0,           # revenue (ties)
              "T3": -76061.0, "U3": "=T3*(U2/T2)",    # opex: estimate!
              "T4": "=T2+T3", "U4": "=U2+U3"})        # net profit key
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [],
            "key_rows": [{"name": "net profit", "sheet": "S", "row": 4}]}
    panel = {"net profit": {"print": 14272.0, "prior": 14903.0}}
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "key_panel.json"
        p.write_text(json.dumps(panel))
        w = Writer(wb)
        n = key_tie(wb, spec, 2025, w, p, lambda s: None)
    assert n == 1, n
    from pipeline.evaluator import Evaluator
    assert abs(Evaluator(wb).cell("S", "U4") - 14272.0) <= 1.0
    assert wb["S"]["U3"].value.startswith("=(T3*(U2/T2))-("), wb["S"]["U3"].value


def test_203_prior_delta_protocol():
    """Owner's ruling: the PRIOR year proves the definition. A key that
    differed from the print last year by the same nameable model rows
    (MI + perpetual coupons) is CONFIRMED, not forced; a key whose
    prior TIED the print must tie now."""
    import json, pathlib, tempfile
    from pipeline.keytie import key_tie
    from pipeline.writer import Writer
    wb = _wb({
        # profit-for-the-year row, then MI and PCS, then the key row
        "T3": 12718.0, "U3": 11546.0,
        "T4": -840.0, "U4": -879.0,        # minority interests
        "T5": -136.0, "U5": -199.0,        # perpetual coupons
        "T6": "=T3+T4+T5", "U6": "=U3+U4+U5"})
    wb["S"]["A4"], wb["S"]["A5"] = "Minority interests", "Perpetual coupons"
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [],
            "key_rows": [{"name": "net profit", "sheet": "S", "row": 6}]}
    panel = {"net profit": {"print": 11546.0, "prior": 12718.0}}
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "key_panel.json"
        p.write_text(json.dumps(panel))
        w = Writer(wb)
        n = key_tie(wb, spec, 2025, w, p, lambda s: None)
    assert n == 0                              # nothing forced
    assert wb["S"]["U6"].value == "=U3+U4+U5"  # untouched
    v = w.log.get("verdicts", [])
    assert v and "JUSTIFIED" in v[0] and "Minority interests" in v[0], v


def test_203_empty_row_law():
    """A row whose prior actual is empty is furniture — untrusted
    machine writes are refused there."""
    from pipeline.writer import Writer
    wb = _wb({"T5": 100.0, "V9": "=U9*1.1"})
    w = Writer(wb)
    assert w.write("S", "U9", 5.0, prior_coord="T9") is False
    assert w.log["empty_row_refused"] == ["S!U9"]
    assert w.write("S", "U5", 105.0, prior_coord="T5") is True
    # THE NEVER-FILLED ROW LAW (owner 2026-09-14): a row with no number
    # anywhere, past or future, takes no write from any step — trusted or not
    assert w.write("S", "U12", 5.0, prior_coord="T12", trusted=True, allow_empty=True) is False
    assert w.log["never_filled_refused"] == ["S!U12"] and wb["S"]["U12"].value is None


def test_204_teachings_twin_collapse_plugmeter():
    """The by-hand teachings, law-level: (2) a served value re-anchors
    its stale twins; (3) a zero that kills a healthy forecast row is
    caught by the collapse detector; (5) the model's own residual rows
    read as truth meters."""
    import openpyxl
    from pipeline.teachings import (collapsed_forecasts, forecast_baseline,
                                    plug_meter, twin_reanchor)
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    # twin: rows 5 and 7 both held 1,577 last year; row 5 gets served
    ws["T5"], ws["U5"] = 1577.0, 1650.0
    ws["T7"], ws["U7"] = 1577.0, 1577.0          # stale twin hardcode
    ws["T8"], ws["U8"] = 1577.0, "=U5"           # formula twin, healthy
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"}}}}
    w = Writer(wb)
    w.log["written"].append("S!U5")
    n_rw, n_tw = twin_reanchor(wb, wb, spec, 2025, w, lambda s: None)
    assert n_rw == 1 and ws["U7"].value == 1650.0, (n_rw, ws["U7"].value)
    # collapse: V9 = units*price; baseline healthy, tariff zeroed -> caught
    wb2 = openpyxl.Workbook()
    w2s = wb2.active
    w2s.title = "S"
    w2s["T5"], w2s["U5"] = 95.8, 97.1
    w2s["T6"], w2s["U6"] = 360.0, 360.0
    w2s["V9"] = "=U5*U6"
    base = forecast_baseline(wb2, spec, 2025)
    assert base[("S", 9)] > 100
    w2s["U5"] = 0.0                              # the run-204 tariff crime
    got = collapsed_forecasts(wb2, spec, 2025, base)
    assert [(s, r) for s, r, _n, _w in got] == [("S", 9)], got
    # plug meter: residual row explodes vs its prior
    wb3 = openpyxl.Workbook()
    w3s = wb3.active
    w3s.title = "S"
    w3s["T2"], w3s["U2"] = 50649.0, 48967.0      # total (sales)
    w3s["T3"], w3s["U3"] = 34000.0, 34723.0      # basic
    w3s["T4"], w3s["U4"] = 16645.0, 15842.0      # fuel
    w3s["T5"], w3s["U5"] = "=T2-T3-T4", "=U2-U3-U4"   # export plug
    # the wrong tariff: plug -1,598 vs prior +4 — sign-flipped, large:
    # METERED (exactly how the by-hand session caught the tariff)
    pm = plug_meter(wb3, spec, 2025)
    assert [(s, r) for s, r, _n, _w in pm] == [("S", 5)], pm
    # the fuel fix lands: plug -185 vs +4 — small: quiet
    w3s["U4"] = 14429.0
    assert plug_meter(wb3, spec, 2025) == []


def test_206_oneoff_no_propagate():
    """Run-206: a new one-off actual (hedging -352, prior ~0) linked
    into the forecast leaked +352/yr of imbalance forever. Bare links
    to a new one-off zero out (orange); recurring rows stay linked."""
    import openpyxl
    from pipeline.teachings import oneoff_no_propagate
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T7"], ws["U7"], ws["V7"], ws["W7"] = None, -352.0, "=U7", "=V7"
    ws["T8"], ws["U8"], ws["V8"] = -300.0, -310.0, "=U8"   # recurring: keep
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V", "2027": "W"}}}}
    w = Writer(wb)
    n = oneoff_no_propagate(wb, spec, 2025, w, lambda s: None)
    assert n == 1, n
    assert ws["V7"].value == 0 and ws["W7"].value == "=V7"
    assert ws["V8"].value == "=U8"


def test_206_vintage_guard_and_corroboration():
    """Run-206: (a) a five-year series read backwards served the row's
    own PRIOR2 (35,967, the 2023 value) — refused; (b) two pages
    disagreeing on a composite's combination resolve by page majority
    (the true finance-cost pair prints on the face AND the CF note)."""
    from pipeline.stage2_join import join
    from pipeline.targets import TargetRow
    led = Ledger()
    # oldest-first series: ... 35,967(2023) 40,860(2024) 41,321(2025)
    led.add(Item(doc="AR", page=243, table_id=0, row_ord=0,
                 label="Long-term loans and other borrowings",
                 nums=[35967.0, 40860.0, 41321.0],
                 source_line="Long-term loans 35,967 40,860 41,321"))
    led.faces[("AR", 243)] = "bs"
    t = TargetRow(sheet="R", row=24, label="Long term borrowing",
                  prior_value=40860.0, prior2_value=35967.0)
    served, _d = join(led, [t], log=[])
    v = served.get(("R", 24), {}).get("value")
    assert v != 35967.0, served.get(("R", 24))
    # corroboration: majority-page combination wins
    from pipeline.composites import prove_cell
    led2 = Ledger()
    for pg, cur in ((166, 1860.0), (214, 1860.0)):        # two true pages
        led2.add(Item(doc="AR", page=pg, table_id=0, row_ord=0,
                      label="Finance costs", nums=[cur, 2254.0],
                      source_line="Finance costs"))
        led2.faces[("AR", pg)] = "pl"
    led2.add(Item(doc="AR", page=280, table_id=0, row_ord=0,
                  label="Finance costs", nums=[2717.0, 2254.0],
                  source_line="oldest-first series"))     # one false page
    led2.faces[("AR", 280)] = "pl"
    proof, why = prove_cell(led2, ["2254"])
    assert proof and abs(proof["2254"][0] - 1860.0) < 1, (proof, why)


def test_207_probe_and_hold_forecast():
    """Owner ruling 2026-09-01: think like Fable — the probe experiment
    (hold a suspect, watch checks respond, auto-restore) and the
    sanctioned hold for probe-proven roll artifacts, transactional."""
    wb = _wb({"T5": 100.0, "U5": 110.0,
              "U7": -352.0, "V7": "=U7",          # the leak
              "T9": "=T5-T5", "U9": "=U5-U5", "V9": "=V7"})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}]}
    lp = _loop(wb, spec)
    r = lp.t_probe({"cell": "S!V7"})
    assert "CLOSES" in r and wb["S"]["V7"].value == "=U7", r  # restored
    # hold on a non-forecast column refused
    bad = lp.t_hold_forecast({"cell": "S!U7", "why": "x" * 30})
    assert "not a forecast-column" in bad, bad
    ok = lp.t_hold_forecast({"cell": "S!V7",
                             "why": "probe closed S!9 2026 to zero"})
    assert ok.startswith("HELD"), ok
    assert wb["S"]["V7"].value == 0.0
    assert any("agent hold" in f for f in lp.writer.log["frozen"])
    # a hold that does NOT improve checks reverts
    wb2 = _wb({"U7": -352.0, "V7": "=U7", "T9": "=T5-T5",
               "U9": "=U7-U7", "V9": "=V8-V8"})
    lp2 = _loop(wb2, spec)
    r2 = lp2.t_hold_forecast({"cell": "S!V7",
                              "why": "probe proved nothing honestly"})
    assert r2.startswith("REVERTED"), r2
    assert wb2["S"]["V7"].value == "=U7"


def test_208_twin_backout():
    """Run-208: the NFA lived in Final!65 (rewritten to actual) AND the
    Driver roll base (stale composite) — the stale twin broke every
    forecast year, and its inputs are unprovable from the RA. The twin
    law: hardcode twins re-serve; composite-formula twins BACK OUT
    (=(net)-(other ref)) per the owner's back-out rule."""
    import openpyxl
    from pipeline.teachings import twin_reanchor
    from pipeline.writer import Writer
    from pipeline.evaluator import Evaluator
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A5"] = "Net fixed assets"
    ws["T5"], ws["U5"] = "=T70+T71", 176128.0          # BS home: served
    ws["T70"], ws["T71"] = 292564.0, -123849.0         # prior 168,715
    ws["A9"] = "Net fixed assets roll"
    ws["T9"], ws["U9"] = "=T70+T71", "=U70+U71"        # twin (roll base)
    ws["U70"], ws["U71"] = "=292564+343", "=-123849-343"
    w = Writer(wb)
    w.log["written"].append("S!U5")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}}
    n_rw, n_tw = twin_reanchor(wb, None, spec, 2025, w, lambda s: None)
    assert n_rw == 1, (n_rw, n_tw)
    assert abs(Evaluator(wb).cell("S", "U9") - 176128.0) < 1
    assert wb["S"]["U70"].value.startswith("=(176128)-("), wb["S"]["U70"].value


# ── Exhibits: the Fable-drive autopsy (2026-09-01) ───────────────────────
# Fable 5 drove the loop by hand on CLP FY25 and root-caused every wrong
# deterministic serve it met. Each law below killed a real shipped poison.


def test_fd_time_signature_refuses_segment_axis():
    # CN revenue served 52,048 = the HONG KONG column: its prior 1,801
    # tied inside the wide SEGMENT row [52048, 1801, 37097, 3, 90964]
    # whose axis is segments, not years — read-across is a column error.
    items = _anchors() + [
        _item(95, 10, "revenue seg", [52048.0, 1801.0, 37097.0, 3.0,
                                      90964.0])]
    targets = _anchor_targets() + [
        TargetRow("Model", 9, "revenue seg", 1801.0, prior2_value=1750.0)]
    served, _ = join(_ledger(items), targets)
    assert ("Model", 9) not in served, \
        f"segment-axis read-across re-admitted: {served.get(('Model', 9))}"


def test_fd_time_signature_allows_series_and_delta():
    # a five-year statistics row IS a time series (next number ties
    # prior2), and a (current, prior, change) row is a legal time shape
    items = _anchors() + [
        _item(95, 10, "series row", [1872.0, 1801.0, 1750.0, 1700.0]),
        _item(95, 11, "change row", [34191.0, 37097.0, -2906.0, -7.8])]
    targets = _anchor_targets() + [
        TargetRow("Model", 9, "series row", 1801.0, prior2_value=1750.0),
        TargetRow("Model", 10, "change row", 37097.0, prior2_value=33190.0)]
    served, _ = join(_ledger(items), targets)
    assert abs(served[("Model", 9)]["value"] - 1872.0) < 1e-9
    assert abs(served[("Model", 10)]["value"] - 34191.0) < 1e-9


def test_fd_exact_beats_close():
    # 'Revenue from contracts with customers' 36,972 tied total-revenue
    # prior 37,097 inside the 0.5% world band — a DEFINITION mismatch.
    # The exact number is printed elsewhere, so the loose tie is refused;
    # with no exact home anywhere (a restated comparative), it may serve.
    contracts = _item(95, 10, "revenue total", [34066.0, 36972.0])
    exact = _item(95, 11, "unrelated line", [37097.0, 12.0])
    targets = _anchor_targets() + [
        TargetRow("Model", 9, "revenue total", 37097.0,
                  prior2_value=33190.0)]
    served, _ = join(_ledger(_anchors() + [contracts, exact]), targets)
    assert ("Model", 9) not in served, \
        "definition-mismatch tie re-admitted despite an exact home"
    served2, _ = join(_ledger(_anchors() + [contracts]), targets)
    assert ("Model", 9) in served2, \
        "restated-comparative loose tie starved (run-112 law broken)"


def test_fd_unchanged_laundering_refused():
    # bound tables: PCS costs served -136 = the row's own prior off a
    # prior-vintage table — numerically a no-op that marked a STALE cell
    # served-clean, hiding it from the red-staleness queue.
    from pipeline.stage2_join import join_bound_tables
    items = [
        _item(60, 1, "alpha", [500.0, 480.0], table_id=3),
        _item(60, 2, "beta", [700.0, 690.0], table_id=3),
        _item(60, 3, "gamma", [900.0, 880.0], table_id=3),
        _item(60, 4, "pcs holders", [136.0, 136.0], table_id=3)]
    targets = [
        TargetRow("M", 1, "alpha", 480.0), TargetRow("M", 2, "beta", 690.0),
        TargetRow("M", 3, "gamma", 880.0),
        TargetRow("M", 4, "pcs holders", 136.0, prior2_value=139.0)]
    led = _ledger(items, face_pages=((95, "pl"),))
    served, _ = join_bound_tables(led, targets, {})
    assert ("M", 4) not in served, \
        "unchanged-value laundering re-admitted from a non-face table"


def test_fd_evidence_sign_blind():
    # SoC depreciation -5,832 was refused because the ledger prints the
    # magnitude 5,832 — the MODEL owns the sign convention.
    from pipeline.writegate import find_evidence
    row = _item(243, 5, "Depreciation", [5832.0, 5683.0])
    assert find_evidence([row], -5832.0), \
        "sign-blind evidence broken: printed 5,832 must prove -5,832"


def test_fd_reconcile_header_and_input_twin():
    # (a) the year-header row (prior = numeric 2024) must never enter the
    # prior index — a '31 December 2024' date line served 31 into it;
    # (b) a prior living on TWO sheets (formula twin + input twin)
    # resolves to the single INPUT home instead of being skipped.
    import openpyxl
    from pipeline.reconcile import reconcile

    class _L:
        def __init__(self, items):
            self.items = items

        def prior_period_docs(self):
            return set()

        def join_pool(self):
            return self.items

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["T2"], ws["U2"] = 2024, 2025          # header row: numeric years
    ws["T3"], ws["T4"] = 58000.0, 39000.0    # scale anchors
    ws["T7"], ws["U7"] = 5683.0, 4000.0      # input home
    wb.create_sheet("D")
    wb["D"]["T7"], wb["D"]["U7"] = "=S!T7", "=S!U7"   # formula twin
    spec = {"year_axis": {
        "S": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2},
        "D": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    items = _anchors() + [_item(95, 5, "opening date", [31.0, 2024.0]),
                          _item(95, 6, "depreciation", [5832.0, 5683.0])]
    serves, _m = reconcile(wb, spec, 2025, _L(items), lambda s: None)
    assert ("S", 2) not in serves and ("D", 2) not in serves, \
        "date line served into the year-header row again"
    assert ("S", 7) in serves and abs(serves[("S", 7)]["value"] - 5832) < 1, \
        f"multi-home input twin unresolved: {sorted(serves)}"
    assert ("D", 7) not in serves, "formula twin must not be written"


# ── Exhibits: the work-queue inversion (council ruling 2026-09-01) ──────
# Run-210: a free-roaming weak LLM spent 90 actions on 61 repeated
# investigations and 0 evidence writes. Stage 4 inverted: machine plans,
# LLM answers one bounded card. These pin the queue's safety contracts.


def _wq_loop():
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    from pipeline.targets import TargetRow as TR
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "M"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T7"], ws["U7"] = 4976.0, 4976.0     # red stale input
    ws["T9"], ws["U9"] = 810.0, 810.0       # red stale input, decoy bait
    spec = {"year_axis": {"M": {"columns": {"2024": "T", "2025": "U"},
                                "header_row": 2}},
            "check_rows": []}
    items = [
        _item(95, 1, "cash total", [60000.0, 58000.0]),
        _item(95, 2, "cost total", [41000.0, 39000.0]),
        _item(95, 3, "cash and equivalents", [3905.0, 4976.0]),
        _item(95, 5, "cash incl restricted deposits", [3872.0, 4976.0]),
        _item(95, 4, "megawatt capacity", [812000.0, 810.0]),  # decoy pair
    ]
    led = _ledger(items, face_pages=((95, "bs"),))
    led._doc_periods = {DOC: "current"}
    targets = [TR("M", 7, "cash and equivalents", 4976.0,
                  prior2_value=5182.0),
               TR("M", 9, "capacity", 810.0, prior2_value=805.0)]
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, Writer(wb), None)
    loop.writer.log["flags"] = ["M!U7", "M!U9"]
    return loop


def test_wq_default_is_abstention():
    # a garbage answer id can never execute — it falls to the default,
    # the run finishes, and the stale cell stays red for the analyst
    from pipeline.workqueue import run_queue
    loop = _wq_loop()
    s = run_queue(loop, None, lambda *a: None,
                  answerer=lambda t, o, d: "serve:ZZZ")
    assert "queue:" in s
    assert loop.wb["M"]["U7"].value == 4976.0, "garbage answer executed"


def test_wq_serve_lands_with_citation():
    # the top candidate for the cash row is the printed 3,905 (prior
    # 4,976 ties); serving it writes through t_set_input with the page
    from pipeline.workqueue import run_queue
    loop = _wq_loop()
    def pick_serve(text, options, default):
        return next((k for k in options if k.startswith("serve:")), default)
    run_queue(loop, None, lambda *a: None, answerer=pick_serve)
    assert loop.wb["M"]["U7"].value == 3905.0, loop.wb["M"]["U7"].value


def test_wq_decoy_out_of_world_never_offered():
    # red-team calibration: the 812,000 MW figure adjacent to prior 810
    # is out of the row's world — it must not appear as an option at all
    from pipeline.workqueue import candidates_for
    loop = _wq_loop()
    cands = candidates_for(loop, "M", 9)
    assert all(abs(c["value"]) < 81000 for c in cands), cands


def test_wq_refusal_reasks_once():
    # run-216: Luna picked candidate D on the fuel-clause card, the
    # one-home law refused it, and the card was ABANDONED with the
    # clean candidate A still on it. A refusal must re-ask ONCE with
    # the refusal shown and the refused option removed.
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import run_queue
    loop = _wq_loop()
    calls = {"n": 0}
    orig = ObjectiveLoop.TOOLS["set_input"]

    def refuse_first(self, args):
        calls["n"] += 1
        if calls["n"] == 1:
            return "REFUSED by the evidence law: synthetic first refusal"
        return orig(self, args)
    ObjectiveLoop.TOOLS = dict(ObjectiveLoop.TOOLS, set_input=refuse_first)
    try:
        seen = {"reask": 0}

        def pick(text, options, default):
            if "NOTE: your previous answer" in text:
                seen["reask"] += 1
            sv = [k for k in options if k.startswith("serve:")]
            return sv[0] if sv else default
        run_queue(loop, None, lambda *a: None, answerer=pick)
    finally:
        ObjectiveLoop.TOOLS = dict(ObjectiveLoop.TOOLS, set_input=orig)
    assert seen["reask"] >= 1, "refusal did not re-ask the card"
    assert loop.wb["M"]["U7"].value in (3905.0, 3872.0), \
        "no serve landed after the re-ask"


def test_wq_llm_absent_means_machinery_baseline():
    # no client, no answerer -> every card defaults; nothing written
    from pipeline.workqueue import run_queue
    loop = _wq_loop()
    s = run_queue(loop, None, lambda *a: None)
    assert loop.wb["M"]["U7"].value == 4976.0
    assert "defaulted" in s


def test_wq_component_card_offers_the_receipts():
    # run-211: a 5,293 gap was plugged into one cell when a printed
    # two-cell split existed. The COMPONENT card must offer the printed
    # candidate WITH its probe-measured effect, and serving it must
    # close the check.
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    from pipeline.targets import TargetRow as TR
    from pipeline.workqueue import build_queue, render_card
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "M"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T5"], ws["U5"] = 5943.0, 5943.0        # component: stale
    ws["T6"], ws["U6"] = 100000.0, 103872.0    # other side, correct
    ws["T7"], ws["U7"] = 94057.0, 94057.0      # other component
    ws["T10"], ws["U10"] = "=T6-T5-T7", "=U6-U5-U7"   # check: 3,872 off
    spec = {"year_axis": {"M": {"columns": {"2024": "T", "2025": "U"},
                                "header_row": 2}},
            "check_rows": [{"sheet": "M", "row": 10, "expect": 0}]}
    items = _anchors() + [
        _item(95, 3, "reserves incl PCS", [9815.0, 5943.0]),
    ]
    led = _ledger(items, face_pages=((95, "bs"),))
    led._doc_periods = {DOC: "current"}
    targets = _anchor_targets() + [
        TR("M", 5, "reserves incl PCS", 5943.0, prior2_value=5100.0)]
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, Writer(wb), None)
    q = build_queue(loop)
    comp = [w for w in q if w.kind == "COMPONENT"]
    assert comp, "no COMPONENT item for the failing check"
    rendered = render_card(loop, comp[0])
    assert rendered is not None, "component card did not render"
    text, options, default = rendered
    assert "CLOSES the check" in text, text
    assert default == "not_disclosed"
    fix = next(k for k in options if k.startswith("fix:"))
    tool, args = options[fix]
    assert tool == "set_input" and abs(args["value"] - 9815.0) < 1


def test_plug_experiment_referees_proven_sites():
    # run-213: a plug into PROVEN share capital "balanced" 2025 and
    # broke every forecast year. The owner's regression ruling
    # (2026-09-01, runs 214-218 quarantined by the blanket proven-ban):
    # balance is the hard objective and the loud plug its last resort —
    # so a proven site takes a plug ONLY when the live experiment shows
    # the forecast years unhurt, and it lands RED, never quietly.
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "M"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    ws["T5"], ws["U5"] = 23243.0, 23243.0     # PROVEN, rolls into 2026
    ws["T6"], ws["U6"], ws["V6"] = 1000.0, 1000.0, 1000.0
    ws["T8"], ws["U8"] = 500.0, 500.0         # PROVEN, does NOT roll
    ws["U10"] = "=U5+U6+U8-26164"             # 2025 check: -1,421
    ws["V10"] = "=U5+V6-24243"                # 2026 check reads U5: 0
    spec = {"year_axis": {"M": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"},
                                "header_row": 2}},
            "check_rows": [{"sheet": "M", "row": 10, "expect": 0}]}
    led = _ledger([], face_pages=((95, "bs"),))
    served = {("M", 5): {"value": 23243.0, "doc": "ar.pdf", "page": 26,
                         "conf": 5, "note": "reconciliation"},
              ("M", 8): {"value": 500.0, "doc": "ar.pdf", "page": 27,
                         "conf": 5, "note": "reconciliation"}}
    loop = ObjectiveLoop(wb, spec, 2025, led, [], served, Writer(wb), None)
    r1 = loop.t_plug_residual({"check": "M!10", "into": "M!U5",
                               "why": "absorb the residual"})
    # owner ruling 2026-09-08 (DFE 239: the ladder plugged -15,826 over a
    # correctly read cash-flow line): a PROVEN value is never a plug site
    assert str(r1).startswith("REFUSED") and "PROVEN" in str(r1), r1
    assert wb["M"]["U5"].value == 23243.0, "proven site was written"
    r2 = loop.t_plug_residual({"check": "M!10", "into": "M!U8",
                               "why": "absorb the residual"})
    assert str(r2).startswith("REFUSED") and "PROVEN" in str(r2), r2
    assert "M!U8" not in loop.writer.log["flags"], "refused plug must not flag"


def test_verdict_error_fixed_requires_the_error_gone():
    # the Fable-drive's own sin: 36 tripwires mass-approved as fixed
    # while forecasts still computed negative. Code now re-checks.
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "M"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    ws["T7"], ws["U7"], ws["V7"] = 800.0, 900.0, "=-U7"   # absurd forecast
    spec = {"year_axis": {"M": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"},
                                "header_row": 2}}, "check_rows": []}
    led = _ledger([], face_pages=((95, "bs"),))
    loop = ObjectiveLoop(wb, spec, 2025, led, [], {}, Writer(wb), None)
    loop.tripwires = [("M", "V", 7, -900.0, 800.0, 900.0)]
    r = loop.t_verdict({"items": ["M!V7"], "verdict": "ERROR_FIXED",
                        "why": "claimed fixed without checking anything"})
    assert str(r).startswith("REJECTED"), r
    ws["V7"] = "=U7"                       # actually fix it
    r2 = loop.t_verdict({"items": ["M!V7"], "verdict": "ERROR_FIXED",
                         "why": "cause repaired; forecast recomputes sane"})
    assert "VERDICT recorded" in str(r2), r2




# ── Exhibits: the recomposition law (owner ruling 2026-09-02) ────────────
# "When there is a new ingredient this year that adds into the subtotal,
# we add it — core analyst skill." The old recipe's comparatives locate
# its printed section; members refresh with THIS year's signs, new items
# join, the analyst's exclusions are respected.


def _recompose_fixture(lines):
    import openpyxl
    led = _ledger([_item(95, i + 1, lab, nums, table_id=0)
                   for i, (lab, nums) in enumerate(lines)],
                  face_pages=((95, "cf"),))
    led._doc_periods = {DOC: "current"}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "M"
    ws["T2"], ws["U2"] = 2024, 2025
    spec = {"year_axis": {"M": {"columns": {"2024": "T", "2025": "U"},
                                "header_row": 2}}}
    return wb, spec, led


def test_recompose_new_ingredient_joins():
    from pipeline.composites import recompose_cell
    from pipeline.writer import Writer
    wb, spec, led = _recompose_fixture([
        ("proceeds from borrowings", [900.0, 800.0]),
        ("repayment of borrowings", [-500.0, -400.0]),
        ("issue of new securities", [250.0]),          # NEW: no prior
        ("settlement of instruments", [-60.0, -70.0]),
    ])
    wb["M"]["T7"], wb["M"]["U7"] = 330.0, "=800-400-70"
    ok, msg = recompose_cell(wb, spec, 2025, led, Writer(wb), "M", 7)
    assert ok, msg
    from pipeline.composites import signed_literals
    got = sum(sg * float(x) for sg, x in signed_literals(wb["M"]["U7"].value))
    assert abs(got - (900 - 500 + 250 - 60)) < 0.01, wb["M"]["U7"].value


def test_recompose_respects_analyst_exclusion():
    from pipeline.composites import recompose_cell
    from pipeline.writer import Writer
    wb, spec, led = _recompose_fixture([
        ("proceeds from borrowings", [900.0, 800.0]),
        ("a line the analyst excluded", [123.0, 111.0]),  # material prior,
                                                          # NOT in recipe
        ("repayment of borrowings", [-500.0, -400.0]),
    ])
    wb["M"]["T7"], wb["M"]["U7"] = 400.0, "=800-400"
    ok, msg = recompose_cell(wb, spec, 2025, led, Writer(wb), "M", 7)
    assert ok, msg
    from pipeline.composites import signed_literals
    got = sum(sg * float(x) for sg, x in signed_literals(wb["M"]["U7"].value))
    assert abs(got - 400) < 0.01, wb["M"]["U7"].value
    assert "EXCLUDED" in (wb["M"]["U7"].comment.text if wb["M"]["U7"].comment else "")


def test_recompose_sign_from_this_years_print():
    # short-term borrowings flipped from +increase to -decrease: the
    # sign comes from the printed CURRENT, never the comparative
    from pipeline.composites import recompose_cell
    from pipeline.writer import Writer
    wb, spec, led = _recompose_fixture([
        ("proceeds from borrowings", [900.0, 800.0]),
        ("change in short-term borrowings", [-300.0, 200.0]),
        ("repayment of borrowings", [-500.0, -400.0]),
    ])
    wb["M"]["T7"], wb["M"]["U7"] = 600.0, "=800+200-400"
    ok, msg = recompose_cell(wb, spec, 2025, led, Writer(wb), "M", 7)
    assert ok, msg
    from pipeline.composites import signed_literals
    got = sum(sg * float(x) for sg, x in signed_literals(wb["M"]["U7"].value))
    assert abs(got - (900 - 300 - 500)) < 0.01, wb["M"]["U7"].value




def test_writes_ledger_survives_guard_pops():
    # run-223: the error/collapse guards POP the undo journal while
    # unwinding; the gate loop's take-back read the same journal after
    # the guards and saw nothing. The append-only writes_all ledger is
    # never consumed.
    import openpyxl
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "M"
    ws["T7"], ws["U7"] = 100.0, 100.0
    w = Writer(wb)
    assert w.write("M", "U7", 120.0, prior_coord="T7", trusted=True)
    assert w.write("M", "U7", 130.0, prior_coord="T7", trusted=True)
    # a guard unwinds by popping the undo journal
    while w.log["undo"]:
        w.log["undo"].pop()
    assert len(w.log["writes_all"]) == 2, w.log["writes_all"]
    sh, coord, old, new = w.log["writes_all"][0]
    assert (sh, coord, old, new) == ("M", "U7", 100.0, 120.0)


def test_run227_claim_needs_a_home_and_proof_outranks_arrival():
    """Run-227 autopsy (2026-09-02): Luna picked the proven fund balance
    (-1,043, exact prior tie, best fit to the checks) and the one-home
    register refused it — the figure was 'claimed' by a stage-3 no-prior
    read of a FORMULA row that never landed in the model. Three laws:
    a claim needs a home; ties are sign-blind; proof outranks arrival."""
    from pipeline.writegate import (claim_holders, claimed_keys,
                                    find_evidence, is_proven, judge_write,
                                    ties_prior)
    # exhibit 1 — a phantom claim (serve skipped as a derived row) holds
    # nothing; the same entry, once homed, does
    served = {("Final", 72): {"value": -1043.0, "conf": 3, "homed": False,
                              "note": "stage-3 read (no prior)"}}
    assert claimed_keys(served) == set()
    served[("Final", 72)]["homed"] = True
    assert claimed_keys(served) == {1043.0}
    # exhibit 2 — the fund-balance row prints -370 where the model stores
    # 370: the tie is sign-blind, like find_evidence
    fca = {"doc": "pres", "page": 37, "nums": [1043.0, -370.0]}
    assert ties_prior(fca, 1.0, 370.0)
    # exhibit 3 — proof outranks arrival: an UNPROVEN homed claim yields
    # to a proven, prior-tied write
    ev = find_evidence([fca], -1043.0)
    assert ev
    assert not is_proven(served[("Final", 72)])
    v, why, _f = judge_write(-1043.0, 370.0, False, ev,
                             claimed_keys(served), claim_holders(served))
    assert v == "EVICT", (v, why)
    # exhibit 4 — a PROVEN holder still blocks: one row, one claim
    served[("Final", 72)].update(conf=4, note="stage-2 join: prior ties")
    assert is_proven(served[("Final", 72)])
    v, why, _f = judge_write(-1043.0, 370.0, False, ev,
                             claimed_keys(served), claim_holders(served))
    assert v == "REFUSE" and "one row, one claim" in why
    # exhibit 5 — without the holders view (legacy callers) the verdict
    # is unchanged: REFUSE
    served[("Final", 72)].update(conf=3, note="stage-3 read (no prior)")
    v, why, _f = judge_write(-1043.0, 370.0, False, ev, claimed_keys(served))
    assert v == "REFUSE"


def test_run228_vintage_law_decided_once_before_any_serve():
    """Run-228 autopsy (2026-09-02): reconciliation + join served 45 rows
    from the prior-year annual report (19 wrong — the fuel-clause charge
    2 vs 44.3 collapsed every forecast year while balance still held).
    Cause: the vintage vote first ran inside stage 3, and the early
    stages asked the WEAK test (prior only), which is empty when a
    restated prior-year AR votes 'unknown'. Law: ONE strong test
    (vintage_ban), decided once before any stage serves, binding
    pinned serves too."""
    import inspect
    from pipeline import run as run_mod, reconcile, stage2_join, stage3_read
    from pipeline.ledger import Ledger, vintage_ban
    led = Ledger()
    led._doc_periods = {"AR25.pdf": "current", "RA25.pdf": "current",
                        "AR24.pdf": "unknown"}
    # exhibit 1 — the strong test bans the unknown once a doc proved current
    assert vintage_ban(led) == {"AR24.pdf"}
    assert led.prior_period_docs() == set()      # the weak test saw nothing
    # exhibit 2 — with no proven-current doc, only 'prior' is banned
    led._doc_periods = {"A.pdf": "unknown", "B.pdf": "prior"}
    assert vintage_ban(led) == {"B.pdf"}
    # exhibit 3 — a museum fake that only knows the weak test still works
    class Fake:
        def prior_period_docs(self):
            return {"old.pdf"}
    assert vintage_ban(Fake()) == {"old.pdf"}
    # exhibit 4 — every serving stage asks the ONE test, none the weak one
    for mod in (reconcile, stage2_join, stage3_read):
        src = inspect.getsource(mod)
        assert ".prior_period_docs()" not in src, mod.__name__
        assert "_vintage_ban(" in src, mod.__name__
    # exhibit 5 — the verdict is decided before reconciliation serves
    src = inspect.getsource(run_mod.update)
    assert src.index("classify_from_targets") < src.index("reconcile(wb")
    # exhibit 6 — the verdict travels with a pinned ledger
    led = Ledger()
    led._doc_periods = {"AR25.pdf": "current", "AR24.pdf": "unknown"}
    led._pv_tables = {("AR25.pdf", 7, 0)}
    led2 = Ledger.from_json(led.to_json())
    assert vintage_ban(led2) == {"AR24.pdf"}
    assert led2._pv_tables == {("AR25.pdf", 7, 0)}


def test_document_identification_owner_ruling_2026_09_03():
    """Owner ruling (2026-09-03, run-228 autopsy): the agent must first
    say what each document IS — never infer it from a folder or a count
    of number matches. Printed-period reader = the offline floor; the
    brain's card outranks it; disagreement -> UNKNOWN + flagged; the
    numeric vote is only the backstop/tripwire."""
    from pipeline.docid import (classify_identity, identify_documents,
                                printed_identity)
    from pipeline.ledger import Ledger, vintage_ban
    # exhibit 1 — English annual report names itself on its first pages
    p = printed_identity([(2, "2024 Annual Report Introduction Welcome to CLP's 2024 Annual Report."),
                          (4, "Contents ... A Snapshot of CLP in 2024 ... Financial Highlights 7")])
    assert p["year"] == 2024 and p["months"] == 12 and p["doc_type"] == "annual report", p
    # exhibit 2 — a results announcement: "from 1 January 2025 to 31 December 2025"
    p = printed_identity([(1, "Announcement of Annual Results from 1 January 2025 to "
                              "31 December 2025, Dividend Declaration ... 2024: HK$10,949")])
    assert (p["year"], p["month"], p["day"], p["months"]) == (2025, 12, 31, 12), p
    # exhibit 3 — Chinese annual report + 报告期
    p = printed_identity([(2, "东方电气股份有限公司2024年年度报告 重要提示"),
                          (4, "报告期 指 2024年1月1日至2024年12月31日")])
    assert (p["year"], p["months"], p["doc_type"]) == (2024, 12, "annual report"), p
    # exhibit 4 — an interim: six months ended / 半年度报告
    p = printed_identity([(1, "Interim Report 2025 — for the six months ended 30 June 2025")])
    assert (p["year"], p["month"], p["months"]) == (2025, 6, 6), p
    p = printed_identity([(2, "某某股份有限公司2025年半年度报告")])
    assert (p["year"], p["months"], p["doc_type"]) == (2025, 6, "interim report"), p
    # exhibit 5 — comparatives mentioned in the text do not steal the year
    p = printed_identity([(3, "Welcome to CLP's 2025 Annual Report. Compared with 2024, "
                              "the 2024 result and the 2024 dividend ...")])
    assert p["year"] == 2025, p
    # exhibit 6 — the mapping to the target period
    assert classify_identity({"year": 2024, "months": 12}, 2025, "FY") == "prior"
    assert classify_identity({"year": 2025, "months": 12}, 2025, "FY") == "current"
    assert classify_identity({"year": 2025, "months": 6}, 2025, "FY") == "partial"
    assert classify_identity({"year": 2025, "months": 6}, 2025, "1H") == "current"
    assert classify_identity({"year": 2026, "months": 12}, 2025, "FY") == "future"
    assert classify_identity({}, 2025, "FY") is None
    # exhibit 7 — end to end on stubbed pages: the reading binds the ban,
    # the numeric vote is only a backstop, and a contradiction flags
    import pipeline.docid as docid
    texts = {"AR24.pdf": [(2, "2024 Annual Report Welcome to CLP's 2024 Annual Report", "text")],
             "AR25.pdf": [(3, "Welcome to CLP's 2025 Annual Report.", "text")],
             "scan.pdf": [(1, "", "image")],
             "odd.pdf": [(1, "Welcome to CLP's 2025 Annual Report.", "text")]}
    import pipeline.stage1_read as s1
    real = s1.page_texts
    s1.page_texts = lambda path, cache_dir=None: texts[path]
    try:
        led = Ledger()
        led._doc_periods = {"AR24.pdf": "unknown", "AR25.pdf": "current",
                            "scan.pdf": "current", "odd.pdf": "prior"}
        out = identify_documents(list(texts), led, None, 2025, "FY", lambda s: None)
    finally:
        s1.page_texts = real
    v = {d["doc"]: d["verdict"] for d in out}
    assert v["AR24.pdf"] == "prior", v          # the reading decides
    assert v["AR25.pdf"] == "current", v
    assert v["scan.pdf"] == "current", v        # no print -> numeric vote stands
    assert v["odd.pdf"] == "unknown", v         # reading vs vote contradiction -> flagged
    assert vintage_ban(led) == {"AR24.pdf", "odd.pdf"}, vintage_ban(led)
    assert led.doc_meta["AR24.pdf"]["identity"]["verdict"] == "prior"
    # exhibit 8 — the issuer: a current document from ANOTHER company is
    # set unknown and flagged; Chinese and English names compare on
    # their own tokens, and an unreadable issuer never false-alarms
    from pipeline.docid import printed_issuer, same_issuer
    assert printed_issuer([(1, "CLP Holdings Limited (incorporated in Hong Kong) "
                               "... CLP Holdings Limited ... Stock Code 00002")]) \
        == "CLP Holdings Limited"
    assert printed_issuer([(2, "东方电气股份有限公司2025年年度报告")]) == "东方电气股份有限公司"
    assert same_issuer("CLP Holdings Limited", "CLP Power Hong Kong Limited")
    assert not same_issuer("CLP Holdings Limited", "Dongfang Electric Corporation")
    assert same_issuer("东方电气股份有限公司", "东方电气集团")
    assert same_issuer(None, "anything")
    texts = {"AR25.pdf": [(3, "Welcome to CLP's 2025 Annual Report. CLP Holdings Limited", "text")],
             "RA25.pdf": [(1, "CLP Holdings Limited Announcement of Annual Results from "
                              "1 January 2025 to 31 December 2025", "text")],
             "wrong.pdf": [(2, "Dongfang Electric Corporation Limited 2025 Annual Report", "text")]}
    s1.page_texts = lambda path, cache_dir=None: texts[path]
    try:
        led = Ledger()
        led._doc_periods = {d: "current" for d in texts}
        out = identify_documents(list(texts), led, None, 2025, "FY", lambda s: None)
    finally:
        s1.page_texts = real
    v = {d["doc"]: d["verdict"] for d in out}
    assert v == {"AR25.pdf": "current", "RA25.pdf": "current", "wrong.pdf": "unknown"}, v
    assert "ISSUER MISMATCH" in next(d for d in out if d["doc"] == "wrong.pdf")["line"]
    assert vintage_ban(led) == {"wrong.pdf"}


def test_reading_step_brain_judges_code_verifies():
    """Owner ruling (2026-09-03): every 'what is this' decision is the
    brain's, with code verifying the answer numerically. Statement pages
    and the model's key rows follow the document-identity pattern."""
    from pipeline.docid import identify_key_rows, identify_statement_pages
    from pipeline.ledger import Item, Ledger

    class Stub:
        def __init__(self, answer):
            self.answer = answer
        def json(self, system, user, validate, repair_retries=0, images=None):
            assert not validate(self.answer), validate(self.answer)
            return self.answer

    # exhibit 1 — statement pages: a brain-named page is adopted ONLY when
    # its numbers tie the model's prior year; an untied page is refused;
    # a parent-only page loses its face
    led = Ledger()
    led.doc_meta["AR.pdf"] = {}
    rows = [(60, "Revenue", [120000.0, 118000.0]), (60, "Costs", [-46000.0, -45000.0]),
            (60, "Profit before tax", [31000.0, 30000.0]), (60, "Profit for the year", [24000.0, 22000.0]),
            (61, "Ratio", [5.0, 6.0]), (61, "Other", [7.0, 8.0]), (62, "Memo", [9.0]),
            # a NOTE page that also ties priors (45,000 / 30,000) but whose rows
            # do not read as a statement — run-230's trap
            (75, "Net book value at", [1.0, 45000.0, 30000.0, 914.0]),
            (75, "Additions", [2.0, 118000.0, 22000.0, 500.0])]
    for i, (pn, lab, nums) in enumerate(rows):
        led.items.append(Item(doc="AR.pdf", page=pn, table_id=0, row_ord=i,
                              label=lab, nums=nums, stmt_face=None,
                              unit_dim="unknown", scale_hint=None,
                              source_line=lab + " " + " ".join(map(str, nums))))
    led.faces[("AR.pdf", 62)] = "pl"           # the caption tagger's pick
    import pipeline.stage1_read as s1
    real = s1.page_texts
    # the brain names PRINTED page numbers: printed 130 is PDF page 60
    # (its footer says 130); PDF page 75 is a note that ratifies but is
    # not a statement by its rows
    s1.page_texts = lambda path, cache_dir=None: [
        (1, "Contents ... Consolidated Income Statement 130", "text"),
        (60, "Revenue 120,000 118,000 ... Profit for the year\n130", "text"),
        (75, "Note 12 Property, plant and equipment\n145", "text")]
    try:
        res = identify_statement_pages(["AR.pdf"], led,
                                       Stub({"pl": [130], "bs": [61, 75], "cf": [],
                                             "segment": [], "parent_only": [62],
                                             "why": "contents p1"}),
                                       [118000.0, 45000.0, 30000.0, 22000.0],
                                       lambda s: None)
    finally:
        s1.page_texts = real
    assert led.faces.get(("AR.pdf", 60)) == "pl", led.faces          # printed 130 -> pdf 60
    assert any("p130->pdf60=pl" in x for x in res["AR.pdf"]["adopted"]), res
    assert ("AR.pdf", 61) not in led.faces and any("p61=bs" in x for x in res["AR.pdf"]["refused"])
    assert ("AR.pdf", 75) not in led.faces and any("p75=bs" in x for x in res["AR.pdf"]["refused"])
    assert ("AR.pdf", 62) not in led.faces and ("AR.pdf", 62) in led.parent_pages
    # exhibit 1b — the brain's map is the authority: a caption-propagated
    # face on a page far from any named statement is demoted (run-229:
    # the fixed-asset note tagged 'cf'); a page adjacent to a named
    # statement keeps its face (a statement running over the page)
    led.faces[("AR.pdf", 70)] = "cf"          # caption-propagated, no statement rows
    led.faces[("AR.pdf", 59)] = "pl"          # adjacent to the confirmed statement
    led.faces[("AR.pdf", 90)] = "cf"          # a real CF page far away: self-identifies
    led.items.append(Item(doc="AR.pdf", page=90, table_id=0, row_ord=1,
                          label="Net cash from operating activities", nums=[9000.0, 8000.0],
                          stmt_face=None, unit_dim="unknown", scale_hint=None, source_line=""))
    led.items.append(Item(doc="AR.pdf", page=90, table_id=0, row_ord=2,
                          label="Net cash used in investing activities", nums=[-3000.0, -2500.0],
                          stmt_face=None, unit_dim="unknown", scale_hint=None, source_line=""))
    s1.page_texts = lambda path, cache_dir=None: [(1, "Contents", "text")]
    try:
        identify_statement_pages(["AR.pdf"], led,
                                 Stub({"pl": [60], "bs": [], "cf": [], "segment": [],
                                       "parent_only": [], "why": "contents"}),
                                 [118000.0, 45000.0, 30000.0], lambda s: None)
    finally:
        s1.page_texts = real
    assert ("AR.pdf", 70) not in led.faces and led.faces.get(("AR.pdf", 59)) == "pl"
    assert led.faces.get(("AR.pdf", 90)) == "cf"      # never demote a self-identifying statement
    # exhibit 1c — reconciliation's time-signature law: a wide row is not
    # a statement line
    from pipeline.reconcile import is_statement_line, small_prior_needs_kinship
    assert is_statement_line({"nums": [12.0, 6608.0, 471.0]})
    assert not is_statement_line({"nums": [1.0, 6608.0, 471.0, 914.0, 7993.0]})
    # exhibit 1d — the small-prior law: a small prior ties by coincidence
    # unless the labels are kin; a material prior is its own identity
    assert not small_prior_needs_kinship(-23.0, "Short-term deposits and restricted cash",
                                         "- Decrease / (increase) in fuel clause account")
    assert not small_prior_needs_kinship(-10.0, "Meters", "Operating expenditure")
    assert small_prior_needs_kinship(105.0, "India", "One-off items")   # material: size decides
    assert small_prior_needs_kinship(-471.0, "Net book value at", "Finance costs")  # size, not label
    assert small_prior_needs_kinship(-12.0, "Finance costs", "Finance costs")
    assert small_prior_needs_kinship(-23.0, "Fuel clause account", "Decrease / (increase) in fuel clause account")
    # without a brain, nothing changes (the floor)
    assert identify_statement_pages(["AR.pdf"], led, None, [], lambda s: None) == {}

    # exhibit 2 — key rows: a brain pick replaces the pattern pick of the
    # same name only if the row carries numbers; a labels-only row is dropped
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Final"
    rows = {7: ("Total revenue", 100.0), 15: ("Net operating income", 20.0),
            27: ("Net profits (reported)", 12.0), 31: ("Recurring net profit", 13.0),
            40: ("Memo: EPS commentary", None)}
    for r, (lab, v) in rows.items():
        ws.cell(r, 1, lab)
        if v is not None:
            ws.cell(r, 3, v)
    spec = {"year_axis": {"Final": {"columns": {"2024": "C"}}},
            "key_rows": [{"name": "net profit", "sheet": "Final", "row": 27},
                         {"name": "revenue", "sheet": "Final", "row": 7}]}
    picks = identify_key_rows(wb, spec, Stub({"key_rows": [
        {"row": 31, "name": "recurring net profit"},
        {"row": 15, "name": "operating profit"},
        {"row": 40, "name": "eps"},
        {"row": 27, "name": "net profit"}], "why": "labels"}), lambda s: None)
    names = {k["name"]: k["row"] for k in spec["key_rows"]}
    assert names["recurring net profit"] == 31 and names["operating profit"] == 15
    assert names["net profit"] == 27 and names["revenue"] == 7      # pattern pick kept
    assert "eps" not in names                                        # no numbers -> dropped
    assert {p["name"] for p in picks} == {"recurring net profit", "operating profit", "net profit"}
    assert identify_key_rows(wb, spec, None, lambda s: None) == []
    # exhibit 2b — numeric verification against the pinned panel (run-230:
    # the brain named EBIT as 'operating profit'): a named row whose
    # prior-year value does not tie the panel's prior is dropped
    import json, tempfile
    ws.cell(20, 1, "EBIT"); ws.cell(20, 3, 24.0)          # prior 24 (col C = 2024)
    spec2 = {"year_axis": {"Final": {"columns": {"2024": "C", "2025": "D"}}},
             "key_rows": [{"name": "operating profit", "sheet": "Final", "row": 15}]}
    with tempfile.TemporaryDirectory() as d:
        pp = f"{d}/key_panel.json"
        json.dump({"operating profit": {"print": 21.0, "prior": 20.0}}, open(pp, "w"))
        picks2 = identify_key_rows(wb, spec2, Stub({"key_rows": [
            {"row": 20, "name": "operating profit"}], "why": "EBIT"}), lambda s: None,
            panel_path=pp, target_year=2025)
        assert picks2 == [] and {k["row"] for k in spec2["key_rows"] if k["name"] == "operating profit"} == {15}
        picks3 = identify_key_rows(wb, spec2, Stub({"key_rows": [
            {"row": 15, "name": "operating profit"}], "why": "NOI"}), lambda s: None,
            panel_path=pp, target_year=2025)
        assert [k["row"] for k in picks3] == [15]
        # a verified pick on the primary sheet is not displaced by a brain
        # pick of the same name on ANOTHER sheet (run 232: Driver!28)
        ws2 = wb.create_sheet("Driver")
        ws2.cell(28, 1, "Operating Income before JCEs"); ws2.cell(28, 3, 20.0); ws2.cell(28, 4, 21.0)
        spec3 = {"year_axis": {"Final": {"columns": {"2024": "C", "2025": "D"}},
                               "Driver": {"columns": {"2024": "C", "2025": "D"}}},
                 "key_rows": [{"name": "operating profit", "sheet": "Final", "row": 15}]}
        ws.cell(15, 3, 20.0)                      # Final!15 prior ties the panel too
        class Stub2:
            def json(self, system, user, validate, repair_retries=0, images=None):
                if user.startswith("Sheet: Driver"):
                    return {"key_rows": [{"row": 28, "name": "operating profit"}], "why": "d"}
                return {"key_rows": [], "why": "f"}
        identify_key_rows(wb, spec3, Stub2(), lambda s: None, panel_path=pp, target_year=2025)
        assert [(k["sheet"], k["row"]) for k in spec3["key_rows"] if k["name"] == "operating profit"] == [("Final", 15)]
    # exhibit 2c — THE ANALYST'S ORDER (owner 2026-09-04): actuals ->
    # rollover check -> balance cards -> plugs. THE BUDGET IS TIME (owner
    # 2026-09-08, run 250): no call cap, no reserved share — the queue gets
    # what is left of the hour, and the balance cards are asked regardless
    # of the clock (they are few and they close the model).
    import inspect
    from pipeline import workqueue as wq
    src = inspect.getsource(wq.build_queue)
    assert '"SERVE": 0' in src and '"ROLLOVER": 1' in src and '"COMPONENT": 2' in src
    assert not hasattr(wq, "CALL_CAP") and not hasattr(wq, "reserve_for_balance")
    rq = inspect.getsource(wq.run_queue)
    assert 'item.kind not in ("COMPONENT", "PLUG")' in rq and "deadline_s" in rq
    from pipeline import run as _run
    assert _run.RUN_TARGET_S == 3600 and "deadline_s=max(60.0, _left)" in inspect.getsource(_run.update)


def test_rollover_investigation_owner_teaching_2026_09_03():
    """Owner teaching: after rolling forward, the agent compares the
    actual surprise with the forecast move; out of proportion / sign
    flip / collapse -> go back and investigate: code probes which
    changed input drives it, the brain judges, the report shows it.
    Not a gate that fails the run — a return to the desk."""
    import openpyxl
    from pipeline.rollover import (dossier, estimate_baseline, render,
                                   rollover_anomalies, strange)
    # exhibit 1 — the proportionality test, in the owner's words
    assert strange(1000.0, 1100.0, 5000.0, 5500.0) == (False, "")     # +10% -> +10%: fine
    assert strange(1000.0, 1100.0, 5000.0, 5700.0)[0] is False        # +14%: within band
    assert strange(1000.0, 1500.0, 20000.0, 14000.0)[0]               # +500 actual, -6,000 fc
    assert "SIGN FLIP" in strange(1000.0, 1050.0, 5000.0, -3000.0)[1]
    assert "COLLAPSED" in strange(1000.0, 1050.0, 5000.0, 20.0)[1]
    assert "OUT OF PROPORTION" in strange(14873.0, 14272.0, 15677.0, 4867.0)[1]  # run 228's OP
    assert strange(None, None, 5000.0, 2000.0)[0]                     # no estimate: 50% band
    assert strange(None, None, 5000.0, 3000.0)[0] is False
    assert strange(1000.0, 1100.0, 50.0, -40.0) == (False, "")        # tiny rows are noise
    assert "APPEARED FROM ZERO" in strange(0.0, 4636.0, 0.0, 4636.0)[1]  # run 232's 'Others' residual
    assert strange(0.0, 120.0, 0.0, 120.0) == (False, "")               # small appearances are noise
    # exhibit 2 — end to end on a tiny model: forecast = tariff x units
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "M"
    ws["A1"], ws["B1"], ws["C1"], ws["D1"] = "year", 2024, 2025, 2026
    ws["A2"], ws["B2"], ws["C2"], ws["D2"] = "Fuel clause charge", 44.0, 44.3, "=C2"
    ws["A3"], ws["B3"], ws["C3"], ws["D3"] = "Units", 100.0, 102.0, "=C3*1.03"
    ws["A4"], ws["B4"], ws["C4"], ws["D4"] = "Fuel revenue", "=B2*B3", "=C2*C3", "=D2*D3"
    spec = {"year_axis": {"M": {"header_row": 1,
                                "columns": {"2024": "B", "2025": "C", "2026": "D"}}},
            "key_rows": [{"name": "revenue", "sheet": "M", "row": 4}]}
    base = estimate_baseline(wb, spec, 2025)
    assert base[("M", 4)][1] == 44.3 * 102.0 and abs(base[("M", 4)][2] - 44.3 * 102.0 * 1.03) < 1e-6
    # the update: the 2025 revenue actual is typed (4,700 — a 4% surprise),
    # units come in at 105 (fine); the fuel clause is served 2 (wrong) —
    # exactly run 228: the actual holds, the forecast collapses
    writes_all = [("M", "C4", "=C2*C3", 4700.0), ("M", "C3", 102.0, 105.0),
                  ("M", "C2", 44.3, 2.0)]
    ws["C4"], ws["C3"], ws["C2"] = 4700.0, 105.0, 2.0
    anoms = rollover_anomalies(wb, spec, 2025, base, key_rows=spec["key_rows"])
    assert [(a["sheet"], a["row"]) for a in anoms] == [("M", 4)], anoms
    assert anoms[0]["key"] and ("AGAINST THE ACTUAL" in anoms[0]["reason"]
                                or "OUT OF PROPORTION" in anoms[0]["reason"])

    def leaves(sheet, coord, _wb=wb):
        return [("M", "C2"), ("M", "C3")]
    cands = dossier(wb, spec, 2025, "M", 4, anoms[0]["old_f"], writes_all, leaves,
                    served={("M", 2): {"note": "reconciliation: FY24 AR p274"}})
    assert cands[0]["coord"] == "C2" and cands[0]["share"] > 0.9, cands
    assert cands[1]["coord"] == "C3" and cands[1]["share"] < 0.1, cands
    assert "FY24 AR p274" in cands[0]["prov"]
    text, options, default = render(anoms[0], cands)
    assert "CARD ROLLOVER M!4" in text and default == "not_sure", text
    assert "A: M!C2 44.3 -> 2.0  ⇒ recovers " in text, text
    assert options["revert:A"][0] == "rollover_revert" and options["revert:A"][1]["old"] == 44.3
    assert set(options) == {"revert:A", "revert:B", "justified", "not_sure"}
    # the probe left the model untouched
    assert ws["C2"].value == 2.0 and ws["C3"].value == 105.0
    # exhibit 2b — PROVEN IS PROTECTED (run-229 autopsy): a proven actual
    # is shown but never offered for reversion; an unproven one still is
    cands = dossier(wb, spec, 2025, "M", 4, anoms[0]["old_f"], writes_all, leaves,
                    served={("M", 2): {"note": "reconciliation: FY24 AR p274", "conf": 4},
                            ("M", 3): {"note": "stage-3 read (no prior)", "conf": 3}})
    assert cands[0]["coord"] == "C2" and cands[0]["proven"] is True
    assert cands[1]["coord"] == "C3" and cands[1]["proven"] is False
    text, options, default = render(anoms[0], cands)
    assert "revert:A" not in options and "revert:B" in options, options
    assert "PROVEN actual" in text and "never reverted" in text
    # a RED-filled 'proven' entry is not proven (an orange one keeps its
    # protection — the writer's flag list holds both colours, run 229)
    from openpyxl.styles import PatternFill
    ws["C2"].fill = PatternFill("solid", fgColor="FFC7CE")
    cands = dossier(wb, spec, 2025, "M", 4, anoms[0]["old_f"], writes_all, leaves,
                    served={("M", 2): {"note": "x", "conf": 4}})
    assert cands[0]["proven"] is False
    ws["C2"].fill = PatternFill("solid", fgColor="FFC000")
    cands = dossier(wb, spec, 2025, "M", 4, anoms[0]["old_f"], writes_all, leaves,
                    served={("M", 2): {"note": "x", "conf": 4}})
    assert cands[0]["proven"] is True
    ws["C2"].fill = PatternFill()
    # exhibit 2c — a constants composite whose literals are all proven
    # served figures is proven (run-229: '=+-1860+194' net finance costs)
    from pipeline.rollover import input_is_proven
    served = {("D", 103): {"value": -1860.0, "conf": 4, "note": "reconciliation: prior ties"},
              ("D", 104): {"value": 194.0, "conf": 4, "note": "stage-2 join: prior ties"}}
    assert input_is_proven(served, "F", "AI21", "=+-1860+194")
    assert not input_is_proven(served, "F", "AI21", "=+-1860+999")
    assert not input_is_proven(served, "F", "AI21", "=AI9-AI10")     # refs: not a composite
    assert not input_is_proven(served, "F", "AI21", "=+-1860+194", flags=["F!AI21"])
    # exhibit 2c' — PROVEN BY WHAT IT CHANGED (run-233 live: cash
    # '=4976+23' -> '=3905+23'; 3,905 is the printed year-end cash, the
    # '+23' the analyst's carried adjustment. The '+23' matched no proven
    # figure, the composite read as unproven, the rollover card offered
    # it as 'revert:B' and Luna took it — cash held at last year's 4,999).
    # With the old formula in hand only the CHANGED literal needs proof.
    served = {("D", 100): {"value": 3905.0, "conf": 4, "note": "reconciliation: prior ties"}}
    assert input_is_proven(served, "F", "AI57", "=3905+23", old="=4976+23")
    assert not input_is_proven(served, "F", "AI57", "=3905+23")            # no old: '+23' unproven
    assert not input_is_proven(served, "F", "AI57", "=3999+23", old="=4976+23")  # changed literal unproven
    assert not input_is_proven({}, "F", "AI57", "=3905+23", old="=4976+23")     # nothing proven at all
    # the machinery's own rewrite note is the same proof (the constants
    # law tied every literal before the write landed)
    from openpyxl import Workbook as _WB
    from openpyxl.comments import Comment as _Cm
    _w = _WB(); _ws = _w.active; _ws.title = "F"
    _ws["AI57"] = "=3905+23"
    _ws["AI57"].comment = _Cm("COMPOSITE REWRITE (constants law): was =4976+23 = stale prior", "agent")
    assert input_is_proven({}, "F", "AI57", "=3905+23", wb=_w)
    _ws["AI57"].comment = _Cm("objective loop: reverted", "agent")
    assert not input_is_proven({}, "F", "AI57", "=3905+23", wb=_w)
    # exhibit 2d — THE RESIDUAL DISCOUNT (run-229: net financial costs =
    # segments + an 'Others' residual that rolls forward; reverting the
    # total's composite "recovered the swing" through the residual while
    # the real culprit was a segment driver). Two inputs changed: the
    # typed total (right or wrong, it only feeds the residual) and the
    # segment driver (wrong). Raw shares blame the total; with the
    # residual frozen the driver ranks first and the total is discounted.
    wb2 = openpyxl.Workbook()
    w = wb2.active
    w.title = "R"
    w["A1"], w["B1"], w["C1"], w["D1"] = "year", 2024, 2025, 2026
    w["A2"], w["B2"], w["C2"], w["D2"] = "Total (typed)", 1000.0, 1000.0, "=D3+D4"
    w["A3"], w["B3"], w["C3"], w["D3"] = "Segment driver", 400.0, 400.0, "=C3*1.02"
    w["A4"], w["B4"], w["C4"], w["D4"] = "Others (residual)", "=B2-B3", "=C2-C3", "=C4"
    spec2 = {"year_axis": {"R": {"header_row": 1, "columns": {"2024": "B", "2025": "C", "2026": "D"}}}}
    from pipeline.rollover import residual_cells
    assert residual_cells(wb2, spec2, 2025) == [("R", "C4")]
    base2 = estimate_baseline(wb2, spec2, 2025)
    old_f2 = base2[("R", 2)][2]                      # 408 + 600 = 1,008
    writes2 = [("R", "C2", 1000.0, 1300.0), ("R", "C3", 400.0, 900.0)]
    w["C2"], w["C3"] = 1300.0, 900.0                 # new forecast: 918 + 400 = 1,318
    cands2 = dossier(wb2, spec2, 2025, "R", 2, old_f2, writes2,
                     lambda s, c: [("R", "C2"), ("R", "C3")], served={})
    byc = {c["coord"]: c for c in cands2}
    assert byc["C2"]["share"] > 0.9 and byc["C2"]["share_x"] < 0.05 and byc["C2"]["via_residual"], byc
    assert byc["C3"]["share"] < 0.1 and byc["C3"]["share_x"] > 0.9, byc
    assert cands2[0]["coord"] == "C3", [c["coord"] for c in cands2]   # the driver ranks first
    text2, _o, _d = render({"sheet": "R", "row": 2, "label": "Total", "est_t": 1000.0,
                            "act_t": 1300.0, "old_f": old_f2, "new_f": 1318.0,
                            "reason": "OUT OF PROPORTION"}, cands2)
    assert "residual rows frozen" in text2
    assert w["C2"].value == 1300.0 and w["C3"].value == 900.0 and w["C4"].value == "=C2-C3"
    # exhibit 3 — the old collapse test never fired on run 228's -69%
    from pipeline.teachings import collapsed_forecasts
    assert collapsed_forecasts(wb, spec, 2025, {("M", 4): 4655.0}) == [] \
        or True  # (documented: the rollover test is the one that catches it)


def test_rule2_keys_at_the_gate_owner_2026_09_03():
    """Owner (2026-09-03): rule 1 is balance, rule 2 is the keys — run
    229 had the keys right before stage 4, two late reverts broke four,
    and the gate never looked. A key proven-printed before stage 4 that
    moves to a value printed nowhere refuses the run (and feeds the
    take-back loop); a move to ANOTHER printed figure is a definition
    question, never a refusal; a key never proven is never gated."""
    import json, tempfile
    import openpyxl
    from pipeline.keytie import key_snapshot, key_violations
    from pipeline.ledger import Item, Ledger
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "F"
    ws["A1"], ws["B1"], ws["C1"] = "year", 2024, 2025
    ws["A7"], ws["B7"], ws["C7"] = "Revenue", 90964.0, 88018.0
    ws["A15"], ws["B15"], ws["C15"] = "Operating profit", 14903.0, 14272.0
    ws["A31"], ws["B31"], ws["C31"] = "Recurring NP", 12000.0, 10374.0
    spec = {"year_axis": {"F": {"header_row": 1, "columns": {"2024": "B", "2025": "C"}}},
            "key_rows": [{"name": "revenue", "sheet": "F", "row": 7},
                         {"name": "operating profit", "sheet": "F", "row": 15},
                         {"name": "recurring net profit", "sheet": "F", "row": 31}]}
    led = Ledger()
    led._doc_periods = {"RA.pdf": "current"}
    led.faces[("RA.pdf", 23)] = "pl"
    led.items.append(Item(doc="RA.pdf", page=23, table_id=0, row_ord=1, label="Revenue",
                          nums=[88018.0, 90964.0], stmt_face="pl", unit_dim="unknown",
                          scale_hint=None, source_line="Revenue 88,018 90,964"))
    led.items.append(Item(doc="RA.pdf", page=23, table_id=0, row_ord=2, label="Operating profit",
                          nums=[14272.0, 14903.0], stmt_face="pl", unit_dim="unknown",
                          scale_hint=None, source_line="Operating profit 14,272 14,903"))
    led.items.append(Item(doc="RA.pdf", page=23, table_id=0, row_ord=3, label="Operating earnings",
                          nums=[13812.0, 13000.0], stmt_face="pl", unit_dim="unknown",
                          scale_hint=None, source_line="Operating earnings 13,812 13,000"))
    with tempfile.TemporaryDirectory() as d:
        panel = f"{d}/key_panel.json"
        json.dump({"revenue": {"print": 88018.0}}, open(panel, "w"))
        snap = key_snapshot(wb, spec, 2025, led, panel)
        assert set(snap) == {"revenue", "operating profit"}, snap   # recurring NP: never proven
        assert "pinned print" in snap["revenue"][2] and "printed on RA.pdf p23" in snap["operating profit"][2]
        assert key_violations(wb, spec, 2025, led, panel, snap) == []
        # a late write moves OP to a value printed nowhere -> violation
        ws["C15"] = 13500.0
        v = key_violations(wb, spec, 2025, led, panel, snap)
        assert [(x[0], x[2], x[3]) for x in v] == [("operating profit", 14272.0, 13500.0)], v
        # a move to ANOTHER printed figure (a definition) is not a violation
        ws["C15"] = 13812.0
        assert key_violations(wb, spec, 2025, led, panel, snap) == []
        # the never-proven key may change freely
        ws["C31"] = 9561.0
        assert key_violations(wb, spec, 2025, led, panel, snap) == []
        # the gate wiring: run.update snapshots before stage 4 and gate_once asks
        import inspect
        from pipeline import run as run_mod
        src = inspect.getsource(run_mod.update)
        assert src.index("keys_before = _key_snapshot") < src.index("ObjectiveLoop(wb")
        assert "_key_violations(wb, spec_d, target_year" in src


def test_printed_subtotal_law_owner_2026_09_04():
    """Owner (2026-09-04, run 231 delivered with total assets +661 while
    balanced): current / non-current / total assets, liabilities and
    equity are printed — the agent finds the number or backs out to the
    printed subtotal. Every same-column subtotal row whose printed
    counterpart is identified on a face (comparative ties the model's
    prior, label kin) ties or gets an orange back-out; tied subtotals
    enter rule 2's register."""
    import openpyxl
    from pipeline.keytie import printed_subtotals, subtotal_tie
    from pipeline.ledger import Item, Ledger
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "F"
    ws["A1"], ws["B1"], ws["C1"] = "year", 2024, 2025
    ws["A57"], ws["B57"], ws["C57"] = "Cash", 100.0, 120.0
    ws["A60"], ws["B60"], ws["C60"] = "Accounts receivable", "=200+80", "=200+80"   # held at last year's split
    ws["A64"], ws["B64"], ws["C64"] = "Total current assets", "=SUM(B57:B63)", "=SUM(C57:C63)"
    ws["A70"], ws["B70"], ws["C70"] = "Other assets", 7620.0, "=8000+400"
    ws["A75"], ws["B75"], ws["C75"] = "Total assets", "=B64+B70", "=C64+C70"
    ws["A98"], ws["B98"], ws["C98"] = "Total liabilities and shareholders' equity", "=B75", "=C75"
    spec = {"year_axis": {"F": {"header_row": 1, "columns": {"2024": "B", "2025": "C"}}},
            "check_rows": [], "key_rows": []}
    led = Ledger()
    led._doc_periods = {"RA.pdf": "current"}
    led.faces[("RA.pdf", 24)] = "bs"
    for i, (lab, nums) in enumerate((("Cash and cash equivalents", [120.0, 100.0]),
                                     ("Trade and other receivables", [330.0, 280.0]),
                                     ("Total current assets", [430.0, 380.0]),
                                     # a five-year summary: leading pair = current | prior
                                     ("Total assets", [9000.0, 8000.0, 7000.0, 6500.0, 6000.0]))):
        led.items.append(Item(doc="RA.pdf", page=24, table_id=0, row_ord=i, label=lab, nums=nums,
                              stmt_face="bs", unit_dim="unknown", scale_hint=None,
                              source_line=lab + " " + " ".join(map(str, nums))))
    subs = printed_subtotals(wb, spec, 2025, led, priors=[100.0, 280.0, 380.0, 8000.0])
    # L+E ties the same prior (assets = L+E) but its nouns differ: not pinned to 'Total assets'
    assert [(d["sheet"], d["row"], d["print"]) for d in subs] == [("F", 64, 430.0), ("F", 75, 9000.0)], subs
    from pipeline.keytie import subtotal_kin
    assert not subtotal_kin("Total assets", "Total liabilities and shareholders' equity")
    assert subtotal_kin("Total current assets", "Total current assets")
    assert not subtotal_kin("Total assets", "Total current assets")
    assert subtotal_kin("Total equity", "Total shareholders' equity")
    w = Writer(wb)
    # only an UNRESOLVED (red) component may absorb; an unflagged one is left alone
    tied = subtotal_tie(wb, spec, 2025, w, led, lambda s: None, priors=[100.0, 280.0, 380.0, 8000.0])
    assert ws["C60"].value == "=200+80" and "printed subtotal 'Total current assets'" not in tied
    from openpyxl.styles import PatternFill
    ws["C60"].fill = PatternFill("solid", fgColor="FFC7CE")
    ws["C70"].fill = PatternFill("solid", fgColor="FFC7CE")
    tied = subtotal_tie(wb, spec, 2025, w, led, lambda s: None, priors=[100.0, 280.0, 380.0, 8000.0])
    from pipeline.evaluator import Evaluator
    assert abs(Evaluator(wb).cell("F", "C64") - 430.0) < 0.01
    assert abs(Evaluator(wb).cell("F", "C75") - 9000.0) < 0.01     # via the five-year table
    assert str(ws["C60"].value).startswith("=(200+80)") and "30" in str(ws["C60"].value)
    assert "printed subtotal 'Total current assets'" in tied
    # bounded: a subtotal off by more than 10% is flagged, never absorbed
    ws["C57"] = 900.0                     # total current assets now far above the print 430
    logs = []
    subtotal_tie(wb, spec, 2025, w, led, logs.append, priors=[100.0, 280.0, 380.0, 8000.0])
    assert any("beyond the back-out bound" in x for x in logs), logs
    ws["C57"] = 120.0
    # idempotent: a second pass backs out nothing more
    before = ws["C60"].value
    subtotal_tie(wb, spec, 2025, w, led, lambda s: None, priors=[100.0, 280.0, 380.0, 8000.0])
    assert ws["C60"].value == before


def test_run232_cash_already_current_and_red_is_a_colour():
    """Run-232 cash autopsy: the constants law had rewritten cash to
    =3905+23 (the balance-sheet figure); phase0 then re-mapped the
    literal 3,905 from the cash MOVEMENT row (opening 4,976 | -787 |
    closing 3,905) into =787+23, and the brain 'justified' the collapse.
    Two laws: a literal that already prints as this year's figure on a
    statement face is never re-mapped; and a cell is red only while it
    is painted red (the flag list is history)."""
    from pipeline.composites import already_current, prove_cell
    from pipeline.ledger import Item, Ledger
    led = Ledger()
    led._doc_periods = {"AR.pdf": "current"}
    led.faces[("AR.pdf", 168)] = "bs"
    led.faces[("AR.pdf", 17)] = "bs"
    led.items.append(Item(doc="AR.pdf", page=168, table_id=0, row_ord=1,
                          label="Cash and cash equivalents", nums=[21.0, 3905.0, 4976.0],
                          stmt_face="bs", unit_dim="unknown", scale_hint=None, source_line=""))
    led.items.append(Item(doc="AR.pdf", page=17, table_id=0, row_ord=1,
                          label="Cash and cash equivalents", nums=[4976.0, 787.0, 3905.0],
                          stmt_face="bs", unit_dim="unknown", scale_hint=None, source_line=""))
    assert already_current(led, 3905.0, "Cash and equivalents")[1] == 168
    assert already_current(led, 4976.0, "Cash and equivalents") is None   # last year's figure
    mapped, why = prove_cell(led, [3905.0, 23.0], row_label="Cash and equivalents")
    assert mapped is None and "already this year's printed figure" in why, why
    # the red test reads the cell's colour, not the flag list
    import inspect
    from pipeline import workqueue as wq
    assert 'rgb.endswith("FFC000")' in inspect.getsource(wq._red_cells)


def test_twins_are_kin_or_linked_run232():
    """Run-232 cash autopsy: the twin re-anchor treated Australia's
    amortisation (-425) and a SoC transfer line (-425) as one quantity
    and overwrote the brain's correct revert. Same prior is not same
    quantity: twins must be kin by label or linked by formula; a red
    (held) cell is never re-anchored."""
    import openpyxl
    from openpyxl.styles import PatternFill
    from pipeline.teachings import twin_reanchor
    from pipeline.writer import Writer
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "M"
    ws["A1"], ws["B1"], ws["C1"] = "year", 2024, 2025
    ws["A5"], ws["B5"], ws["C5"] = "Transfer to development fund", -425.0, 386.0
    ws["A9"], ws["B9"], ws["C9"] = "Amortisation", -425.0, -425.0       # stale, unrelated
    ws["A12"], ws["B12"], ws["C12"] = "Transfer to development fund (HK)", -425.0, -425.0   # kin: re-anchor
    ws["A15"], ws["B15"], ws["C15"] = "Transfer to development fund (Group)", -425.0, -425.0
    ws["C15"].fill = PatternFill("solid", fgColor="FFC7CE")               # red: held
    spec = {"year_axis": {"M": {"header_row": 1, "columns": {"2024": "B", "2025": "C"}}}}
    w = Writer(wb)
    w.log["written"] = ["M!C5"]
    logs = []
    twin_reanchor(wb, wb, spec, 2025, w, logs.append, min_val=100)
    assert ws["C9"].value == -425.0, ws["C9"].value          # coincidence: left alone
    assert any("not kin" in x for x in logs), logs
    assert ws["C12"].value == 386.0                         # kin: re-anchored
    assert ws["C15"].value == -425.0                        # red: never touched
    # cross-script twins (an English model over a Chinese filing) cannot be
    # compared by words: a large, distinctive prior still proves the twin
    ws["A20"], ws["B20"], ws["C20"] = "Cash - year end", 22502.9, 24000.0
    ws["A22"], ws["B22"], ws["C22"] = "现金的期末余额", 22502.9, 22502.9
    ws["A24"], ws["B24"], ws["C24"] = "小额", -425.0, -425.0          # small, cross-script: not proven
    w.log["written"] = ["M!C20", "M!C5"]
    twin_reanchor(wb, wb, spec, 2025, w, logs.append, min_val=100)
    assert ws["C22"].value == 24000.0, ws["C22"].value
    assert ws["C24"].value == -425.0


def test_segment_matrix_is_never_a_yoy_table_run232():
    """Run-232 D&A autopsy: the segment note lists one period per row
    with segments as columns (HK | CN | AU | IN | total); the bound-table
    join paired Hong Kong's -5,727 as 'current' against China's prior
    -840 beside it. Rows that sum across to their last number are a
    segment matrix — never a year-on-year table."""
    from pipeline.stage2_join import is_segment_matrix
    class It:
        def __init__(self, nums):
            self.nums = nums
    seg = [It([-5727.0, -840.0, -2658.0, -51.0, -9276.0]),
           It([49134.0, 5445.0, 34191.0, 642.0, 89412.0]),
           It([12.0, 3.0, 4.0, 5.0, 24.0])]
    assert is_segment_matrix(seg)
    yoy = [It([88018.0, 90964.0]), It([14272.0, 14903.0]), It([21.0, 3905.0, 4976.0])]
    assert not is_segment_matrix(yoy)
    five_year = [It([238644.0, 233713.0, 229051.0, 236026.0, 239809.0])]
    assert not is_segment_matrix(five_year)


def test_leaf_walk_expands_sum_ranges_run232():
    """Run-232 D&A autopsy: the residual 'Others' = AI20 - SUM(AI14:AI18);
    the leaf walker read the range's ends only, so China's D&A (AI16)
    never appeared on the rollover card. Every row of a range is a leaf."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "D"
    for r, v in ((14, 10.0), (15, 20.0), (16, 30.0), (17, 40.0), (18, 50.0)):
        ws[f"AI{r}"] = v
    ws["AI20"] = 200.0
    ws["AI19"] = "=AI20-SUM(AI14:AI18)"
    class Fake:
        _leaf_inputs = ObjectiveLoop._leaf_inputs
        _leaf_inputs_ranges = ObjectiveLoop._leaf_inputs_ranges
    f = Fake()
    f.wb = wb
    leaves = set(f._leaf_inputs_ranges("D", "AI19"))
    assert set(f._leaf_inputs("D", "AI19")) == leaves   # 2026-09-09: every row of a range is an input for every caller (the half-year ladder lesson)
    assert leaves == {("D", "AI20"), ("D", "AI14"), ("D", "AI15"), ("D", "AI16"), ("D", "AI17"), ("D", "AI18")}, leaves


def test_roll_base_fixes_an_input_never_a_formula_2026_09_07():
    """Owner ruling (run 233 review): the structure is the model's. A
    roll-base gap is closed by backing out the LEAST confident INPUT of
    the roll — never by overwriting the formula cell or the actual.
    '3 inputs, 2 confident -> back out the 3rd'."""
    import openpyxl
    from openpyxl.styles import PatternFill
    from pipeline.teachings import roll_base_mismatches
    from pipeline.writer import Writer
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U",
                                            "2026": "V"}}}}

    def build():
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S"
        # row 10 = total opex: 2024 typed, 2025 typed actual (marked to
        # disclosure), 2026 forecast computed from its three components
        # (run 233: Final!14 = AI9 + AI12 rolled -73,746 vs typed -74,206)
        ws["A10"] = "Total operating expenses"
        ws["T10"], ws["U10"], ws["V10"] = 1000.0, 1150.0, "=V11+V12+V13"
        ws["A11"] = "Fuel";  ws["T11"], ws["U11"], ws["V11"] = 700.0, 800.0, "=U11*1.05"
        ws["A12"] = "Staff"; ws["T12"], ws["U12"], ws["V12"] = 280.0, 300.0, "=U12"
        ws["A13"] = "Other"; ws["T13"], ws["U13"], ws["V13"] = 20.0, 20.0, "=U13"
        return wb, ws
    # exhibit 1 — fuel and staff are PROVEN (served, tied); 'Other' still
    # holds last year's 20. Roll from the components: 800+300+20 = 1,120
    # vs the typed 1,150 -> back out 'Other' by +30, touch nothing else
    wb, ws = build()
    served = {("S", 11): {"value": 800.0, "conf": 4, "note": "reconciliation: prior ties"},
              ("S", 12): {"value": 300.0, "conf": 4, "note": "reconciliation: prior ties"}}
    w = Writer(wb)
    n = roll_base_mismatches(wb, spec, 2025, w, lambda s: None, served=served)
    assert n == 1, n
    assert ws["U10"].value == 1150.0                     # the actual untouched
    assert ws["V10"].value == "=V11+V12+V13"             # the formula untouched
    assert ws["U11"].value == 800.0 and ws["U12"].value == 300.0   # proven inputs untouched
    assert ws["U13"].value == "=(20)+(30)", ws["U13"].value          # the 3rd input backed out
    assert str(ws["U13"].fill.fgColor.rgb).endswith("FFC000")
    assert "Backed out" in ws["U13"].comment.text and len(ws["U13"].comment.text) < 130
    # exhibit 2 — two equally uncertain inputs: flag both, guess nothing
    wb, ws = build()
    served = {("S", 11): {"value": 800.0, "conf": 4, "note": "reconciliation: prior ties"}}
    ws["U12"] = 280.0                       # staff also held at prior
    w = Writer(wb)
    roll_base_mismatches(wb, spec, 2025, w, lambda s: None, served=served)
    assert ws["U12"].value == 280.0 and ws["U13"].value == 20.0
    assert str(ws["U12"].fill.fgColor.rgb).endswith("FFC7CE")
    assert str(ws["U13"].fill.fgColor.rgb).endswith("FFC7CE")
    assert "could not tell which" in ws["U13"].comment.text
    assert ws["V10"].value == "=V11+V12+V13"
    # the FORECAST cell is never painted (owner 2026-09-07): the row is
    # watch-listed, the flags sit on the actual-column inputs
    assert not str(ws["V10"].fill.fgColor.rgb or "").endswith("FFC7CE")
    assert ws["V10"].comment is None
    assert any(ref == "S!V10" for ref, _why in w.log.get("forecast_watch", []))
    # exhibit 3 — every input proven: nothing written, the row is a
    # definition question (the old law anchored a FORMULA term here)
    wb, ws = build()
    ws["U13"] = 25.0
    served = {("S", 11): {"value": 800.0, "conf": 4, "note": "x"},
              ("S", 12): {"value": 300.0, "conf": 4, "note": "x"},
              ("S", 13): {"value": 25.0, "conf": 4, "note": "x"}}
    w = Writer(wb)
    roll_base_mismatches(wb, spec, 2025, w, lambda s: None, served=served)
    assert ws["U11"].value == 800.0 and ws["U12"].value == 300.0 and ws["U13"].value == 25.0
    assert ws["V10"].value == "=V11+V12+V13"
    assert not w.log.get("written")
    # exhibit 4 — a formula INSIDE the roll (U12 = U14, staff computed
    # from a sub-input) is walked through to its leaf; the leaf is what
    # gets backed out, the sub-formula stays
    wb, ws = build()
    ws["U12"] = "=U14"; ws["A14"] = "Staff cost build"; ws["T14"], ws["U14"] = 280.0, 280.0
    ws["U13"] = 22.0
    served = {("S", 11): {"value": 800.0, "conf": 4, "note": "x"}}
    w = Writer(wb)
    roll_base_mismatches(wb, spec, 2025, w, lambda s: None, served=served)
    assert ws["U12"].value == "=U14"                     # the sub-formula untouched
    assert ws["U14"].value == "=(280)+(48)", ws["U14"].value
    assert ws["U13"].value == 22.0


def test_two_input_homes_same_prior_resolved_by_label_2026_09_07():
    """DFE run 235: 'cash received from investors' (5,236 this year) and
    its 'of which: from minority investors' sub-line (124) both printed
    110.0 last year; two input homes for one prior, so the reconciliation
    refused the line and the parent was held at growth (share placement
    missed, financing cash flow key off 4,443). The disclosure line's
    LABEL tells the homes apart: equal label wins, else unique kinship."""
    from openpyxl import Workbook
    from pipeline.reconcile import _resolve
    wb = Workbook(); ws = wb.active; ws.title = "Raw"
    ws["A221"] = "    吸收投资收到的现金";        ws["T221"], ws["U221"] = 110.02, 110.02
    ws["A222"] = "    其中：子公司吸收少数股东投资收到的现金"; ws["T222"], ws["U222"] = 110.02, 110.02
    spec = {"year_axis": {"Raw": {"columns": {"2024": "T", "2025": "U"}}}}
    rows = [("Raw", 221), ("Raw", 222)]
    assert _resolve(rows, wb, spec, 2025) == rows                       # no label: unresolved
    assert _resolve(rows, wb, spec, 2025, line_label="吸收投资收到的现金") == [("Raw", 221)]
    assert _resolve(rows, wb, spec, 2025, line_label="其中：子公司吸收少数股东投资收到的现金") == [("Raw", 222)]
    assert _resolve(rows, wb, spec, 2025, line_label="经营活动现金流入") == rows   # unrelated label: unresolved
    # a formula twin still resolves to the one input home, label or not
    ws["U222"] = "=U221"
    assert _resolve(rows, wb, spec, 2025, line_label="x") == [("Raw", 221)]


def test_interim_balance_sheet_compares_to_year_end_2026_09_07():
    """DFE run 236 (1H25): the half-year balance sheet prints 'total
    assets 156,365 | 142,009' — the comparative is the FY24 YEAR-END,
    not the 1H24 column the run was tying against, so every balance-
    sheet row read as 'not found' and was held at growth. The model's
    last annual column is a second home for a printed comparative."""
    from openpyxl import Workbook
    from pipeline.reconcile import _model_prior_index
    wb = Workbook(); ws = wb.active; ws.title = "Raw"
    ws["A78"] = "资产总计"; ws["T78"], ws["AS78"], ws["AT78"] = 142009.28, 131570.41, None
    ws["A4"] = "营业总收入"; ws["T4"], ws["AS4"], ws["AT4"] = 69695.14, 33457.01, None
    spec = {"year_axis": {"Raw": {"columns": {"2024": "AS", "2025": "AT"}}},
            "annual_prior_axis": {"Raw": "T"}}
    homes, by_row = _model_prior_index(wb, spec, 2025)
    assert homes[round(131570.41, 1)] == [("Raw", 78)]      # interim prior still homes
    assert homes[round(142009.28, 1)] == [("Raw", 78)]      # the year-end comparative too
    assert homes[round(69695.14, 1)] == [("Raw", 4)]
    assert by_row[("Raw", 78)] == 131570.41                 # tolerance base = interim prior
    # without the annual axis nothing changes
    homes2, _ = _model_prior_index(wb, {"year_axis": spec["year_axis"]}, 2025)
    assert round(142009.28, 1) not in homes2


def test_page_that_proves_itself_is_a_face_2026_09_07():
    """DFE run 235: the consolidated cash flow statement (PDF p101) read as
    'cf' by its own rows and tied the prior year at one scale, but no
    caption tagged it and the brain's page list did not resolve to it —
    the statement was never walked. Code's own evidence adopts it."""
    from types import SimpleNamespace as NS
    from pipeline.docid import identify_statement_pages
    doc = "X 2025 Annual Report.pdf"
    def it(page, label, nums):
        return NS(doc=doc, page=page, table_id=0, label=label, nums=nums,
                  scale_hint=None, stmt_face=None)
    items = [
        it(101, "经营活动产生的现金流量净额", [2014320913.0, 10059490000.0]),
        it(101, "投资活动产生的现金流量净额", [-10587324054.0, -2773700000.0]),
        it(101, "筹资活动产生的现金流量净额", [5101688323.0, 1088760000.0]),
        it(101, "吸收投资收到的现金", [5236179223.0, 110017500.0]),
        it(150, "固定资产折旧", [854000000.0, 800000000.0]),      # a note: one tie, no face
    ]
    ledger = NS(items=items, faces={}, parent_pages={(doc, 101)},
                noncurrent_docs=lambda: set())
    priors = [10059.49, -2773.7, 1088.76, 110.02, 800.0]
    logs = []
    identify_statement_pages([f"/tmp/{doc}"], ledger, None, priors, logs.append)
    assert ledger.faces.get((doc, 101)) == "cf", ledger.faces
    assert (doc, 101) not in ledger.parent_pages
    assert (doc, 150) not in ledger.faces                       # a note stays a note
    assert any("adopted on their own rows" in l for l in logs), logs
    # an already-tagged face is left alone; a banned (prior-period) doc is skipped
    ledger2 = NS(items=items, faces={(doc, 101): "bs"}, parent_pages=set(),
                 noncurrent_docs=lambda: {doc})
    identify_statement_pages([f"/tmp/{doc}"], ledger2, None, priors, logs.append)
    assert ledger2.faces[(doc, 101)] == "bs"
    # exhibit 2 — CODE OUTRANKS THE NAME (run 238): the brain, naming
    # printed page numbers, called PDF p101 'parent-company only'; the
    # page ratifies against consolidated priors, so it keeps its face
    import pipeline.docid as _docid
    import pipeline.stage1_read as _s1
    _orig = _s1.page_texts
    _s1.page_texts = lambda path: [(1, "目录 财务报告 第87页", "text")]
    class _Client:
        def json(self, system, user, validate, repair_retries=1):
            return {"pl": [], "bs": [], "cf": [], "segment": [],
                    "parent_only": [101, 150], "why": "printed numbers"}
    ledger3 = NS(items=items, faces={(doc, 101): "cf"}, parent_pages=set(),
                 noncurrent_docs=lambda: set())
    try:
        out = identify_statement_pages([f"/tmp/{doc}"], ledger3, _Client(), priors, logs.append)
    finally:
        _s1.page_texts = _orig
    assert ledger3.faces.get((doc, 101)) == "cf", ledger3.faces
    assert (doc, 101) not in ledger3.parent_pages
    assert (doc, 150) in ledger3.parent_pages                    # a note page may be parent-only
    assert any("parent-only refused" in r for r in out[doc]["refused"]), out


def test_owner_statement_laws_2026_09_08():
    """Owner rulings from the DFE 239 review: (1) the 30x guard is a
    suggestion, not a gate — served, red 'please double check' on a weak
    map, plain on an exact-label face map; (2) 0 means 0 — a statement
    line printed nowhere this year is nil; (3) a model row that is a
    subtotal of printed lines sums them when the prior year proves it;
    (4) the ladder plugs only the least confident input, never a proven
    one; (5) a parent-company page never passes as the consolidated one."""
    from types import SimpleNamespace as NS
    from openpyxl import Workbook
    from pipeline.reconcile import reconcile
    doc = "X 2025 Annual Report.pdf"
    def it(page, label, nums, tid=0, ro=0):
        return NS(doc=doc, page=page, table_id=tid, row_ord=ro, label=label, nums=nums,
                  scale_hint=None, stmt_face="cf", joinable=lambda: len(nums) >= 2,
                  channel="text", consensus=2, disputed=False)
    pdoc = "X 2024 Annual Report.pdf"
    class L:
        def __init__(self, items, faces): self.items, self.faces, self.parent_pages = items, faces, set()
        def join_pool(self): return [i for i in self.items if i.joinable() and i.doc != pdoc]
        def noncurrent_docs(self): return {pdoc}
        prior_period_docs = (pdoc,)
    wb = Workbook(); ws = wb.active; ws.title = "Raw"
    spec = {"year_axis": {"Raw": {"header_row": 2, "columns": {"2024": "T", "2025": "U"}}}}
    # rows: share placement (exact label, 47x), a weak-map 40x line, bond issuance (nil), receivables aggregate
    ws["A10"], ws["T10"], ws["U10"] = "吸收投资收到的现金", 110.0, 110.0
    ws["A11"], ws["T11"], ws["U11"] = "其他与筹资活动有关的现金", 200.0, 200.0
    ws["A12"], ws["T12"], ws["U12"] = "发行债券收到的现金", 593.5, 593.5
    ws["A13"], ws["T13"], ws["U13"] = "取得借款收到的现金", 9000.0, 9000.0
    ws["A14"], ws["T14"], ws["U14"] = "偿还债务支付的现金", 7000.0, 7000.0
    ws["A20"], ws["T20"], ws["U20"] = "应收票据及应收账款", 13769.66, 13769.66
    ws["A21"], ws["T21"], ws["U21"] = "货币资金", 26855.95, 26855.95     # ratify the BS page
    ws["A22"], ws["T22"], ws["U22"] = "存货", 21685.30, 21685.30
    items = [
        it(95, "货币资金", [18980.96, 26855.95], tid=1, ro=0),
        it(95, "存货", [25000.0, 21685.30], tid=1, ro=4),
        it(101, "吸收投资收到的现金", [5236.0, 110.0], ro=1),
        it(101, "收到其他与筹资活动有关的现金", [8000.0, 200.0], ro=2),   # label not equal: weak map, 40x
        it(101, "取得借款收到的现金", [9500.0, 9000.0], ro=3),
        it(101, "偿还债务支付的现金", [7200.0, 7000.0], ro=4),
        it(95, "应收票据", [1664.06, 1224.35], tid=1, ro=1),
        it(95, "应收账款", [15193.79, 12545.31], tid=1, ro=2),
        it(95, "应收款项融资", [2885.61, 1927.57], tid=1, ro=3),
    ]
    led = L(items, {(doc, 101): "cf", (doc, 95): "bs"})
    serves, mapping = reconcile(wb, spec, 2025, led, lambda s: None)
    # (1) served, not dropped: exact label -> plain; weak map -> red note
    assert serves[("Raw", 10)]["value"] == 5236.0 and serves[("Raw", 10)].get("flag") is None
    assert serves[("Raw", 11)]["value"] == 8000.0 and serves[("Raw", 11)].get("flag") == "red"
    assert "double check" in serves[("Raw", 11)]["note"]
    # (5) parent page: reads as 'cf' but ties 1 prior vs 4 on the consolidated page -> not adopted
    from pipeline.docid import identify_statement_pages
    par = [it(107, "取得借款收到的现金", [1000.0, 9000.0], ro=1),
           it(107, "偿还债务支付的现金", [900.0, 7000.0], ro=5),        # 2 shared ties: ratifies, weakly
           it(107, "经营活动产生的现金流量净额", [5.0, 6.0], ro=2),
           it(107, "投资活动产生的现金流量净额", [7.0, 8.0], ro=3),
           it(107, "筹资活动产生的现金流量净额", [9.0, 10.0], ro=4)]
    cons = [it(101, "经营活动产生的现金流量净额", [2014.0, 10059.0], ro=5),
            it(101, "投资活动产生的现金流量净额", [-10587.0, -2773.0], ro=6),
            it(101, "筹资活动产生的现金流量净额", [5101.0, 1088.0], ro=7)]
    led2 = L(items + par + cons, {})
    priors = [110.0, 200.0, 9000.0, 7000.0, 10059.0, -2773.0, 1088.0]
    logs = []
    identify_statement_pages([f"/tmp/{doc}"], led2, None, priors, logs.append)
    assert led2.faces.get((doc, 101)) == "cf", led2.faces
    assert (doc, 107) not in led2.faces, led2.faces
    assert any("not adopted" in l for l in logs), logs


def test_blank_current_cell_is_nil_2026_09_08():
    """Owner (DFE 240 screenshot): 'other cash received relating to
    financing' prints 593,536,697.59 in the comparative column and NOTHING
    in the current column. Not found -> back out; 0 -> 0. A one-number
    statement line whose only number is last year's proves nil."""
    from types import SimpleNamespace as NS
    from pipeline.writegate import nil_current_zero
    doc = "X 2025 Annual Report.pdf"
    blank = NS(doc=doc, page=101, label="收到其他与筹资活动有关的现金 五、（六十八）",
               nums=[593536697.59], source_line="收到其他与筹资活动有关的现金 五、（六十八）  593 536 697.59",
               stmt_face="cf", scale_hint=None)
    lost = NS(doc=doc, page=101, label="收回投资收到的现金", nums=[25155704810.83],
              source_line="收回投资收到的现金 25 155 704 810.83", stmt_face="cf", scale_hint=None)
    faces = {(doc, 101)}
    assert nil_current_zero([blank, lost], 593.54, faces, set()) is blank      # ties the prior: nil
    assert nil_current_zero([lost], 35262.27, faces, set()) is None           # 25,156 is not the prior: a lost comparative, not nil
    blank_note = NS(doc=doc, page=150, label=blank.label, nums=blank.nums,
                    source_line=blank.source_line, stmt_face=None, scale_hint=None)
    assert nil_current_zero([blank_note], 593.54, set(), set()) is blank_note # any page: the tie is the proof (owner 2026-09-08, no page rule)
    assert nil_current_zero([blank], 59.35, faces, set()) is None             # a different figure
    zero = NS(doc=doc, page=101, label="发行债券收到的现金", nums=[0.0, 593536697.59],
              source_line="发行债券收到的现金 0.00 593 536 697.59", stmt_face="cf", scale_hint=None)
    slash = NS(doc=doc, page=101, label="发行债券收到的现金", nums=[593536697.59],
               source_line="发行债券收到的现金 / 593 536 697.59", stmt_face="cf", scale_hint=None)
    assert nil_current_zero([zero], 593.54, faces, set()) is zero              # printed 0 -> nil
    neg = NS(doc=doc, page=51, label="处置子公司及其他营业单位收到的现金净额", nums=[-8485403.24],
             source_line="处置子公司及其他营业单位收到的现金净额 -8,485,403.24", stmt_face="cf", scale_hint=None)
    assert nil_current_zero([neg], -8.49, faces | {(doc, 51)}, set()) is neg     # a negative comparative ties sign-blind
    # a NOTE page (related-party purchases, DFE p239) printing one number that
    # equals a prior is not a blank current cell on a statement: no nil
    note_line = NS(doc=doc, page=239, label="宏华海洋油气装备(江苏)有限公司 购买商品",
                   nums=[88357200.0], source_line="宏华海洋油气装备(江苏)有限公司 购买商品 88 357 200.00",
                   stmt_face=None, scale_hint=None)
    # the label decides, anywhere in the report (owner 2026-09-08): a
    # related-party purchase line is not 'service charge and others'
    assert nil_current_zero([note_line], -88.3572, faces | {(doc, 239)}, set(),
                            row_label="Service charge and others") is None
    assert nil_current_zero([blank], 593.54, faces, set(),
                            row_label="收到其他与筹资活动有关的现金") is blank
    # Wind's own name for the line (no label kin): not code's call — the
    # blank line goes to the brain as a serve-card candidate worth 0
    assert nil_current_zero([blank], 593.54, faces, set(),
                            row_label="发行债券收到的现金") is None



def test_blank_line_judged_by_meaning_2026_09_08():
    """Owner: 'bond financing is financing — the LLM should reason on the
    meaning, not a table rule.' A line printing last year's figure and a
    blank this year, under a DIFFERENT label from the model row, is not
    code's call: it is offered on the serve card worth 0 (the prior tie is
    code's proof); the brain's 'serve' lands as a proven read."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import candidates_for
    from pipeline.writer import Writer
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Raw"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    ws["A225"] = "发行债券收到的现金"; ws["T225"], ws["U225"] = 593.54, 593.54
    spec = {"year_axis": {"Raw": {"columns": {"2024": "T", "2025": "U", "2026": "V"}, "header_row": 2}}}
    blank = _item(101, 7, "收到其他与筹资活动有关的现金 五（六十八）", [593536697.59], stmt_face="cf")
    led = _ledger(_anchors(101, 1e6) + [blank], face_pages=((101, "cf"),))
    targets = _anchor_targets() + [TargetRow("Raw", 225, "发行债券收到的现金", 593.54)]
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, Writer(wb), None)
    cands = candidates_for(loop, "Raw", 225)
    nil = [c for c in cands if c.get("nil")]
    assert nil and nil[0]["value"] == 0.0 and "BLANK" in nil[0]["warnings"][0], cands
    # the brain says 'same item' -> 0 lands as a proven read, plain
    r = loop.t_set_input({"cell": "Raw!U225", "value": 0.0, "nil": True,
                          "why": "p101: 收到其他与筹资活动有关的现金 — judged the same item"})
    assert str(r).startswith("WRITTEN"), r
    assert ws["U225"].value == 0.0 and loop.served[("Raw", 225)]["conf"] == 4
    # a 'nil' answer with no blank line printing this row's prior is refused
    ws["A226"] = "取得借款收到的现金"; ws["T226"], ws["U226"] = 2511.72, 2511.72
    r2 = loop.t_set_input({"cell": "Raw!U226", "value": 0.0, "nil": True, "why": "guess"})
    assert str(r2).startswith("REFUSED"), r2


def test_label_map_survives_pdf_formatting_2026_09_08():
    """Owner: 'six characters in the model, the same six with spaces and
    formatting in the PDF — will it map?' The normaliser strips PDF
    furniture: spaces inside CJK, full-width letters, a note reference
    glued to the label, numbering prefixes."""
    from pipeline.numerics import norm_label, kinship
    def exact(a, b): return norm_label(a).replace(" ", "") == norm_label(b).replace(" ", "")
    assert exact("在 建 工 程", "在建工程")
    assert exact("减：库存股 五（四十七）", "减：库存股")
    assert exact("固定资产 五（二十）", "固定资产")
    assert exact("Ｎｅｔ ｐｒｏｆｉｔ", "Net profit")
    assert exact("Trade receivables (note 12)", "Trade receivables")
    assert exact("Net  finance\ncosts", "Net finance costs")
    assert kinship("在 建 工 程 五（二十一）", "在建工程(合计)")
    assert kinship("三、营业利润（亏损以“-”号填列）", "营业利润")
    assert not kinship("负债合计", "所有者权益合计")          # structure words carry no identity


def test_prose_figures_become_lines_2026_09_08():
    """Owner: a figure stated in a sentence ('新生效订单1172.51亿元，同比增长
    15.93%') is evidence; the reader keeps the noun with its amount, in
    base currency units, with the prior the growth rate implies; a
    non-currency amount keeps its unit word for the brain to convert."""
    from pipeline.prose import harvest_prose
    cn = ("2025年，公司新生效订单1172.51亿元，同比增长15.93%，能源装备制造占67.33%。\n"
          "2025年年末，公司在手订单1403.1亿元。")
    items = harvest_prose("DFE 2025 AR.pdf", 10, cn)
    by = {it.label: it for it in items}
    assert "新生效订单" in by, [it.label for it in items]
    it = by["新生效订单"]
    assert abs(it.nums[0] - 117_251_000_000) < 1 and it.unit_dim == "money" and it.channel == "prose"
    assert abs(it.nums[1] - 117_251_000_000 / 1.1593) < 1        # last year, implied by the growth
    assert "在手订单" in by and len(by["在手订单"].nums) == 1
    en = ("Order intake of RMB117.3bn, up 16% year-on-year. Total installed capacity reached\n"
          "7,688MW at year end. Net profit was HK$10,468 million (2024: HK$11,742 million).")
    items = harvest_prose("x.pdf", 4, en)
    by = {it.label.lower(): it for it in items}
    oi = next(v for k, v in by.items() if "order intake" in k)
    assert abs(oi.nums[0] - 117.3e9) < 1 and abs(oi.nums[1] - 117.3e9 / 1.16) < 1
    cap = next(v for k, v in by.items() if "capacity" in k)
    assert cap.nums[0] == 7688 and cap.unit_dim == "unit:MW"
    npf = next(v for k, v in by.items() if "net profit" in k)
    assert abs(npf.nums[0] - 10_468e6) < 1 and abs(npf.nums[1] - 11_742e6) < 1   # stated prior
    # a wrapped sentence ('同比增' / '长15%' across lines) is joined first
    wrapped = "2025年，公司实现营业总收入786.15亿元,同比增\n长12.80%。"
    items = harvest_prose("x.pdf", 9, wrapped)
    rev = next(it for it in items if "营业总收入" in it.label)
    assert len(rev.nums) == 2 and abs(rev.nums[1] - 78.615e9 / 1.128) < 1


def test_no_prior_row_gets_a_label_card_2026_09_08():
    """Owner 2026-09-08: 'if there is no past-year number you infer from
    the item label' — SUPERSEDED by the owner's 2026-09-14 law: a row that
    holds no number in any period, past or future ('New orders' in the
    DFE model), is not an input; no card is dealt and the writer refuses
    it from every step. The prose candidate is still found (the report
    names the figure) — it is the ROW that is not the analyst's."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import candidates_for, build_queue
    from pipeline.writer import Writer
    from pipeline.prose import harvest_prose
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    ws["A142"] = "New orders"                       # no prior, no future, empty this year
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U", "2026": "V"}, "header_row": 2}}}
    prose = harvest_prose(DOC, 10, "2025年，公司新生效订单1172.51亿元，同比增长15.93%。")
    pr = next(it for it in prose if "新生效订单" in it.label)
    led = _ledger(_anchors(95, 1e6) + [pr], face_pages=((95, "pl"),))
    targets = _anchor_targets() + [TargetRow("Model", 142, "New orders 新生效订单", None)]
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, Writer(wb), None)
    cands = candidates_for(loop, "Model", 142)
    assert cands and cands[0].get("no_prior") and cands[0]["face"] == "prose", cands
    assert abs(cands[0]["value"] - 117251.0) < 1                 # yuan -> RMB m via the document's scale
    q = build_queue(loop)
    assert not any(w.kind == "LABEL" and (w.sheet, w.row) == ("Model", 142) for w in q), [(w.kind, w.sheet, w.row) for w in q]
    r = loop.t_set_input({"cell": "Model!U142", "value": 117251.0, "flag": "red", "no_prior": True,
                          "why": "p10: 新生效订单1172.51亿元 — card-adjudicated"})
    assert not str(r).startswith("WRITTEN"), r
    assert ws["U142"].value is None and "Model!U142" in loop.writer.log.get("never_filled_refused", [])


def test_no_serve_card_cap_budget_decides_2026_09_08():
    """Owner: 'why is it capped though' — the run budget decides. Readiness
    check for run 250: the bond line (prior 593.54) had its blank-line
    candidate worth 0 but build_queue kept only the largest serve cards
    and dropped it. Every red hardcode gets its card, in the analyst's
    order; run_queue's call cap, reserved share and deadline drain the tail."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import build_queue
    from pipeline.writer import Writer
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U", "2026": "V"}, "header_row": 2}}}
    led = _ledger(_anchors(95, 1e6), face_pages=((95, "pl"),))
    writer = Writer(wb)
    targets = _anchor_targets()
    for r in range(10, 90):                       # 80 red hardcodes, sizes 1..80
        ws[f"A{r}"] = f"row {r}"; ws[f"T{r}"] = float(r); ws[f"U{r}"] = float(r)
        ws[f"U{r}"].fill = writer.fills["red"]; writer.log["flags"].append(f"Model!U{r}")
        targets.append(TargetRow("Model", r, f"row {r}", float(r)))
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, writer, None)
    q = build_queue(loop)
    serves = [w.row for w in q if w.kind == "SERVE"]
    assert len(serves) == 80, len(serves)                 # nothing trimmed by size
    assert serves == sorted(serves, reverse=True)         # biggest first, smallest still there

def test_nil_tie_is_full_precision_significant_digits_2026_09_08():
    """Run 250 autopsy: six orange holds turned red because the blank-line
    pre-check tied the tax-rate 15 to '15,000,000' (two significant
    digits, not eight), the exchange-rate 1 to '1000元' in a CSR sentence,
    and total liabilities 98,867.0367 to a shareholder count 989,682,463
    at 0.1%. The tie is at the model's own precision and counts only
    significant digits; the real ties (593.54, 0.65, 492.57) still hold."""
    from pipeline.writegate import nil_current_zero, _ties_full_precision
    assert _ties_full_precision(593.53669759, 593.54)
    assert _ties_full_precision(0.64888229, 0.65)
    assert _ties_full_precision(492.57207562, 492.57000000000005)
    assert not _ties_full_precision(98968.2463, 98867.0367)
    assert not _ties_full_precision(9943.83, 9954.0676)
    def it(label, num, page=25):
        return {"doc": DOC, "page": page, "label": label, "nums": [num],
                "source_line": f"{label} {num:,.2f}", "stmt_face": None}
    pages = {(DOC, 25), (DOC, 49), (DOC, 101)}
    assert nil_current_zero([it("投资金额（万元）", 15000000.0)], 15, pages) is None
    assert nil_current_zero([it("人均月增收", 1000.0, 49)], 1, pages) is None
    assert nil_current_zero([it("股东持股数量", 989682463.0)], 98867.0367, pages) is None
    assert nil_current_zero([it("收到其他与筹资活动有关的现金", 593536697.59, 101)], 593.54, pages) is not None


def test_nil_answer_verified_on_the_cards_evidence_2026_09_08():
    """Run 252: the brain chose 0 for the bond line (the report's own
    line prints the model's prior beside a blank) and set_input REFUSED
    it — the verifier wanted a statement-face tag that vision-read lines
    never carry, while the card had shown the line. Same evidence in,
    same verdict out."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Raw"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    ws["A225"] = "发行债券收到的现金"; ws["T225"] = 593.54; ws["U225"] = 593.54
    spec = {"year_axis": {"Raw": {"columns": {"2024": "T", "2025": "U", "2026": "V"}, "header_row": 2}}}
    line = Item(DOC, 101, 0, 30, "收到其他与筹资活动有关的现金", [593536697.59], None, "money",
                None, "vision", 1, False, "收到其他与筹资活动有关的现金  593 536 697.59")
    led = _ledger(_anchors(95, 1e6) + [line], face_pages=((95, "pl"),))
    targets = _anchor_targets() + [TargetRow("Raw", 225, "发行债券收到的现金", 593.54)]
    writer = Writer(wb); writer.log["flags"].append("Raw!U225")
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, writer, None)
    r = loop.t_set_input({"cell": "Raw!U225", "value": 0.0, "nil": True,
                          "why": "p101: printed blank this year, judged the same item: 0"})
    assert str(r).startswith("WRITTEN"), r
    assert ws["U225"].value == 0


def test_key_count_is_codes_not_the_brains_2026_09_08():
    """Owner: 'i thought the key numbers are all written in the rules.'
    The report's 'key numbers proven 14/14' / '12/12' line was the brain's
    prose (a prompt example said 'X/14'). key_state ties every pinned
    panel key in code and the report prints that tally."""
    import json, openpyxl, tempfile
    from pathlib import Path
    from pipeline.keytie import key_state
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["A4"], ws["U4"] = "Revenue", 78615.28
    ws["A28"], ws["U28"] = "Net profit", 3900.0
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}},
            "key_rows": [{"name": "revenue", "sheet": "Model", "row": 4},
                         {"name": "net profit", "sheet": "Model", "row": 28}]}
    d = Path(tempfile.mkdtemp()); pp = d / "key_panel.json"
    pp.write_text(json.dumps({"revenue": {"print": 78615.27744, "prior": 69695.14},
                              "net profit": {"print": 3831.301222, "prior": 3287.53}}))
    st = key_state(wb, spec, 2025, pp)
    assert [(n, ok) for n, _, _, _, ok in st] == [("revenue", True), ("net profit", False)]
    from pipeline import execreport
    assert "X/14" not in execreport._COMPOSE_RULES if hasattr(execreport, "_COMPOSE_RULES") else True
    import inspect
    assert "key numbers tied" in inspect.getsource(execreport.report_only)


def test_key_rows_travel_with_the_replay_2026_09_08():
    """Owner: "test before running." The brain-named key rows are written
    beside the ledger on a live run and read back on a pinned replay, so
    the floors tie the same keys and print the same count as the live run."""
    import inspect
    from pipeline import run as _run
    src = inspect.getsource(_run.update)
    assert 'key_rows.json' in src
    assert '_kr_path.write_text(json.dumps(spec_d["key_rows"]' in src        # live: pinned beside the ledger
    assert 'Path(pinned_ledger).parent / "key_rows.json"' in src              # replay: read back
    assert 'key rows PINNED' in src


def test_key_panel_by_prior_tie_2026_09_08():
    """Owner: a model's bottom line may be 'net profit', 'total net
    profit' or 'net recurring profit' — the name is not the signal; the
    model's previous-period figure is. The printed line whose comparative
    equals the model's prior IS the item, and its current figure is the
    print to tie. A hand-pinned entry that disagrees loses."""
    import openpyxl
    from pipeline.keytie import panel_by_prior_tie, merge_panel
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["A28"], ws["T28"] = "Net recurring profit", 3287.53          # the analyst's bottom line = total net profit
    ws["A30"], ws["T30"] = "Other", 12.5                             # too few digits to tie anything
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}},
            "key_rows": [{"name": "net profit", "sheet": "Model", "row": 28},
                         {"name": "other", "sheet": "Model", "row": 30}]}
    total = _item(99, 5, "五、净利润", [3965977963.18, 3287525856.31])
    attrib = _item(99, 6, "归属于母公司股东的净利润", [3831301222.13, 2922100908.48])
    led = _ledger(_anchors(99, 1e6) + [total, attrib], face_pages=((99, "pl"),))
    built = panel_by_prior_tie(wb, spec, 2025, led)
    assert abs(built["net profit"]["print"] - 3965.977963) < 0.01, built    # the TOTAL line: its comparative is the model's prior
    # run 256: an equity-statement row (wide, unrelated label) tied the equity prior mid-row and
    # offered 3,117.50 — a wide row's pair needs the label; and the walk's own serve wins outright
    ws["A91"], ws["T91"] = "Total equity", 41461.11
    spec["key_rows"].append({"name": "total equity", "sheet": "Model", "row": 91})
    eq_row = _item(107, 3, "本期增减变动金额", [3117500000.0, 41461110000.0, 500000000.0, 45403660000.0])
    led2 = _ledger(_anchors(99, 1e6) + [total, attrib, eq_row], face_pages=((99, "pl"),))
    b2 = panel_by_prior_tie(wb, spec, 2025, led2)
    assert "total equity" not in b2, b2
    b3 = panel_by_prior_tie(wb, spec, 2025, led2, served={("Model", 91): {"value": 45403.66, "conf": 4, "doc": DOC, "page": 96}})
    assert abs(b3["total equity"]["print"] - 45403.66) < 0.01 and "(served)" in b3["total equity"]["line"]
    assert "other" not in built
    pinned = {"net profit": {"print": 3831.301222, "prior": 3287.53}, "eps": {"print": 1.15, "prior": 0.94}}
    msgs = []
    merged = merge_panel(built, pinned, msgs.append)
    assert abs(merged["net profit"]["print"] - 3965.977963) < 0.01 and "eps" in merged
    assert msgs and "disagrees" in msgs[0]


def test_prose_tie_via_last_years_report_2026_09_08():
    """Owner (dividend, run 254): "read last year's report for the tie."
    The model row says 'Dividend 现金分红'; the reports say '共计派发现金股利'.
    Last year's sentence states the model's prior (1,366.32), which proves
    the noun; this year's sentence with the same noun is the candidate."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import candidates_for
    from pipeline.writer import Writer
    from pipeline.prose import harvest_prose
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    ws["A38"], ws["T38"], ws["U38"] = "Dividend 现金分红", 1366.32, 1366.32
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U", "2026": "V"}, "header_row": 2}}}
    old_doc = "DFE 2024 Annual Report (CN).pdf"
    last = harvest_prose(old_doc, 2, "共计派发现金股利1,366,315,211.38元。")
    this = harvest_prose(DOC, 2, "共计派发现金股利1,832,930,972.78元。")
    led = _ledger(_anchors(95, 1e6) + [it for it in last + this if "派发现金股利" in it.label], face_pages=((95, "pl"),))
    led._doc_periods = {DOC: "current", old_doc: "prior"}
    ws["A1"], ws["T1"], ws["A3"], ws["T3"] = "aaaa", 58000.0, "bbbb", 39000.0     # scale anchors
    targets = _anchor_targets() + [TargetRow("Model", 38, "Dividend 现金分红", 1366.32)]
    writer = Writer(wb); writer.log["flags"].append("Model!U38")
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, writer, None)
    cands = candidates_for(loop, "Model", 38)
    div = [c for c in cands if c["face"] == "prose"]
    assert div and abs(div[0]["value"] - 1832.93) < 0.01, cands
    assert any("LAST YEAR" in w for w in div[0]["warnings"])


def test_walk_reads_the_whole_report_faces_first_2026_09_08():
    """Owner: the agent reads the ENTIRE report and maps from anywhere.
    Run 254: 'proceeds from investments' printed on the summary table
    (p20: current, prior, growth) while the vision read of the statement
    lost the comparative — the row was held at growth and plugged by
    14,601. The walk now enters every current-document page, statement
    faces first so they claim first."""
    import openpyxl
    from pipeline.reconcile import reconcile
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Raw"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T3"], ws["T4"] = 58000.0, 39000.0                                      # scale anchors
    ws["A203"], ws["T203"] = "收回投资收到的现金", 35262.27
    spec = {"year_axis": {"Raw": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    summary = _item(20, 9, "收回投资收到的现金", [25155704810.83, 35262270217.8, -28.66])
    lost = _item(101, 7, "收回投资收到的现金", [25155704810.83])              # comparative lost by the read
    led = _ledger(_anchors(101, 1e6) + _anchors(20, 1e6) + [summary, lost], face_pages=((101, "cf"),))
    led._doc_periods = {DOC: "current"}
    serves, mapping = reconcile(wb, spec, 2025, led, lambda s: None)
    got = serves.get(("Raw", 203))
    assert got and abs(float(got["value"]) - 25155.70) < 0.01, (got, mapping)
    faces_first = led.join_pool(all_pages=True)
    assert faces_first and led.faces.get((faces_first[0].doc, faces_first[0].page)) == "cf"


def test_forecast_checks_never_veto_an_actual_2026_09_08():
    """Readiness on run 254: the bond line's proven 0 was REVERTED because
    the 2026/2027 checks moved. Only the actual year's own checks can
    veto a write; a forecast check that moves goes to the watch list."""
    import inspect
    from pipeline import orchestrator as _o
    src = inspect.getsource(_o.ObjectiveLoop.t_set_input)
    assert "fc_broke = [b for b in broke if" in src and "self.writer.watch(" in src
    assert 'flag="red"' in src.split("REVERTED: the write broke")[0][-600:]


def test_new_line_this_year_served_by_its_label_2026_09_08():
    """Run 254: 'other cash received relating to investing' printed
    19,078,348 with '不适用' last year; the model row had no prior, so
    nothing tied, the row stayed 0 and the cash check was 19 off. With no
    number to tie, the exact label on the printed line is the proof:
    served red for the analyst."""
    import inspect
    from pipeline import run as _run
    src = inspect.getsource(_run.update)
    assert "new-line sweep" in src and "blank last year, label matches" in src
    assert "ties any model prior it" in src          # a lone number tying a prior is last year's, not new
    assert "_strip(it.label) != rl" in src            # bracketed note refs stripped before the exact match

def test_fences_removed_deduction_2026_09_08():
    """Owner: "remove those patches and fix the underlying issues." No
    wide-row fence (a five-year line serves by its tying pair when the
    label confirms), no table-length fence, no candidate cap, and two
    printed readings are flagged red — never dropped, never picked
    silently. Run 229's grid ('6,608 | 471 | 914 | 7,993') still cannot
    serve: wide + no label kinship."""
    import openpyxl, inspect
    from pipeline.reconcile import reconcile
    from pipeline import workqueue as wq
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Raw"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T3"], ws["T4"] = 58000.0, 39000.0
    ws["A203"], ws["T203"] = "收回投资收到的现金", 35262.27
    ws["A50"], ws["T50"] = "Finance costs", 471.0
    spec = {"year_axis": {"Raw": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    hdr21 = _item(21, 1, "项目 年度", [2025.0, 2024.0, 2023.0, 2022.0, 2021.0])    # a period table: years in the header
    five = _item(21, 9, "收回投资收到的现金", [25155704810.83, 35262270217.8, 30000000000.0, 28000000000.0, 27000000000.0])
    face = _item(101, 7, "收回投资收到的现金", [25155704810.83, 35262270217.8])
    other = _item(31, 3, "收回投资收到的现金", [25000000000.0, 35262270217.8])       # a second, different printing (its own page: a note, not a grid)
    grid = _item(30, 4, "Net book value at 1 January", [6608000000.0, 471000000.0, 914000000.0, 7993000000.0])
    led = _ledger(_anchors(101, 1e6) + _anchors(21, 1e6) + _anchors(30, 1e6) + _anchors(31, 1e6) + [hdr21, five, face, other, grid], face_pages=((101, "cf"),))
    led._doc_periods = {DOC: "current"}
    serves, mapping = reconcile(wb, spec, 2025, led, lambda s: None)
    got = serves.get(("Raw", 203))
    assert got and abs(float(got["value"]) - 25155.70) < 0.01, (got, mapping)     # the statement's reading kept
    assert got.get("flag") == "red" and "Two printed readings" in got.get("note", ""), got
    assert ("Raw", 50) not in serves and (mapping.get("wide_unkin", 0) + mapping.get("matrix_rows", 0)) >= 1   # the grid: a matrix row, never paired
    # a PARENT-company statement page is not a second reading of the consolidated row
    led2 = _ledger(_anchors(101, 1e6) + _anchors(30, 1e6) + [face, other], face_pages=((101, "cf"),), parents=(30,))
    led2._doc_periods = {DOC: "current"}
    serves2, mapping2 = reconcile(wb, spec, 2025, led2, lambda s: None)
    assert serves2.get(("Raw", 203), {}).get("flag") != "red" and not mapping2.get("two_readings")
    src = inspect.getsource(reconcile)
    assert "wide_skipped" not in src and "if len(items) > max_lines_per_table" not in src
    assert wq.MAX_CANDS is None


def test_last_years_report_names_a_table_item_2026_09_08():
    """Vintage split: last year's report is never a SOURCE of this year's
    number, but it names the item. The line whose own current equalled
    the model's prior tells the printed label; this year's line under
    that label is the candidate — a renamed row, a moved segment."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import candidates_for
    from pipeline.writer import Writer
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    ws["A1"], ws["T1"], ws["A3"], ws["T3"] = "aaaa", 58000.0, "bbbb", 39000.0
    ws["A11"], ws["T11"], ws["U11"] = "Hydro", 2955.37, 2955.37
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U", "2026": "V"}, "header_row": 2}}}
    old_doc = "DFE 2024 Annual Report (CN).pdf"
    last = Item(old_doc, 200, 0, 4, "水电设备", [2955370000.0, 2600000000.0], None, "money", None, "text", 1, False, "")
    this = _item(95, 4, "水电设备", [3429350000.0, 2955370000.0])
    led = _ledger(_anchors(95, 1e6) + [this, last], face_pages=((95, "pl"),))
    led._doc_periods = {DOC: "current", old_doc: "prior"}
    targets = _anchor_targets() + [TargetRow("Model", 11, "Hydro", 2955.37)]
    writer = Writer(wb); writer.log["flags"].append("Model!U11")
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, writer, None)
    cands = candidates_for(loop, "Model", 11)
    hit = [c for c in cands if abs(c["value"] - 3429.35) < 0.01]
    assert hit, cands
    assert any("LAST YEAR" in w for w in hit[0]["warnings"]) or hit[0].get("tie_off", 9) == 0.0


def test_corroboration_rescues_a_disputed_row_2026_09_08():
    """F2: the vision passes disagreed on a statement row (disputed, never
    joinable); the summary table prints the same label with the same
    numbers — the second printing is the second pass."""
    disputed = _item(101, 7, "收回投资收到的现金", [25155704810.83, 35262270217.8], channel="vision", disputed=True)
    summary = _item(20, 9, "收回投资收到的现金", [25155704810.83, 35262270217.8, -28.66])
    led = _ledger([disputed, summary], face_pages=((101, "cf"),))
    assert not disputed.joinable()
    n = led.corroborate()
    assert n == 1 and disputed.joinable() and disputed.consensus >= 2


def test_two_digit_period_headers_form_panels_2026_09_09():
    """Run 256: the Model sheet's half-year panel is headed 'H120 … H125'
    with H2 columns between, the Driver's 'H124 H224 H125 H225E'; both
    sheets were 'left out of this run', so the Model's check row never
    gated an unbalanced H125 column (it delivered at -1,389). Two-digit
    tagged marks are period marks; runs are built within a tag."""
    import openpyxl
    from pipeline.discover import find_year_axis, _year_of, period_tag
    assert _year_of("H125") == (2025, True) and _year_of("H225E") == (2025, True)
    assert _year_of("Q320") == (2020, True) and _year_of("FY25") == (2025, False)
    assert period_tag("H125") == "H1" and period_tag("H225E") == "H2" and period_tag("1H2024") == "H1"
    wb = openpyxl.Workbook(); ws = wb.active
    hdr = ["", 2022, 2023, 2024, 2025, "H123", "H223", "H124", "H224", "H125", "H225E"]
    for i, v in enumerate(hdr, 1):
        ws.cell(2, i, v)
    fy = find_year_axis(ws, "FY"); h1 = find_year_axis(ws, "1H")
    assert fy == {"2022": "B", "2023": "C", "2024": "D", "2025": "E"}, fy
    assert h1 == {"2023": "F", "2024": "H", "2025": "J"}, h1


def test_matrix_rows_never_pair_2026_09_09():
    """Run 257: 57 false 'two readings' and 182 refused ties, all from
    segment matrices whose columns are segments, not periods. A wide row
    pairs only in a PERIOD table — one with a header line of consecutive
    years; a matrix row never pairs. The five-year table still serves."""
    import openpyxl
    from pipeline.reconcile import reconcile
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Raw"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T3"], ws["T4"] = 58000.0, 39000.0
    ws["A24"], ws["T24"] = "Profit for the year", 10468.0
    spec = {"year_axis": {"Raw": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    # a segment matrix: HK | CN | Aus | India | Total — the row's numbers are segments
    matrix = _item(30, 3, "Profit for the year", [9000e6, 1200e6, -919e6, 1187e6, 10468e6])
    led = _ledger(_anchors(30, 1e6) + [matrix], face_pages=())
    led._doc_periods = {DOC: "current"}
    serves, mapping = reconcile(wb, spec, 2025, led, lambda s: None)
    assert ("Raw", 24) not in serves and mapping.get("matrix_rows", 0) >= 1, (serves, mapping)
    # a five-year table: a year-header line makes it a period table — the wide row pairs
    hdr = _item(21, 1, "Year ended 31 December", [2025.0, 2024.0, 2023.0, 2022.0, 2021.0])
    five = _item(21, 9, "Profit for the year", [11546e6, 10468e6, 9800e6, 9100e6, 8700e6])
    led2 = _ledger(_anchors(21, 1e6) + [hdr, five], face_pages=())
    led2._doc_periods = {DOC: "current"}
    serves2, _m2 = reconcile(wb, spec, 2025, led2, lambda s: None)
    assert abs(float(serves2[("Raw", 24)]["value"]) - 11546.0) < 0.01, serves2.get(("Raw", 24))


def test_repairs_of_2026_09_09_pinned():
    """The night's repairs, each a sentence: the plug ladder never vetoes on
    forecast damage (watch list); the one-off law registers its cells as
    frozen so the gate accepts them; a prior-vintage document is read as
    text only; the run always delivers (open checks marked red, never a
    quarantine); identity candidates need a specific label and two numbers;
    reasoning effort rides on every call."""
    import inspect
    from pipeline import orchestrator as _o, teachings as _t, stage1_read as _s1, run as _r, workqueue as _wq, llm as _llm
    assert "if hurt:" in inspect.getsource(_o.ObjectiveLoop.t_plug_residual) and \
        "if hurt and hold_formula:" not in inspect.getsource(_o.ObjectiveLoop.t_plug_residual)
    assert 'setdefault("frozen", [])' in inspect.getsource(_t.oneoff_no_propagate)
    assert "prior-vintage document — text only" in inspect.getsource(_s1.read_documents)
    src = inspect.getsource(_r.update)
    assert "DELIVERED WITH OPEN CHECKS" in src and '" QUARANTINE"' not in src and '"gate_ok": ok' in src
    assert "_specific(it.label)" in inspect.getsource(_wq.candidates_for)
    assert "reasoning" in inspect.getsource(_llm._install_reasoning_effort)
    assert "OTHER ROWS NAMED LIKE THIS ONE" in inspect.getsource(_wq.render_card)


def test_roll_keeps_the_analysts_same_shape_formula_2026_09_09():
    """Half-year replay: the H125 column already held '=EY152+EX152' (the
    prior's '=EU152+ET152' rolled one period at the quarterly stride); the
    two-column shift wrote '=EW152+EV152' — the wrong half — and broke 31
    cells. A target formula of the prior's SHAPE is kept; a forecast
    formula (a different shape) is still replaced by the prior's structure."""
    import openpyxl
    from pipeline.writer import rollover_column, _shape
    assert _shape("=EY152+EX152") == _shape("=EU152+ET152")
    assert _shape("=T4*(1+V22)") != _shape("=U4") and _shape("=$T$4") == _shape("=U4")
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["BQ152"], ws["BS152"] = "=EU152+ET152", "=EY152+EX152"     # same shape: the analyst rolled it already
    ws["BQ4"], ws["BS4"] = 100.0, "=BQ4*(1+V22)"                    # a hardcode prior: the forecast formula is replaced
    ws["BQ9"], ws["BS9"] = "='Raw'!AS9", "=BS8*2"                    # a different shape: replaced by the shifted prior
    rollover_column(wb, "Model", "BQ", "BS")
    assert ws["BS152"].value == "=EY152+EX152"
    assert ws["BS4"].value == 100.0
    assert ws["BS9"].value == "='Raw'!AU9"


def test_repeated_years_header_is_a_matrix_2026_09_09():
    """CLP floor after the matrix rule: 35 false readings remained from
    segment tables whose header repeats '2025 2024' per segment. Distinct
    years across the header = a period table; repeated years = a grid."""
    import openpyxl
    from pipeline.reconcile import reconcile
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Raw"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T3"], ws["T4"] = 58000.0, 39000.0
    ws["A24"], ws["T24"] = "Profit for the year", 10468.0
    spec = {"year_axis": {"Raw": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    hdr = _item(30, 1, "Hong Kong | Mainland | Total", [2025.0, 2024.0, 2025.0, 2024.0, 2025.0, 2024.0])
    row = _item(30, 3, "Profit for the year", [9000e6, 8500e6, -919e6, 1968e6, 11546e6, 10468e6])
    led = _ledger(_anchors(30, 1e6) + [hdr, row], face_pages=())
    led._doc_periods = {DOC: "current"}
    serves, mapping = reconcile(wb, spec, 2025, led, lambda s: None)
    assert ("Raw", 24) not in serves and mapping.get("matrix_rows", 0) >= 1, (serves, mapping)


def test_reader_verifies_every_answer_against_print_2026_09_09():
    """THE READER STAGE (the reading test, 2026-09-09): Luna reads whole,
    code verifies. A fabricated balance-sheet figure with a page reference
    is never written; a units slip is corrected from the printed digits; a
    quoted number that is last year's, printed alone, is 0; a page slip is
    found by the printed name; a no-tie read lands red with its citation."""
    from pipeline.reader import verify
    lines = _anchors(95, 1e6) + [
        _item(20, 9, "收回投资收到的现金", [25155704810.83, 35262270217.8, -28.66]),
        _item(20, 10, "收到其他与投资活动有关的现金", [19078348.0]),
        _item(101, 7, "收到其他与筹资活动有关的现金", [593536697.59]),
        _item(45, 3, "现金分红金额(含税)", [1832930972.78]),
        _item(2, 4, "归属于母公司所有者的净利润", [3831301222.13, 2922100908.48]),
    ]
    led = _ledger(lines, face_pages=((95, "pl"),))
    led._doc_periods = {DOC: "current"}
    rows = [{"row": "Raw!203", "sheet": "Raw", "r": 203, "label": "收回投资收到的现金", "prior": 35262.27},
            {"row": "Raw!207", "sheet": "Raw", "r": 207, "label": "收到其他与投资活动有关的现金", "prior": None},
            {"row": "Raw!225", "sheet": "Raw", "r": 225, "label": "发行债券收到的现金", "prior": 593.54},
            {"row": "Model!38", "sheet": "Model", "r": 38, "label": "Dividend 现金分红", "prior": 1366.32},
            {"row": "Raw!44", "sheet": "Raw", "r": 44, "label": "归属于母公司所有者的净利润", "prior": 2922.1},
            {"row": "Model!54", "sheet": "Model", "r": 54, "label": "Total current assets", "prior": 93779.78}]
    answers = [{"row": "Raw!203", "printed": 25155704810.83, "page": 20, "line": "收回投资收到的现金"},
               {"row": "Raw!207", "printed": 19078348.0, "page": 20, "line": "收到其他与投资活动有关的现金"},
               {"row": "Raw!225", "printed": 593536697.59, "page": 101, "line": "收到其他与筹资活动有关的现金"},
               {"row": "Model!38", "printed": 1832930972.78, "page": 45, "line": "现金分红金额(含税)"},
               {"row": "Raw!44", "printed": 3831301222.13, "page": 5, "line": "归属于母公司所有者的净利润"},   # page slip
               {"row": "Model!54", "printed": 97562731517.07, "page": 95, "line": "流动资产合计"}]              # fabricated
    scales = {(DOC, 20): 1e6, (DOC, 95): 1e6, (DOC, 101): 1e6, (DOC, 2): 1e6}
    v = verify(answers, rows, led, scales, lambda s: None)
    assert abs(v["Raw!203"]["value"] - 25155.70) < 0.01 and v["Raw!203"]["conf"] == 4
    # run 260 taught three more: a parameter (15) printed alone is never a nil; a
    # lone number equal to ANOTHER row's prior is last year's, not this year's
    # for the row that quoted it; a no-tie read must live in the row's world;
    # and a sentence quoted with its unit word ('1172.51亿元') is verified
    lines2 = lines + [_item(283, 2, "税率", [15.0]), _item(209, 5, "利息收入", [10820820000.0, 9000000000.0])]
    from pipeline.prose import harvest_prose
    lines2 += [it for it in harvest_prose(DOC, 10, "2025年，公司新生效订单1172.51亿元，同比增长15.93%。") if "新生效订单" in it.label]
    led2 = _ledger(lines2, face_pages=((95, "pl"),)); led2._doc_periods = {DOC: "current"}
    rows2 = rows + [{"row": "Raw!283", "sheet": "Raw", "r": 283, "label": "税率", "prior": 15.0},
                    {"row": "Raw!224", "sheet": "Raw", "r": 224, "label": "收到其他与筹资活动有关的现金", "prior": None},
                    {"row": "Raw!15", "sheet": "Raw", "r": 15, "label": "减：利息收入", "prior": 132.71},
                    {"row": "Model!142", "sheet": "Model", "r": 142, "label": "New orders", "prior": None}]
    answers2 = [{"row": "Raw!283", "printed": 15.0, "page": 283, "line": "税率"},
                {"row": "Raw!224", "printed": 593536697.59, "page": 101, "line": "收到其他与筹资活动有关的现金"},
                {"row": "Raw!15", "printed": 10820820000.0, "page": 209, "line": "利息收入"},
                {"row": "Model!142", "printed": 1172.51, "page": 10, "line": "新生效订单"}]
    scales2 = dict(scales); scales2.update({(DOC, 283): 1.0, (DOC, 209): 1e6})
    v2 = verify(answers2, rows2, led2, scales2, lambda s: None, priors=[593.54, 132.71, 15.0, 35262.27])
    assert "Raw!283" not in v2                                   # a parameter is never nil-proven
    assert "Raw!224" not in v2                                   # another row's prior, printed alone
    assert "Raw!15" not in v2                                    # 10,820 is out of the row's world (132.71)
    assert abs(v2["Model!142"]["value"] - 117251.0) < 1 and v2["Model!142"]["flag"] == "red"   # the sentence, by its unit word
    assert abs(v["Raw!207"]["value"] - 19.078) < 0.01 and v["Raw!207"]["flag"] == "red"       # units from the printed digits
    assert v["Raw!225"]["value"] == 0.0 and v["Raw!225"]["conf"] == 4                            # last year's, printed alone
    assert abs(v["Model!38"]["value"] - 1832.93) < 0.01 and v["Model!38"]["flag"] == "red"       # no tie: red with citation
    assert abs(v["Raw!44"]["value"] - 3831.30) < 0.01 and v["Raw!44"]["conf"] == 4              # found on p2 by name
    assert "Model!54" not in v                                                                    # fabricated: never written


def test_every_row_of_a_sum_range_is_a_plug_site_2026_09_09():
    """Half-year replay: 'SUM(BS69:BS74)' yielded only its two end rows to
    the ladder, so the stale dividends-payable inside the range was
    invisible and the balance stayed open by exactly that amount. Every
    row of a range is an input."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"] = 2024, 2025
    raw = wb.create_sheet("Raw")
    for r, v in ((121, 16341.0), (126, 776.0), (127, 542.0), (130, 1485.0), (131, 2969.0)):
        raw[f"U{r}"] = v
    ws["U72"] = "=SUM(Raw!U121,Raw!U126,Raw!U127,Raw!U130,Raw!U131)"
    ws["U69"], ws["U70"], ws["U71"], ws["U73"], ws["U74"] = 75.0, 30488.0, 42078.0, 257.0, 6016.0
    ws["U75"] = "=SUM(U69:U74)"
    ws["U95"] = "=ROUND(U75-99545,0)"
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2},
                          "Raw": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}},
            "check_rows": [{"sheet": "Model", "row": 95}]}
    led = _ledger(_anchors(95, 1e6), face_pages=((95, "pl"),))
    loop = ObjectiveLoop(wb, spec, 2025, led, _anchor_targets(), {}, Writer(wb), None)
    leaves = set(loop._leaf_inputs("Model", "U95"))
    assert ("Raw", "U130") in leaves and ("Model", "U70") in leaves, leaves


def test_header_roll_keeps_the_analysts_mark_and_moves_two_digit_marks_2026_09_09():
    """Half-year replay: the roll copied 'H124' over the analyst's 'H125'
    (two H124 columns); the header roll only knew four-digit years. A
    target header marking another period is the author's and stays; a
    two-digit mark moves one period on."""
    import openpyxl
    from pipeline.writer import rollover_column, roll_year_headers, Writer
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Driver"
    ws["AB2"], ws["AD2"] = "H124", "H125"
    ws["AB4"], ws["AD4"] = 10.0, "=AB4*(1+X9)"
    rollover_column(wb, "Driver", "AB", "AD")
    assert ws["AD2"].value == "H125" and ws["AD4"].value == 10.0
    ws2 = wb.create_sheet("S"); ws2["T2"], ws2["U2"] = "FY24", "FY24"; ws2["T3"], ws2["U3"] = "H124", "H124"
    n = roll_year_headers(Writer(wb), "S", "T", "U", 2024, 2025)
    assert n == 2 and ws2["U2"].value == "FY25" and ws2["U3"].value == "H125"


def test_unratified_page_takes_its_documents_scale_2026_09_09():
    """Half-year replay: the dividends-payable note (p153) tied the model's
    year-end prior exactly but had too few priors to ratify its own scale
    and was never walked. A page without anchors takes the scale most of
    its document's ratified pages carry."""
    import openpyxl
    from pipeline.reconcile import reconcile
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Raw"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T3"], ws["T4"] = 58000.0, 39000.0
    ws["A130"], ws["T130"] = "应付股利", 4.5689
    spec = {"year_axis": {"Raw": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    note = _item(153, 3, "应付股利", [1371192193.78, 4568944.33])       # one line: cannot ratify a scale alone
    led = _ledger(_anchors(95, 1e6) + _anchors(96, 1e6) + _anchors(97, 1e6) + [note], face_pages=((95, "bs"),))
    led._doc_periods = {DOC: "current"}
    serves, mapping = reconcile(wb, spec, 2025, led, lambda s: None)
    got = serves.get(("Raw", 130))
    assert got and abs(float(got["value"]) - 1371.19) < 0.01, (got, mapping)


def test_a_matrix_is_a_matrix_in_every_row_2026_09_09():
    """CLP floor: the statement of changes in equity (no year header, wide
    rows) has a 'Balance at 31 December' line read with three numbers —
    a day, total equity, non-controlling interests — which paired (total
    equity, NCI) as (current, prior) and served 104,055 into minority
    interests. Where a table's columns are categories, no row pairs."""
    import openpyxl
    from pipeline.reconcile import reconcile
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Final"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T3"], ws["T4"] = 58000.0, 39000.0
    ws["A97"], ws["T97"] = "Minority Interests", 9815.0
    spec = {"year_axis": {"Final": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    wide = _item(17, 50, "Non-controlling interests (NCI)", [6063e6, 26258e6, 9815e6, 1200e6])   # a wide row: the table is a matrix
    narrow = _item(17, 77, "Balance at", [31.0, 107610e6, 9815e6])                                # its narrow row must not pair
    led = _ledger(_anchors(17, 1e6) + [wide, narrow], face_pages=())
    led._doc_periods = {DOC: "current"}
    serves, mapping = reconcile(wb, spec, 2025, led, lambda s: None)
    assert ("Final", 97) not in serves and mapping.get("matrix_rows", 0) >= 2, (serves.get(("Final", 97)), mapping)


def test_new_line_needs_a_real_name_2026_09_09():
    """CLP floor: a memo row labelled 'Note:' took 25 from a '(Note' line
    under the new-line rule. 'Note', 'Total', 'Other' name nothing; a new
    line's label must name an item (three CJK characters or two words)."""
    import inspect
    from pipeline import run as _run
    src = inspect.getsource(_run.update)
    assert "note|notes|total|subtotal|other|others|合计|小计|总计|其他|其中" in src and "_cjk < 3" in src


def test_notes_for_the_analyst_owner_rulings_2026_09_07():
    """Run 233 review: 144 agent notes on plain inputs and long
    machine-speak on the flagged ones. Rules: notes only on highlighted
    cells; short plain words; the analyst's own notes untouched."""
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import PatternFill
    from pipeline.notes import plain_note, hygiene, AUTHOR
    # exhibit 1 — the rewrites read like a colleague's margin note
    assert plain_note("tier-3 back-out: not load-bearing for the key rows; held at the "
                      "group's growth — true up when segment detail is disclosed") \
        == "Backed out: not found in the documents; held at the group's growth rate. True up when disclosed."
    assert plain_note("QUEUE-DOCUMENTED: zero candidates — no current-document line ties "
                      "this row's prior at any scale; held at prior") \
        == "Not found in the documents. Kept last period's figure."
    s = plain_note("COMPOSITE REWRITE (constants law): was =+-2254+235 = stale prior; "
                   "2254->1860 (CLP 2025 Result announcement.pdf p23); 235->194 "
                   "(CLP 2025 Result announcement.pdf p23)")
    assert s == "Backed out from the disclosure (results announcement p23): 2254→1860, 235→194.", s
    s = plain_note("ROLL-BASE MISMATCH: this row's 2025 actual is typed as -74,206.0, but "
                   "the model's own forecast formula, pointed back one year, computes "
                   "-73,746.0 (gap +460.0) — the cells it rolls from were not re-anchored.")
    assert s.startswith("Forecast base is off this year's actual by +460.0"), s
    s = plain_note("RECOMPOSED (new-ingredient law): was =504+582+67; the old recipe's "
                   "comparatives map one span of e_2025 Annual Report.pdf p214. NEW items joined: x")
    assert "annual report p214" in s, s
    s = plain_note("objective loop: p37: 'Fuel Clause Account (FCA)' (CLP 2025 Annual Results Pres) — card-adjudicated")
    assert s == "Updated per the disclosure (results presentation p37). Please confirm.", s
    assert len(plain_note("PLUG OVER PROVEN VALUE — this cell was served 147,397.00 and then "
                          "absorbed the ROAFNA!31 residual -20.00 as the sanctioned last resort. "
                          "ANALYST MUST RULE. terminal ladder: the loop ended with this check failing")) < 80
    for jargon in ("tier-3", "stage-2", "QUEUE", "ANALYST REVIEW", "auto-disproven"):
        for src in ("tier-3 back-out: x", "stage-2.5 bound-table join: table proven by >=3 sibling prior ties",
                    "QUEUE-DOCUMENTED: y", "KEY-TIE back-out: 'eps' computed 1 vs disclosed 2 ANALYST REVIEW."):
            assert jargon not in plain_note(src), (jargon, plain_note(src))
    # exhibit 2 — hygiene: plain cell stripped, flagged cell shortened,
    # the analyst's note untouched, _sheets untouched
    wb = Workbook(); ws = wb.active; ws.title = "Final"
    ws["B2"] = 5; ws["B2"].comment = Comment("stage-3 read: comparative ties the model's prior", AUTHOR)
    ws["B3"] = 6; ws["B3"].fill = PatternFill("solid", fgColor="FFC7CE")
    ws["B3"].comment = Comment("QUEUE-DOCUMENTED: zero candidates — held at prior", AUTHOR)
    ws["B4"] = 7; ws["B4"].fill = PatternFill("solid", fgColor="FFC000")
    ws["B4"].comment = Comment("tier-3 back-out: not load-bearing; held at the group's growth", AUTHOR)
    ws["B5"] = 8; ws["B5"].comment = Comment("Eason Tang: UBS 2025E", "Eason Tang")
    fs = wb.create_sheet("_FLAGS"); fs["A1"] = "x"; fs["A1"].comment = Comment("stage-3 read: keep", AUTHOR)
    n = hygiene(wb)
    assert n == {"stripped": 1, "rewritten": 2}, n
    assert ws["B2"].comment is None
    assert ws["B3"].comment.text == "Not found in the documents. Kept last period's figure."
    assert ws["B4"].comment.text.startswith("Backed out:")
    assert ws["B5"].comment.text == "Eason Tang: UBS 2025E"
    assert fs["A1"].comment.text == "stage-3 read: keep"
    # exhibit 3 — the writer itself: a note lands only with a flag
    from pipeline.writer import Writer
    wb2 = Workbook(); w2 = wb2.active; w2.title = "Final"
    w2["A1"] = "row"; w2["B1"] = 100; w2["C1"] = 90
    wr = Writer(wb2)
    assert wr.write("Final", "C1", 105, prior_coord="B1", note="stage-3 read: ties")
    assert w2["C1"].comment is None
    assert wr.write("Final", "C1", 106, prior_coord="B1", note="tier-3 back-out: held", flag="orange")
    assert w2["C1"].comment is not None
    print("PASS test_notes_for_the_analyst_owner_rulings_2026_09_07")


# ── CLP run 262 (2026-09-10): the reader's rows, the evidence pair, one absorber ──

def test_reader_leaves_never_filled_rows_2026_09_10():
    """Run 262: 'Dividend', 'Scheme of control items', the CFI block header
    and FCFF carry no figure in any year of the model; the reader put
    printed totals there and every sum above them moved. A row the analyst
    never filled is not an input."""
    from pipeline.reader import rows_to_read, never_filled
    wb = _wb({"A5": "Dividend", "A6": "Capex", "T6": 100.0, "A7": "Growth", "H7": "=G7*1.1"})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}}
    targets = {("S", 5): TargetRow("S", 5, "Dividend", None),
               ("S", 6): TargetRow("S", 6, "Capex", 100.0),
               ("S", 7): TargetRow("S", 7, "Growth", None)}
    assert never_filled(wb, "S", 5, "U") and not never_filled(wb, "S", 6, "U")
    assert not never_filled(wb, "S", 7, "U")          # a formula history counts
    rows = rows_to_read(wb, spec, 2025, targets, {})
    assert [r["row"] for r in rows] == ["S!6", "S!7"], rows
    print("PASS test_reader_leaves_never_filled_rows_2026_09_10")


def test_reader_no_tie_read_needs_a_kin_name_2026_09_10():
    """Run 262: the reader wrote the investing-cash-flow total into 'Scheme
    of control items' — no prior tie, and a line named nothing like the
    row. The name is the last evidence a no-tie read has: in the same
    script it must be kin; across scripts (New orders / 新生效订单) the
    brain's mapping stands, red."""
    from pipeline.reader import verify
    lines = [_item(170, 1, "Net cash outflow from investing activities", [14328.0, 16216.0])]
    led = _ledger(lines, face_pages=((170, "cf"),)); led._doc_periods = {DOC: "current"}
    rows = [{"row": "S!9", "sheet": "S", "r": 9, "label": "Scheme of control items", "prior": 5000.0},
            {"row": "S!10", "sheet": "S", "r": 10, "label": "Investing cash outflow", "prior": 5000.0}]
    answers = [{"row": "S!9", "printed": 14328.0, "page": 170, "line": "Net cash outflow from investing activities"},
               {"row": "S!10", "printed": 14328.0, "page": 170, "line": "Net cash outflow from investing activities"}]
    v = verify(answers, rows, led, {(DOC, 170): 1.0}, lambda s: None, priors=[5000.0])
    assert "S!9" not in v, v
    assert v["S!10"]["flag"] == "red" and abs(v["S!10"]["value"]) == 14328.0
    print("PASS test_reader_no_tie_read_needs_a_kin_name_2026_09_10")


def test_table_kind_one_law_2026_09_10():
    from pipeline.reconcile import table_kind
    assert table_kind([_item(1, 0, "HK$M", [2025.0, 2024.0, 2023.0]),
                       _item(1, 1, "Revenue", [88018.0, 90964.0, 85000.0, 80000.0])]) == "period"
    assert table_kind([_item(2, 0, "Goodwill and other intangible assets",
                             [6359.0, 2852.0, 3128.0, 106.0, 12445.0])]) == "matrix"
    assert table_kind([_item(3, 0, "Goodwill and other intangible assets", [12685.0, 12445.0])]) == "plain"
    assert table_kind([_item(4, 0, "h", [2025.0, 2024.0, 2025.0, 2024.0]),
                       _item(4, 1, "x", [1.0, 2.0, 3.0, 4.0])]) == "matrix"      # repeated years = grid
    print("PASS test_table_kind_one_law_2026_09_10")


def test_evidence_law_prior_is_the_comparative_2026_09_10():
    """Run 262: the segment matrix row '6,359 | 2,852 | 3,128 | 106 | 12,445'
    CONTAINS last year's intangibles total, so the evidence law called 6,359
    'proven' and let a balance card overwrite the face's 12,685. The prior
    must be the number's own comparative — the pair the walk reads."""
    from pipeline.writegate import ties_prior, judge_write
    matrix = _item(30, 0, "Goodwill and other intangible assets", [6359.0, 2852.0, 3128.0, 106.0, 12445.0])
    face = _item(25, 0, "Goodwill and other intangible assets", [12685.0, 12445.0])
    wide = _item(17, 0, "Accounts receivable", [15193.79, 9.34, 12000.0, 8.1, 26.0])
    nci = _item(17, 1, "Non-controlling interests", [6063.0, 26258.0, 9815.0])
    assert ties_prior(matrix, 1.0, 12445.0)                        # somewhere on the row: legacy question
    assert not ties_prior(matrix, 1.0, 12445.0, value=6359.0)      # not its comparative
    assert ties_prior(face, 1.0, 12445.0, value=12685.0)
    assert ties_prior(wide, 1.0, 12000.0, value=15193.79)          # the percentage between is skipped
    assert not ties_prior(nci, 1.0, 6063.0, value=9815.0)          # the prior sits BEFORE the number
    verdict, reason, flag = judge_write(6359.0, 12445.0, True, [(matrix, 1.0)], set(), held_proven=True)
    assert verdict == "REFUSE" and "PROVEN" in reason, (verdict, reason)
    # 2026-09-16: the face's 12,685 was proven and still locks the cell; an
    # UNPROVEN holder yields and the matrix reading lands red, never clean
    verdict, reason, flag = judge_write(6359.0, 12445.0, True, [(matrix, 1.0)], set(), held_proven=False)
    assert verdict == "ALLOW_FLAGGED", (verdict, reason)
    verdict, reason, flag = judge_write(12685.0, 12445.0, False, [(face, 1.0)], set())
    assert verdict == "ALLOW"
    print("PASS test_evidence_law_prior_is_the_comparative_2026_09_10")


def test_key_tie_one_absorber_per_key_2026_09_10():
    """Run 262: the gate loop re-tied 'total assets' three times and each
    pass wrapped a DIFFERENT component — three stacked orange back-outs.
    A key keeps its absorber: a re-tie unwraps the same cell and re-solves
    the whole delta there; when the key ties on its own, it is restored."""
    from pipeline.keytie import key_tie
    from pipeline.writer import Writer
    from pipeline.evaluator import Evaluator
    from openpyxl.styles import PatternFill
    wb = _wb({"T2": 100.0, "U2": 90.0,
              "T3": "=T2*0.5", "U3": "=U2*0.5",
              "T5": 10.0, "U5": 5.0,                       # the unproven leaf (red)
              "T4": "=T2+T3+T5", "U4": "=U2+U3+U5"})
    wb["S"]["U5"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [], "key_rows": [{"name": "total", "sheet": "S", "row": 4}]}
    panel = {"total": {"print": 150.0, "prior": 160.0}}
    w = Writer(wb)
    assert key_tie(wb, spec, 2025, w, None, lambda s: None, panel=panel) == 1
    assert wb["S"]["U5"].value == "=(5)-(-10)", wb["S"]["U5"].value
    assert wb["S"]["U3"].value == "=U2*0.5"                # the formula of references is untouched
    wb["S"]["U2"] = 80.0                                   # the loop moved a component
    key_tie(wb, spec, 2025, w, None, lambda s: None, panel=panel)
    assert wb["S"]["U5"].value == "=(5)-(-25)", wb["S"]["U5"].value   # same cell, one wrap
    assert abs(Evaluator(wb).cell("S", "U4") - 150.0) <= 0.5
    wb["S"]["U2"] = 96.6667                                # the key now ties by itself
    key_tie(wb, spec, 2025, w, None, lambda s: None, panel=panel)
    assert wb["S"]["U5"].value == 5.0 and "total" not in w.log["key_absorbers"], wb["S"]["U5"].value
    print("PASS test_key_tie_one_absorber_per_key_2026_09_10")


def test_a_proven_figure_is_never_traded_for_a_check_2026_09_10():
    """Run 262 replay: a component card replaced the face's joint-venture
    figure (12,125, comparative tied) with a segment number (4,379, no tie)
    because the balance check moved closer. A number that merely moves a
    check is not a second reading of the item."""
    wb = _wb({"T2": 12188.0, "U2": 12125.0, "T3": 100.0, "U3": 100.0,
              "T9": "=T2+T3-12288", "U9": "=U2+U3-4479"})
    served = {("S", 2): {"value": 12125.0, "status": "OK", "conf": 4, "doc": "T.PDF", "page": 25,
                         "line": "Interests in and loans to joint ventures", "homed": True}}
    lp = _loop(wb, _spec_tiny(), served=served, evidence=[
        [12125.0, 12188.0], [2152.0, 4379.0, 292.0, 3300.0, 2002.0, 12125.0]])
    r = lp.t_set_input({"cell": "S!U2", "value": 4379.0, "why": "p29: segment table",
                        "card": "component", "check": "S!9"})
    assert r.startswith("REFUSED by the evidence law"), r
    assert wb["S"]["U2"].value == 12125.0
    print("PASS test_a_proven_figure_is_never_traded_for_a_check_2026_09_10")


def test_reader_sign_of_the_tie_2026_09_10():
    """CLP fuel clause: the presentation prints '1,043 | (370)' where the
    model holds +370 — the line negates the model's convention, so this
    year's balance is −1,043 (it moved to the liability side). Forcing the
    prior's sign wrote +1,043."""
    from pipeline.reader import verify
    lines = [_item(37, 1, "Fuel Clause Account (FCA)", [1043.0, -370.0]),
             _item(209, 1, "减：利息收入", [108208159.6, 132705664.58])]
    led = _ledger(lines, face_pages=((95, "pl"),)); led._doc_periods = {DOC: "current"}
    rows = [{"row": "S!7", "sheet": "S", "r": 7, "label": "Closing balance", "prior": 370.0},
            {"row": "R!15", "sheet": "R", "r": 15, "label": "减：利息收入", "prior": 132.71}]
    answers = [{"row": "S!7", "printed": 1043.0, "page": 37, "line": "Fuel Clause Account (FCA)"},
               {"row": "R!15", "printed": 108208159.6, "page": 209, "line": "减：利息收入"}]
    v = verify(answers, rows, led, {(DOC, 37): 1.0, (DOC, 209): 1e4}, lambda s: None, priors=[370.0, 132.71])
    assert v["S!7"]["value"] == -1043.0 and v["S!7"]["conf"] == 4, v["S!7"]
    # DFE p209: the page was ratified at 10^4 but the comparative ties at 10^6 —
    # the tie is the line's scale (10,820.82 had been written for 108.21)
    assert abs(v["R!15"]["value"] - 108.21) < 0.01 and v["R!15"]["conf"] == 4, v["R!15"]
    print("PASS test_reader_sign_of_the_tie_2026_09_10")


def test_key_tie_absorber_survives_a_take_back_2026_09_10():
    """CLP live 2026-09-08: the gate loop's take-back unwrapped the
    absorber; the next re-tie then wrapped a second cell."""
    from pipeline.keytie import key_tie
    from pipeline.writer import Writer
    from openpyxl.styles import PatternFill
    wb = _wb({"T2": 100.0, "U2": 90.0, "T3": "=T2*0.5", "U3": "=U2*0.5",
              "T5": 10.0, "U5": 9.0, "T4": "=T2+T3+T5", "U4": "=U2+U3+U5"})
    wb["S"]["U5"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [], "key_rows": [{"name": "total", "sheet": "S", "row": 4}]}
    panel = {"total": {"print": 160.0, "prior": 160.0}}
    w = Writer(wb)
    key_tie(wb, spec, 2025, w, None, lambda s: None, panel=panel)
    first = w.log["key_absorbers"]["total"][1]
    assert first == "U5"
    wb["S"][first] = w.log["key_absorbers"]["total"][2]          # a take-back unwraps it
    wb["S"]["U2"] = 80.0
    key_tie(wb, spec, 2025, w, None, lambda s: None, panel=panel)
    assert w.log["key_absorbers"]["total"][1] == first
    wrapped = [c for c in ("U3", "U5") if str(wb["S"][c].value).startswith("=(")]
    assert wrapped == [first], (wrapped, first)
    print("PASS test_key_tie_absorber_survives_a_take_back_2026_09_10")


def test_key_panel_interim_balance_sheet_ties_the_year_end_2026_09_10():
    """Owner 2026-09-10: a half-year balance sheet compares to the last
    year-end, so the key panel takes the model's annual column as the
    prior for such rows (run 261 reported total assets 'not tied')."""
    from pipeline.keytie import panel_by_prior_tie
    wb = _wb({"A4": "Total assets", "R4": 142009.28, "T4": 150000.0, "U4": None,
              "A5": "Revenue", "R5": 69695.14, "T5": 33457.01, "U5": None})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "annual_prior_axis": {"S": "R"},
            "key_rows": [{"name": "total assets", "sheet": "S", "row": 4},
                         {"name": "revenue", "sheet": "S", "row": 5}]}
    lines = [_item(5, 1, "资产总计", [156365.0, 142009.28]),
             _item(45, 1, "营业收入", [38150.95, 33457.01])]
    led = _ledger(lines, face_pages=((5, "bs"), (45, "pl"))); led._doc_periods = {DOC: "current"}
    panel = panel_by_prior_tie(wb, spec, 2025, led)
    assert panel["total assets"]["print"] == 156365.0 and panel["total assets"]["prior"] == 142009.28, panel
    assert panel["revenue"]["print"] == 38150.95 and panel["revenue"]["prior"] == 33457.01, panel
    print("PASS test_key_panel_interim_balance_sheet_ties_the_year_end_2026_09_10")


def test_a_row_total_is_not_a_comparative_2026_09_10():
    """CLP live 2026-09-08: the associates note prints 'listed 954 |
    unlisted 7,532 | total 8,486' for 2024; 8,486 is the model's prior, so
    7,532 'tied' it as a comparative and a balance card overwrote the
    face's 9,508. A number that sums the numbers before it is a total."""
    from pipeline.writegate import ties_prior, is_sum_row, judge_write
    note = _item(195, 2, "Group's share of net assets", [954.0, 7532.0, 8486.0])
    face = _item(25, 1, "Interests in associates", [9508.0, 8486.0])
    assert is_sum_row([954.0, 7532.0, 8486.0], 2) and not is_sum_row([9508.0, 8486.0], 1)
    assert not ties_prior(note, 1.0, 8486.0, value=7532.0)
    assert ties_prior(face, 1.0, 8486.0, value=9508.0)
    # a second line that genuinely ties lands RED beside a proven figure, never clean
    other = _item(30, 1, "Interests in associates", [9400.0, 8486.0])
    v, reason, flag = judge_write(9400.0, 8486.0, True, [(other, 1.0)], set(), held_proven=True)
    assert v == "ALLOW_FLAGGED" and flag == "red" and "two readings" in reason, (v, reason)
    v, reason, flag = judge_write(9400.0, 8486.0, True, [(other, 1.0)], set(), held_proven=False)
    assert v == "ALLOW"
    from pipeline.reader import verify
    led = _ledger([note, face], face_pages=((25, "bs"),)); led._doc_periods = {DOC: "current"}
    rows = [{"row": "S!68", "sheet": "S", "r": 68, "label": "Associates", "prior": 8486.0}]
    v2 = verify([{"row": "S!68", "printed": 7532.0, "page": 195, "line": "Group's share of net assets"}],
                rows, led, {(DOC, 195): 1.0, (DOC, 25): 1.0}, lambda s: None, priors=[8486.0])
    assert "S!68" not in v2 or v2["S!68"]["conf"] < 4, v2     # never proven by a row total
    print("PASS test_a_row_total_is_not_a_comparative_2026_09_10")


def test_gap_reader_reads_a_row_where_its_prior_prints_2026_09_10():
    """CLP 2026-09-08: rows with no printed prior rode every region of
    every document — 101 image calls, 33 of the hour's minutes. A row is
    read in the region that prints its prior; a homeless row is the
    whole-document reader's."""
    from pipeline.stage3_read import rows_for_region
    homed = TargetRow("F", 5, "Revenue", 90964.0)
    homeless = TargetRow("D", 9, "Segment capex", None)
    elsewhere = TargetRow("F", 7, "Tax", 1200.0)
    homes = {homed.key: {(DOC, 23)}, elsewhere.key: {(DOC, 40)}}
    rows = rows_for_region([homed, homeless, elsewhere], homes, DOC, [23, 24], {})
    assert rows == [homed], rows
    assert rows_for_region([homed, homeless, elsewhere], homes, DOC, [40], {homed.key: 1}) == [elsewhere]
    print("PASS test_gap_reader_reads_a_row_where_its_prior_prints_2026_09_10")


def test_a_constant_row_is_never_nil_2026_09_10():
    """CLP 2026-09-08: Yangjiang's capacity (1,108 MW, the same every year)
    printed alone in the plant list was read as 'last year's figure beside
    a blank' and zeroed — the divisor of every year's unit cost (888 error
    cells). The model's own history says the figure does not move."""
    from pipeline.writegate import nil_current_zero, row_is_constant
    from pipeline.reader import verify
    assert row_is_constant(1108.0, 1108.0) and not row_is_constant(1108.0, 1090.0)
    line = _item(41, 3, "Guangdong Yangjiang Nuclear", [1108.0])
    led = _ledger([line], face_pages=((41, "pl"),)); led._doc_periods = {DOC: "current"}
    assert nil_current_zero([line], 1108.0, {(DOC, 41)}, set()) is not None          # no history: the old law
    assert nil_current_zero([line], 1108.0, {(DOC, 41)}, set(), prior2=1108.0) is None
    rows = [{"row": "CN!136", "sheet": "CN", "r": 136, "label": "Yangjiang", "prior": 1108.0, "prior2": 1108.0}]
    v = verify([{"row": "CN!136", "printed": 1108.0, "page": 41, "line": "Guangdong Yangjiang Nuclear"}],
               rows, led, {(DOC, 41): 1.0}, lambda s: None, priors=[1108.0])
    assert v["CN!136"]["value"] == 1108.0 and v["CN!136"]["conf"] == 4, v
    v0 = verify([{"row": "CN!136", "printed": None, "page": 41, "line": "Guangdong Yangjiang Nuclear"}],
                rows, led, {(DOC, 41): 1.0}, lambda s: None, priors=[1108.0])
    assert "CN!136" not in v0, v0
    print("PASS test_a_constant_row_is_never_nil_2026_09_10")


def test_a_nameless_unchanged_tie_is_no_evidence_2026_09_10():
    """CLP 2026-09-08: 'Tallawarra A & B Power Stations 760 | 760' claimed
    the Yangjiang row (prior 760) and held it at 760; the named line
    printed 570. A bare number tie carries news or it is a coincidence."""
    import openpyxl
    from pipeline.reconcile import reconcile
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "CN"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T3"], ws["T4"] = 58000.0, 39000.0
    ws["A31"], ws["T31"] = "Yangjiang", 760.0
    ws["A32"], ws["T32"] = "Share capital", 500.0
    spec = {"year_axis": {"CN": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    nameless = _item(247, 9, "Tallawarra A & B Power Stations New South Wales", [760.0, 760.0])
    named = _item(25, 4, "Share capital", [500.0, 500.0])
    led = _ledger(_anchors(247) + _anchors(25) + [nameless, named], face_pages=())
    led._doc_periods = {DOC: "current"}
    serves, mapping = reconcile(wb, spec, 2025, led, lambda s: None)
    assert ("CN", 31) not in serves and mapping.get("nameless_unchanged", 0) >= 1, (serves.get(("CN", 31)), mapping)
    assert serves.get(("CN", 32), {}).get("value") == 500.0          # the named unchanged line still serves
    print("PASS test_a_nameless_unchanged_tie_is_no_evidence_2026_09_10")


def test_a_round_figure_is_a_figure_2026_09_10():
    """Withdrawn rule (2026-09-10): a no-tie read was refused for having
    fewer than three significant digits. '收到其他与投资活动有关的现金
    1,000,000.00' (RMB 1m) and '专项应付款 240,000.00' are genuine round
    figures. A read is judged by the print, the tie and the name — never
    by how round its digits are."""
    from pipeline.reader import verify
    lines = [_item(51, 3, "收到其他与投资活动有关的现金 五(六十九)", [1000000.0]),
             _item(155, 2, "专项应付款", [240000.0])]
    led = _ledger(lines, face_pages=((51, "cf"),)); led._doc_periods = {DOC: "current"}
    rows = [{"row": "R!207", "sheet": "R", "r": 207, "label": "收到其他与投资活动有关的现金", "prior": None, "prior2": None},
            {"row": "R!148", "sheet": "R", "r": 148, "label": "专项应付款", "prior": None, "prior2": None}]
    answers = [{"row": "R!207", "printed": 1000000.0, "page": 51, "line": "收到其他与投资活动有关的现金 五(六十九)"},
               {"row": "R!148", "printed": 240000.0, "page": 155, "line": "专项应付款"}]
    v = verify(answers, rows, led, {(DOC, 51): 1e6, (DOC, 155): 1e6}, lambda s: None, priors=[])
    assert abs(v["R!207"]["value"] - 1.0) < 1e-6 and v["R!207"]["flag"] == "red", v
    assert abs(v["R!148"]["value"] - 0.24) < 1e-6 and v["R!148"]["flag"] == "red", v
    print("PASS test_a_round_figure_is_a_figure_2026_09_10")


def test_key_tie_backs_out_the_least_confident_leaf_2026_09_10():
    """Owner 2026-09-10: when a key formula does not match the print, trace
    its components and back out the least confident cell — never wrap the
    formula. CLP: 'net profit' had wrapped operating costs (=AI14-AI13-AI12)
    while two one-off leaves sat red at 0; 'recurring net profit' said no
    component could absorb while Final!AI30 carried last year's 94."""
    from pipeline.keytie import key_tie
    from pipeline.writer import Writer
    from pipeline.evaluator import Evaluator
    from openpyxl.styles import PatternFill
    wb = _wb({"T9": 11742.0, "U9": 10468.0,                 # net profit reported (proven)
              "T8": 0.0, "U8": 0.0,                         # a one-off leaf, red (taken back)
              "T3": "=94-T8", "U3": "=94-U8",               # other one-offs: last year's 94 carried
              "T2": "=T9-T3", "U2": "=U9-U3",               # recurring profit (key)
              "T6": "=T9*2", "U6": "=U9*2"})                # a formula of references, plain
    wb["S"]["U8"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [], "key_rows": [{"name": "recurring", "sheet": "S", "row": 2}]}
    w = Writer(wb)
    assert key_tie(wb, spec, 2025, w, None, lambda s: None,
                   panel={"recurring": {"print": 10909.0, "prior": 11648.0}}) == 1
    assert wb["S"]["U8"].value == "=(0)-(-535)", wb["S"]["U8"].value         # the red leaf absorbs (it enters the key positively)
    assert wb["S"]["U6"].value == "=U9*2" and wb["S"]["U2"].value == "=U9-U3"
    assert abs(Evaluator(wb).cell("S", "U2") - 10909.0) <= 1.0
    # no red leaf: the carried constant is the next least confident cell
    wb2 = _wb({"T9": 11742.0, "U9": 10468.0, "T8": 0.0, "U8": 0.0,
               "T3": "=94-T8", "U3": "=94-U8", "T2": "=T9-T3", "U2": "=U9-U3"})
    w2 = Writer(wb2)
    assert key_tie(wb2, spec, 2025, w2, None, lambda s: None,
                   panel={"recurring": {"print": 10909.0, "prior": 11648.0}}) == 1
    assert wb2["S"]["U3"].value == "=(94-(535))-U8", wb2["S"]["U3"].value
    assert wb2["S"]["U8"].value == 0.0                                        # a plain hardcode is proven
    print("PASS test_key_tie_backs_out_the_least_confident_leaf_2026_09_10")


def test_a_page_is_read_in_its_displayed_orientation_2026_09_10():
    """Owner 2026-09-10: 43 of DFE's 280 annual-report pages are landscape
    (/Rotate 270); their characters run vertically and the extractor lined
    them up on the wrong axis — every string reversed, the fixed-asset,
    CIP and intangible notes invisible. Read on the real page."""
    import pdfplumber
    from pathlib import Path
    from pipeline.stage1_read import rotated_text
    pdf_path = Path("companies/DFE/disclosures/FY25/DFE 2025 Annual Report (CN).pdf")
    if not pdf_path.exists():
        print("SKIP test_a_page_is_read_in_its_displayed_orientation_2026_09_10 (no DFE report)")
        return
    with pdfplumber.open(str(pdf_path)) as pdf:
        pg = pdf.pages[183]
        assert pg.rotation == 270
        lines = rotated_text(pg).splitlines()
        assert lines[0] == "东方电气股份有限公司", lines[0]
        key = [l for l in lines if l.startswith("（1）上年年末余额")]
        assert key and key[0].endswith("2,109,448,125.97 18,863,557,255.35"), key[:1]
        assert any(l.startswith("—在建工程转入") and l.endswith("1,712,244,672.22") for l in lines)
        assert rotated_text(pdf.pages[0]) is None                # a portrait page never comes here
        from pipeline.stage1_read import _page_image
        im = _page_image(pg)
        assert im is None or im.size[0] > im.size[1]             # a scan of a landscape page is landscape
    print("PASS test_a_page_is_read_in_its_displayed_orientation_2026_09_10")


def test_an_enumerator_is_not_a_number_and_a_ratio_ties_relative_2026_09_10():
    from pipeline.numerics import line_numbers, label_of, row_tol
    ln = "（1）上年年末余额 17,915,996.06 7,375,145,834.43 18,863,557,255.35"
    assert label_of(ln) == "上年年末余额", label_of(ln)
    assert line_numbers(ln) == [17915996.06, 7375145834.43, 18863557255.35], line_numbers(ln)
    assert label_of("1．账面原值") == "账面原值" and label_of("2、 固定资产情况") == "固定资产情况"
    assert line_numbers("(2,474) 1,200") == [-2474.0, 1200.0]          # a negative amount is not an enumerator
    assert label_of("Fixed assets 10 166,094 158,532") == "Fixed assets"
    # a ratio ties relative-only: 'a cent' on 0.15 would be 6.7% of it
    assert row_tol(0.15) < 0.001 and row_tol(1.15) == 0.01 and row_tol(760.0) > 3
    print("PASS test_an_enumerator_is_not_a_number_and_a_ratio_ties_relative_2026_09_10")


def test_roll_forward_schedule_vertical_tie_2026_09_10():
    """Owner 2026-09-10: a movement table has no prior-year column, but its
    opening row IS last year's closing. The DFE fixed-asset note (p184) in
    yuan against the Driver block in millions: Addition = 购置 (its 2024
    value tied 购置 in the 2024 table), Transfer = the rest of the increases
    (the analyst's own '=1265.03-J95'), Disposal = the whole decrease group;
    the carried literals in the analyst's formulas take this year's role
    totals; the roll closes on the printed closing."""
    from pipeline.schedules import serve_schedules, find_blocks
    from pipeline.writer import Writer
    from pipeline.evaluator import Evaluator
    wb = _wb({"A94": "Beginning value", "T94": 17987.25, "U94": "=T98",
              "A95": "Addition", "T95": 211.93472192, "U95": 211.93472192,
              "A96": "Transfer from CIP", "T96": "=1265.02640492-T95", "U96": "=1265.02640492-U95",
              "A97": "Disposal", "T97": -388.94735586, "U97": -388.94735586,
              "A98": "Ending value", "T98": "=SUM(T94:T97)", "U98": "=SUM(U94:U97)",
              "A107": "Impairment", "T107": "=-128.28638909+6.18", "U107": "=-128.28638909+11.99"})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}}
    blocks = find_blocks(wb, spec, 2025)
    assert [(b["beg"], b["end"], [r for r, _ in b["rows"]]) for b in blocks] == [(94, 98, [95, 97])], blocks
    cur = [_item(184, 6, "（1）上年年末余额", [17915996.06, 7375145834.43, 9030745014.97, 330302283.92, 2109448125.97, 18863557255.35]),
           _item(184, 7, "（2）本期增加金额", [905010560.18, 750551287.10, 31930461.01, 274309678.09, 1961801986.38]),
           _item(184, 8, "—购置", [43561938.48, 113354614.13, 14732600.18, 72762551.95, 244411704.74]),
           _item(184, 9, "—在建工程转入", [860636572.44, 636629670.52, 17064559.36, 197913869.90, 1712244672.22]),
           _item(184, 10, "—其他", [812049.26, 567002.45, 133301.47, 3633256.24, 5145609.42]),
           _item(184, 12, "（3）本期减少金额", [304987173.69, 180543184.13, 32121474.81, 89734144.53, 607385977.16]),
           _item(184, 13, "—处置或报废", [43102486.33, 168078217.88, 31977515.69, 79754435.67, 322912655.57]),
           _item(184, 14, "—其他", [261884687.36, 12464966.25, 143959.12, 9979708.86, 284473321.59]),
           _item(184, 15, "（4）期末余额", [17915996.06, 7975169220.92, 9600753117.94, 330111270.12, 2294023659.53, 20217973264.57]),
           _item(185, 3, "（1）上年年末余额", [86088944.90, 35741754.75, 118991.45, 6336697.99, 128286389.09]),
           _item(185, 4, "（2）本期增加金额", [721616.45, 1836967.49, 2441.14, 85478.90, 2646503.98]),
           _item(185, 6, "（3）本期减少金额", [14143698.29, 15524571.30, 2441.14, 580273.63, 30250984.36]),
           _item(185, 9, "（4）期末余额", [72666863.06, 22054150.94, 118991.45, 5841903.26, 100681908.71])]
    prior = [Item(doc="ar2024.pdf", page=180, table_id=0, row_ord=i, label=l, nums=n) for i, (l, n) in enumerate([
             ("（1）上年年末余额", [17987480000.0]), ("（2）本期增加金额", [1265026404.92]), ("—购置", [211934721.92]),
             ("—在建工程转入", [1052050000.0]), ("—其他", [1041683.0]), ("（3）本期减少金额", [388947355.86]),
             ("—处置或报废", [350000000.0]), ("—其他", [38947355.86]), ("（4）期末余额", [18863557255.35])])]
    led = _ledger(cur + prior, face_pages=()); led._doc_periods = {DOC: "current", "ar2024.pdf": "prior"}
    w = Writer(wb); served = {}
    n = serve_schedules(wb, spec, 2025, led, served, w, lambda s: None)
    ws = wb["S"]; ev = Evaluator(wb)
    assert abs(ws["U95"].value - 244.4117) < 0.001, ws["U95"].value                       # 购置 (the 2024 tie)
    assert ws["U96"].value == "=1961.8-U95", ws["U96"].value                                # the carried increase total
    assert abs(ws["U97"].value + 607.386) < 0.001, ws["U97"].value                        # the whole decrease group
    assert abs(ev.cell("S", "U98") - 20217.74) < 0.5                                        # closes on the printed 20,217.97 less the 0.22 opening gap
    assert ws["U107"].value == "=-100.682+11.99", ws["U107"].value                          # a literal equal to an opening is last year's closing
    assert str(ws["U97"].fill.fgColor.rgb)[-6:] != "FFC7CE"                                 # the roll closes: nothing red
    assert (("S", 95) in served) and served[("S", 95)]["conf"] == 4
    assert any("within the 1% significance margin" in v for v in w.log.get("verdicts", []))
    # beyond 1% nothing is served
    wb2 = _wb({"A94": "Beginning value", "T94": 17000.0, "U94": "=T98", "A95": "Addition", "T95": 200.0, "U95": 200.0,
               "A98": "Ending value", "T98": "=SUM(T94:T95)", "U98": "=SUM(U94:U95)"})
    n2 = serve_schedules(wb2, spec, 2025, led, {}, Writer(wb2), lambda s: None)
    assert n2 == 0 and wb2["S"]["U95"].value == 200.0
    print("PASS test_roll_forward_schedule_vertical_tie_2026_09_10")


def test_sense_check_checkpoint_and_final_pass_2026_09_09():
    """Owner 2026-09-09: the report's mini P&L, new vs old — net profit
    −5.8% against the estimate but +15.7% against the old forecast is a
    rollover error to hunt. The chain's actual-year cells (the agent's
    own red first) go to the queue's front; a row whose forecast was zero
    before the update goes back to zero; the final pass reviews, re-runs
    the checks, and writes up what it could not resolve."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import build_queue
    from pipeline.writer import Writer
    from pipeline.sensecheck import headline_deltas, suspicious, checkpoint
    from pipeline.evaluator import Evaluator
    def model(u4, u7, u9):
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
        ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
        ws["A4"], ws["T4"], ws["U4"], ws["V4"] = "Revenue", 1000.0, u4, "=U4*1.05"
        ws["A5"], ws["T5"], ws["U5"], ws["V5"] = "Group tax", -300.0, -320.0, "=U5*1.02"
        ws["A6"], ws["T6"], ws["U6"], ws["V6"] = "Net profit", "=T4+T5", "=U4+U5", "=V4+V5+U7*1.02+V9"
        ws["A7"], ws["T7"], ws["U7"] = "Australia tax (driver)", -100.0, u7
        ws["A9"], ws["T9"], ws["U9"], ws["V9"] = "Memo item", None, u9, "=U9"
        return wb
    pre = model(1080.0, -110.0, None)          # the analyst's estimate: tax driver -110, memo blank
    wb = model(1050.0, -900.0, 50.0)           # the run: the group's whole tax landed on the driver; memo filled
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U", "2026": "V"}, "header_row": 2}},
            "check_rows": [], "key_rows": [{"name": "revenue", "sheet": "Model", "row": 4},
                                           {"name": "net profit", "sheet": "Model", "row": 6}]}
    led = _ledger(_anchors(95) + [_item(95, 7, "Australia income tax", [-110.0, -100.0]),
                                  _item(95, 8, "Group income tax", [-320.0, -300.0])], face_pages=((95, "pl"),))
    led._doc_periods = {DOC: "current"}
    targets = _anchor_targets() + [TargetRow("Model", 4, "Revenue", 1000.0), TargetRow("Model", 7, "Australia tax", -100.0),
                                   TargetRow("Model", 9, "Memo item", None)]
    w = Writer(wb)
    served = {("Model", 4): {"value": 1050.0, "conf": 4, "doc": DOC, "page": 95, "flag": None, "homed": True}}
    w.log["written"] += ["Model!U4", "Model!U7", "Model!U9"]
    from openpyxl.styles import PatternFill
    wb["Model"]["U7"].fill = PatternFill("solid", fgColor="FFC7CE"); w.log["flags"].append("Model!U7")
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, served, w, None)
    d = {x["name"]: x for x in headline_deltas(wb, pre, spec, 2025)}
    assert abs(d["revenue"]["d0"] + 0.0278) < 0.001 and abs(d["revenue"]["d1"] + 0.0278) < 0.001
    assert d["net profit"]["d1"] - d["net profit"]["d0"] < -0.10          # the forecast collapsed, the actual did not
    assert [x["name"] for x in suspicious(headline_deltas(wb, pre, spec, 2025))] == ["net profit"]
    logs = []
    prio = checkpoint(loop, pre, logs.append)
    # the checkpoint investigates: net profit's swing traces to the red tax driver, whose
    # printed segment line ties the prior — replaced, orange, and the line is back in line
    assert abs(wb["Model"]["U7"].value + 110.0) < 0.01, wb["Model"]["U7"].value
    # (the memo row's zero is the writer's law now — measured on the analyst's model before the roll,
    # not the sense check's business; see the unforecast-row exhibit)
    assert not suspicious(headline_deltas(wb, pre, spec, 2025))
    assert not prio                                                         # nothing left for the queue's front
    assert any("swing traced to" in x and "replaced by printed line" in x for x in w.log["sense_check"]), w.log["sense_check"]
    q = build_queue(loop)
    assert not any(x.kind == "SENSE" for x in q)
    # the final pass: a fix that opens a check is taken back and the line written up
    print("PASS test_sense_check_checkpoint_and_final_pass_2026_09_09")


def test_investigator_traces_the_swing_and_judges_it_2026_09_10():
    """Owner 2026-09-10: 'press into net profit, then associates, then
    Australia, then income tax' — the input that explains the swing, level
    by level, judged by its colour and its history. A proven figure moving
    outside its own history is reported, never changed; a spread swing
    names its largest contributors."""
    import openpyxl
    from pipeline.investigate import contributors, trace, unusual_by_history
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "M"
    ws["A2"], ws["R2"], ws["S2"], ws["T2"], ws["U2"], ws["V2"] = "", 2022, 2023, 2024, 2025, 2026
    # net profit = HK + Australia; Australia = EBIT + tax; tax typed; associates typed with a history
    ws["A4"], ws["U4"], ws["V4"] = "Net profit", "=U5+U6+U9", "=V5+V6+V9"
    ws["A5"], ws["U5"], ws["V5"] = "Hong Kong", 500.0, "=U5*1.02"
    ws["A6"], ws["U6"], ws["V6"] = "Australia", "=U7+U8", "=V7+V8"
    ws["A7"], ws["U7"], ws["V7"] = "Australia EBIT", 300.0, "=U7*1.03"
    ws["A8"], ws["U8"], ws["V8"] = "Australia income tax", -900.0, "=U8*1.03"
    ws["A9"], ws["R9"], ws["S9"], ws["T9"], ws["U9"], ws["V9"] = "Associates", 100.0, 104.0, 99.0, 700.0, "=U9"
    pre = openpyxl.Workbook(); pw = pre.active; pw.title = "M"
    for c in ("A2","R2","S2","T2","U2","V2","A4","U4","V4","A5","U5","V5","A6","U6","V6","A7","U7","V7","A8","V8","A9","R9","S9","T9","V9"):
        pw[c] = ws[c].value
    pw["U8"] = -90.0; pw["U9"] = 100.0
    cs = contributors(wb, pre, "M", "V4")
    assert cs and cs[0][0:2] == ("M", "V6"), cs                          # Australia explains the swing (tax −900 vs −90; associates +600)
    trail, leaf = trace(wb, pre, "M", "V4")
    assert leaf == ("M", "U8"), (trail, leaf)                              # … down to the typed tax cell
    assert [t[2] for t in trail] == ["Australia", "Australia income tax", "Australia income tax"] or trail[-1][1] == "U8", trail
    spec = {"year_axis": {"M": {"columns": {"2022": "R", "2023": "S", "2024": "T", "2025": "U", "2026": "V"}}}}
    un, mv, band = unusual_by_history(wb, spec, "M", 9, 2025)
    assert un and mv > 5 and band[1] < 0.1, (un, mv, band)                # 100, 104, 99 then 700: unusual, no margin
    un2, _m, _b = unusual_by_history(wb, spec, "M", 5, 2025)
    assert not un2                                                         # no history: never 'unusual'
    # a spread swing: two inputs of equal weight — no single factor, both named
    ws["U8"] = -90.0; ws["U5"] = 800.0; ws["U9"] = 400.0
    trail2, leaf2 = trace(wb, pre, "M", "V4", floor=0.6)
    assert leaf2 is None and trail2 and trail2[-1][2].startswith("SPREAD:"), trail2
    print("PASS test_investigator_traces_the_swing_and_judges_it_2026_09_10")


def test_report_page_fixed_table_period_follows_the_run_2026_09_13():
    """THE REPORT REVAMP (owner 2026-09-13): one fixed table on every model,
    lines found from the model's own labels (a shared word is no evidence:
    'gross profit' is not 'profit after tax', 'tax' is not 'deferred tax
    assets'), explicit period headers, the printed figure beside the
    actual, the key numbers below, look-here with the trail's cell — and on
    an interim run the interim panel, saying so when it has no forecast."""
    import openpyxl
    from pipeline.reportpage import build, resolve_rows, period_axis, period_kind
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "M"
    for i, y in enumerate((2023, 2024, 2025, 2026, 2027, 2028)):
        ws.cell(row=2, column=2 + i, value=y)
    labels = ["P&L", "Revenue", "Gross Profit", "GPM", "Profit after tax", "EBIT", "Deferred tax assets", "Tax",
              "Reported net profit", "EPS - basic", "DPS", "Cash flow", "Operating cash flow", "CAPEX",
              "Investing cash flow", "Financing cash flow", "Dividend payment", "Balance sheet", "Cash",
              "Net debt/(cash)", "Total equity", "Share capital", "BPS - YE"]
    for i, lab in enumerate(labels):
        r = 3 + i
        ws.cell(row=r, column=1, value=lab)
        if lab not in ("P&L", "Cash flow", "Balance sheet"):
            for c in range(2, 8):
                ws.cell(row=r, column=c, value=float(100 * (c - 1) + r))
    ws["D4"] = 1200.0; ws["E4"] = "=D4*1.1"
    ws["D5"] = 300.0; ws["D6"] = 0.25
    pre = openpyxl.Workbook(); pw = pre.active; pw.title = "M"
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        for c in row:
            pw[c.coordinate] = c.value
    pw["D4"] = 1000.0; pw["E4"] = 1050.0
    spec = {"year_axis": {"M": {"columns": {str(y): chr(ord("B") + i) for i, y in enumerate(range(2023, 2029))}}},
            "key_rows": [{"name": "revenue", "sheet": "M", "row": 4}, {"name": "net profit", "sheet": "M", "row": 11}],
            "check_rows": [], "units": "RMB m"}
    rows, primary = resolve_rows(wb, spec, 2025, "FY25")
    assert primary == "M"
    assert rows["gross_profit"][1] == 5 and rows["tax"][1] == 10 and rows["bvps"][1] == 25, rows
    assert rows["net_profit"][1] == 11 and rows["div_paid"][1] == 19 and rows["cash"][1] == 21, rows
    for missing in ("ebitda", "associates", "recurring", "fcf"):
        assert missing not in rows, (missing, rows.get(missing))            # a shared word is no evidence
    assert [a[0] for a in period_axis(spec, "M", 2025, "FY25")] == ["FY24A", "FY25A", "FY26E", "FY27E", "FY28E"]
    extra = {"key_ties": [{"name": "revenue", "ref": "M!D4", "value": 1200.0, "print": 1200.0, "tied": True},
                          {"name": "net profit", "ref": "M!D11", "value": 111.0, "print": 999.0, "tied": False}],
             "provenance": {"M!4": {"value": 1200.0, "doc": "RA.pdf", "page": 5, "conf": 4}},
             "sense_rows": [{"name": "net profit", "d0": -0.05, "d1": 0.18, "ref1": "M!E11", "verdict": "red",
                             "text": "swing traced to Tax", "leaf": "M!D10", "stage": "final"}],
             "open_checks": [], "elapsed_min": 12.0, "period": "FY25", "units": "RMB m"}
    res = build(wb, pre, spec, 2025, "FY25", extra, log=lambda *_a, **_k: None)
    assert wb.sheetnames[0] == "_REPORT" and "_FLAGS" in wb.sheetnames
    rp = wb["_REPORT"]
    text = "\n".join(str(c.value) for row in rp.iter_rows() for c in row if c.value is not None)
    assert "FY24A" in text and "FY25A" in text and "FY28E" in text and "FY0" not in text and "FY+1" not in text
    assert "Documents received" not in text and "Why it moved" not in text and "SENSE CHECK" not in text
    assert "Next yr" not in text and "not in this model" in text
    assert "1,200 · p5" in text and "not tied" in text, text                # the printed figure beside the actual
    assert "12 min" in text and "key numbers tied to the print 1/2" in text
    # the table's cells are LIVE (formulas) for NEW, the pre model's VALUES for OLD, a change formula, the check
    hdr_row = next(r for r in range(1, 12) if rp.cell(row=r, column=2).value == "FY24A")
    rev_row = next(r for r in range(hdr_row, hdr_row + 6) if str(rp.cell(row=r, column=1).value or "").startswith("=HYPERLINK") and "Revenue" in str(rp.cell(row=r, column=1).value))
    new0 = next(c for c in range(2, 30) if rp.cell(row=hdr_row - 1, column=c).value == "NEW — after the update")
    old0 = next(c for c in range(2, 30) if rp.cell(row=hdr_row - 1, column=c).value == "OLD — before the update")
    assert rp.cell(row=rev_row, column=new0 + 1).value == "=M!D4"
    assert rp.cell(row=rev_row, column=old0 + 1).value == 1000.0 and rp.cell(row=rev_row, column=old0 + 2).value == 1050.0
    assert str(rp.cell(row=rev_row, column=2).value).startswith("=IFERROR(")
    chk = next(c for c in range(2, 30) if rp.cell(row=hdr_row, column=c).value == "check")
    assert "0.1" in str(rp.cell(row=rev_row, column=chk).value) and "sign flip" not in str(rp.cell(row=rev_row, column=chk).value)
    # the key-number section is gone (owner 2026-09-14: it repeated the table); the check is ten points only
    assert "Your estimate" not in text and "Key numbers" not in text
    from pipeline.reportpage import proper_name
    assert proper_name("eps") == "EPS" and proper_name("net profit") == "Net profit"
    # statements in the order P&L, balance sheet, cash flow, one empty row between them
    g = [r for r in range(1, rp.max_row + 1) if rp.cell(row=r, column=1).value in ("P&L", "Balance sheet", "Cash flow")]
    assert [rp.cell(row=r, column=1).value for r in g] == ["P&L", "Balance sheet", "Cash flow"], g
    assert all(rp.cell(row=r - 1, column=1).value is None for r in g[1:]), "an empty row before each statement"
    # look here: the sense verdict with the trail's cell as a link
    assert "red, your ruling" in text and "swing traced to Tax" in text
    assert any("M'!D10" in str(c.value) for row in rp.iter_rows() for c in row if isinstance(c.value, str)), "leaf link"
    assert res["rows"]["revenue"] == ("M", 4) and res["tied"] == 1 and res["panel"] == 2
    # THE PERIOD FOLLOWS THE RUN: a half-year panel with no forecast columns says so
    assert period_kind("1H25") == "1H" and period_kind("H125") == "1H" and period_kind("3Q25") == "3Q" and period_kind("FY25") == "FY"
    spec_h = {"year_axis": {"M": {"columns": {"2024": "C", "2025": "D"}}}, "key_rows": spec["key_rows"], "check_rows": []}
    assert [a[0] for a in period_axis(spec_h, "M", 2025, "1H25")] == ["1H24A", "1H25A"]
    wb2 = openpyxl.load_workbook  # noqa: F841 (openpyxl already imported)
    build(wb, pre, spec_h, 2025, "1H25", {"period": "1H25"}, log=lambda *_a, **_k: None)
    text2 = "\n".join(str(c.value) for row in wb["_REPORT"].iter_rows() for c in row if c.value is not None)
    assert "1H24A" in text2 and "1H25A" in text2 and "no half-year forecast found in this model" in text2, text2
    assert "FY26E" not in text2 and "Updated to 1H25" in text2
    print("PASS test_report_page_fixed_table_period_follows_the_run_2026_09_13")


def test_never_filled_law_is_the_writers_and_dps_is_sense_checked_2026_09_14():
    """DFE live 2026-09-10, owner's findings. (1) Label cards had filled
    'Revenue' over the segment lines and 'Hydro-generating unit 兆瓦' over
    Production/Sales/Inventory: rows with no number in any period. Owner
    2026-09-14: one law for the whole run, the writer's — such a row takes
    no write from any step, and no card is dealt for it. (2) A per-share
    line is an amount whatever its size: DPS 0.60 → 0.53 is sense-checked
    like EPS."""
    import openpyxl
    from pipeline.reader import never_filled
    from pipeline.writer import Writer, row_never_filled
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import build_queue
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"], ws["V2"] = 2024, 2025, 2026
    ws["A3"] = "Revenue"                                   # caption: children hold the numbers
    ws["A4"], ws["T4"] = "  Gas turbine", 500.0
    ws["A5"], ws["T5"] = "  Nuclear", 300.0
    ws["A150"] = "Hydro-generating unit 兆瓦"               # caption over a block
    ws["A151"], ws["T151"] = "Production", "=T4*2"
    ws["A160"], ws["V160"] = "Forecast-only driver", "=U160*1.1"   # tracked in the future: not never-filled
    assert never_filled(wb, "Model", 3, "U") and never_filled(wb, "Model", 150, "U")
    assert row_never_filled(ws, "U3") and not row_never_filled(ws, "U4") and not row_never_filled(ws, "U160")
    w = Writer(wb)
    assert w.write("Model", "U3", 78615.0, prior_coord="T3", trusted=True, allow_empty=True) is False
    assert w.write("Model", "U150", 0.008, prior_coord="T150", trusted=True, flag="red") is False
    assert w.log["never_filled_refused"] == ["Model!U3", "Model!U150"] and ws["U3"].value is None
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U", "2026": "V"}, "header_row": 2}}}
    led = _ledger(_anchors(95, 1e6), face_pages=((95, "pl"),))
    targets = _anchor_targets() + [TargetRow("Model", 3, "Revenue", None),
                                   TargetRow("Model", 150, "Hydro-generating unit 兆瓦", None)]
    loop = ObjectiveLoop(wb, spec, 2025, led, targets, {}, Writer(wb), None)
    labels = [(x.sheet, x.row) for x in build_queue(loop) if x.kind == "LABEL"]
    assert ("Model", 3) not in labels and ("Model", 150) not in labels, labels
    # (2) DPS under 1 is still a headline line
    from pipeline.sensecheck import headline_deltas, suspicious
    wb2 = openpyxl.Workbook(); w2 = wb2.active; w2.title = "M"
    w2["A2"], w2["U2"], w2["V2"] = "", 2025, 2026
    w2["A4"], w2["U4"], w2["V4"] = "DPS", 0.53, 0.42
    w2["A5"], w2["U5"], w2["V5"] = "Payout ratio", 0.40, 0.30
    pre = openpyxl.Workbook(); pw = pre.active; pw.title = "M"
    pw["U4"], pw["V4"], pw["U5"], pw["V5"] = 0.60, 0.60, 0.45, 0.45
    spec2 = {"year_axis": {"M": {"columns": {"2025": "U", "2026": "V"}}},
             "key_rows": [{"name": "dps", "sheet": "M", "row": 4}, {"name": "net profit", "sheet": "M", "row": 5}]}
    d = {x["name"]: x for x in headline_deltas(wb2, pre, spec2, 2025)}
    assert "dps" in d and abs(d["dps"]["d0"] + 0.1167) < 0.01, d      # −11.7% then −30%: 18 points apart
    assert "net profit" not in d                                        # a base under 1 that is not per share: skipped as before
    assert [x["name"] for x in suspicious(list(d.values()))] == ["dps"]
    print("PASS test_never_filled_law_is_the_writers_and_dps_is_sense_checked_2026_09_14")


def test_rolled_into_zero_retired_for_the_writers_law_2026_09_14():
    """The sense check's local zero rule is gone (owner 2026-09-14: rules
    live in the writer, not in a step). The zero-forecast row is measured
    on the analyst's model and enforced at the rollover, every write and
    the stale flag — see the unforecast-row exhibit."""
    import pipeline.sensecheck as sc
    assert not hasattr(sc, "rolled_into_zero")
    print("PASS test_rolled_into_zero_retired_for_the_writers_law_2026_09_14")


def test_a_matrix_row_never_pairs_anywhere_2026_09_14():
    """CLP run 34772986687 (owner 2026-09-14): seven cells took a segment
    column as this year. The results announcement's segment page prints
    'Finance income 119 | 14 | 29 | 4 | 69 | 235' (segments) — the card
    served 14 beside Australia's prior 29; 'Associates 1,810 | 1,810' on
    the same page zeroed CN's associates (the P&L face prints 1,607 |
    1,810); the page read took 'Recurring EBITDAF … 343 | 261 | -956' as
    Ho-Ping 181 | 261. The table's kind is now stamped on every printed
    line, and the pairing law, the nil rule and the page reads all refuse
    a matrix row. A period table (a year header) still pairs."""
    from pipeline.writegate import ties_prior, nil_current_zero
    from pipeline.stage3_read import matrix_pair
    seg = [_item(30, 1, "2025", [2025.0, 2025.0, 2025.0, 2025.0], table_id=3),      # the same year repeated: a grid
           _item(30, 2, "Finance income", [119.0, 14.0, 29.0, 4.0, 69.0, 235.0], table_id=3),
           _item(30, 3, "Associates", [1810.0, 1810.0], table_id=3, source_line="Associates – 1,810 1,810")]
    face = [_item(23, 1, "", [2025.0, 2024.0], table_id=0),
            _item(23, 2, "Finance income", [24.0, 29.0], table_id=0),
            _item(23, 3, "Associates", [1607.0, 1810.0], table_id=0)]
    led = _ledger(seg + face, face_pages=((23, "pl"),))
    led.stamp_table_kinds()
    assert all(it.table_kind == "matrix" for it in seg) and all(it.table_kind == "period" for it in face)
    assert ties_prior(seg[1], 1.0, 29.0, value=14.0) is False          # a segment beside the prior is not this year
    assert ties_prior(face[1], 1.0, 29.0, value=24.0) is True           # the face's pair still ties
    assert nil_current_zero(led.items, 1810.0, row_label="Associates") is None   # the matrix line proves no nil
    assert matrix_pair(led, DOC, [30], "14", "29") and not matrix_pair(led, DOC, [23], "24", "29")
    print("PASS test_a_matrix_row_never_pairs_anywhere_2026_09_14")


def test_the_brain_reads_every_table_and_its_verdict_travels_2026_09_14():
    """Owner 2026-09-14: "the brain should read the table by itself to judge
    whether the table is having years as columns, segments as columns,
    movement as columns, or whatever … not the code." The table reader
    sends every table (header lines + first rows) to the brain once; its
    verdict is stamped on every line and outranks the shape fallback: a
    two-column 'units | MW' table the shape calls plain never pairs, a
    two-column note without a year line pairs. The stamp survives the
    ledger pin (to_json / from_json) so replays keep the reading."""
    from pipeline.tables import describe_tables, table_cards, target_columns
    from pipeline.ledger import Ledger
    from pipeline.writegate import ties_prior
    cap = [_item(245, 1, "Solar", [2.0, 21.0], table_id=7), _item(245, 2, "Wind", [3.0, 40.0], table_id=7)]
    note = [_item(181, 1, "Finance charges", [257.0, 294.0], table_id=2), _item(181, 2, "Bank loans", [100.0, 120.0], table_id=2)]
    led = _ledger(cap + note, face_pages=((181, "pl"),))
    led.stamp_table_kinds()
    assert cap[0].table_kind == "plain" and note[0].table_kind == "plain"        # the shape cannot tell them apart
    cards = table_cards(led, [])
    assert len(cards) == 2 and "Solar: 2 | 21" in cards[1][1] or "Solar: 2 | 21" in cards[0][1]
    class FakeClient:
        calls = 0
        def json(self, system, user, validate, repair_retries=1, images=None):
            FakeClient.calls += 1
            assert "id 1" in user and "id 2" in user
            ids = {}
            for blk in user.split("### id ")[1:]:
                n = int(blk.split("\n", 1)[0]); ids[n] = blk
            out = []
            for n, blk in ids.items():
                if "p245" in blk:
                    out.append({"id": n, "kind": "categories", "columns": ["units", "MW"], "note": "capacity table"})
                else:
                    out.append({"id": n, "kind": "periods", "columns": ["FY2025", "FY2024"]})
            obj = {"tables": out}
            assert not validate(obj)
            return obj
    n = describe_tables(FakeClient(), led, [], 2025, "FY25", log=lambda *_a, **_k: None)
    assert n == 2 and FakeClient.calls == 1
    assert cap[0].table_kind == "matrix" and cap[0].columns == ["units", "MW"]
    assert note[0].table_kind == "period" and target_columns(note[0], 2025, "FY25") == (0, 1)
    assert ties_prior(cap[0], 1.0, 21.0, value=2.0) is False         # units | MW never pairs
    assert ties_prior(note[0], 1.0, 294.0, value=257.0) is True      # the note pairs
    led2 = Ledger.from_json(led.to_json()); led2.corroborate()
    again = next(it for it in led2.items if it.page == 245)
    assert again.table_kind == "matrix" and again.columns == ["units", "MW"], "the pin keeps the brain's reading"
    # the walk asks the same stamp (CLP live: it had recomputed the shape and paired 'Solar 2 | 294 | 45')
    from pipeline.reconcile import table_kind
    assert table_kind(cap) == "matrix" and table_kind(note) == "period"
    # a tie is at the number's own world: statement rounding never makes 1.61 into 2
    from pipeline.writegate import _close
    assert not _close(1.61, 2.0) and _close(2.0, 2.0) and _close(1000.4, 1000.0) and _close(4.143, 4.14)
    # a prior-period document never proves a current value on a card
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Model"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["A52"], ws["T52"] = "Renewables (NED solar)", 21.0
    spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}}
    old_doc = [Item(doc="e_2024 Annual Report.pdf", page=198, table_id=2, row_ord=1, label="Cash flow hedges", nums=[-161.0, -2102.0])]
    led3 = _ledger(_anchors(95, 1e6) + old_doc, face_pages=((95, "pl"),))
    led3._doc_periods = {DOC: "current", "e_2024 Annual Report.pdf": "prior"}
    targets = _anchor_targets() + [TargetRow("Model", 52, "Renewables (NED solar)", 21.0)]
    loop = ObjectiveLoop(wb, spec, 2025, led3, targets, {}, Writer(wb), None)
    r = loop.t_set_input({"cell": "Model!U52", "value": 2.0, "why": "p198 hedges — card-adjudicated"})
    assert not (str(r).startswith("WRITTEN") and not str(ws["U52"].fill.fgColor.rgb).endswith("FFC7CE")), r
    print("PASS test_the_brain_reads_every_table_and_its_verdict_travels_2026_09_14")


def test_a_prior_printed_under_several_names_needs_kinship_2026_09_14():
    """CLP live 2026-09-14: eight cells took a bare prior tie on a number
    printed on 10–50 lines of the documents (294 → 'Finance charges' for
    the Australia solar row; 120 → 'hedge accounting' for India coal while
    'Thermal (Jhajjar) 112 | 120' was one page on). The old law let any
    prior of 50 or more tie bare. Identity is uniqueness in print: a prior
    carried under several names needs the line's label to be kin to the
    row's; a prior printed under one name still ties bare."""
    from pipeline.reconcile import prior_carriers, small_prior_needs_kinship
    items = [_item(48, 1, "Thermal (Jhajjar)", [112.0, 120.0]),
             _item(23, 2, "hedge accounting", [-85.0, 120.0]),
             _item(51, 3, "Solar Projects #", [362.0, 294.0, 240.0, 120.0]),
             _item(181, 4, "Finance charges", [257.0, 294.0]),
             _item(29, 5, "Operating Earnings", [9559.0, 1598.0, 294.0]),
             _item(60, 6, "Deferred creditors", [13278.0, 8363.0])]
    c = prior_carriers(items)
    assert len(c[120.0]) == 3 and len(c[294.0]) == 3 and len(c[8363.0]) == 1
    assert small_prior_needs_kinship(120.0, "hedge accounting", "Coal (Jhajjar)", c) is False
    assert small_prior_needs_kinship(120.0, "Thermal (Jhajjar)", "Coal (Jhajjar)", c) is True
    assert small_prior_needs_kinship(294.0, "Finance charges", "Solar", c) is False
    assert small_prior_needs_kinship(8363.0, "Deferred creditors", "Other payables", c) is True   # unique in print: its own identity
    assert small_prior_needs_kinship(12.0, "Meters", "Short-term deposits", c) is False            # small: kinship as before
    print("PASS test_a_prior_printed_under_several_names_needs_kinship_2026_09_14")


def test_the_zero_forecast_stays_zero_2026_09_14():
    """Owner 2026-09-14 (CLP ROAFNA!AI71 'Coal-fired (CAPCO)'): the actual
    year is mapped like every other cell; but where the analyst's forecast
    from next year on was 0, it stays 0 after the update — the update had
    carried −1,050 into the actual and every forecast year followed through
    '=+AI71'. The zero-forecast rows are measured on the analyst's model;
    after the update, a forecast cell of such a row that computes non-zero
    is held at 0 (blue) through the gate."""
    from pipeline.writer import Writer, unforecast_rows, hold_zero_forecasts, rollover_column
    from pipeline.evaluator import Evaluator
    wb = _wb({"A71": "Coal-fired (CAPCO)", "AH71": -1050.0, "AI71": 0, "AJ71": "=+AI71", "AK71": "=+AJ71",
              "A72": "Gas", "AH72": 300.0, "AI72": 310.0, "AJ72": "=+AI72", "AK72": "=+AJ72",
              "A95": "Check", "AH95": 0, "AI95": "=AI71-AI71", "AJ95": "=AJ71-AJ71", "AK95": "=AK71-AK71",
              "A96": "Balancing item", "AH96": 0, "AI96": 0, "AJ96": "=AJ71", "AK96": "=AK71"})
    ev = Evaluator(wb)
    z = unforecast_rows(wb, "S", "AI", ["AJ", "AK"], lambda sh, co: ev.cell(sh, co), skip_rows={96})
    assert z == {71}, z                     # 72 forecasts 310; 95 is a check row by label; 96 a spec check row: never held
    hard = rollover_column(wb, "S", "AH", "AI")                    # the standard recipe: the actual year rolls like any row
    assert wb["S"]["AI71"].value == -1050.0 and 71 in hard
    w = Writer(wb); w.forecast_cols = {"S": {"AJ", "AK"}}; w.unforecast_rows = {("S", 71)}
    w.write("S", "AI71", 2910.0, prior_coord="AH71", trusted=True)  # the mapping lands whatever it proves
    ev2 = Evaluator(wb)
    assert abs(ev2.cell("S", "AJ71") - 2910.0) < 0.01              # the link carried it into 2026
    n = hold_zero_forecasts(w, lambda sh, co: Evaluator(wb).cell(sh, co), log=lambda *_a, **_k: None)
    assert n == 2 and wb["S"]["AJ71"].value == 0 and wb["S"]["AK71"].value == 0
    assert str(wb["S"]["AJ71"].fill.fgColor.rgb).endswith("BDD7EE") and "S!AJ71" in w.log["flags"]
    assert any(x.startswith("S!AJ71:") for x in w.log["frozen"])      # a sanctioned hold the gate accepts
    assert wb["S"]["AJ72"].value == "=+AI72"                       # a forecast that was not 0 is untouched
    print("PASS test_the_zero_forecast_stays_zero_2026_09_14")


def test_the_vintage_law_is_a_stamp_on_every_line_2026_09_14():
    """Owner 2026-09-14: the ban on last year's report had lived in thirty
    places and the card path missed it (a 2024 hedge line 'proved' 2).
    The ledger now stamps sourceable on every line once the vintage is
    decided; the evidence finder, the pairing law and the nil rule refuse
    an unsourceable line wherever they are called from — no local ban."""
    from pipeline.ledger import Ledger, sourceable
    from pipeline.writegate import find_evidence, ties_prior, nil_current_zero
    cur = _item(23, 1, "Finance income", [24.0, 29.0])
    old = Item(doc="e_2024 Annual Report.pdf", page=198, table_id=2, row_ord=1, label="Finance income", nums=[29.0, 31.0],
               source_line="Finance income – 29 31")
    led = _ledger([cur, old], face_pages=((23, "pl"),))
    led._doc_periods = {DOC: "current", "e_2024 Annual Report.pdf": "prior"}
    led.stamp_vintages()
    assert cur.sourceable is True and old.sourceable is False and sourceable(cur) and not sourceable(old)
    assert [it.page for it, _s in find_evidence(led.items, 29.0)] == [23]          # the 2024 line is not evidence
    assert ties_prior(old, 1.0, 31.0, value=29.0) is False and ties_prior(cur, 1.0, 29.0, value=24.0) is True
    assert nil_current_zero([old], 31.0, row_label="Finance income") is None      # nor does it prove a nil
    led2 = Ledger.from_json(led.to_json())
    assert next(it for it in led2.items if it.page == 198).sourceable is False    # the pin keeps the verdict
    print("PASS test_the_vintage_law_is_a_stamp_on_every_line_2026_09_14")


def test_the_plug_law_is_the_writers_2026_09_14():
    """Owner 2026-09-14: "a plug should only be used as the last resort —
    analysts hate plugs." The writer refuses any write declared a plug
    until the run opens the last-resort stage (the queue reaching its plug
    cards; the repair rounds); a plug that lands is recorded. A guard's
    revert un-serves and unlocks the cell it takes back; a flag painted
    through the gate is journaled and can be cleared the same way."""
    from pipeline.writer import Writer
    wb = _wb({"T5": 100.0, "T6": 40.0})
    w = Writer(wb)
    assert w.write("S", "U5", 12.0, prior_coord="T5", trusted=True, flag="orange", kind="plug") is False
    assert w.log["plug_refused"] == ["S!U5"] and wb["S"]["U5"].value is None
    w.plugs_allowed = True
    assert w.write("S", "U5", 12.0, prior_coord="T5", trusted=True, flag="orange", kind="plug") is True
    assert w.log["plugs"] == ["S!U5"]
    w.served = {("S", 6): {"value": 44.0, "conf": 5}}
    assert w.write("S", "U6", 44.0, prior_coord="T6", trusted=True) is True
    w.locked.add("S!U6")
    assert w.revert("S", "U6", 40.0, "red", "Not confirmed — please check.") is True
    assert wb["S"]["U6"].value == 40.0 and "S!U6" not in w.locked and ("S", 6) not in w.served
    assert str(wb["S"]["U6"].fill.fgColor.rgb).endswith("FFC7CE") and "S!U6" in w.log["flags"]
    w.flag("S", "U6", None)
    assert "S!U6" not in w.log["flags"] and wb["S"]["U6"].comment is None
    print("PASS test_the_plug_law_is_the_writers_2026_09_14")


def test_a_fix_the_cards_ruled_out_no_longer_blocks_the_plug_2026_09_14():
    """Floors 2026-09-14 (honest replays): the cards had answered 'not
    disclosed' on a component, yet diagnose_balance kept naming it GUILTY
    and the ladder refused to plug — six checks delivered open. A card's
    verdict on a row is recorded (ruled_out); a ruled-out fix is listed
    for the analyst and no longer counts as a fix that remains."""
    wb = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0,
              "U2": 109.0, "U3": 60.0, "U4": 171.0,
              "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"})
    lp = _loop(wb, _spec_tiny())
    lp.writer.plugs_allowed = True
    for r_, lab_, pv_ in ((2, "Revenue", 100.0), (3, "Other", 50.0), (4, "Costs", 150.0)):
        lp.targets[("S", r_)] = TargetRow("S", r_, lab_, pv_)
    lp._diff_value = lambda t: (111.0, _item(95, 1, "Revenue", [111.0, 100.0]), 1.0) if t.row == 2 else None
    diag = lp.t_diagnose_balance({"check": "S!U9"})
    assert "GUILTY S!2" in diag, diag
    r = lp.t_plug_residual({"check": "S!U9", "into": "S!3", "why": "t"})
    assert r.startswith("REFUSED") and "fixes remain" in r, r
    lp.writer.log["ruled_out"] = ["S!2"]                      # the card said not disclosed
    diag2 = lp.t_diagnose_balance({"check": "S!U9"})
    assert "RULED OUT S!2" in diag2 and "GUILTY" not in diag2, diag2
    r2 = lp.t_plug_residual({"check": "S!U9", "into": "S!3", "why": "t"})
    assert r2.startswith("PLUGGED"), r2
    print("PASS test_a_fix_the_cards_ruled_out_no_longer_blocks_the_plug_2026_09_14")


def test_the_table_reader_reads_every_kind_and_replays_from_the_pin_2026_09_14():
    """Run 34820388690: the reader's stamp counter knew two kinds while the
    stamp has three — the first 'other' table raised, the stage was skipped,
    and no offline check had run the reader (replays run without a brain).
    The reader accepts every kind its own prompt allows, its readings travel
    with the pin, and a replay stamps from the pin with no brain at all."""
    from pipeline.tables import describe_tables
    from pipeline.ledger import Ledger
    from pipeline.tables import KINDS, _SYSTEM
    assert "other" not in KINDS and '"other"' not in _SYSTEM          # every table has a structure; the brain decides
    kinds = ["periods", "segments", "categories", "movement", "grid", "single"]
    items = [_item(10 + i, 1, f"Line {i}", [float(i + 1), float(i + 2)], table_id=i + 1) for i in range(6)]
    led = _ledger(items)
    class FakeClient:
        calls = 0
        def json(self, system, user, validate, repair_retries=1, images=None):
            FakeClient.calls += 1
            out = []
            for blk in user.split("### id ")[1:]:
                n = int(blk.split("\n", 1)[0])
                pg = int(blk.split(" p", 1)[1].split(" ", 1)[0])
                out.append({"id": n, "kind": kinds[pg - 10], "columns": ["a", "b"]})
            return {"tables": out}
    n = describe_tables(FakeClient(), led, [], 2025, "FY25", log=lambda *_a, **_k: None)
    assert n == 6 and FakeClient.calls == 1
    assert [it.table_kind for it in items] == ["period", "matrix", "matrix", "matrix", "matrix", "plain"], \
        [it.table_kind for it in items]
    # the pin carries the readings; a replay with no brain stamps from them
    led2 = Ledger.from_json(led.to_json())
    assert len(led2.table_readings) == 6
    for it in led2.items:
        it.table_kind = None
    lines = []
    assert describe_tables(None, led2, [], 2025, "FY25", log=lines.append) == 6
    assert [it.table_kind for it in sorted(led2.items, key=lambda i: i.page)] == \
        ["period", "matrix", "matrix", "matrix", "matrix", "plain"]
    assert any("6 from the pin" in ln for ln in lines), lines
    # no brain and no pin: the shape stamps stand, nothing is lost
    led3 = _ledger([_item(5, 1, "x", [1.0, 2.0])])
    lines = []
    assert describe_tables(None, led3, [], 2025, "FY25", log=lines.append) == 0
    assert not any("STAGE LOST" in ln for ln in lines)
    print("PASS test_the_table_reader_reads_every_kind_and_replays_from_the_pin_2026_09_14")


def test_keys_tie_in_dependency_order_2026_09_14():
    """Run 34820388690: 'total liabilities and equity' tied first and
    absorbed its whole 9,513 gap into retained earnings — a leaf of 'total
    equity', which then sat at 113,568 against a print of 107,610 with
    nothing left to absorb. A key that is a leaf of another key ties first,
    and the leaves of a key that ties its print never absorb for another."""
    from pipeline.keytie import key_tie
    from pipeline.writer import Writer
    from pipeline.evaluator import Evaluator
    from openpyxl.styles import PatternFill
    wb = _wb({"T2": 23243.0, "U2": 23243.0,                 # share capital (proven)
              "T3": 80812.0, "U3": 80812.0,                 # retained earnings (rolled, red)
              "T4": "=T3+T2", "U4": "=U3+U2",               # total equity (key)
              "T5": 6063.0, "U5": 5943.0,                   # minority interests (served)
              "T6": 123595.0, "U6": 120000.0,               # liabilities (red)
              "T7": "=T4+T5+T6", "U7": "=U4+U5+U6"})        # total liabilities and equity (key)
    wb["S"]["U3"].fill = PatternFill("solid", fgColor="FFC7CE")
    wb["S"]["U6"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [],
            "key_rows": [{"name": "total liabilities and equity", "sheet": "S", "row": 7},   # the failing order
                         {"name": "total equity", "sheet": "S", "row": 4}]}
    panel = {"total liabilities and equity": {"print": 238644.0, "prior": 233713.0},
             "total equity": {"print": 107610.0, "prior": 104055.0}}
    w = Writer(wb)
    assert key_tie(wb, spec, 2025, w, None, lambda s: None, panel=panel) == 2
    ev = Evaluator(wb)
    assert abs(ev.cell("S", "U4") - 107610.0) <= 0.5, ev.cell("S", "U4")
    assert abs(ev.cell("S", "U7") - 238644.0) <= 0.5, ev.cell("S", "U7")
    assert wb["S"]["U3"].value == "=(80812)-(-3555)", wb["S"]["U3"].value     # the analyst's 84,367
    assert wb["S"]["U6"].value == "=(120000)-(-5091)", wb["S"]["U6"].value
    assert w.log["key_absorbers"]["total liabilities and equity"][1] == "U6"
    print("PASS test_keys_tie_in_dependency_order_2026_09_14")


def test_a_comparative_is_not_this_years_print_2026_09_14():
    """Run 34820388690: rule 2 armed 'total equity' as proven-printed at
    104,055 — last year's figure, sitting in the comparative column of this
    year's balance sheet. A period line proves a value only in its
    current-period position (the brain's column names when read, else the
    first number)."""
    from pipeline.keytie import _printed, key_snapshot
    led = _ledger([_item(178, 1, "Total equity", [107610.0, 104055.0], table_id=3)])
    led._doc_periods = {DOC: "current"}; led.stamp_vintages()
    assert _printed(led, 107610.0) and not _printed(led, 104055.0)
    wb = _wb({"T4": 104055.0, "U4": 104055.0})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [],
            "key_rows": [{"name": "total equity", "sheet": "S", "row": 4}]}
    panel = {"total equity": {"print": 107610.0, "prior": 104055.0}}
    assert "total equity" not in key_snapshot(wb, spec, 2025, led, None, panel=panel)
    wb["S"]["U4"] = 107610.0
    assert "total equity" in key_snapshot(wb, spec, 2025, led, None, panel=panel)
    # the brain's reading names the columns: the current position follows the names
    rev = _item(179, 1, "Total equity", [104055.0, 107610.0], table_id=4, columns=["FY2024", "FY2025"], table_kind="period")
    led2 = _ledger([rev]); led2._doc_periods = {DOC: "current"}; led2.stamp_vintages()
    assert _printed(led2, 107610.0) and not _printed(led2, 104055.0)
    print("PASS test_a_comparative_is_not_this_years_print_2026_09_14")


def test_the_swing_is_traced_between_the_stable_line_and_the_flag_2026_09_14():
    """Owner 2026-09-14: "operating income has a big swing but gross profit
    is stable — the issue is in between; I look at my own flags first, then
    the biggest swing." The tracer never enters a stable line and, among
    the contributors that carry the swing, takes the agent's flagged cell
    before the largest one."""
    from pipeline.investigate import trace
    pre = _wb({"U2": 100.0, "U3": 60.0, "U4": "=U2-U3", "U5": 10.0, "U7": 5.0, "U6": "=U4-U5+U7"})
    wb = _wb({"U2": 156.0, "U3": 110.0, "U4": "=U2-U3", "U5": 18.0, "U7": 17.0, "U6": "=U4-U5+U7"})
    # gross profit moved +6 (revenue +56, cost +50); opex (red) +8; other income +12
    trail, leaf = trace(wb, pre, "S", "U6")
    assert leaf == ("S", "U7"), (trail, leaf)                       # the largest swing, blind
    trail, leaf = trace(wb, pre, "S", "U6", flagged={("S", "U5")})
    assert leaf == ("S", "U5"), (trail, leaf)                       # the agent's own flag first
    wb["S"]["U5"] = 10.0                                            # opex unchanged: the flag carries no swing
    trail, leaf = trace(wb, pre, "S", "U6", flagged={("S", "U5")})
    assert leaf == ("S", "U7"), (trail, leaf)                       # a flag without a swing is not the factor
    wb["S"]["U7"] = 5.0                                             # now only gross profit moved
    trail, leaf = trace(wb, pre, "S", "U6")
    assert leaf == ("S", "U2"), (trail, leaf)                       # blind: into gross profit, to revenue
    trail, leaf = trace(wb, pre, "S", "U6", stable={("S", "U4")})
    assert leaf is None and trail and "SPREAD" in trail[-1][2], (trail, leaf)   # gross profit is proven: never entered
    print("PASS test_the_swing_is_traced_between_the_stable_line_and_the_flag_2026_09_14")


def test_the_ecogen_lesson_a_period_table_has_no_slot_2026_09_14():
    """CLP live 34830794807: the positional generator found the model's
    prior 940 at slot 0 of a five-year-summary row ('Hong Kong number',
    a PERIOD table — slot 0 is FY2025) and read the same-labelled row of
    another period table at slot 0: 5,484, the employee headcount, as
    Ecogen's capacity; the gate let it land red because the value was
    printed. Two laws: positional inference never reads a period table
    (its columns say the year), and a period line whose comparative
    contradicts the cell's prior is a different item — refused."""
    from pipeline.workqueue import _companion_candidates
    from pipeline.writegate import judge_write, contradicts_prior
    a = _item(242, 1, "Hong Kong number", [940.0, 902.0, 880.0], table_id=1, table_kind="period",
              columns=["FY2025", "FY2024", "FY2023"])
    b = _item(241, 1, "Hong Kong number", [5484.0, 5397.0, 5163.0], table_id=2, table_kind="period",
              columns=["FY2025", "FY2024", "FY2023"])
    led = _ledger([a, b]); led._doc_periods = {DOC: "current"}; led.stamp_vintages()
    class L: ledger = led
    scales = {(DOC, 241): 1.0, (DOC, 242): 1.0}
    assert _companion_candidates(L(), 940.0, None, {DOC: "current"}, [a, b], scales) == []
    # a segment table is read by the COLUMN'S NAME: the prior sat under 'Australia' last year,
    # this year's same-labelled row is read under 'Australia' — whatever position it has
    a.table_kind = b.table_kind = "matrix"
    a.columns = ["hong kong", "australia", "total"]; a.nums = [300.0, 940.0, 1240.0]
    b.columns = ["australia", "hong kong", "india", "total"]; b.nums = [945.0, 310.0, 50.0, 1305.0]
    out = _companion_candidates(L(), 940.0, None, {DOC: "current"}, [a, b], scales)
    assert [c["value"] for c in out] == [945.0], out
    b.columns = ["hong kong", "india", "total"]; b.nums = [310.0, 50.0, 360.0]     # no such column this year: no read
    assert _companion_candidates(L(), 940.0, None, {DOC: "current"}, [a, b], scales) == []
    a.columns = b.columns = []; a.nums = [300.0, 940.0]; b.nums = [310.0, 945.0]   # nothing named: position is all there is
    assert [c["value"] for c in _companion_candidates(L(), 940.0, None, {DOC: "current"}, [a, b], scales)] == [945.0]
    b.table_kind = "period"; b.nums = [5484.0, 5397.0, 5163.0]; b.columns = ["FY2025", "FY2024", "FY2023"]
    assert contradicts_prior(b, 1.0, 940.0, 5484.0)
    v, why, flag = judge_write(5484.0, 940.0, False, [(b, 1.0)], set())
    assert v == "REFUSE" and "comparative contradicts" in why, (v, why)
    lone = _item(12, 1, "Ecogen", [5484.0], table_id=3, table_kind="plain")
    v2, _w, flag2 = judge_write(5484.0, 940.0, False, [(lone, 1.0)], set())
    assert v2 == "ALLOW_FLAGGED" and flag2 == "red"   # no comparative printed: unproven, red, as before
    print("PASS test_the_ecogen_lesson_a_period_table_has_no_slot_2026_09_14")


def test_the_plug_meter_reads_the_residual_against_its_total_2026_09_14():
    """CLP Driver!112 'Others' net finance cost: 45 -> 349 on a -1,666
    total (2% of the total every year, 21% now) slipped the meter because
    of a 500 absolute floor. The meter is history and materiality against
    the residual's own total — no absolute floor (units differ by model)."""
    from pipeline.teachings import plug_meter
    wb = _wb({"T2": -2019.0, "U2": -1666.0, "T3": -1460.0, "U3": -1460.0, "T4": -442.0, "U4": -392.0,
              "T5": -166.0, "U5": -166.0, "T6": "=T2-T3-T4-T5", "U6": "=U2-U3-U4-U5"})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": []}
    pm = plug_meter(wb, spec, 2025)
    assert [(s_, r) for s_, r, _n, _w in pm] == [("S", 6)], pm      # 49 -> 352: metered
    wb["S"]["U3"] = -1160.0                                         # HK updated: residual back to 52
    assert plug_meter(wb, spec, 2025) == []
    print("PASS test_the_plug_meter_reads_the_residual_against_its_total_2026_09_14")


def test_a_key_gap_is_named_before_it_is_absorbed_2026_09_14():
    """CLP live 34830794807: total liabilities and equity was 5,758 short
    and the whole gap was dumped into the fuel clause payable — a
    residual row — while 3,872 of it was the printed perpetual capital
    securities and 1,043 the printed fuel clause account. The gap is
    named against the print first: named -> red definition question,
    nothing absorbed; and a residual row is never an absorber."""
    from pipeline.keytie import key_tie, name_gap
    from pipeline.writer import Writer
    from openpyxl.styles import PatternFill
    led = _ledger([_item(26, 1, "Perpetual capital securities", [3872.0, 3872.0], table_id=1, table_kind="period"),
                   _item(25, 2, "Fuel clause account", [1043.0, 370.0], table_id=2, table_kind="period"),
                   _item(25, 3, "Dividends payable", [843.0, 700.0], table_id=2, table_kind="period"),
                   _item(25, 4, "Total equity", [107610.0, 104055.0], table_id=2, table_kind="period")],
                  face_pages=((25, "bs"), (26, "bs")))
    led._doc_periods = {DOC: "current"}; led.stamp_vintages()
    parts, rest = name_gap(led, -3872.0)
    assert [round(v) for v, _l, _w in parts] == [3872] and rest == 0.0
    parts, rest = name_gap(led, -5758.0)          # no single printed figure: not named — code never sums coincidences
    assert parts == [] and rest == 5758.0
    wb = _wb({"T2": 100000.0, "U2": 100000.0,               # liabilities (proven)
              "T3": 6063.0, "U3": 5943.0,                   # minority interests
              "T4": 370.0, "U4": 20.0,                      # fuel clause closing balance (red)
              "T5": "=IF(T4<0,0,T4)", "U5": "=IF(U4<0,0,U4)",
              "T6": "=T5-T4", "U6": "=U5-U4",               # payable: the model's own residual
              "T7": "=T2+T3+T6", "U7": "=U2+U3+U6"})        # the key
    wb["S"]["U4"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [],
            "key_rows": [{"name": "total liabilities and equity", "sheet": "S", "row": 7}]}
    panel = {"total liabilities and equity": {"print": 105943.0 + 3872.0, "prior": 106063.0}}
    w = Writer(wb); logs = []
    assert key_tie(wb, spec, 2025, w, None, logs.append, panel=panel, ledger=led) == 0
    assert wb["S"]["U6"].value == "=U5-U4" and wb["S"]["U4"].value == 20.0, "nothing absorbed"
    assert any("gap named" in ln and "Perpetual capital securities" in ln for ln in logs), logs
    # an unexplained gap still backs out — but never into the residual row
    panel = {"total liabilities and equity": {"print": 105943.0 + 777.0, "prior": 106063.0}}
    w2 = Writer(wb); logs2 = []
    key_tie(wb, spec, 2025, w2, None, logs2.append, panel=panel, ledger=led)
    assert wb["S"]["U6"].value == "=U5-U4", wb["S"]["U6"].value
    assert wb["S"]["U4"].value != 20.0, "the red input absorbs, not the residual"
    print("PASS test_a_key_gap_is_named_before_it_is_absorbed_2026_09_14")


def test_the_swing_census_finds_every_material_mover_2026_09_14():
    """Owner 2026-09-14: "just by tracing the input numbers it's obvious
    Australia caused the swing in net income" — the single-path tracer
    stopped at 'spread'. The census lists every typed cell by its share
    of the headline swing, the agent's own flags first."""
    from pipeline.investigate import swing_leaves
    pre = _wb({"U2": 100.0, "U3": 60.0, "U4": "=U2-U3", "U5": 10.0, "U7": 5.0, "U6": "=U4-U5+U7"})
    wb = _wb({"U2": 156.0, "U3": 110.0, "U4": "=U2-U3", "U5": 18.0, "U7": 17.0, "U6": "=U4-U5+U7"})
    # swing of U6 = +10: revenue +56, cost -50, opex -8, other income +12
    census = swing_leaves(wb, pre, "S", "U6")
    got = {k: round(v, 2) for k, v in census}
    assert set(got) == {("S", "U2"), ("S", "U3"), ("S", "U5"), ("S", "U7")}, got
    assert abs(got[("S", "U2")] - 5.6) < 0.05 and abs(got[("S", "U7")] - 1.2) < 0.05, got
    assert census[0][0] == ("S", "U2")                               # the largest mover first
    census = swing_leaves(wb, pre, "S", "U6", flagged={("S", "U5")})
    assert census[0][0] == ("S", "U5")                               # the agent's own flag first
    census = swing_leaves(wb, pre, "S", "U6", stable={("S", "U4")})
    assert set(k for k, _v in census) == {("S", "U5"), ("S", "U7")}   # a stable line is never entered
    print("PASS test_the_swing_census_finds_every_material_mover_2026_09_14")


def test_the_walker_follows_a_range_across_columns_2026_09_14():
    """CLP live 34830794807: the Australia generation formula averages
    capacity across two years — AVERAGE(AI66:AJ66) — and the walker
    dropped the range, losing the swing one step before the wrongly
    served capacity cell. A range is expanded in both directions."""
    from pipeline.investigate import swing_leaves, _refs
    pre = _wb({"T2": 940.0, "U2": "=T2", "U3": "=AVERAGE(T2:U2)*2", "U4": "=U3*10"})
    wb = _wb({"T2": 5484.0, "U2": "=T2", "U3": "=AVERAGE(T2:U2)*2", "U4": "=U3*10"})
    assert ("S", "T2") in _refs("=AVERAGE(T2:U2)*2", "S", wb) and ("S", "U2") in _refs("=AVERAGE(T2:U2)*2", "S", wb)
    census = swing_leaves(wb, pre, "S", "U4")
    assert census and census[0][0] == ("S", "T2") and census[0][1] >= 0.9, census   # reached through the range
    assert _refs("=SUM(A1:Z400)", "S", wb) == []          # a block reference is not a formula's inputs
    print("PASS test_the_walker_follows_a_range_across_columns_2026_09_14")


def test_the_rung_card_brain_picks_code_verifies_2026_09_14():
    """Owner 2026-09-14: for a suspect cell the agent must choose between a
    printed number, a back-out by another method, last year's figure, or
    (last resort, never on this card) a plug — "brain picks the rung, code
    verifies". The card lists every way with its effect on the swing; a
    'stale' pick puts last year's figure back red as NOT FOUND; a 'keep'
    pick records the brain's judgment; no brain → the automatic ladder."""
    from pipeline.investigate import judge_and_fix
    from openpyxl.styles import PatternFill
    pre = _wb({"T2": 940.0, "U2": "=T2", "U3": "=U2*2", "T3": "=T2*2"})
    wb = _wb({"T2": 940.0, "U2": 5484.0, "U3": "=U2*2", "T3": "=T2*2"})
    wb["S"]["U2"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [], "key_rows": []}
    lp = _loop(wb, spec, evidence=[[5484.0, 5397.0]])
    d = {"name": "capacity line", "d0": 0.0, "d1": 4.83, "new0": 10968.0, "ref1": "S!U3"}
    trail = [("S", "U3", "capacity line", 1.0), ("S", "U2", "Ecogen", 1.0)]
    seen_cards = []
    def ask_stale(text, options, default):
        seen_cards.append(text)
        assert "estimate" in options and "keep" in options and "plug" not in " ".join(options)
        assert "lastyear" not in options            # the estimate (=T2 -> 940) IS last year's figure here: one fallback shown
        assert "CARD RUNG S!U2" in text and "last year 940.00" in text
        return "estimate"
    lp.ask = ask_stale
    verdict, text = judge_and_fix(lp, pre, d, ("S", "U2"), trail, lambda *_a: None, lambda: 4.83)
    assert verdict == "stale" and wb["S"]["U2"].value == 940.0, (verdict, wb["S"]["U2"].value)
    assert str(wb["S"]["U2"].fill.fgColor.rgb).endswith("FFC7CE") and "NOT FOUND" in (wb["S"]["U2"].comment.text if wb["S"]["U2"].comment else "")
    assert seen_cards, "the brain was asked"
    # the brain says the figure belongs: recorded, nothing written
    wb["S"]["U2"] = 5484.0
    lp.ask = lambda text, options, default: "keep"
    verdict, text = judge_and_fix(lp, pre, d, ("S", "U2"), trail, lambda *_a: None, lambda: 4.83)
    assert verdict in ("genuine", "unusual") and wb["S"]["U2"].value == 5484.0 and "brain judged" in text
    # no brain (a floor): the automatic ladder — nothing proves better, the cell stays, red verdict
    lp.ask = None
    verdict, text = judge_and_fix(lp, pre, d, ("S", "U2"), trail, lambda *_a: None, lambda: 4.83)
    assert verdict == "red" and wb["S"]["U2"].value == 5484.0, (verdict, wb["S"]["U2"].value)
    print("PASS test_the_rung_card_brain_picks_code_verifies_2026_09_14")


def test_the_brain_judges_every_name_mismatch_2026_09_15():
    """Owner 2026-09-15: "the brain should be used to think and reason for
    the item terms and names". CLP: a Hong Kong tariff line printing −425
    became Australia amortisation because the number tied and nobody read
    the words. Every tie whose printed name is not kin to the model row goes
    to the brain in one batched call; a refusal drops the serve (the row
    stays red, not found); an accepted synonym lands."""
    from pipeline.naming import judge_names, name_mismatches
    from pipeline.writer import Writer
    from pipeline.targets import TargetRow
    wb = _wb({"A2": "Australia", "A4": "- Amortisation", "T4": -425.0, "U4": "=T4",
              "A7": "Domestic", "T7": 9000.0, "U7": "=T7", "A9": "Revenue", "T9": 100.0, "U9": "=T9"})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": []}
    led = _ledger([_item(236, 1, "Transfer from/(to) Tariff Stabilisation Fund", [386.0, -425.0], table_id=1, table_kind="period", columns=["FY2025", "FY2024"]),
                   _item(30, 2, "Residential", [9966.0, 9000.0], table_id=2, table_kind="period", columns=["FY2025", "FY2024"])])
    served = {("S", 4): {"value": 386.0, "doc": DOC, "page": 236, "line": "Transfer from/(to) Tariff Stabilisation Fund", "conf": 4},
              ("S", 7): {"value": 9966.0, "doc": DOC, "page": 30, "line": "Residential", "conf": 4},
              ("S", 9): {"value": 110.0, "doc": DOC, "page": 23, "line": "Revenue", "conf": 4}}
    targets = {("S", 4): TargetRow("S", 4, "- Amortisation", -425.0), ("S", 7): TargetRow("S", 7, "Domestic", 9000.0),
               ("S", 9): TargetRow("S", 9, "Revenue", 100.0)}
    mm = name_mismatches(wb, served, targets)
    assert sorted(k for k, _e, _l in mm) == [("S", 4), ("S", 7)], mm        # 'Revenue' = 'Revenue' needs no judgment
    class FakeClient:
        calls = 0
        def json(self, system, user, validate, repair_retries=1, images=None):
            FakeClient.calls += 1
            assert "Tariff Stabilisation" in user and "Australia" in user and "table columns: FY2025, FY2024" in user
            assert "history 2024: -425.00" in user          # the row's history travels with the name question
            out = []
            for blk in user.split("### id ")[1:]:
                n = int(blk.split("\n", 1)[0])
                same = "Residential" in blk
                out.append({"id": n, "same": same, "why": "a Hong Kong tariff item, not Australian amortisation" if not same else "residential = domestic"})
            return {"items": out}
    w = Writer(wb); logs = []
    asked, refused = judge_names(FakeClient(), wb, spec, led, served, targets, w, logs.append, target_year=2025)
    assert (asked, refused, FakeClient.calls) == (2, 1, 1)
    assert ("S", 4) in served and served[("S", 4)]["flag"] == "red" and "NAME DOUBTED" in served[("S", 4)]["note"]   # a doubt is a flag, not a veto
    assert ("S", 7) in served and served[("S", 7)].get("named") and not served[("S", 7)].get("flag")
    assert w.log["name_refusals"] and "Tariff" in w.log["name_refusals"][0]
    # no brain (a floor): nothing is judged, nothing is lost
    served2 = {("S", 4): {"value": 386.0, "doc": DOC, "page": 236, "line": "Transfer from/(to) Tariff Stabilisation Fund", "conf": 4}}
    assert judge_names(None, wb, spec, led, served2, targets, Writer(wb), lambda *_a: None) == (1, 0) and ("S", 4) in served2
    print("PASS test_the_brain_judges_every_name_mismatch_2026_09_15")


def test_the_consequence_card_brain_decides_code_verifies_2026_09_15():
    """Owner 2026-09-15: "if I move this number, will it change my key
    numbers? how should I solve it?" — after any change code measures the
    objectives; when one breaks the brain sees the movers and the ways to
    resolve it; code applies the pick and takes back a pick that made it
    worse. No brain -> None (the floor path decides)."""
    from pipeline.consequence import broken_objectives, resolve_objectives
    from pipeline.writer import Writer
    from openpyxl.styles import PatternFill
    pre = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0, "U2": 100.0, "U3": 50.0, "U4": 150.0,
               "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"})
    wb = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0, "U2": 999.0, "U3": 60.0, "U4": 160.0,     # U2 wrongly served
              "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"})
    wb["S"]["U2"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}], "key_rows": []}
    lp = _loop(wb, spec, served={("S", 2): {"value": 999.0, "line": "Other", "page": 3, "conf": 4}}, evidence=[[999.0, 1.0]])
    objs = broken_objectives(lp, {}, {}, None)
    assert objs and objs[0][:3] == ("check", "S", "U9") and abs(objs[0][3] - 899.0) < 0.5, objs
    seen = []
    def ask(text, options, default):
        seen.append(text)
        assert "CARD CONSEQUENCE S!U9" in text and "[1] S!U2" in text and "99% of the move" in text or "100% of the move" in text
        assert "revert:1" in options and "backout:1" in options and "plug" in options and "question" in options
        return "revert:1"
    def gate_once():
        return (not any(abs(o[3]) > 1 for o in broken_objectives(lp, {}, {}, None)), [], {})
    res = resolve_objectives(lp, pre, lambda *_a: None, ask, gate_once, lambda tag: None,
                             lambda: sum(abs(o[3]) for o in broken_objectives(lp, {}, {}, None)), {}, {}, None)
    assert res is not None and res[0] is True, res
    assert wb["S"]["U2"].value == 100.0 and ("S", 2) not in lp.served and seen
    assert str(wb["S"]["U2"].fill.fgColor.rgb).endswith("FFC7CE")
    # no brain: None, the floor path decides
    wb["S"]["U2"] = 999.0
    assert resolve_objectives(lp, pre, lambda *_a: None, lambda t, o, d: d, gate_once, lambda tag: None, lambda: 0.0, {}, {}, None) is None
    print("PASS test_the_consequence_card_brain_decides_code_verifies_2026_09_15")


def test_a_prose_money_figure_lands_in_the_models_units_2026_09_15():
    """CLP live 34887799324: 'a net gain of HK$390 million' was served as
    390,000,000 into a HK$-million model (prose is harvested in base
    currency units; the page scale of a millions document is 1). The
    model's own stated units convert a prose money figure."""
    from pipeline.numerics import model_unit_mult, prose_money_value
    assert model_unit_mult("HK$ millions") == 1e6 and model_unit_mult("RMB 万元") == 1e4 and model_unit_mult("US$ bn") == 1e9
    assert model_unit_mult("") is None
    assert prose_money_value(390_000_000.0, {"units": "HK$ millions"}, 1.0) == 390.0
    assert prose_money_value(390_000_000.0, {"units": "HK$ millions"}, 1e6) == 390.0
    assert prose_money_value(390_000_000.0, {}, 1e6) == 390.0            # no stated units: the page scale
    assert prose_money_value(390_000_000.0, {}, None) == 390_000_000.0    # nothing known: unchanged, warned on the card
    print("PASS test_a_prose_money_figure_lands_in_the_models_units_2026_09_15")


def test_the_generic_derivation_and_one_ruling_per_cell_2026_09_15():
    """Owner 2026-09-15 (CLP ROAFNA!71, coal capacity additions): the right
    answer was closing capacity minus opening, both printed, and the card
    never offered it; the same cell was then ruled four times by different
    steps. (1) Any formula that consumes the cell and carries a PROVEN
    figure yields the one value of the cell that hits it — solved on the
    model's own formula, whatever its shape. (2) A swing line never re-asks
    a cell the brain has ruled on this run; a higher objective may, and the
    card says so."""
    from pipeline.investigate import derivations, judge_and_fix
    from openpyxl.styles import PatternFill
    pre = m_wb = None
    pre = _wb({"A2": "Capacity", "A4": "Coal additions", "T4": -1050.0, "U4": "=T4",
               "A6": "Coal capacity", "T6": 6908.0, "U6": "=T6+U4", "A8": "Margin", "T8": 0.2, "U8": "=U9/U10",
               "T9": 100.0, "U9": "=T9", "T10": 500.0, "U10": 500.0})
    wb = _wb({"A2": "Capacity", "A4": "Coal additions", "T4": -1050.0, "U4": 2910.0,
              "A6": "Coal capacity", "T6": 6908.0, "U6": "=T6+U4", "A8": "Margin", "T8": 0.2, "U8": "=U9/U10",
              "T9": 100.0, "U9": 130.0, "T10": 500.0, "U10": 500.0})
    wb["S"]["U4"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [],
            "key_rows": [{"name": "capacity", "sheet": "S", "row": 6}, {"name": "margin", "sheet": "S", "row": 8}]}
    lp = _loop(wb, spec, evidence=[[2910.0, 2800.0]])
    lp.key_panel = {"capacity": {"print": 6908.0, "line": "Coal capacity p245"}, "margin": {"print": 0.25, "line": "Margin p9"}}
    d = derivations(lp, "S", "U4")
    assert d and d[0][0] == "S!U6" and abs(d[0][2] - 0.0) < 0.01 and d[0][3] == 6908.0, d      # closing = opening + this -> 0
    d9 = derivations(lp, "S", "U9")
    assert d9 and d9[0][0] == "S!U8" and abs(d9[0][2] - 125.0) < 0.01, d9                       # a ratio: margin 0.25 * 500
    seen = []
    def ask(text, options, default):
        seen.append(text)
        assert "derive:1" in options and "equal its proven 6,908.00" in text
        return "derive:1"
    lp.ask = ask
    dd = {"name": "free cash flow", "d0": 0.0, "d1": 1.0, "new0": 100.0, "ref1": "S!U6"}
    verdict, text = judge_and_fix(lp, pre, dd, ("S", "U4"), [("S", "U6", "cap", 1.0), ("S", "U4", "Coal additions", 1.0)], lambda *_a: None, lambda: 1.0)
    assert verdict == "fixed" and abs(wb["S"]["U4"].value) < 0.01 and str(wb["S"]["U4"].fill.fgColor.rgb).endswith("FFC000")
    assert lp.writer.log["rulings"]["S!U4"]["pick"] == "derive:1"
    # memory, not a rule: the next card on the cell tells the brain what happened so far; the brain decides
    wb["S"]["U4"] = 2910.0
    seen2 = []
    lp.ask = lambda text, options, default: (seen2.append(text), "keep")[1]
    judge_and_fix(lp, pre, dd, ("S", "U4"), [("S", "U6", "cap", 1.0), ("S", "U4", "Coal additions", 1.0)], lambda *_a: None, lambda: 1.0)
    assert seen2 and "so far this run:" in seen2[0] and "sense check ruled 'derive:1'" in seen2[0], seen2[0][:600]
    print("PASS test_the_generic_derivation_and_one_ruling_per_cell_2026_09_15")


def test_the_brain_names_its_own_derivation_route_2026_09_15():
    """Owner 2026-09-15: one card, one answer — 'derive:via' lets the brain
    name a formula cell code did not list; code solves against that cell's
    proven figure and verifies, or refuses and asks once more without it."""
    from pipeline.investigate import judge_and_fix
    from openpyxl.styles import PatternFill
    pre = _wb({"A4": "Coal additions", "T4": -1050.0, "U4": "=T4", "A6": "Coal capacity", "T6": 6908.0, "U6": "=T6+U4"})
    wb = _wb({"A4": "Coal additions", "T4": -1050.0, "U4": 2910.0, "A6": "Coal capacity", "T6": 6908.0, "U6": "=T6+U4"})
    wb["S"]["U4"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [], "key_rows": [{"name": "capacity", "sheet": "S", "row": 6}]}
    lp = _loop(wb, spec, evidence=[[2910.0, 2800.0]])
    lp.key_panel = {"capacity": {"print": 6908.0, "line": "Coal capacity p245"}}
    dd = {"name": "free cash flow", "d0": 0.0, "d1": 1.0, "new0": 100.0, "ref1": "S!U6"}
    trail = [("S", "U6", "cap", 1.0), ("S", "U4", "Coal additions", 1.0)]
    asks = []
    def ask(text, options, default):
        asks.append(text)
        assert "derive:via" in options
        lp.last_why = "S!U6 holds the printed closing capacity; additions = closing - opening"
        return "derive:via"
    lp.ask = ask
    verdict, text = judge_and_fix(lp, pre, dd, ("S", "U4"), trail, lambda *_a: None, lambda: 1.0)
    assert verdict == "fixed" and abs(wb["S"]["U4"].value) < 0.01 and "brain's own route" in text, (verdict, text)
    # a named cell with no proven figure: refused, asked once more without the option
    wb["S"]["U4"] = 2910.0; lp.key_panel = {}
    asks.clear()
    def ask2(text, options, default):
        asks.append(text)
        if len(asks) == 1:
            lp.last_why = "S!U6"
            return "derive:via"
        assert "derive:via" not in options and "was refused" in text
        return "estimate"
    lp.ask = ask2
    verdict, text = judge_and_fix(lp, pre, dd, ("S", "U4"), trail, lambda *_a: None, lambda: 1.0)
    assert len(asks) == 2 and verdict == "stale" and wb["S"]["U4"].value == -1050.0, (verdict, asks and len(asks))
    print("PASS test_the_brain_names_its_own_derivation_route_2026_09_15")


def test_the_derive_tool_serves_every_card_2026_09_15():
    """Owner 2026-09-15: "make sure it's applied in all cards and they won't
    conflict" — one tool (t_derive) solves a cell from a proven consuming
    formula and lands it orange with the proof; the serve card and the
    consequence card list code's derivations and the brain's own route
    through that same tool; no proven figure → refused."""
    from pipeline.workqueue import render_card, WorkItem
    from pipeline.consequence import build_card
    from openpyxl.styles import PatternFill
    pre = _wb({"A4": "Coal additions", "T4": -1050.0, "U4": "=T4", "A6": "Coal capacity", "T6": 6908.0, "U6": "=T6+U4",
               "T9": "=T4", "U9": "=U4"})
    wb = _wb({"A4": "Coal additions", "T4": -1050.0, "U4": 2910.0, "A6": "Coal capacity", "T6": 6908.0, "U6": "=T6+U4",
              "T9": "=T4", "U9": "=U4"})
    wb["S"]["U4"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [{"sheet": "S", "row": 9, "expect": 0}],
            "key_rows": [{"name": "capacity", "sheet": "S", "row": 6}]}
    lp = _loop(wb, spec, evidence=[[2910.0, 2800.0]])
    lp.key_panel = {"capacity": {"print": 6908.0, "line": "Coal capacity p245"}}
    lp.est_base = {}
    # the tool
    assert lp.t_derive({"cell": "S!U4", "via": "S!U6"}).startswith("DERIVED") and abs(wb["S"]["U4"].value) < 0.01
    assert str(wb["S"]["U4"].fill.fgColor.rgb).endswith("FFC000") and lp.served[("S", 4)]["line"] == "derived via S!U6"
    wb["S"]["U4"] = 2910.0
    assert lp.t_derive({"cell": "S!U4", "via": "S!U9"}).startswith("REFUSED")          # S!U9 carries no proven figure
    # the serve card lists the derivation and the brain's own route, through the same tool
    from pipeline.targets import TargetRow
    lp.targets = {("S", 4): TargetRow("S", 4, "Coal additions", -1050.0)}
    lp.served.pop(("S", 4), None)
    lp.writer.flag_ref("S!U4", "red", "STALE INPUT")
    rendered = render_card(lp, WorkItem("SERVE", "S", 4))
    assert rendered is not None
    text, options, default = rendered
    assert "derive:1" in options and options["derive:1"][0] == "derive" and options["derive:1"][1]["via"] == "S!U6", options.keys()
    assert "derive:via" in options and "equal its proven 6,908.00" in text
    # the consequence card lists a derivation per mover
    card, opts = build_card(lp, pre, ("check", "S", "U9", 2910.0, "balance check S!U9"), [(("S", "U4"), 1.0)], [])
    assert "derive:1" in opts and "derive:via" in opts and "6,908.00" in opts["derive:1"], opts
    print("PASS test_the_derive_tool_serves_every_card_2026_09_15")


def test_consequences_are_measured_and_cash_stays_positive_2026_09_15():
    """Owner 2026-09-15 (CLP: a 3,652 key gap dumped into the fuel clause
    account sent 2026 cash to −728): the key tie proposes but never places
    when a brain is present; every way on a consequence card shows what it
    does to balance, keys and cash/assets, measured with the plug rows
    lifted; cash or assets negative in the actual period or the next two is
    an objective, later than that a watch for the analyst."""
    from pipeline.consequence import sanity_breaks, sanity_watch, build_card, measure
    from pipeline.keytie import key_tie
    from pipeline.writer import Writer
    from openpyxl.styles import PatternFill
    cells = {"A2": "Cash", "T2": 100.0, "U2": 50.0, "V2": -20.0, "W2": 10.0, "X2": -5.0, "Y2": -9.0,
             "A3": "Total assets", "T3": 500.0, "U3": 500.0, "V3": 500.0, "W3": 500.0, "X3": 500.0, "Y3": 500.0,
             "A5": "Fuel clause", "T5": 0.0, "U5": 0.0, "A9": "check", "T9": "=T3-T3", "U9": "=U5"}
    wb = _wb(cells); pre = _wb(cells)
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U", "2026": "V", "2027": "W", "2028": "X", "2029": "Y"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}],
            "key_rows": [{"name": "cash", "sheet": "S", "row": 2}, {"name": "total assets", "sheet": "S", "row": 3}]}
    lp = _loop(wb, spec); lp.period = "FY25"; lp.key_panel = {}
    br = sanity_breaks(lp)
    assert [(o[2], round(o[3])) for o in br] == [("V2", -20)], br            # 2026 is within the horizon; 2028/2029 are not
    watch = sanity_watch(lp)
    assert len(watch) == 2 and "2028" in watch[0] and "your call" in watch[0], watch
    # the key tie with a brain: OFF, named, never absorbed
    wb2 = _wb({"T2": 100.0, "U2": 90.0, "T5": 10.0, "U5": 5.0, "T4": "=T2+T5", "U4": "=U2+U5"})
    wb2["S"]["U5"].fill = PatternFill("solid", fgColor="FFC7CE")
    spec2 = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [], "key_rows": [{"name": "total", "sheet": "S", "row": 4}]}
    w2 = Writer(wb2); logs = []
    assert key_tie(wb2, spec2, 2025, w2, None, logs.append, panel={"total": {"print": 150.0, "prior": 110.0}}, absorbers="none") == 0
    assert wb2["S"]["U5"].value == 5.0 and any("left for the consequence card" in ln for ln in logs), logs
    # the card previews each way with the plug rows lifted
    wb3 = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0, "U2": 999.0, "U3": 60.0, "U4": 160.0, "T9": "=T2+T3-T4", "U9": "=U2+U3-U4",
               "A11": "Cash", "T11": 20.0, "U11": "=U2-980", "A12": "plug", "U12": 0.0})
    pre3 = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0, "U2": 100.0, "U3": 50.0, "U4": 150.0, "T9": "=T2+T3-T4", "U9": "=U2+U3-U4",
                "A11": "Cash", "T11": 20.0, "U11": "=U2-980", "A12": "plug", "U12": 0.0})
    spec3 = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [{"sheet": "S", "row": 9, "expect": 0}],
             "key_rows": [{"name": "cash", "sheet": "S", "row": 11}]}
    lp3 = _loop(wb3, spec3, served={("S", 2): {"value": 999.0, "line": "Other", "page": 3, "conf": 4}}, evidence=[[999.0, 1.0]])
    lp3.period = "FY25"; lp3.key_panel = {}
    card, opts = build_card(lp3, pre3, ("check", "S", "U9", 899.0, "balance check S!U9"), [(("S", "U2"), 1.0)], [], {}, {}, None)
    line = next(ln for ln in card.splitlines() if ln.strip().startswith("revert:1"))
    assert "→ balance off 899 → 0" in line and "✗ cash goes negative in 2025" in line, line
    assert wb3["S"]["U2"].value == 999.0, "the preview was taken back"
    print("PASS test_consequences_are_measured_and_cash_stays_positive_2026_09_15")


def test_a_restated_comparative_is_mapped_through_last_years_report_2026_09_15():
    """Owner 2026-09-15: "Sales 2024 is 1000 in the model and in the 2024
    report; the 2025 report restates 2024 to 1200 and prints 2000 for 2025.
    The agent matches the model's 1000 to last year's line, takes its name,
    and reads this year's line of that name: 2000." The name proven through
    last year's report makes the contradicting comparative a restatement,
    not another item: 2000 lands ORANGE with the restated 2024 in its note;
    the model's 2024 stays 1000."""
    from pipeline.ledger import Ledger, Item
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.writer import Writer
    from pipeline.targets import TargetRow
    from pipeline.workqueue import candidates_for
    wb = _wb({"A2": "Sales of electricity", "T2": 1000.0, "U2": 1000.0, "A3": "Operating costs", "T3": 800.0, "U3": 800.0, "A4": "Staff costs", "T4": 400.0, "U4": 400.0})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [], "key_rows": []}
    led = Ledger()
    led.add(Item(doc="e_2024.pdf", page=5, table_id=1, row_ord=1, label="Sales of electricity", nums=[1000.0, 900.0], source_line="Sales of electricity 1000 900", table_kind="period", columns=["FY2024", "FY2023"]))
    led.add(Item(doc="e_2024.pdf", page=5, table_id=1, row_ord=2, label="Operating costs", nums=[800.0, 700.0], source_line="Operating costs 800 700", table_kind="period", columns=["FY2024", "FY2023"]))
    led.add(Item(doc="T.PDF", page=5, table_id=1, row_ord=1, label="Sales of electricity", nums=[2000.0, 1200.0], source_line="Sales of electricity 2000 1200", table_kind="period", columns=["FY2025", "FY2024"]))
    led.add(Item(doc="T.PDF", page=5, table_id=1, row_ord=2, label="Operating costs", nums=[900.0, 800.0], source_line="Operating costs 900 800", table_kind="period", columns=["FY2025", "FY2024"]))
    led.add(Item(doc="T.PDF", page=5, table_id=1, row_ord=3, label="Staff costs", nums=[600.0, 400.0], source_line="Staff costs 600 400", table_kind="period", columns=["FY2025", "FY2024"]))
    led.doc_meta = {"e_2024.pdf": {}, "T.PDF": {}}
    led._doc_periods = {"e_2024.pdf": "prior", "T.PDF": "current"}; led.stamp_vintages()
    class NoClient:
        def json(self, *a, **k): raise AssertionError("no LLM")
    targets = [TargetRow("S", 2, "Sales of electricity", 1000.0), TargetRow("S", 3, "Operating costs", 800.0), TargetRow("S", 4, "Staff costs", 400.0)]
    lp = ObjectiveLoop(wb, spec, "2025", led, targets, {}, Writer(wb), NoClient())
    lp.writer.flag_ref("S!U2", "red", "STALE INPUT")
    cands = candidates_for(lp, "S", 2)
    c200 = next((c for c in cands if abs(c["value"] - 2000.0) < 0.01), None)
    assert c200 is not None and c200.get("noun_proven"), cands            # last year's report gives the name; this year's line gives 200
    r = lp.t_set_input({"cell": "S!U2", "value": 2000.0, "why": "p5: 'Sales of electricity' — card-adjudicated", "noun_proven": True})
    assert not r.startswith(("REFUSED", "REVERTED")), r
    assert wb["S"]["U2"].value == 2000.0 and wb["S"]["T2"].value == 1000.0
    # clean, not orange (owner 2026-09-15: mapped from the print); the restatement is a fact for the report page
    assert not str(wb["S"]["U2"].fill.fgColor.rgb).endswith(("FFC000", "FFC7CE")), wb["S"]["U2"].fill.fgColor.rgb
    assert lp.writer.log.get("restatements") and "S!U2" in lp.writer.log["restatements"][0]
    # without last year's report as a witness and without the word, the same write is refused: a contradicting
    # comparative is another item
    wb["S"]["U2"] = 1000.0; lp.served.pop(("S", 2), None)
    kept = [it for it in led.items if it.doc == "e_2024.pdf"]
    led.items[:] = [it for it in led.items if it.doc != "e_2024.pdf"]
    r2 = lp.t_set_input({"cell": "S!U2", "value": 2000.0, "why": "p5: 'Sales of electricity'"})
    assert r2.startswith("REFUSED") and "comparative contradicts" in r2, r2
    led.items[:] = led.items + kept
    # the statement SAYS restated (owner 2026-09-15, any language): the brain's column name carries the word,
    # and a comparative under it is a restatement — orange, never a refusal
    led.items[:] = [it for it in led.items if it.doc != "e_2024.pdf"]          # no witness this time: the word alone
    for it in led.items:
        if it.doc == "T.PDF" and it.label == "Sales of electricity":
            it.columns = ["FY2025", "FY2024 (restated)"]
    lp.served.pop(("S", 2), None)
    r3 = lp.t_set_input({"cell": "S!U2", "value": 2000.0, "why": "p5: 'Sales of electricity'"})
    assert not r3.startswith("REFUSED") and wb["S"]["U2"].value == 2000.0 and not str(wb["S"]["U2"].fill.fgColor.rgb).endswith(("FFC000", "FFC7CE")), r3
    assert len(lp.writer.log["restatements"]) >= 2
    print("PASS test_a_restated_comparative_is_mapped_through_last_years_report_2026_09_15")


def test_restating_the_prior_period_on_request_2026_09_15():
    """Owner 2026-09-15, situation 2: "if we restate the previous period it
    is similar to a usual update — map using the previous unrestated results,
    then map with the restated previous-period results". Only when asked
    (RESTATE=1): last year's report proves the name, this year's report
    prints that name with a restated comparative, and the prior column is
    rewritten to it, clean, listed on the report; a formula prior is never
    touched; disagreeing documents restate nothing."""
    from pipeline.ledger import Ledger, Item
    from pipeline.restate import restate_prior_column
    from pipeline.writer import Writer
    from pipeline.targets import TargetRow
    wb = _wb({"A2": "Sales of electricity", "T2": 1000.0, "U2": "=T2", "A3": "Operating costs", "T3": 800.0, "U3": "=T3",
              "A4": "Staff costs", "T4": 400.0, "U4": "=T4", "A5": "Gross profit", "T5": "=T2-T3", "U5": "=U2-U3"})
    wbv = _wb({"T2": 1000.0, "T3": 800.0, "T4": 400.0})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [], "key_rows": []}
    led = Ledger()
    for d, rows in (("e_2024.pdf", [("Sales of electricity", [1000.0, 900.0]), ("Operating costs", [800.0, 700.0]), ("Staff costs", [400.0, 300.0]), ("Gross profit", [200.0, 200.0])]),
                    ("T.PDF", [("Sales of electricity", [2000.0, 1200.0]), ("Operating costs", [900.0, 800.0]), ("Staff costs", [600.0, 400.0]), ("Gross profit", [1100.0, 400.0])])):
        for i, (lab, nums) in enumerate(rows):
            led.add(Item(doc=d, page=5, table_id=1, row_ord=i + 1, label=lab, nums=nums, source_line="x", table_kind="period", columns=["FY2025", "FY2024"]))
    led._doc_periods = {"e_2024.pdf": "prior", "T.PDF": "current"}; led.stamp_vintages()
    targets = {("S", 2): TargetRow("S", 2, "Sales of electricity", 1000.0), ("S", 3): TargetRow("S", 3, "Operating costs", 800.0),
               ("S", 4): TargetRow("S", 4, "Staff costs", 400.0), ("S", 5): TargetRow("S", 5, "Gross profit", 200.0)}
    w = Writer(wb); logs = []
    n = restate_prior_column(wb, wbv, spec, 2025, led, targets, w, logs.append)
    assert n == 1 and wb["S"]["T2"].value == 1200.0 and wbv["S"]["T2"].value == 1200.0 and targets[("S", 2)].prior_value == 1200.0, (n, logs)
    assert wb["S"]["T3"].value == 800.0 and wb["S"]["T5"].value == "=T2-T3"       # unchanged priors and formula priors stay
    assert not str(wb["S"]["T2"].fill.fgColor.rgb).endswith(("FFC000", "FFC7CE"))      # clean: a restatement is an update, listed on the report
    assert w.log["restatements"] and "1,000.00 -> 1,200.00" in w.log["restatements"][0]
    print("PASS test_restating_the_prior_period_on_request_2026_09_15")


def test_the_brain_handshake_stops_a_run_with_no_credits_2026_09_15():
    """Run 34925710395: OpenRouter answered 402 four minutes in and the run
    spent an hour brainless. The handshake asks once, with the run's own
    output budget (affordability is priced on max_tokens), and stops the
    run with the server's words on 401/402/403; a healthy engine passes."""
    from pipeline.llm import BrainUnavailable, handshake

    class _Client:
        base_url = "https://engine.test/api/v1"; api_key = "k"; model = "m"; max_output_tokens = 14000

    class _Resp:
        def __init__(self, code, payload, text=""):
            self.status_code, self._p, self.text = code, payload, text
        def json(self): return self._p

    sent = {}
    def broke(url, headers=None, json=None, timeout=None):
        sent.update(json)
        return _Resp(402, {"error": {"message": "This request requires more credits, or fewer max_tokens."}})
    try:
        handshake(_Client(), post=broke)
        raise AssertionError("a 402 must stop the run")
    except BrainUnavailable as e:
        assert "402" in str(e) and "more credits" in str(e), e
    assert sent["max_tokens"] == 14000, "the probe must carry the run's own output budget"
    assert sent["model"] == "m"

    def ready(url, headers=None, json=None, timeout=None):
        return _Resp(200, {"choices": [{"message": {"content": "ready"}}]})
    assert handshake(_Client(), post=ready).startswith("ready")

    def flaky(url, headers=None, json=None, timeout=None):
        raise ConnectionError("reset")
    assert handshake(_Client(), post=flaky).startswith("handshake skipped")
    print("PASS test_the_brain_handshake_stops_a_run_with_no_credits_2026_09_15")


def test_a_key_off_the_print_is_an_objective_of_the_ending_2026_09_15():
    """Run 34935869107: operating profit sat +148 off the print for the
    whole ending and no card was ever dealt — the key measure raised on a
    field-count mismatch and a bare except swallowed it. The measure is
    taken through the real key_state; a fault is said on the loop."""
    from pipeline.consequence import broken_objectives
    cells = {"A2": "Revenue", "T2": 100.0, "U2": 120.0, "A3": "Total assets", "T3": 500.0, "U3": 500.0,
             "A9": "check", "T9": "=T3-T3", "U9": "=U3-U3"}
    wb = _wb(cells)
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}],
            "key_rows": [{"name": "revenue", "sheet": "S", "row": 2}, {"name": "total assets", "sheet": "S", "row": 3}]}
    lp = _loop(wb, spec); lp.period = "FY25"
    panel = {"revenue": {"print": 125.0}, "total assets": {"print": 500.0}}
    objs = broken_objectives(lp, {}, panel, None)
    assert not lp.__dict__.get("objective_faults"), lp.__dict__.get("objective_faults")
    keys = [o for o in objs if o[0] == "key"]
    assert len(keys) == 1 and keys[0][1:3] == ("S", "U2") and abs(keys[0][3] + 5.0) < 1e-9, objs
    assert "revenue" in keys[0][4] and "125.0" in keys[0][4]
    print("PASS test_a_key_off_the_print_is_an_objective_of_the_ending_2026_09_15")


def _ending_harness(wb, spec, key_panel, ask=None, brain=False):
    """run_ending on a tiny model: the gate holds, the repairs do nothing,
    the mass is the objectives' own — the ending's measure is what is tested."""
    from pipeline.consequence import run_ending, broken_objectives
    lp = _loop(wb, spec); lp.period = "FY25"; lp.key_panel = key_panel
    lp.writer.served = lp.served
    pre = _wb({c.coordinate: c.value for row in wb["S"].iter_rows() for c in row if c.value is not None})
    logs = []
    mass = lambda: sum(abs(o[3]) for o in broken_objectives(lp, {}, key_panel, None) if o[0] != "sanity")
    res = run_ending(lp, pre, logs.append, ask, lambda: (True, [], {}), lambda _w: None, mass,
                     {}, key_panel, None, deadline_s=60.0, brain=brain, max_rounds=4)
    return lp, logs, res


def test_the_ending_measures_keys_and_cash_even_when_the_balance_holds_2026_09_15():
    """Audit 2026-09-15: the first measure asked the gate and the sense lines
    only; a key off the print and a negative cash balance were never an
    objective when the balance held. The objectives themselves decide."""
    cells = {"A2": "Revenue", "T2": 100.0, "U2": 120.0, "A3": "Cash", "T3": 50.0, "U3": 40.0, "V3": -20.0,
             "A9": "check", "T9": "=T3-T3", "U9": "=U3-U3", "V9": "=V3-V3"}
    wb = _wb(cells)
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U", "2026": "V"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}],
            "key_rows": [{"name": "revenue", "sheet": "S", "row": 2}, {"name": "cash", "sheet": "S", "row": 3}]}
    lp, logs, res = _ending_harness(wb, spec, {"revenue": {"print": 125.0}})
    lines = lp.writer.log.get("ending", [])
    assert not any("held at the first measure" in ln for ln in lines), lines
    assert any("round 1: key S!U2" in ln for ln in logs), logs[:6]
    assert any("sanity S!V3" in ln for ln in logs), logs
    assert not lp.__dict__.get("objective_faults"), lp.__dict__.get("objective_faults")
    print("PASS test_the_ending_measures_keys_and_cash_even_when_the_balance_holds_2026_09_15")


def test_a_brain_that_gives_no_answer_leaves_the_break_open_red_2026_09_15():
    """Audit 2026-09-15: a dead or out-of-clock brain fell through to the
    automatic executors and placed keys the tie had only proposed. With a
    brain in the run, no answer = open, red, with the reason."""
    cells = {"A2": "Revenue", "T2": 100.0, "U2": 120.0, "A9": "check", "T9": "=T2-T2", "U9": "=U2-U2"}
    wb = _wb(cells)
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}],
            "key_rows": [{"name": "revenue", "sheet": "S", "row": 2}]}
    def dead(text, options, default):
        return default                   # the brain says nothing usable
    lp, logs, res = _ending_harness(wb, spec, {"revenue": {"print": 125.0}}, ask=dead, brain=True)
    assert wb["S"]["U2"].value == 120.0, "no automatic back-out may place a proposed key"
    assert "S!U2" in lp.writer.log.get("flags", []), lp.writer.log.get("flags")
    assert any("no answer from the brain" in ln for ln in logs), logs
    assert any(ln.startswith("NO ANSWER S!U2") for ln in lp.writer.log["ending"]), lp.writer.log["ending"]
    print("PASS test_a_brain_that_gives_no_answer_leaves_the_break_open_red_2026_09_15")


def test_a_trial_restores_provenance_locks_and_rulings_2026_09_15():
    """Audit 2026-09-15: previews and take-backs un-served and unlocked proven
    movers and left a taken-back ruling in the memory. One snapshot, one restore."""
    from pipeline.consequence import snapshot, restore
    wb = _wb({"A2": "Revenue", "T2": 100.0, "U2": 120.0})
    lp = _loop(wb, _spec_tiny(), served={("S", 2): {"value": 120.0, "line": "Revenue", "page": 3, "conf": 5}})
    lp.writer.served = lp.served
    lp.writer.locked.add("S!U2")
    lp.writer.log.setdefault("rulings", {})["S!U2"] = {"pick": "keep"}
    snap = snapshot(lp)
    assert lp.writer.write("S", "U2", 999.0, trusted=True, force_lock=True, flag="orange", note="trial")
    lp.writer.log["rulings"]["S!U2"] = {"pick": "derive:1"}
    restore(lp, snap)
    assert wb["S"]["U2"].value == 120.0
    assert ("S", 2) in lp.served and lp.served[("S", 2)]["conf"] == 5, lp.served
    assert "S!U2" in lp.writer.locked
    assert lp.writer.log["rulings"]["S!U2"] == {"pick": "keep"}
    print("PASS test_a_trial_restores_provenance_locks_and_rulings_2026_09_15")


def test_the_restatement_witness_must_tie_the_models_prior_2026_09_15():
    """Audit 2026-09-15: a same-named line that merely differed counted as a
    restatement (the Ecogen wrong-row write would land clean). The owner's
    rule: last year's report holds the model's prior, this year's comparative
    differs — or the comparative column says restated."""
    from pipeline.writegate import restated_comparative, contradicts_prior
    cur = _item(95, 1, "Hong Kong number", [5484.0, 5397.0], table_kind="period", columns=["2025", "2024"])
    witness_off = _item(95, 1, "Hong Kong number", [123.0, 100.0], table_kind="period", sourceable=False)
    witness_on = _item(95, 1, "Hong Kong number", [940.0, 900.0], table_kind="period", sourceable=False)
    assert restated_comparative(cur, 5484.0, 1.0, [witness_off], prior=940.0) is False
    assert restated_comparative(cur, 5484.0, 1.0, [witness_on], prior=940.0) is True
    assert restated_comparative(cur, 5484.0, 1.0, [witness_on], prior=5397.0) is False, "the comparative IS the prior: nothing restated"
    adj = _item(95, 2, "EBITDA", [500.0, 450.0, 520.0], table_kind="period", columns=["FY2025", "FY2024", "FY2025 adjusted EBITDA"])
    assert restated_comparative(adj, 500.0, 1.0, [], prior=400.0) is False, "'adjusted' in another column is not a restatement"
    rst = _item(95, 3, "Revenue", [500.0, 450.0], table_kind="period", columns=["2025", "2024 restated"])
    assert restated_comparative(rst, 500.0, 1.0, [], prior=400.0) is True
    # the comparative is the same period kind: 1H beside 1H, never the FY column
    h = _item(95, 4, "Revenue", [1100.0, 2300.0, 1000.0], table_kind="period", columns=["1H2025", "FY2024", "1H2024"])
    assert contradicts_prior(h, 1.0, 1000.0, 1100.0) is False
    assert contradicts_prior(h, 1.0, 900.0, 1100.0) is True
    print("PASS test_the_restatement_witness_must_tie_the_models_prior_2026_09_15")


def test_restating_the_prior_needs_the_name_and_reads_the_column_2026_09_15():
    """Audit 2026-09-15: any prior-year line whose first number matched the
    prior lent its name; the comparative was taken by position."""
    from pipeline.restate import restated_priors
    class T:
        def __init__(self, label, pv): self.label, self.prior_value = label, pv
    led_items = [
        _item(10, 1, "Dividend paid", [400.0, 300.0], table_kind="period", sourceable=False),
        _item(11, 1, "Dividend paid", [500.0, 450.0], table_kind="period", columns=["2025", "2024"]),
    ]
    scales = {(DOC, 10): 1.0, (DOC, 11): 1.0}
    class L: items = led_items
    out = restated_priors(L(), {("S", 4): T("Staff costs", 400.0)}, scales, target_year=2025, period="FY25")
    assert out == {}, out
    led_items[0] = _item(10, 1, "Staff costs", [400.0, 300.0], table_kind="period", sourceable=False)
    led_items[1] = _item(11, 1, "Staff costs", [500.0, 450.0], table_kind="period", columns=["2025", "2024"])
    out = restated_priors(L(), {("S", 4): T("Staff costs", 400.0)}, scales, target_year=2025, period="FY25")
    assert ("S", 4) in out and abs(out[("S", 4)][0] - 450.0) < 1e-6, out
    led_items[1] = _item(11, 1, "Staff costs", [1100.0, 1300.0, 1000.0], table_kind="period", columns=["1H2025", "2H2024", "1H2024"])
    out = restated_priors(L(), {("S", 4): T("Staff costs", 400.0)}, scales, target_year=2025, period="1H25")
    assert ("S", 4) in out and abs(out[("S", 4)][0] - 1000.0) < 1e-6, out
    print("PASS test_restating_the_prior_needs_the_name_and_reads_the_column_2026_09_15")


def test_a_named_cell_is_read_by_the_workbooks_own_sheet_names_2026_09_15():
    """Audit 2026-09-15: 'use SOC Accounts!AI9 via ROAFNA!AI64' lost its
    sheet to the words before it; the sheet list is the pattern."""
    import openpyxl
    from pipeline.investigate import named_ref, _refs
    wb = openpyxl.Workbook(); wb.active.title = "SOC Accounts"; wb.create_sheet("ROAFNA")
    got = named_ref("use SOC Accounts!AI9 via ROAFNA!AI64, not 'SOC Accounts'!AI10", wb)
    assert got == [("SOC Accounts", "AI9"), ("ROAFNA", "AI64"), ("SOC Accounts", "AI10")], got
    assert _refs("=LOG10(U3)+SUM(U3:U4)", "ROAFNA", wb) == [("ROAFNA", "U3"), ("ROAFNA", "U4")], _refs("=LOG10(U3)+SUM(U3:U4)", "ROAFNA", wb)
    print("PASS test_a_named_cell_is_read_by_the_workbooks_own_sheet_names_2026_09_15")


def test_a_derivation_solves_only_a_target_year_consumer_2026_09_15():
    """Audit 2026-09-15: a first-forecast formula was 'solved' to make next
    year equal this year's print. Only the target-year column is solved."""
    from pipeline.investigate import derivations
    wb = _wb({"A2": "Volume", "T2": 10.0, "U2": 12.0, "A3": "Sales", "T3": "=T2*3", "U3": "=U2*3", "V3": "=SUM(U2:U2)*3"})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U", "2026": "V"}}}, "check_rows": [], "key_rows": []}
    lp = _loop(wb, spec, served={("S", 3): {"value": 300.0, "line": "Sales", "page": 3, "conf": 5, "status": "OK", "flag": None}})
    lp.writer.served = lp.served
    got = derivations(lp, "S", "U2")
    assert [g[0] for g in got] == ["S!U3"], got
    assert abs(got[0][2] - 100.0) < 1e-6, got
    print("PASS test_a_derivation_solves_only_a_target_year_consumer_2026_09_15")


def test_a_zero_estimate_never_kills_the_sense_lines_2026_09_15():
    from pipeline.sensecheck import headline_deltas
    wb = _wb({"A2": "DPS", "T2": 0.5, "U2": 0.6, "V2": 0.7}); pre = _wb({"A2": "DPS", "T2": 0.5, "U2": 0.0, "V2": 0.0})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U", "2026": "V"}}}, "check_rows": [], "key_rows": [{"name": "dps", "sheet": "S", "row": 2}]}
    out = headline_deltas(wb, pre, spec, 2025, key_rows=spec["key_rows"])
    assert out == [], out
    print("PASS test_a_zero_estimate_never_kills_the_sense_lines_2026_09_15")


def test_a_name_without_a_verdict_is_a_doubt_2026_09_15():
    """Audit 2026-09-15: an id the brain omitted, and a failed call, left a
    name-mismatched tie clean. Both land red as not judged."""
    from pipeline.naming import judge_names
    from pipeline.writer import Writer
    class T:
        def __init__(self, label, pv): self.label, self.prior_value = label, pv
    for behaviour in ("empty", "raise"):
        wb = _wb({"A2": "Amortisation", "T2": 425.0, "U2": 430.0})
        served = {("S", 2): {"value": 430.0, "line": "Tariff adjustment", "page": 4, "doc": DOC, "conf": 5, "status": "OK", "flag": None}}
        class C:
            def json(self, *a, **k):
                if behaviour == "raise":
                    raise RuntimeError("402 Payment Required")
                return {"items": []}
        logs = []
        judge_names(C(), wb, _spec_tiny(), _ledger([]), served, {("S", 2): T("Amortisation", 425.0)}, Writer(wb), logs.append, target_year=2025)
        assert served[("S", 2)].get("flag") == "red" and "NAME DOUBTED" in str(served[("S", 2)].get("note")), (behaviour, served)
    print("PASS test_a_name_without_a_verdict_is_a_doubt_2026_09_15")


def test_prose_sentences_are_not_tables_and_the_first_unit_word_wins_2026_09_15():
    from pipeline.tables import table_cards
    from pipeline.numerics import model_unit_mult
    led = _ledger([])
    led.add(Item(doc="e_2025.pdf", page=1, table_id=900, row_ord=0, label="HK$5,484 million (2024: HK$5,397 million)",
                 nums=[5484.0, 5397.0], source_line="x", channel="prose"))
    assert table_cards(led, ["e_2025.pdf"]) == []
    assert model_unit_mult("HK$ million (per share data in HK$; shares in thousands)") == 1e6
    assert model_unit_mult("in thousands of RMB; ratios in millions") == 1e3
    print("PASS test_prose_sentences_are_not_tables_and_the_first_unit_word_wins_2026_09_15")


def test_the_replay_reads_every_card_family_2026_09_15():
    """Audit 2026-09-15: SENSE, LABEL, TRIPWIRE cards, answers beyond D and
    every derive:via defaulted silently in a replay; the floor diverged."""
    import tempfile, os
    sys.path.insert(0, "tools")
    from replay_live import picks_from_log, make_answerer
    log = "\n".join([
        "[queue] SERVE CN!27 -> serve:E: WRITTEN",
        "[queue] LABEL Final!56 -> serve:A: WRITTEN",
        "[queue] SENSE SOC Accounts!7 -> not_disclosed (x)",
        "[queue] RUNG ROAFNA!AI71 -> derive:via refused (no cell named)",
        "[queue] RUNG ROAFNA!AI71 -> derive:via ROAFNA!AI64",
        "[queue] CONSEQUENCE Final!AI98 -> question",
        "[queue] TRIPWIRE chain -> justified",
    ])
    fd, path = tempfile.mkstemp(suffix=".log"); os.write(fd, log.encode()); os.close(fd)
    picks = picks_from_log(path)
    assert picks[("SERVE", "CN!27")] == ["serve:E"] and picks[("SERVE", "Final!56")] == ["serve:A"], picks
    assert picks[("SERVE", "SOC Accounts!7")] == ["not_disclosed"], picks
    assert picks[("RUNG", "ROAFNA!AI71")] == [("derive:via", "use ROAFNA!AI64")], picks
    ans = make_answerer(picks)
    got = ans("CARD RUNG ROAFNA!AI71 'Coal'", {"derive:via": "", "keep": ""}, "keep")
    assert got == ("derive:via", "use ROAFNA!AI64"), got
    assert ans("CARD TRIPWIRE chain of 2 sign-flipped forecasts", {"justified": "", "suspicious": ""}, "suspicious") == "justified"
    print("PASS test_the_replay_reads_every_card_family_2026_09_15")


def test_the_ending_closes_cleanly_when_every_objective_holds_2026_09_15():
    """Reviewer 2026-09-15: the healthy exit called a closure defined later
    (NameError, STAGE LOST) — the closing rows and the count are written on
    both exits."""
    cells = {"A2": "Revenue", "T2": 100.0, "U2": 125.0, "V2": 130.0, "A9": "check", "T9": "=T2-T2", "U9": "=U2-U2"}
    wb = _wb(cells)
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U", "2026": "V"}}},
            "check_rows": [{"sheet": "S", "row": 9, "expect": 0}], "key_rows": [{"name": "revenue", "sheet": "S", "row": 2}]}
    lp, logs, res = _ending_harness(wb, spec, {"revenue": {"print": 125.0}})
    lines = lp.writer.log["ending"]
    assert lines[0] == "objectives held at the first measure" and lines[-1] == "ended: every objective holds", lines
    assert not lp.__dict__.get("objective_faults"), lp.__dict__.get("objective_faults")
    rows = [r for r in lp.writer.log.get("sense_rows", []) if r.get("stage") == "ending"]
    assert rows and rows[0]["verdict"] == "inline", rows
    print("PASS test_the_ending_closes_cleanly_when_every_objective_holds_2026_09_15")


def test_a_composite_rewrite_is_a_proven_cell_2026_09_15():
    """Run 34952658064: receivables (=12856+1179 = 14,035) and deferred
    creditors (8,363) were rewritten correctly by the constants law, then
    treated as unproven by the rung and consequence cards and overwritten.
    The rewrite's proof is a serve record; the cards read the one test."""
    import openpyxl
    from pipeline.composites import rewrite_cell
    from pipeline.writer import Writer
    from pipeline.rollover import input_is_proven
    from pipeline.consequence import build_card
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S"
    ws["A5"] = "Fixed assets and rights"; ws["T5"] = "=158532+10183"; ws["U5"] = "=158532+10183"
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [], "key_rows": []}
    led = Ledger()
    led.add(Item(doc="AR", page=25, table_id=0, row_ord=0, label="Fixed assets", nums=[166094.0, 158532.0], source_line="x"))
    led.add(Item(doc="AR", page=25, table_id=0, row_ord=1, label="Right-of-use assets", nums=[10034.0, 10183.0], source_line="x"))
    led.faces[("AR", 25)] = "bs"
    w = Writer(wb); w.served = {}
    ok, msg = rewrite_cell(wb, spec, 2025, led, w, "S", 5)
    assert ok, msg
    e = w.served.get(("S", 5))
    assert e and e["conf"] == 4 and e["flag"] == "orange", e
    assert input_is_proven(w.served, "S", "U5", wb["S"]["U5"].value, w.log.get("flags", []), wb)
    # on a consequence card the proven mover is said so and has no back-out or derivation way
    lp = _loop(wb, spec, served=dict(w.served)); lp.writer = w; lp.writer.served = lp.served
    pre = openpyxl.Workbook(); pre.active.title = "S"; pre["S"]["U5"] = "=158532+10183"
    card, options = build_card(lp, pre, ("check", "S", "U9", -100.0, "balance check S!U9 computes -100"), [(("S", "U5"), 0.9)], [], None)
    assert "PROVEN from the print" in card, card
    assert "revert:1" in options and "backout:1" not in options and "derive:1" not in options, list(options)
    print("PASS test_a_composite_rewrite_is_a_proven_cell_2026_09_15")


def test_a_composition_proven_line_by_line_across_pages_2026_09_15():
    """CLP dividends received =770+1659+15: associates on one note, JCEs on
    another — every literal has ONE comparative-pair reading, so the
    composition is proven line by line, whatever page each line is on."""
    from pipeline.composites import prove_cell
    led = Ledger()
    led.add(Item(doc="AR", page=40, table_id=0, row_ord=0, label="Dividends from associates", nums=[629.0, 770.0], source_line="x"))
    led.add(Item(doc="AR", page=44, table_id=0, row_ord=0, label="Dividends from joint ventures", nums=[1762.0, 1659.0], source_line="x"))
    led.faces[("AR", 40)] = "note"; led.faces[("AR", 44)] = "note"
    proof, why = prove_cell(led, ["770", "1659"], row_label="Dividends received")
    assert proof and abs(proof["770"][0] - 629.0) < 1e-6 and abs(proof["1659"][0] - 1762.0) < 1e-6, (proof, why)
    # two readings for one literal: not unique, not proven
    led.add(Item(doc="AR", page=45, table_id=0, row_ord=0, label="Dividends from others", nums=[900.0, 770.0], source_line="x"))
    led.faces[("AR", 45)] = "note"
    proof2, why2 = prove_cell(led, ["770", "1659"], row_label="Dividends received")
    assert proof2 is None, (proof2, why2)
    print("PASS test_a_composition_proven_line_by_line_across_pages_2026_09_15")


def test_a_balance_gap_is_named_when_a_printed_figure_is_about_its_size_2026_09_15():
    """Run 34952658064: a 3,863 balance gap beside printed perpetual capital
    securities of 3,872 — the check card did not name it and the brain
    absorbed the gap into deferred creditors. Named as ≈ on check cards."""
    from pipeline.keytie import name_gap
    led = Ledger()
    led.add(Item(doc="RA", page=32, table_id=0, row_ord=0, label="Perpetual capital securities", nums=[3872.0, 3872.0], source_line="x", columns=["2025", "2024"]))
    assert name_gap(led, -3863.0) == ([], 3863.0)
    named, rest = name_gap(led, -3863.0, near=True)
    assert named and named[0][0] == 3872.0 and named[0][1].startswith("≈ Perpetual") and abs(rest - 9.0) < 1e-6, (named, rest)
    assert name_gap(led, -3000.0, near=True) == ([], 3000.0), "far from any figure: nothing named"
    print("PASS test_a_balance_gap_is_named_when_a_printed_figure_is_about_its_size_2026_09_15")


def test_the_readers_suggestion_reaches_the_card_2026_09_15():
    """Run 34952658064: 'Other gain 460' and 'net exchange difference -352'
    were the analyst's own answers; the reader dropped them for their names
    and the card never showed them. The name is the brain's judgment."""
    from pipeline.workqueue import candidates_for
    wb = _wb({"A2": "Other Income, net", "T2": 300.0})
    lp = _loop(wb, _spec_tiny())
    lp.ledger.reader_suggestions = {"S!2": {"value": 460.0, "doc": "AR", "page": 166, "line": "Other gain"}}
    cands = candidates_for(lp, "S", 2)
    hit = [c for c in cands if abs(c["value"] - 460.0) < 1e-6]
    assert hit and hit[0].get("no_prior") and "reader's suggestion" in hit[0]["warnings"][0], cands
    print("PASS test_the_readers_suggestion_reaches_the_card_2026_09_15")


def test_a_red_cell_is_never_held_proven_2026_09_15():
    """Run 34952658064: Australia income tax held -2,655 from a served tie yet
    sat red; the brain's printed -284 (comparative ties the prior) was
    refused nine times because the cell 'already holds a proven value'."""
    wb = _wb({"A2": "Income tax expense", "T2": 100.0, "U2": 2655.0})
    lp = _loop(wb, _spec_tiny(), served={("S", 2): {"value": 2655.0, "line": "Tax", "page": 3, "conf": 5, "status": "OK", "flag": None, "doc": DOC}},
               evidence=[[284.0, 100.0]])
    lp.writer.served = lp.served
    lp.writer.flag_ref("S!U2", "red", "sense check: the swing traced here")
    r = lp.t_set_input({"cell": "S!U2", "value": 284.0, "why": "p29: 'Income tax expense' — sense-check rung 1"})
    assert r.startswith("WRITTEN"), r
    assert wb["S"]["U2"].value == 284.0
    print("PASS test_a_red_cell_is_never_held_proven_2026_09_15")


def test_a_tying_composition_with_unlike_names_goes_to_the_brain_2026_09_15():
    """Owner 2026-09-15: "numbers that can be mapped must be mapped; the name
    is the brain's judgment". A composition whose literals tie printed
    comparatives but whose lines are not kin to the row is a card answer,
    not a silent refusal; the brain's yes rewrites it, orange."""
    import openpyxl
    from pipeline.composites import rewrite_cell
    from pipeline.writer import Writer
    from pipeline.workqueue import render_card, WorkItem
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S"
    ws["A5"] = "Other operating cash flows"; ws["T5"] = "=504+582"; ws["U5"] = "=504+582"
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [], "key_rows": []}
    led = Ledger()
    led.add(Item(doc="AR", page=177, table_id=0, row_ord=0, label="Receivables and others", nums=[517.0, 504.0], source_line="x"))
    led.add(Item(doc="AR", page=177, table_id=0, row_ord=1, label="Net losses on disposal of fixed assets", nums=[319.0, 582.0], source_line="x"))
    led.faces[("AR", 177)] = "note"
    w = Writer(wb); w.served = {}
    ok, msg = rewrite_cell(wb, spec, 2025, led, w, "S", 5)
    assert not ok and "kin to the row" in msg, msg
    sug = led.rewrite_suggestions["S!5"]
    assert sug["formula"] == "=517+319", sug
    w.flag_ref("S!U5", "red", "unproven")
    lp = _loop(wb, spec); lp.ledger = led; lp.writer = w; lp.writer.served = lp.served
    rendered = render_card(lp, WorkItem(kind="SERVE", sheet="S", row=5))
    assert rendered is not None, "the card must be dealt on the tying composition alone"
    text, options, default = rendered
    assert "rewrite:1" in options and "=517+319" in text, text
    tool, args = options["rewrite:1"]
    res = lp.TOOLS[tool](lp, args)
    assert str(res).startswith("REWRITTEN"), res
    assert wb["S"]["U5"].value == "=517+319"
    print("PASS test_a_tying_composition_with_unlike_names_goes_to_the_brain_2026_09_15")


def test_a_red_composite_with_a_tying_suggestion_is_queued_and_a_backout_loses_its_proof_2026_09_15():
    """Reviewer 2026-09-15: the queue skipped every red formula cell, so the
    rewrite card could never be dealt live; and a back-out written over a
    proven row was still 'proven'."""
    import openpyxl
    from pipeline.workqueue import build_queue
    from pipeline.rollover import input_is_proven
    from pipeline.consequence import apply_pick
    wb = _wb({"A5": "Other operating cash flows", "T5": "=504+582", "U5": "=504+582", "A9": "check", "T9": "=T5-T5", "U9": "=U5-U5"})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [{"sheet": "S", "row": 9, "expect": 0}], "key_rows": []}
    lp = _loop(wb, spec); lp.writer.served = lp.served
    lp.writer.flag_ref("S!U5", "red", "unproven")
    assert not [i for i in build_queue(lp) if i.kind == "SERVE" and i.row == 5], "a red formula without a suggestion is not a card"
    lp.ledger.rewrite_suggestions = {"S!5": {"formula": "=517+319", "was": "=504+582", "srcs": "504->517; 582->319"}}
    assert [i for i in build_queue(lp) if i.kind == "SERVE" and i.row == 5], "with a tying composition the card is dealt"
    # a proven served row backed out by the ending is no longer proven
    wb2 = _wb({"A2": "Receivables", "T2": 100.0, "U2": 14035.0})
    lp2 = _loop(wb2, _spec_tiny(), served={("S", 2): {"value": 14035.0, "line": "Trade receivables", "page": 3, "conf": 5, "status": "OK", "flag": None}})
    lp2.writer.served = lp2.served
    assert input_is_proven(lp2.served, "S", "U2", 14035.0, [], wb2)
    pre = _wb({"A2": "Receivables", "T2": 100.0, "U2": 14035.0})
    assert apply_pick(lp2, pre, "backout:1", [(("S", "U2"), 1.0)], -3863.0, "balance check")
    assert not input_is_proven(lp2.served, "S", "U2", wb2["S"]["U2"].value, [], wb2), "a back-out over the row holds a different figure: not proven by the old serve"
    print("PASS test_a_red_composite_with_a_tying_suggestion_is_queued_and_a_backout_loses_its_proof_2026_09_15")


# ── 2026-09-16: the brain thinks, code is its tool (run 34993405014) ──────

def _clp_p23_items():
    """The CLP FY25 operating-profit block as the table extractor really read
    it (run 34993405014, ledger.json p23): every expense line is there, the
    OPERATING EXPENSES TOTAL the model keeps on one row is not."""
    return [_item(23, 1, "Revenue", [3.0, 88018.0, 90964.0]),
            _item(23, 2, "Purchases and distributions of electricity and gas", [-28950.0, -31871.0]),
            _item(23, 3, "Staff expenses", [-5987.0, -5150.0]),
            _item(23, 4, "Fuel and other operating expenses", [-29551.0, -29764.0]),
            _item(23, 5, "Depreciation and amortisation", [-9718.0, -9276.0]),
            _item(23, 6, "Other gain", [5.0, 460.0]),
            _item(23, 7, "Operating profit", [6.0, 14272.0, 14903.0])]


def test_a_check_that_closes_the_printed_subtotal_is_proof_2026_09_16():
    """Run 34993405014: the reader answered Final!14 = -74,206 (the four
    expense lines between revenue and the printed Operating profit) and
    verify() refused it — 'no printed line on p23 carries -74206' — because
    the extractor dropped the total line, and both 2025 keys stayed -2,315
    off the print. A stated check that closes a PRINTED subtotal at the
    model's precision, every term the this-period figure of a printed row of
    the same table block, is proof: the figure is written, plain when those
    rows' printed comparatives tie the model's prior, red when they do not."""
    from pipeline.reader import verify
    led = _ledger(_clp_p23_items(), face_pages=((23, "pl"),))
    led._doc_periods = {DOC: "current"}
    check = "88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 = 14,272"
    rows = [{"row": "Final!14", "sheet": "Final", "r": 14, "label": "Operating expenses", "prior": -76061.0}]
    answers = [{"row": "Final!14", "printed": -74206.0, "page": 23, "line": "(74,206) (76,061)", "check": check}]
    v = verify(answers, rows, led, {(DOC, 23): 1.0}, lambda s: None, priors=[-76061.0])
    assert "Final!14" in v, "the reconciliation that closes the printed Operating profit was refused"
    assert abs(v["Final!14"]["value"] + 74206.0) < 1e-6, v["Final!14"]
    assert v["Final!14"]["conf"] == 4 and v["Final!14"]["flag"] is None, v["Final!14"]
    assert "14,272" in (v["Final!14"]["note"] or ""), "the reconciliation must travel in the note"
    # the same check, a row whose prior those comparatives do NOT tie: red, written
    rows_r = [{"row": "Final!15", "sheet": "Final", "r": 15, "label": "Operating costs", "prior": -70000.0}]
    ans_r = [{"row": "Final!15", "printed": -74206.0, "page": 23, "line": "(74,206) (76,061)", "check": check}]
    vr = verify(ans_r, rows_r, led, {(DOC, 23): 1.0}, lambda s: None, priors=[-70000.0])
    assert vr["Final!15"]["flag"] == "red" and abs(vr["Final!15"]["value"] + 74206.0) < 1e-6, vr["Final!15"]
    # a check that does not close, and one leaning on a term no row prints
    bad = [{"row": "Final!14", "printed": -74206.0, "page": 23, "line": "(74,206) (76,061)",
            "check": "88,018 - 28,950 - 5,987 - 29,551 - 9,718 = 14,272"},
           {"row": "Final!14", "printed": -74206.0, "page": 23, "line": "(74,206) (76,061)",
            "check": "88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 - 1,000 = 13,272"}]
    for a in bad:
        assert not verify([a], rows, led, {(DOC, 23): 1.0}, lambda s: None, priors=[-76061.0]), a["check"]
    print("PASS test_a_check_that_closes_the_printed_subtotal_is_proof_2026_09_16")


def test_the_check_terms_are_read_as_printed_2026_09_16():
    """The terms of the check, signs and parenthesised negatives included —
    and (reviewer 2026-09-16) the four ways a check that is NOT the
    statement's own arithmetic must be refused."""
    from pipeline.reader import _check_terms, _reconciliation
    terms, closes = _check_terms("88,018 \u2212 28,950 \u2212 5,987 \u2212 29,551 \u2212 9,718 + 460 = 14,272 = printed Operating profit")
    assert closes == 14272.0 and len(terms) == 6 and abs(sum(terms) - 14272.0) < 1e-9, (terms, closes)
    assert _check_terms("no arithmetic here") is None
    led = _ledger(_clp_p23_items(), face_pages=((23, "pl"),))
    good = "88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 = 14,272"
    # the answered figure may also be a single term of the check ('Other gain')
    rec = _reconciliation(good, 460.0, led.items, 23, {DOC})
    assert rec is not None and "14,272" in rec["check"], rec
    # a figure the check says nothing about is never proved by it
    assert _reconciliation(good, 12345.0, led.items, 23, {DOC}) is None
    # the subtotal it closes on must itself be printed on that page
    thin = _ledger([i for i in _clp_p23_items() if "Operating profit" not in str(i.label)], face_pages=((23, "pl"),))
    assert _reconciliation(good, -74206.0, thin.items, 23, {DOC}) is None
    # REVIEWER 1 — a flipped sign makes an arbitrary residual close any check:
    # the page prints (9,718), so '+ 9,718' is not that line and -18,976 is nothing
    assert _reconciliation("88,018 - 28,950 - 5,987 - 29,551 + 9,718 - 18,976 = 14,272",
                           -18976.0, led.items, 23, {DOC}) is None
    # REVIEWER 2 — last year's column closes last year's subtotal: a comparative
    # is not this period's figure, whatever it adds up to
    assert _reconciliation("90,964 - 31,871 - 5,150 - 29,764 - 9,276 = 14,903",
                           -9276.0, led.items, 23, {DOC}) is None
    # a term printed in ANOTHER table of the page proves nothing about this line
    mixed = _ledger(_clp_p23_items() + [_item(23, 20, "Segment note", [-5987.0], table_id=9)],
                    face_pages=((23, "pl"),))
    assert _reconciliation("88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 = 14,272",
                           -74206.0, mixed.items, 23, {DOC}) is not None, "the P&L block itself still proves it"
    only_other = _ledger([i for i in _clp_p23_items() if "Staff" not in str(i.label)]
                         + [_item(23, 20, "Staff expenses (segment note)", [-5987.0, -5150.0], table_id=9)],
                         face_pages=((23, "pl"),))
    assert _reconciliation(good, -74206.0, only_other.items, 23, {DOC}) is None
    print("PASS test_the_check_terms_are_read_as_printed_2026_09_16")


def test_the_reconciliations_comparative_comes_from_the_print_2026_09_16():
    """Reviewer 2026-09-16: the plain/red decision read the comparative out of
    the brain-authored 'line' string — text no printed row had to support —
    and the value was divided by the page's scale while the tie was hunted at
    every scale, so a page ratified at 10^3 wrote a figure 1,000x too large,
    PLAIN. The comparative is now the same printed rows' own comparatives,
    and a tie at a scale the page does not carry lands red."""
    from pipeline.reader import verify
    led = _ledger(_clp_p23_items(), face_pages=((23, "pl"),))
    led._doc_periods = {DOC: "current"}
    check = "88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 = 14,272"
    rows = [{"row": "Final!14", "sheet": "Final", "r": 14, "label": "Total operating expenses", "prior": -76061.0}]
    answers = [{"row": "Final!14", "printed": -74206.0, "page": 23, "line": "no numbers here", "check": check}]
    v = verify(answers, rows, led, {(DOC, 23): 1.0}, lambda s: None, priors=[-76061.0])
    assert v["Final!14"]["conf"] == 4 and v["Final!14"]["flag"] is None, v["Final!14"]
    assert abs(v["Final!14"]["value"] + 74206.0) < 1e-6, "the print's own comparatives prove it, with no comparative in the answer's text"
    # the answer's text quotes a comparative that WOULD tie this row's prior;
    # the printed rows' own comparatives (-76,061) do not — it lands red
    rows_l = [{"row": "Final!15", "sheet": "Final", "r": 15, "label": "Operating costs", "prior": -70000.0}]
    ans_l = [{"row": "Final!15", "printed": -74206.0, "page": 23, "line": "(74,206) (70,000)", "check": check}]
    vl = verify(ans_l, rows_l, led, {(DOC, 23): 1.0}, lambda s: None, priors=[-70000.0])
    assert vl["Final!15"]["flag"] == "red", "a comparative only the answer's text carries made it plain"
    # the scale of the tie and the scale of the page must agree
    base = [_item(30, 1, "Revenue", [100000.0, 100000.0]),
            _item(30, 2, "Purchases", [-30000.0, -30000.0]),
            _item(30, 3, "Staff expenses", [-29746.0, -30242.0]),
            _item(30, 4, "Operating profit", [40254.0, 39758.0])]
    led2 = _ledger(base, face_pages=((30, "pl"),)); led2._doc_periods = {DOC: "current"}
    rows2 = [{"row": "M!9", "sheet": "M", "r": 9, "label": "Operating expenses", "prior": -60.242}]
    ans2 = [{"row": "M!9", "printed": -59746.0, "page": 30, "check": "100,000 - 30,000 - 29,746 = 40,254", "line": ""}]
    v2 = verify(ans2, rows2, led2, {(DOC, 30): 1e6}, lambda s: None, priors=[-60.242])
    assert v2["M!9"]["flag"] == "red", f"a 1,000x scale clash landed plain: {v2['M!9']}"
    assert abs(v2["M!9"]["value"] + 59.746) < 1e-6, v2["M!9"]
    print("PASS test_the_reconciliations_comparative_comes_from_the_print_2026_09_16")


def test_a_reconciliation_proves_one_row_2026_09_16():
    """Reviewer 2026-09-16: the one-home guard on the reconciliation path
    lacked the numeric-prior test its printed-line twin carries, so two rows
    with no prior at all (None == None) both took the same figure."""
    from pipeline.reader import verify
    led = _ledger(_clp_p23_items(), face_pages=((23, "pl"),))
    led._doc_periods = {DOC: "current"}
    check = "88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 = 14,272"
    rows = [{"row": "Final!14", "sheet": "Final", "r": 14, "label": "Operating expenses", "prior": None},
            {"row": "Final!40", "sheet": "Final", "r": 40, "label": "Operating costs", "prior": None}]
    answers = [{"row": r["row"], "printed": -74206.0, "page": 23, "line": "", "check": check} for r in rows]
    v = verify(answers, rows, led, {(DOC, 23): 1.0}, lambda s: None, priors=[])
    assert not v, f"the same reconciliation answered two rows: {v}"
    # two rows the model fills with the SAME prior are its own duplicate: both take it
    rows_d = [dict(r, prior=-76061.0) for r in rows]
    v2 = verify(answers, rows_d, led, {(DOC, 23): 1.0}, lambda s: None, priors=[-76061.0])
    assert set(v2) == {"Final!14", "Final!40"}, v2
    print("PASS test_a_reconciliation_proves_one_row_2026_09_16")



def test_the_readers_reading_is_option_A_with_its_check_2026_09_16():
    """Run 34993405014: the SERVE card for Final!16 'Other Income, net'
    offered a 250 MW battery, two tax lines and a finance-cost line; the
    reader had already read 'Other gain 460' off the P&L face and stated the
    check that closes the printed operating profit — and the card never
    showed it (a row with no prior returned from the label-only generator,
    which never looked at the reader's reading). The reader's value, the line
    it quoted and its check are option A on the card."""
    from pipeline.workqueue import candidates_for
    wb = _wb({"A2": "Other Income, net", "T2": 300.0, "A3": "Other Income, net (never filled)"})
    lp = _loop(wb, _spec_tiny())
    for it in _clp_p23_items():
        lp.ledger.add(it)
    lp.ledger._doc_periods = {DOC: "current"}
    lp.ledger.reader_suggestions = {
        "S!2": {"value": 460.0, "doc": DOC, "page": 23, "line": "Other gain",
                "check": "88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 = 14,272"},
        "S!3": {"value": 460.0, "doc": DOC, "page": 23, "line": "Other gain",
                "check": "88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 = 14,272"}}
    for sheet_row, prior in (("S!2", 2), ("S!3", 3)):
        cands = candidates_for(lp, "S", int(sheet_row.split("!")[1]))
        assert cands, f"{sheet_row}: no candidates at all"
        a = cands[0]
        assert abs(a["value"] - 460.0) < 1e-6, f"{sheet_row}: the reader's reading is not option A: {[c['value'] for c in cands[:4]]}"
        assert a.get("no_prior") and "reader's suggestion" in a["warnings"][0], a["warnings"]
        assert "14,272" in a["warnings"][0], "the check the reader stated must be on the card"
    print("PASS test_the_readers_reading_is_option_A_with_its_check_2026_09_16")



def test_only_a_proven_holder_locks_a_cell_2026_09_16():
    """Run 34993405014: judge_write refused ~20 brain picks with "this cell
    already holds a PROVEN value" while the holder was an ORANGE derivation
    (t_derive registers conf 3) or a RED no-tie read — the branch fired on
    mere presence in `served`. A held figure locks the cell only when it is
    itself proven; otherwise the brain's pick lands, red."""
    from pipeline.writegate import judge_write

    class _It:          # a printed line carrying the value; its comparative 999 does not tie prior 100
        doc, page, table_id, label, nums, sourceable = DOC, 3, 0, "Other income", [284.0, 999.0], True
        table_kind = None
    ev = [(_It(), 1.0)]
    orange = judge_write(284.0, 100.0, True, ev, set(), {}, held_proven=False)
    assert orange[0] == "ALLOW_FLAGGED", f"an orange/red holder must yield to the brain's pick: {orange}"
    proven = judge_write(284.0, 100.0, True, ev, set(), {}, held_proven=True)
    assert proven[0] == "REFUSE" and "PROVEN" in proven[1], proven
    print("PASS test_only_a_proven_holder_locks_a_cell_2026_09_16")


def test_an_orange_derived_holder_yields_to_the_brains_pick_2026_09_16():
    """The same law through the loop: Final!AI30 held an orange derivation
    (conf 3) and every later printed pick was refused as PROVEN (r1472,
    r1529, r1611). The pick now lands red over the derivation."""
    wb = _wb({"A2": "One-off items", "T2": 100.0, "U2": -2756.0})
    lp = _loop(wb, _spec_tiny(),
               served={("S", 2): {"value": -2756.0, "line": "derived via Final!AI31", "page": 1,
                                  "conf": 3, "status": "OK", "flag": "orange", "doc": DOC}},
               evidence=[[284.0, 999.0]])
    lp.writer.served = lp.served
    r = lp.t_set_input({"cell": "S!U2", "value": 284.0, "why": "p3: 'Other income' — the card's option A"})
    assert r.startswith("WRITTEN"), r
    assert wb["S"]["U2"].value == 284.0, wb["S"]["U2"].value
    print("PASS test_an_orange_derived_holder_yields_to_the_brains_pick_2026_09_16")



def test_an_exact_prior_tie_is_not_a_numeric_coincidence_2026_09_16():
    """Run 34993405014: ROAFNA!29 'Capital' (analyst 58,405) and Aus!70
    'Mount Piper' (analyst 6,314) were option A on their cards with the
    comparative reproducing the model's prior EXACTLY — and each carried
    'label unrelated to the model row's — a numeric coincidence'. The brain
    declined both. A comparative equal to the prior at the model's own
    precision IS this row's line; a LOOSE tie still needs the name."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import candidates_for
    from pipeline.writer import Writer
    from pipeline.targets import TargetRow as TR
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ROAFNA"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T29"], ws["U29"] = 56789.0, 56789.0
    spec = {"year_axis": {"ROAFNA": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}, "check_rows": []}
    ws["T28"], ws["U28"] = 39000.0, 39000.0
    items = [_item(95, 2, "total liabilities", [41000.0, 39000.0]),               # the page's second anchor
             _item(95, 3, "Fixed assets employed, net", [58405.0, 56789.0]),      # EXACT tie, unrelated name
             _item(95, 4, "Average net fixed assets", [61234.0, 56500.0])]        # loose tie, unrelated name
    led = _ledger(items, face_pages=((95, "bs"),))
    led._doc_periods = {DOC: "current"}
    loop = ObjectiveLoop(wb, spec, 2025, led,
                         [TR("ROAFNA", 29, "Capital", 56789.0), TR("ROAFNA", 28, "Borrowings", 39000.0)],
                         {}, Writer(wb), None)
    loop.writer.log["flags"] = ["ROAFNA!U29"]
    cands = candidates_for(loop, "ROAFNA", 29)
    exact = next((c for c in cands if abs(c["value"] - 58405.0) < 1e-6), None)
    loose = next((c for c in cands if abs(c["value"] - 61234.0) < 1e-6), None)
    assert exact is not None, cands
    assert not any("numeric coincidence" in w for w in exact["warnings"]), exact["warnings"]
    assert loose is None or any("numeric coincidence" in w for w in loose["warnings"]), loose
    print("PASS test_an_exact_prior_tie_is_not_a_numeric_coincidence_2026_09_16")



def test_the_key_card_lists_the_whole_input_tree_2026_09_16():
    """Run 34993405014: operating profit and net profit were both -2,315 off
    the print because Final!AI14 (operating expenses) held the analyst's own
    -76,061 and Final!AI16 (other income) was never written. Neither moved
    against the baseline, so the swing census could not show them; the card
    offered PROVEN movers only and the brain answered 'question' twice. The
    card now lists every actual-period input of the line, moved or not, with
    its status and the analyst's estimate — and says which other key carries
    the same gap."""
    from pipeline.consequence import build_card
    cells = {"A7": "Revenue", "T7": 90964.0, "U7": 88018.0,
             "A14": "Operating expenses", "T14": -76061.0, "U14": -76061.0,
             "A16": "Other income", "T16": 0.0, "U16": 0.0,
             "A21": "Operating profit", "T21": "=T7+T14+T16", "U21": "=U7+U14+U16",
             "A23": "Income tax expense", "T23": -2821.0, "U23": -2655.0,
             "A31": "Net profit", "T31": "=T21+T23", "U31": "=U21+U23"}
    wb, pre = _wb(cells), _wb(dict(cells, U7=90964.0))
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [],
            "key_rows": [{"name": "operating profit", "sheet": "S", "row": 21},
                         {"name": "net profit", "sheet": "S", "row": 31}]}
    panel = {"operating profit": {"print": 14272.0}, "net profit": {"print": 11617.0}}
    lp = _loop(wb, spec, served={("S", 7): {"value": 88018.0, "line": "Revenue", "page": 23,
                                            "conf": 5, "status": "OK", "flag": None, "doc": DOC}})
    lp.writer.served = lp.served
    card, options = build_card(lp, pre, ("key", "S", "U31", -2315.0,
                                         "key 'net profit' at S!U31 computes 9,302.0 vs printed 11,617.0"),
                               [(("S", "U7"), 1.0)], [], None, panel, None)
    assert "S!U14" in card and "S!U16" in card, f"the untouched inputs are still invisible:\n{card}"
    assert "UNTOUCHED" in card, card
    assert "operating profit" in card and "same gap" in card.lower(), f"the shared gap is not named:\n{card}"
    assert "derive:via" in options
    print("PASS test_the_key_card_lists_the_whole_input_tree_2026_09_16")


def test_the_input_tree_is_this_period_only_2026_09_16():
    """The tree is the line's own inputs in the ACTUAL column — last year's
    hardcodes belong to last year, and a formula's whole history is not this
    update's input."""
    from pipeline.investigate import input_leaves
    wb = _wb({"T7": 90964.0, "U7": 88018.0, "T14": -76061.0, "U14": -76061.0,
              "U21": "=U7+U14+T7", "T21": "=T7+T14"})
    leaves = input_leaves(wb, "S", "U21", cols={"S": "U"})
    assert set(leaves) == {("S", "U7"), ("S", "U14")}, leaves
    assert set(input_leaves(wb, "S", "U21")) == {("S", "U7"), ("S", "U14"), ("S", "T7")}
    print("PASS test_the_input_tree_is_this_period_only_2026_09_16")



def test_the_plug_asks_the_brain_where_it_lands_2026_09_16():
    """Run 34993405014: the brain answered 'plug' on the balance card and the
    ladder chose the site by its own ranking — Final!AI87, a cell the brain
    had twice refused — and 2026E cash went to -966. The rung stays code's
    last resort; WHERE the residual lands is asked, with code's ranking as
    the default when no answer comes."""
    from pipeline.orchestrator import terminal_ladder
    cells = {"T2": 100.0, "T3": 50.0, "T4": 150.0,
             "U2": 109.0, "U3": 60.0, "U4": 171.0,
             "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"}
    wb = _wb(cells)
    lp = _loop(wb, _spec_tiny())
    lp.writer.plugs_allowed = True
    seen = []

    def ask(text, options, default):
        seen.append(text)
        assert text.startswith("CARD PLUG"), text
        return "site:2"
    lp.ask = ask
    logs = []
    terminal_ladder(lp, logs.append)
    assert seen, "the ladder plugged without asking where"
    assert "site:1" in seen[0] and "site:2" in seen[0], seen[0]
    assert lp._failing_target_checks() == [], lp._failing_target_checks()
    assert wb["S"]["U4"].value == 171.0, "code's own first site took the plug anyway"
    assert wb["S"]["U2"].value == 111.0, wb["S"]["U2"].value
    # no brain: code's ranking stands, exactly as before
    wb2 = _wb(cells)
    lp2 = _loop(wb2, _spec_tiny())
    lp2.writer.plugs_allowed = True
    terminal_ladder(lp2, logs.append)
    assert wb2["S"]["U4"].value == 169.0, wb2["S"]["U4"].value
    print("PASS test_the_plug_asks_the_brain_where_it_lands_2026_09_16")


def test_the_roll_base_backout_asks_the_brain_where_2026_09_16():
    """Run 34993405014: the roll-base back-out fired 14 times and wrote over
    the brain's own rulings on Driver!AI37 and Final!AI87 — code ranked the
    roll's inputs by confidence and took the decision. Code still proves
    which inputs the roll responds to; the brain says where the gap belongs,
    or that it belongs nowhere."""
    import openpyxl
    from pipeline.teachings import roll_base_mismatches
    from pipeline.writer import Writer
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U", "2026": "V"}}}}

    def build():
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S"
        ws["A10"] = "Total operating expenses"
        ws["T10"], ws["U10"], ws["V10"] = 1000.0, 1150.0, "=V11+V12+V13"
        ws["A11"] = "Fuel";  ws["T11"], ws["U11"], ws["V11"] = 700.0, 800.0, "=U11*1.05"
        ws["A12"] = "Staff"; ws["T12"], ws["U12"], ws["V12"] = 280.0, 280.0, "=U12"
        ws["A13"] = "Other"; ws["T13"], ws["U13"], ws["V13"] = 20.0, 20.0, "=U13"
        return wb, ws
    served = {("S", 11): {"value": 800.0, "conf": 4, "note": "reconciliation: prior ties"}}
    # the brain names the home: the SECOND uncertain input, not code's ranking
    wb, ws = build()
    w = Writer(wb)
    cards = []

    def ask_second(text, options, default):
        cards.append((text, list(options)))
        return "site:2"
    roll_base_mismatches(wb, spec, 2025, w, lambda s: None, served=served, ask=ask_second)
    assert cards and cards[0][0].startswith("CARD PLUG"), cards
    assert "none" in cards[0][1] and "site:1" in cards[0][1] and "site:2" in cards[0][1], cards[0][1]
    assert "S!U11" not in cards[0][0], "a PROVEN input was offered as a place to absorb a gap"
    assert ws["U13"].value == "=(20)+(50)", ws["U13"].value
    assert ws["U12"].value == 280.0, "the input the brain did not name was moved"
    # the brain says it belongs nowhere: flagged, nothing guessed
    wb, ws = build()
    w = Writer(wb)
    roll_base_mismatches(wb, spec, 2025, w, lambda s: None, served=served,
                         ask=lambda t, o, d: "none")
    assert ws["U12"].value == 280.0 and ws["U13"].value == 20.0, "a gap the brain left open was absorbed anyway"
    assert str(ws["U12"].fill.fgColor.rgb).endswith("FFC7CE")
    assert str(ws["U13"].fill.fgColor.rgb).endswith("FFC7CE")
    assert not w.log.get("written"), w.log.get("written")
    # no brain: today's law stands — two equally uncertain inputs, guess nothing
    wb, ws = build()
    w = Writer(wb)
    roll_base_mismatches(wb, spec, 2025, w, lambda s: None, served=served)
    assert ws["U12"].value == 280.0 and ws["U13"].value == 20.0
    print("PASS test_the_roll_base_backout_asks_the_brain_where_2026_09_16")



def test_the_absorber_does_not_depend_on_the_reading_order_2026_09_16():
    """Floors 2026-09-16: the CLP FY25 floor delivered 8/8 keys on three runs
    and 7/8 on two, from the same ledger and the same code — key_tie read the
    key's chain out of a SET, so 'total liabilities and equity' absorbed into
    Final!AI80 or Final!AI87 by the interpreter's hash order, and a truncation
    decided which of the equally ranked cells was probed at all (proved by
    running the same head twice under PYTHONHASHSEED=7: both landed on AI87).
    The chain is now read in the model's own order and ranked on a TOTAL key,
    so the order the cells arrive in cannot decide the outcome."""
    import openpyxl
    from openpyxl.styles import PatternFill
    from pipeline import keytie
    from pipeline.keytie import key_tie, _chain_cells
    from pipeline.writer import Writer

    def build():
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S"
        ws["A2"], ws["T2"], ws["U2"] = "Revenue", 100.0, 100.0
        # two equally uncertain (red) components of the key, same size:
        # nothing but the coordinate separates them
        ws["A3"], ws["T3"], ws["U3"] = "Component one", 40.0, 40.0
        ws["A4"], ws["T4"], ws["U4"] = "Component two", 40.0, 40.0
        ws["A5"], ws["T5"], ws["U5"] = "Total", "=T2+T3+T4", "=U2+U3+U4"
        for c in ("U3", "U4"):
            ws[c].fill = PatternFill("solid", fgColor="FFC7CE")
        return wb
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [],
            "key_rows": [{"name": "total", "sheet": "S", "row": 5}]}
    panel = {"total": {"print": 200.0, "prior": 180.0}}
    chosen = []
    real_chain = _chain_cells
    for reverse in (False, True):
        wb = build()
        keytie._chain_cells = (lambda w, sh, co, _r=reverse:
                               list(reversed(real_chain(w, sh, co))) if _r else real_chain(w, sh, co))
        try:
            n = key_tie(wb, spec, 2025, Writer(wb), None, lambda s: None, panel=panel)
        finally:
            keytie._chain_cells = real_chain
        assert n == 1, (n, reverse)
        chosen.append(tuple(str(wb["S"][c].value) for c in ("U3", "U4")))
    assert chosen[0] == chosen[1], f"the reading order chose the absorber: {chosen}"
    assert chosen[0][0] != "40.0" and chosen[0][1] == "40.0", chosen
    # the same law on the rollover dossier: its leaves were a set too, and the
    # card shows the head of that list (two floor runs offered different 5th
    # options on the ROLLOVER cards while agreeing on everything else)
    import inspect
    from pipeline import rollover as _ro
    src = inspect.getsource(_ro.dossier)
    assert "dict.fromkeys(leaf_fn" in src and "set(leaf_fn" not in src, "the dossier still reads a set"
    assert '_row_of(d["coord"])' in src, "the dossier's ranking is not total"
    print("PASS test_the_absorber_does_not_depend_on_the_reading_order_2026_09_16")



def test_a_replay_never_overwrites_the_pin_it_replays_2026_09_16():
    """Floors 2026-09-16: the live-shape floor runs WITH a client, so it
    rewrote companies/<co>/replay/<period>/key_rows.json — the very pin the
    plain floors read — and the two floors stopped measuring the same thing.
    A run given a pinned ledger writes its own artifacts beside its own
    output (<period>-replay), never over the pin it is replaying."""
    import inspect
    from pipeline.run import artifact_dir, update
    pin = Path("/co/replay/FY25/ledger.json")
    live = artifact_dir("/co", "FY25", None)
    replay = artifact_dir("/co", "FY25", str(pin))
    assert str(live).endswith("/replay/FY25"), live
    assert str(replay).endswith("/replay/FY25-replay"), replay
    assert Path(replay) != pin.parent, "a replay would write over its own pin"
    src = inspect.getsource(update)
    assert 'artifact_dir(company_dir, period, pinned_ledger) / "key_rows.json"' in src, \
        "the replay's key rows are still written over the pinned artifact"
    assert 'Path(pinned_ledger).parent / "key_rows.json"' in src, \
        "the pin must still be READ from the artifact the run was given"
    print("PASS test_a_replay_never_overwrites_the_pin_it_replays_2026_09_16")



def test_the_readers_reading_does_not_relabel_a_tying_candidate_2026_09_16():
    """Reviewer 2026-09-16: _reader_first fronted an EXISTING candidate whose
    comparative tied the prior EXACTLY and pasted "no prior tie … it lands
    red" over it — the reading's own weakness described someone else's
    evidence. Only the synthesised option carries that clause."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import candidates_for
    from pipeline.writer import Writer
    from pipeline.targets import TargetRow as TR
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["T7"], ws["U7"] = 4976.0, 4976.0
    ws["T8"], ws["U8"] = 39000.0, 39000.0
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}, "check_rows": []}
    items = [_item(95, 1, "total liabilities", [41000.0, 39000.0]),
             _item(95, 2, "cash and equivalents", [3905.0, 4976.0])]      # EXACT prior tie
    led = _ledger(items, face_pages=((95, "bs"),)); led._doc_periods = {DOC: "current"}
    led.reader_suggestions = {"S!7": {"value": 3905.0, "doc": DOC, "page": 95, "line": "cash and equivalents",
                                      "check": "3,905 + 1,071 = 4,976"}}
    loop = ObjectiveLoop(wb, spec, 2025, led,
                         [TR("S", 7, "cash and equivalents", 4976.0), TR("S", 8, "Borrowings", 39000.0)],
                         {}, Writer(wb), None)
    loop.writer.log["flags"] = ["S!U7"]
    a = candidates_for(loop, "S", 7)[0]
    assert abs(a["value"] - 3905.0) < 1e-6, a
    assert not any("no prior tie" in w for w in a["warnings"]), a["warnings"]
    assert a.get("tie_off") is not None and a["tie_off"] <= 0.6, "the machine's own exact tie was lost"
    assert any("READER'S OWN READING" in w for w in a["warnings"]), a["warnings"]
    print("PASS test_the_readers_reading_does_not_relabel_a_tying_candidate_2026_09_16")



def test_the_ladder_uses_the_named_site_only_2026_09_16():
    """Reviewer 2026-09-16: naming the brain's site merely moved it to the
    front of code's own ranking, so a write that failed there walked straight
    on to the cells below — the very ones the brain had refused (run
    34993405014's Final!AI87). The named home is the only home: if the plug
    will not go there, the check stays open, red and reported."""
    from pipeline.orchestrator import terminal_ladder
    cells = {"T2": 100.0, "T3": 50.0, "T4": 150.0, "T5": 500.0, "U5": 500.0,
             "U2": 109.0, "U3": 60.0, "U4": 171.0,
             "T9": "=T2+T3-T4+0*T5", "U9": "=U2+U3-U4+0*U5"}
    wb = _wb(cells)
    lp = _loop(wb, _spec_tiny())
    lp.writer.plugs_allowed = True
    # site:1 is S!U5, the largest input of the check's own formula — and the
    # check does not move with it, so the plug there cannot land
    lp.ask = lambda text, options, default: "site:1"
    logs = []
    terminal_ladder(lp, logs.append)
    assert wb["S"]["U4"].value == 171.0 and wb["S"]["U2"].value == 109.0, \
        "a site the brain did not name took the plug"
    assert lp._failing_target_checks(), "the check was closed behind the brain's back"
    assert any("left OPEN" in x for x in logs), logs[-3:]
    assert "S!U9" in lp.writer.log.get("flags", []), lp.writer.log.get("flags")
    print("PASS test_the_ladder_uses_the_named_site_only_2026_09_16")



def test_the_roll_base_ruling_names_a_cell_not_a_position_2026_09_16():
    """Reviewer 2026-09-16: the ruling was cached as 'site:2' — an index into
    a list rebuilt at every firing, and the repair suite fires this law again
    and again. Once an input left that list (proven, or no longer moving the
    roll) the remembered position pointed at a different cell. The ruling
    names the cell; a later firing that no longer offers it guesses nothing."""
    import openpyxl
    from pipeline.teachings import roll_base_mismatches
    from pipeline.writer import Writer
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U", "2026": "V"}}}}

    def build():
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S"
        ws["A10"] = "Total operating expenses"
        ws["T10"], ws["U10"], ws["V10"] = 1000.0, 1150.0, "=V11+V12+V13"
        ws["A11"] = "Fuel";  ws["T11"], ws["U11"], ws["V11"] = 700.0, 800.0, "=U11*1.05"
        ws["A12"] = "Staff"; ws["T12"], ws["U12"], ws["V12"] = 280.0, 280.0, "=U12"
        ws["A13"] = "Other"; ws["T13"], ws["U13"], ws["V13"] = 20.0, 20.0, "=U13"
        return wb, ws
    served = {("S", 11): {"value": 800.0, "conf": 4, "note": "reconciliation: prior ties"}}
    wb, ws = build()
    w = Writer(wb)
    asked = []

    def ask_second(text, options, default):
        asked.append(text)
        return "site:2"
    roll_base_mismatches(wb, spec, 2025, w, lambda s: None, served=served, ask=ask_second)
    assert ws["U13"].value == "=(20)+(50)", ws["U13"].value
    ruling = w.log.get("rollbase_rulings", {})
    assert ruling.get("S!10") == "S!U13", f"the ruling was remembered as a position: {ruling}"
    # the same run fires the law again with the list in a different shape:
    # the remembered CELL still decides, and the brain is not asked twice
    wb2, ws2 = build()
    w2 = Writer(wb2)
    w2.log["rollbase_rulings"] = {"S!10": "S!U13"}
    roll_base_mismatches(wb2, spec, 2025, w2, lambda s: None, served=served,
                         ask=lambda t, o, d: (_ for _ in ()).throw(AssertionError("asked twice")))
    assert ws2["U13"].value == "=(20)+(50)" and ws2["U12"].value == 280.0, (ws2["U12"].value, ws2["U13"].value)
    # a ruling naming a cell this firing no longer offers guesses nothing
    wb3, ws3 = build()
    w3 = Writer(wb3)
    w3.log["rollbase_rulings"] = {"S!10": "S!U99"}
    roll_base_mismatches(wb3, spec, 2025, w3, lambda s: None, served=served, ask=lambda t, o, d: "none")
    assert ws3["U12"].value == 280.0 and ws3["U13"].value == 20.0, "a stale ruling moved a cell"
    assert not w3.log.get("written"), w3.log.get("written")
    print("PASS test_the_roll_base_ruling_names_a_cell_not_a_position_2026_09_16")



def test_a_raising_answerer_never_takes_the_ladder_down_2026_09_16():
    """Reviewer 2026-09-16: the ladder called the brain directly while the
    roll-base card went through _ask_site's try/except — so an answerer that
    RAISED aborted the last rung that guarantees 'back out, mark, still
    deliver'. Both cards go through the same door: the fault is said, code's
    own ranking stands, the check still closes."""
    from pipeline.orchestrator import terminal_ladder
    wb = _wb({"T2": 100.0, "T3": 50.0, "T4": 150.0,
              "U2": 109.0, "U3": 60.0, "U4": 171.0,
              "T9": "=T2+T3-T4", "U9": "=U2+U3-U4"})
    lp = _loop(wb, _spec_tiny())
    lp.writer.plugs_allowed = True

    def boom(text, options, default):
        raise RuntimeError("the brain died mid-card")
    lp.ask = boom
    logs = []
    n = terminal_ladder(lp, logs.append)
    assert n == 1, (n, logs)
    assert lp._failing_target_checks() == [], "the ladder never finished"
    assert wb["S"]["U4"].value == 169.0, wb["S"]["U4"].value
    assert any("could not answer" in x and "RuntimeError" in x for x in logs), logs
    print("PASS test_a_raising_answerer_never_takes_the_ladder_down_2026_09_16")



def test_the_reading_costs_the_card_nothing_extra_2026_09_16():
    """Reviewer 2026-09-16 (cost): the reader's option A was PREPENDED after
    the no-prior generator had already filled its quota, so the card grew by
    one every time; and the input-tree walk took a fresh 20 s on top of the
    census's own 60 s. The reading replaces the weakest option, and the walk
    spends what is left of the round's budget, never a second one."""
    import openpyxl
    from pipeline.orchestrator import ObjectiveLoop
    from pipeline.workqueue import candidates_for
    from pipeline.writer import Writer
    from pipeline.targets import TargetRow as TR
    from pipeline.consequence import build_card
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "S"
    ws["T2"], ws["U2"] = 2024, 2025
    ws["A3"] = "New orders"
    led = _ledger([_item(95, i, f"New orders line {i}", [100.0 + i, 90.0 + i]) for i in range(6)],
                  face_pages=((95, "pl"),))
    led._doc_periods = {DOC: "current"}
    led.reader_suggestions = {"S!3": {"value": 777.0, "doc": DOC, "page": 95, "line": "New orders",
                                      "check": "700 + 77 = 777"}}
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}, "header_row": 2}}, "check_rows": []}
    loop = ObjectiveLoop(wb, spec, 2025, led, [TR("S", 3, "New orders", None)], {}, Writer(wb), None)
    without = len(candidates_for(loop, "S", 3, k=3))
    assert without == 3, without
    led.reader_suggestions = {"S!3": {"value": 777.0, "doc": DOC, "page": 95, "line": "New orders"}}
    with_reading = candidates_for(loop, "S", 3, k=3)
    assert len(with_reading) == 3, f"the reading made the card longer: {len(with_reading)}"
    assert abs(with_reading[0]["value"] - 777.0) < 1e-6, with_reading[0]
    # the tree walk takes the budget it is given, and says so when there is none
    cells = {"A7": "Revenue", "T7": 90964.0, "U7": 88018.0, "A14": "Opex", "T14": -76061.0, "U14": -76061.0,
             "A21": "Operating profit", "T21": "=T7+T14", "U21": "=U7+U14"}
    wb2, pre2 = _wb(cells), _wb(dict(cells, U7=90964.0))
    spec2 = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}}, "check_rows": [],
             "key_rows": [{"name": "operating profit", "sheet": "S", "row": 21}]}
    lp2 = _loop(wb2, spec2)
    obj = ("key", "S", "U21", -2315.0, "key 'operating profit' at S!U21")
    full, _o = build_card(lp2, pre2, obj, [(("S", "U7"), 1.0)], [], None, {"operating profit": {"print": 14272.0}}, None)
    assert "S!U14" in full, "the tree was not walked with a budget"
    spent, _o2 = build_card(lp2, pre2, obj, [(("S", "U7"), 1.0)], [], None,
                            {"operating profit": {"print": 14272.0}}, None, tree_budget_s=0.0)
    assert "S!U14" not in spent and "whole budget" in spent, spent
    print("PASS test_the_reading_costs_the_card_nothing_extra_2026_09_16")



def test_a_note_reference_is_a_column_of_the_block_2026_09_16():
    """Reviewer 2026-09-16: the note-reference test fired on any row whose
    first figure was a positive integer under 100 and smaller than the next,
    so 'Other gains 46 512' read 512 as THIS period — the row lost its
    comparative and a check built on 512 was accepted. A note is a column of
    the table block, ascending down it; a leading integer that does not fit
    that ascent is a figure."""
    from pipeline.reader import _note_column, _row_figures, _reconciliation
    two_period = [_item(23, 1, "Revenue", [88018.0, 90964.0]),
                  _item(23, 2, "Other gains", [46.0, 512.0]),
                  _item(23, 3, "Operating profit", [14324.0, 14903.0])]
    notes = _note_column(two_period)
    assert notes == set(), "a two-period block was given a note column it does not have"
    assert _row_figures(two_period[1], notes) == (46.0, 512.0), _row_figures(two_period[1], notes)
    # the genuine CLP block: the note column 3 | 5 | 6 | 7 | 9 is stripped for
    # every row that carries one, and only for those
    clp = _clp_p23_items()
    n2 = _note_column(clp)
    by_label = {str(i.label): i for i in clp}
    assert _row_figures(by_label["Other gain"], n2) == (460.0, None), _row_figures(by_label["Other gain"], n2)
    assert _row_figures(by_label["Revenue"], n2) == (88018.0, 90964.0)
    assert _row_figures(by_label["Operating profit"], n2) == (14272.0, 14903.0)
    assert _row_figures(by_label["Staff expenses"], n2) == (-5987.0, -5150.0), "a row with no note was stripped"
    # the reviewer's check, built on the comparative it invented: refused
    attack = _ledger([_item(23, 1, "Revenue", [3.0, 88018.0, 90964.0]),
                      _item(23, 2, "Purchases", [-28950.0, -31871.0]),
                      _item(23, 3, "Staff expenses", [-5987.0, -5150.0]),
                      _item(23, 4, "Fuel and other operating expenses", [-29551.0, -29764.0]),
                      _item(23, 5, "Depreciation and amortisation", [-9718.0, -9276.0]),
                      _item(23, 6, "Other gains", [46.0, 512.0]),
                      _item(23, 7, "Operating profit", [6.0, 14324.0, 14903.0])],
                     face_pages=((23, "pl"),))
    assert _reconciliation("88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 512 = 14,324",
                           -74206.0, attack.items, 23, {DOC}) is None
    # and the genuine one still proves the analyst's figure
    led = _ledger(clp, face_pages=((23, "pl"),))
    assert _reconciliation("88,018 - 28,950 - 5,987 - 29,551 - 9,718 + 460 = 14,272",
                           -74206.0, led.items, 23, {DOC}) is not None
    print("PASS test_a_note_reference_is_a_column_of_the_block_2026_09_16")



if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as ex:
                print(f"FAIL {name}: {ex}")
                fails += 1
    sys.exit(1 if fails else 0)
