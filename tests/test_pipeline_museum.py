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
    w = Writer(_wb({"T5": 0.94}))
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
    from pipeline.gate import flag_budget
    spec = _spec_tiny()
    cells = {f"U{r}": 1.0 for r in range(1, 11)}
    wb = _wb(cells)
    flags = [f"S!U{r}" for r in (1, 2, 3)]      # 30% flagged
    assert flag_budget(wb, spec, "2025", flags), "over-budget flags passed"
    assert not flag_budget(wb, spec, "2025", ["S!U1"])


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
    assert ws["V5"].fill.start_color.rgb.endswith("FFC000")
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
    verdict, why, flag = judge_write(53546.5, 12545.3, True, ev, set())
    assert verdict == "REFUSE" and "proven" in why.lower()

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
    claimed = {("12053065.PDF", 95, 6892.7)}
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
