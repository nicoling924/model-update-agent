"""The updater museum — every scar becomes an exhibit BEFORE the code that
could reintroduce it (BUILD_PLAN §3.5: museum-as-contract).

Run: python3 -m pytest tests/test_updater_museum.py -q   (or plain python3)
Stdlib + openpyxl only; no LLM, no I/O beyond temp workbooks.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from updater.evidence import EvidenceBook, FLAG_FOR_GRADE
from updater.toolbox import Toolbox
from updater.writer import Writer
from updater.checks import scorecard, summarize
from updater.numerics import line_numbers, parse_number, row_tol


def _wb():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Model"
    return wb, ws


class EvidenceGradeLaw(unittest.TestCase):
    """BUILD_PLAN §3.1: flags fall out of grades — they cannot be forgotten."""

    def test_grade_c_and_d_always_flag(self):
        self.assertEqual(FLAG_FOR_GRADE["C"], "red")
        self.assertEqual(FLAG_FOR_GRADE["D"], "orange")
        self.assertIsNone(FLAG_FOR_GRADE["A"])

    def test_grade_a_requires_citation(self):
        book = EvidenceBook()
        with self.assertRaises(ValueError):
            book.record("Model!U5", "A", "join")     # no citation
        book.record("Model!U5", "A", "join", citation="p95: line")

    def test_unknown_grade_refused(self):
        book = EvidenceBook()
        with self.assertRaises(ValueError):
            book.record("Model!U5", "E", "join", citation="x")


class NotDisclosedProofLaw(unittest.TestCase):
    """Owner guard: 'could not find' != 'not disclosed' — the claim needs a
    recorded exhausted search (>=3 distinct places)."""

    def test_lazy_claim_refused(self):
        book = EvidenceBook()
        with self.assertRaises(ValueError):
            book.claim_not_disclosed("Model!49", ["looked once"])

    def test_proven_claim_accepted(self):
        book = EvidenceBook()
        t = book.claim_not_disclosed(
            "Model!49", ["direct find on faces", "prior triangulation",
                         "five-year summary + notes"])
        self.assertEqual(t.verdict, "not_disclosed")


class SelfAnnouncingToolLaw(unittest.TestCase):
    """The learner served ZERO for 5 runs and nothing noticed — never again."""

    def test_zero_serve_is_surfaced(self):
        box = Toolbox()
        box.register("dead_tool", lambda a: "MISS: nothing", kind="query")
        for _ in range(3):
            box.call("dead_tool", {})
        ann = "\n".join(box.announcements())
        self.assertIn("dead_tool: 0/3", ann)
        self.assertIn("SERVING NOTHING", ann)

    def test_healthy_tool_not_accused(self):
        box = Toolbox()
        box.register("ok_tool", lambda a: "WRITTEN", kind="write")
        box.call("ok_tool", {})
        ann = "\n".join(box.announcements())
        self.assertIn("ok_tool: 1/1", ann)
        self.assertNotIn("SERVING NOTHING", ann)

    def test_tool_error_contained(self):
        box = Toolbox()

        def boom(a):
            raise RuntimeError("kaput")
        box.register("boom", boom)
        self.assertTrue(box.call("boom", {}).startswith("TOOL ERROR"))


class WorldBandGuard(unittest.TestCase):
    """run-112b/115: a mechanical write never leaves the row's magnitude."""

    def test_band_refuses_raw_yuan(self):
        wb, ws = _wb()
        ws["T5"] = 4043.0                      # prior actual, millions
        w = Writer(wb)
        ok = w.write("Model", "U5", 4_043_000_000.0, prior_coord="T5")
        self.assertFalse(ok)
        self.assertTrue(w.log["band_refused"])

    def test_numeric_preview_guards_formula_strings(self):
        wb, ws = _wb()
        ws["T5"] = 100.0
        w = Writer(wb)
        ok = w.write("Model", "U5", "=99999999+1", prior_coord="T5")
        self.assertFalse(ok)                   # run-114 law


class NoFlagBudgetLaw(unittest.TestCase):
    """Dead doctrine stays dead: many flags never fail anything."""

    def test_summarize_never_says_failing(self):
        wb, ws = _wb()
        ws["A1"] = "row"
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}
        for r in range(1, 30):
            ws[f"U{r}"] = 1.0
        flags = [f"Model!U{r}" for r in range(1, 25)]   # 24/29 flagged: >80%
        card = scorecard(wb, spec, "2025", flags=flags)
        text = summarize(card, "2025", flags=flags, spec=spec, wb=wb)
        self.assertNotIn("FAILING", text)
        self.assertNotIn("BUDGET", text.upper())
        self.assertIn("never a blocker", text)


class KeyPlugSiteProtection(unittest.TestCase):
    """run-38: the tie-web plugged INTO the sales cell. Key rows are never
    plug sites — enforced in the loop's plug tool."""

    def test_plug_refuses_key_row(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T5"], ws["U5"] = 100.0, 110.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 9}],
                "key_rows": [{"sheet": "Model", "row": 5, "name": "revenue"}]}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_plug_residual({"check": "Model!9", "into": "Model!U5",
                                    "why": "test"})
        self.assertIn("REFUSED", out)
        self.assertIn("key rows", out)


class TransactionalWriteLaw(unittest.TestCase):
    """run-39: a write that breaks a passing check auto-reverts."""

    def test_set_input_reverts_on_broken_check(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        # check row 3: U1 - U2 must stay 0; U1=U2=50 passes.
        ws["T1"], ws["T2"] = 50.0, 50.0
        ws["U1"], ws["U2"] = 50.0, 50.0
        ws["U3"] = "=U1-U2"
        ws["T3"] = "=T1-T2"
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 3}],
                "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_set_input({"cell": "Model!U1", "value": 75.0,
                                "why": "p12: test line"})
        self.assertIn("REVERTED", out)
        self.assertEqual(ws["U1"].value, 50.0)   # restored

    def test_citation_required(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["U1"] = 1.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_set_input({"cell": "Model!U1", "value": 2.0,
                                "why": "because"})
        self.assertIn("REFUSED", out)
        self.assertIn("citation", out.lower().replace("cite", "citation"))


class NotDisclosedKeyRefusal(unittest.TestCase):
    """Keys are correct-or-flagged: a key can never be quietly stale."""

    def test_key_row_refused(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["U5"] = 1.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [],
                "key_rows": [{"sheet": "Model", "row": 5, "name": "revenue"}]}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_not_disclosed({"cell": "Model!U5",
                                    "looked": ["a", "b", "c"]})
        self.assertIn("REFUSED", out)


class RestatementPauseLaw(unittest.TestCase):
    """BOSS_MINDMAP Task B: detection pauses with a question; an answer
    resumes; below-threshold mismatches never pause."""

    def _targets(self, n, prior=1000.0):
        class T:
            def __init__(self, row):
                self.sheet = "Model"
                self.row = row
                self.key = ("Model", row)
                self.label = f"revenue line {row}"
                self.prior_value = prior + row
        return [T(r) for r in range(1, n + 1)]

    def _ledger(self, labels_nums):
        class It:
            def __init__(self, label, nums):
                self.doc = "AR25"
                self.page = 5
                self.label = label
                self.source_line = label + " " + " ".join(str(n) for n in nums)
                self.nums = nums

            def joinable(self):
                return True

        class L:
            def __init__(self, items):
                self.items = items
                self.faces = {("AR25", 5): "bs"}

            def prior_period_docs(self):
                return set()

            def face(self, d, p):
                return self.faces.get((d, p))
        return L([It(lab, nums) for lab, nums in labels_nums])

    class _JudgeYes:
        def json(self, system, user, validate, repair_retries=1):
            return {"verdict": "restatement", "why": "coherent BS cluster"}

    class _JudgeNo:
        def json(self, system, user, validate, repair_retries=1):
            return {"verdict": "noise", "why": "note-line homonyms"}

    def test_judged_restatement_pauses_and_answer_resumes(self):
        from updater.restate import RestatementPause, check_or_pause
        targets = self._targets(6)
        led = self._ledger([(t.label, [1500.0, 1300.0]) for t in targets])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RestatementPause):
                check_or_pause(d, "FY25", led, targets, [],
                               client=self._JudgeYes())
            import json
            from updater.restate import state_path
            p = state_path(d, "FY25")
            self.assertTrue(p.exists())
            p.write_text(json.dumps({"status": "answered", "restate": False}),
                         encoding="utf-8")
            out = check_or_pause(d, "FY25", led, targets, [],
                                 client=self._JudgeYes())
            self.assertEqual(out.get("status"), "answered")

    def test_judged_noise_continues(self):
        from updater.restate import check_or_pause
        targets = self._targets(6)
        led = self._ledger([(t.label, [1500.0, 1300.0]) for t in targets])
        with tempfile.TemporaryDirectory() as d:
            out = check_or_pause(d, "FY25", led, targets, [],
                                 client=self._JudgeNo())
            self.assertEqual(out.get("status"), "judged_noise")

    def test_dry_run_never_pauses(self):
        """Pausing is a judgment call; dry runs cannot judge — candidates
        are logged, never raised (the DFE false-fire law)."""
        from updater.restate import check_or_pause
        targets = self._targets(6)
        led = self._ledger([(t.label, [1500.0, 1300.0]) for t in targets])
        with tempfile.TemporaryDirectory() as d:
            out = check_or_pause(d, "FY25", led, targets, [], client=None)
            self.assertEqual(out.get("status"), "candidates")

    def test_matching_comparatives_no_pause(self):
        from updater.restate import check_or_pause
        targets = self._targets(6)
        led = self._ledger([(t.label, [1234.5, t.prior_value])
                            for t in targets])
        with tempfile.TemporaryDirectory() as d:
            out = check_or_pause(d, "FY25", led, targets, [],
                                 client=self._JudgeYes())
            self.assertEqual(out.get("status"), "none")

    def test_note_homonym_shapes_filtered(self):
        """3-number note lines and out-of-band values never become
        suspects (the exact DFE dry-run noise classes)."""
        from updater.restate import scan
        targets = self._targets(6)
        led = self._ledger(
            [(t.label, [56.4, 26.9, 83.3]) for t in targets[:3]]   # 3 nums
            + [(t.label, [1579.8, 229.9]) for t in targets[3:]])   # band out
        self.assertEqual(scan(led, targets), [])


class ArgToleranceLaw(unittest.TestCase):
    """run-1-live: the agent found AR 56,432.1 cited to p102 and lost it to
    argument-format misses. Write tools now accept the forms engines
    actually produce."""

    def _loop(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T1"], ws["U1"] = 50.0, 50.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        return AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None), ws

    def test_citation_alias_accepted(self):
        loop, ws = self._loop()
        out = loop.t_set_input({"cell": "Model!U1", "value": 60.0,
                                "citation": "p102: accounts receivable"})
        self.assertIn("WRITTEN", out)
        self.assertEqual(ws["U1"].value, 60.0)

    def test_sheet_plus_bare_cell_accepted(self):
        loop, ws = self._loop()
        out = loop.t_set_input({"sheet": "Model", "cell": "U1", "value": 61.0,
                                "why": "p102: line"})
        self.assertIn("WRITTEN", out)

    def test_row_ref_with_column_accepted(self):
        loop, _ = self._loop()
        sheet, row = loop._row_ref({"row": "Model!U49"})
        self.assertEqual((sheet, row), ("Model", 49))
        sheet, row = loop._row_ref({"cell": "U49", "sheet": "Model"})
        self.assertEqual((sheet, row), ("Model", 49))


class ConversionPressureLaw(unittest.TestCase):
    """run-1-live: 75/120 actions were traces. A stretch with no landed
    write now carries an escalating STEERING nudge."""

    def test_steering_appears_after_streak(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["U1"] = 1.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []

        class _Script:
            """Client scripted to trace the same-ish cells forever."""
            def __init__(self):
                self.n = 0

            def json(self, system, user, validate, repair_retries=1):
                self.n += 1
                if self.n > 8:
                    return {"action": "finish", "args": {"summary": "done"}}
                return {"action": "trace_cell",
                        "args": {"cell": f"Model!U{self.n}"}}
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=_Script(), budget=12)
        loop.run()
        self.assertIn("STEERING", getattr(loop, "_last", ""))

    def test_full_result_reaches_the_engine(self):
        """Run-1-live discovery: the legacy loop showed only the first 110
        chars of a result — the engine never saw multi-line tool output.
        The state block must carry the last result IN FULL."""
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["U1"] = 1.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        loop._last = "tool {}\nline1\nline2 GUILTY detail"
        self.assertIn("line2 GUILTY detail", loop._state_block())


class VacuousKeysLaw(unittest.TestCase):
    """run-1-live: law 4 passed on an EMPTY key list. Never again."""

    def test_empty_keys_cannot_pass(self):
        from updater.police import deterministic
        wb, ws = _wb()
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}
        out = deterministic(wb, spec, "2025", [], {}, EvidenceBook(),
                            {"flags": []})
        self.assertNotEqual(out["laws"]["4_keys"], "PASS")
        self.assertIn("NO KEY ROWS", out["laws"]["4_keys"])


class CellCitationLaw(unittest.TestCase):
    """run-2: the agent found the cash-tie fix citing a proven workbook
    cell and the page-only guard blocked it. Cell cites are legal."""

    def test_cell_cite_accepted(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T1"], ws["U1"] = 50.0, 50.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_set_input({"cell": "Model!U1", "value": 60.0,
                                "why": "ties Raw financials!U243 (statement)"})
        self.assertIn("WRITTEN", out)

    def test_citation_free_still_refused(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["U1"] = 1.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_set_input({"cell": "Model!U1", "value": 2.0,
                                "why": "because it looks right"})
        self.assertIn("REFUSED", out)


class KeysOracleLaw(unittest.TestCase):
    """run-2: formula-computed keys with correct values were counted
    unproven by write-bookkeeping. Law 4 judges VALUES via the evidence
    oracle; no-evidence keys must be flagged or they are findings."""

    def _setup(self, flag):
        wb, ws = _wb()
        ws["T5"], ws["U5"] = 100.0, 110.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [],
                "key_rows": [{"sheet": "Model", "row": 5, "name": "revenue"}]}

        class T:
            sheet, row, key, label, prior_value = "Model", 5, ("Model", 5), \
                "revenue", 100.0

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        from updater.police import verify
        return verify(wb, spec, "2025", _Ledger(), [T()], {}, EvidenceBook(),
                      {"flags": ["Model!U5"] if flag else []})

    def test_no_evidence_unflagged_is_finding(self):
        out = self._setup(flag=False)
        self.assertIn("FAIL", out["laws"]["4_keys"])
        self.assertTrue(any("unverified" in f for f in out["findings"]))

    def test_no_evidence_flagged_is_honest(self):
        out = self._setup(flag=True)
        self.assertIn("PASS", out["laws"]["4_keys"])


class BalancedOrMarkedLaw(unittest.TestCase):
    """Owner review of run 2: the model shipped unbalanced with unmarked
    check cells. Any still-failing check is red-flagged by CODE."""

    def test_failing_check_gets_flagged(self):
        from updater import ops
        from updater.evidence import EvidenceBook
        wb, ws = _wb()
        ws["U1"], ws["U2"] = 100.0, 60.0
        ws["U3"] = "=U1-U2"                       # check row, residual 40
        spec = {"year_axis": {"Model": {"columns": {"2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 3}],
                "key_rows": []}
        w = Writer(wb)
        book = EvidenceBook()
        n = ops.flag_failed_checks(wb, spec, "2025", w, book, lambda s: None)
        self.assertEqual(n, 1)
        self.assertIn("Model!U3", w.log["flags"])
        self.assertEqual(book.entries["Model!U3"].grade, "C")

    def test_passing_check_untouched(self):
        from updater import ops
        from updater.evidence import EvidenceBook
        wb, ws = _wb()
        ws["U1"], ws["U2"] = 100.0, 100.0
        ws["U3"] = "=U1-U2"
        spec = {"year_axis": {"Model": {"columns": {"2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 3}],
                "key_rows": []}
        w = Writer(wb)
        n = ops.flag_failed_checks(wb, spec, "2025", w, EvidenceBook(),
                                   lambda s: None)
        self.assertEqual(n, 0)
        self.assertEqual(w.log["flags"], [])


class PlugRedirectLaw(unittest.TestCase):
    """Owner review of run 2: three plug attempts died on formula cells.
    A formula 'into' redirects to its input site, like set_input."""

    def test_plug_lands_through_link_cell(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        raw = wb.create_sheet("Raw")
        # Model!U5 is a link to Raw!U7 (the typed input); check U9 = U5-U6
        ws["T5"], ws["U5"] = "=Raw!T5", "=Raw!U5"
        raw["T5"], raw["U5"] = 80.0, 80.0
        ws["T6"], ws["U6"] = 80.0, 120.0
        ws["U9"], ws["T9"] = "=U5-U6", "=T5-T6"
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}},
                              "Raw": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 9}],
                "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_plug_residual({"check": "Model!9", "into": "Model!U5",
                                    "why": "test plug"})
        self.assertIn("PLUGGED", out)
        self.assertEqual(raw["U5"].value, 120.0)   # landed at the input site


class ThirdLookIsAPlugLaw(unittest.TestCase):
    """run-4: 67 diagnoses of four evidence-less checks, zero plugs. The
    second guilty-free diagnosis of a check escalates with plug sites."""

    def test_second_diagnosis_escalates(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T1"], ws["U1"] = 100.0, 100.0
        ws["T2"], ws["U2"] = 60.0, 20.0
        ws["U3"], ws["T3"] = "=U1-U2", "=T1-T2"     # residual 80
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 3}],
                "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        first = loop.t_diagnose_balance({"check": "Model!3"})
        self.assertNotIn("ESCALATE NOW", first)
        second = loop.t_diagnose_balance({"check": "Model!3"})
        self.assertIn("ESCALATE NOW", second)
        self.assertIn("Model!U", second)             # names a plug site


def _mock_item(doc, page, label, nums):
    class It:
        pass
    it = It()
    it.doc, it.page, it.label, it.nums = doc, page, label, list(nums)
    it.source_line = f"{label} " + " ".join(f"{n:,.2f}" for n in nums)
    it.scale_hint = None
    it.joinable = lambda: True
    return it


def _mock_ledger(items, face="bs"):
    class L:
        pass
    led = L()
    led.items = list(items)
    led.faces = {(it.doc, it.page): face for it in items}
    led.prior_period_docs = lambda: set()
    led.face = lambda d, p: led.faces.get((d, p))
    led.join_pool = lambda: led.items
    return led


def _mock_target(sheet, row, label, prior):
    class T:
        pass
    t = T()
    t.sheet, t.row, t.key, t.label, t.prior_value = \
        sheet, row, (sheet, row), label, prior
    return t


class TruthOutranksBalanceLaw(unittest.TestCase):
    """run-6: a plug moved a disclosure-proven cell (2,156.07, cited p95)
    to 14,272 to zero the balance check — falsifying CA/TA by 12,116.
    Plugs REFUSE disclosure-proven cells."""

    def test_plug_refuses_proven_cell(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        # U5 and U6 tie their evidence; U7 is stale with NO evidence (the
        # residual's true home); check U9 = U5 - U6 - U7
        ws["T5"], ws["U5"] = 1000.0, 1200.0
        ws["T6"], ws["U6"] = 500.0, 700.0
        ws["T7"], ws["U7"] = 500.0, 400.0
        ws["U9"], ws["T9"] = "=U5-U6-U7", "=T5-T6-T7"
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 9}],
                "key_rows": []}
        targets = [_mock_target("Model", 5, "alpha receivables", 1000.0),
                   _mock_target("Model", 6, "beta payables", 480.0),
                   _mock_target("Model", 7, "misc stale", 500.0)]
        led = _mock_ledger([
            _mock_item("AR", 5, "alpha receivables", [1200.0, 1000.0]),
            _mock_item("AR", 5, "beta payables", [700.0, 480.0])])
        loop = AgentLoop(wb, spec, 2025, led, targets, {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_plug_residual({"check": "Model!9", "into": "Model!U5",
                                    "why": "test"})
        self.assertIn("REFUSED", out)
        self.assertIn("disclosure-proven", out)
        self.assertEqual(ws["U5"].value, 1200.0)


class SignAwarePlugLaw(unittest.TestCase):
    """run-6: six plugs doubled the residual on negative-entry components
    and reverted. The plug measures the check's derivative first."""

    def test_plug_lands_on_negative_entry_component(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T1"], ws["U1"] = 100.0, 100.0
        ws["T2"], ws["U2"] = 100.0, 20.0        # enters check negatively
        ws["U3"], ws["T3"] = "=U1-U2", "=T1-T2"  # residual 80
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 3}],
                "key_rows": []}
        loop = AgentLoop(wb, spec, 2025, _mock_ledger([]), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_plug_residual({"check": "Model!3", "into": "Model!U2",
                                    "why": "test"})
        self.assertIn("PLUGGED", out)
        self.assertEqual(ws["U2"].value, 100.0)   # 20 - 80/(-1)


class TargetColumnGuardLaw(unittest.TestCase):
    """run-6: two 2025 actuals were written into the 2026 column (V75).
    Mark-to-actual writes outside the target column are refused unless
    explicitly declared a forecast integrity repair."""

    def _loop(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["U1"], ws["V1"] = 1.0, 2.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U",
                                                    "2026": "V"}}},
                "check_rows": [], "key_rows": []}
        return AgentLoop(wb, spec, 2025, _mock_ledger([]), [], {}, Writer(wb),
                         EvidenceBook(), client=None), ws

    def test_forecast_column_refused(self):
        loop, ws = self._loop()
        out = loop.t_set_input({"cell": "Model!V1", "value": 9.0,
                                "why": "p10: line"})
        self.assertIn("REFUSED", out)
        self.assertEqual(ws["V1"].value, 2.0)

    def test_declared_integrity_repair_allowed(self):
        loop, ws = self._loop()
        out = loop.t_set_input({"cell": "Model!V1", "value": 9.0,
                                "why": "p10: integrity repair",
                                "forecast_repair": True})
        self.assertIn("WRITTEN", out)


class ReclassFinderLaw(unittest.TestCase):
    """run-6: the −12,116 was a reclass whose destination row has no prior
    to triangulate on — but the residual fingerprints it. diagnose names
    the RECLASS CANDIDATE with its exact set_input."""

    def test_reclass_candidate_named(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T1"], ws["U1"] = 90.0, 100.0        # stale; disclosed 112
        ws["T2"], ws["U2"] = 90.0, 112.0
        ws["U3"], ws["T3"] = "=U1-U2", "=T1-T2"  # residual -12
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 3}],
                "key_rows": []}
        targets = [_mock_target("Model", 1, "gamma investments", 90.0),
                   _mock_target("Model", 7, "anchor one", 1000.0),
                   _mock_target("Model", 8, "anchor two", 500.0)]
        led = _mock_ledger([
            # two anchors ratify the page's scale
            _mock_item("AR", 5, "anchor one", [1100.0, 1000.0]),
            _mock_item("AR", 5, "anchor two", [600.0, 500.0]),
            # the reclass destination: model 100, disclosed 112
            _mock_item("AR", 5, "gamma investments", [112.0])])
        loop = AgentLoop(wb, spec, 2025, led, targets, {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_diagnose_balance({"check": "Model!3"})
        self.assertIn("RECLASS CANDIDATE", out)
        self.assertIn("Model!U1", out)


class ImpliedPriorLaw(unittest.TestCase):
    """Owner keys law (run-7 review): segment breakdowns must be UPDATED.
    The run-103 mechanism, ported: implied_prior = current/(1+pct) tying
    the model's own prior serves single-year MD&A rows."""

    def _spec(self):
        return {"year_axis": {"Driver": {"columns": {"2024": "I",
                                                     "2025": "J"}}},
                "check_rows": [], "key_rows": []}

    def test_unique_tie_becomes_candidate(self):
        """CANDIDATES only — never a write (measured: flat lines admit
        prose coincidences; the agent judges, then set_inputs)."""
        from updater import ops
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Driver"
        ws["I6"], ws["J6"] = 28358.2, 28358.2      # stale segment row
        t = _mock_target("Driver", 6, "clean energy equipment", 28358.2)
        # MD&A line: current 31,780.0 with 同比+12.07% — implied ≈ prior
        it = _mock_item("AR", 12, "clean energy equipment", [31780.0, 12.07])
        it.source_line = "清洁高效能源装备 31,780.0 同比增长 12.07%"
        led = _mock_ledger([it])
        cands = ops.implied_prior_candidates(wb, self._spec(), "2025", [t],
                                             led, {}, lambda s: None)
        self.assertEqual(len(cands), 1)
        self.assertAlmostEqual(cands[0]["value"], 31780.0, places=1)
        self.assertEqual(ws["J6"].value, 28358.2)   # NOT written

    def test_ambiguous_or_flat_refused(self):
        from updater import ops
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Driver"
        ws["I6"], ws["J6"] = 1000.0, 1000.0
        t = _mock_target("Driver", 6, "alpha segment", 1000.0)
        # ~0% change matches every stagnant row — must be refused
        it = _mock_item("AR", 12, "alpha segment", [1001.0, 0.1])
        it.source_line = "alpha segment 1,001.0 同比增长 0.1%"
        led = _mock_ledger([it])
        cands = ops.implied_prior_candidates(wb, self._spec(), "2025", [t],
                                             led, {}, lambda s: None)
        self.assertEqual(cands, [])
        self.assertEqual(ws["J6"].value, 1000.0)

    def test_non_change_percents_refused(self):
        """The measured coincidence classes: an ownership stake (2.41%) and
        an FX-sensitivity percent must never act as a 同比."""
        from updater import ops
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Driver"
        ws["I6"], ws["J6"] = 44258.0, 44258.0
        t = _mock_target("Driver", 6, "production", 44258.0)
        it = _mock_item("AR", 68, "associate", [60000.0, 2.41, 45338.1])
        it.source_line = "联营企业 60,000.00 2.41% 45,338.1"   # no 同比/增减
        led = _mock_ledger([it])
        cands = ops.implied_prior_candidates(wb, self._spec(), "2025", [t],
                                             led, {}, lambda s: None)
        self.assertEqual(cands, [])


class KeysNotExcusedByFlagsLaw(unittest.TestCase):
    """Owner keys law: a key with known disclosed evidence must TIE — a
    red flag no longer counts as passing."""

    def test_flagged_mismatch_still_fails(self):
        from updater.police import verify
        wb, ws = _wb()
        ws["T5"], ws["U5"] = 1000.0, 900.0     # disclosed says 1,200
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [],
                "key_rows": [{"sheet": "Model", "row": 5,
                              "name": "investing cash flow"}]}
        targets = [_mock_target("Model", 5, "investing activities", 1000.0),
                   _mock_target("Model", 6, "anchor", 480.0)]
        led = _mock_ledger([
            _mock_item("AR", 5, "investing activities", [1200.0, 1000.0]),
            _mock_item("AR", 5, "anchor", [600.0, 480.0])])
        out = verify(wb, spec, "2025", led, targets, {}, EvidenceBook(),
                     {"flags": ["Model!U5"]})     # flagged — and still FAIL
        self.assertIn("FAIL", out["laws"]["4_keys"])
        self.assertIn("FAIL", out["laws"]["1_announced"])


class StaleDriverLeavesLaw(unittest.TestCase):
    """Owner keys law: segment leaves feeding revenue/GP still holding
    exactly their prior value are stale and fail law 4."""

    def test_stale_leaf_detected(self):
        from updater.police import _stale_driver_leaves
        wb, ws = _wb()
        ws["U4"] = "=U6+U7"
        ws["T6"], ws["U6"] = 28358.2, 28358.2     # stale segment leaf
        ws["T7"], ws["U7"] = 7258.0, 8100.0       # updated leaf
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [],
                "key_rows": [{"sheet": "Model", "row": 4, "name": "revenue"}]}
        stale = _stale_driver_leaves(wb, spec, "2025")
        self.assertEqual(stale, ["Model!U6"])


class PlugChecksOnlyLaw(unittest.TestCase):
    """run-8: the agent fed KEY cells as 'checks' and the tool zeroed CFI
    itself, then ping-ponged components. Plugs zero SPEC CHECK ROWS only;
    one plug per cell per run."""

    def _loop(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        # two check rows sharing component U2; U5 is a key-like cell
        ws["T1"], ws["U1"] = 100.0, 100.0
        ws["T2"], ws["U2"] = 100.0, 20.0
        ws["U3"], ws["T3"] = "=U1-U2", "=T1-T2"      # check: residual 80
        ws["T6"], ws["U6"] = 50.0, 50.0
        ws["U7"], ws["T7"] = "=U2-U6+30", "=T2-T6+50"  # second check on U2
        ws["T5"], ws["U5"] = 900.0, -11181.0          # a key cell (CFI-like)
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 3},
                               {"sheet": "Model", "row": 7}],
                "key_rows": [{"sheet": "Model", "row": 5,
                              "name": "investing cash flow"}]}
        return AgentLoop(wb, spec, 2025, _mock_ledger([]), [], {}, Writer(wb),
                         EvidenceBook(), client=None), ws

    def test_key_cell_as_check_refused(self):
        loop, ws = self._loop()
        out = loop.t_plug_residual({"check": "Model!U5", "into": "Model!U2",
                                    "why": "test"})
        self.assertIn("REFUSED", out)
        self.assertIn("not a check row", out)
        self.assertEqual(ws["U5"].value, -11181.0)   # key untouched

    def test_r_prefixed_check_ref_parses(self):
        # U1 feeds only check 3 (U2 is shared with check 7, and the
        # full-scorecard law now rightly reverts plugs there)
        loop, ws = self._loop()
        out = loop.t_plug_residual({"check": "Model!r3", "into": "Model!U1",
                                    "why": "test"})
        self.assertIn("PLUGGED", out)                # 'r3' == row 3

    def test_shared_cell_plug_reverts_not_ping_pongs(self):
        """The old ping-pong cell (U2 feeds checks 3 AND 7): the full-
        scorecard law reverts the plug instead of letting the residual
        migrate between checks."""
        loop, ws = self._loop()
        out = loop.t_plug_residual({"check": "Model!3", "into": "Model!U2",
                                    "why": "test"})
        self.assertIn("REVERTED", out)
        self.assertEqual(ws["U2"].value, 20.0)

    def test_second_plug_on_same_cell_refused(self):
        loop, ws = self._loop()
        first = loop.t_plug_residual({"check": "Model!3", "into": "Model!U1",
                                      "why": "test"})
        self.assertIn("PLUGGED", first)
        ws["U6"] = 55.0                  # keep check 7 failing post-plug
        second = loop.t_plug_residual({"check": "Model!7", "into": "Model!U1",
                                       "why": "test"})
        self.assertIn("REFUSED", second)
        self.assertIn("already a plug site", second)


class KeyDiagnoseForbidsPlugLaw(unittest.TestCase):
    """run-8: key-mode diagnosis must name the legal exit (components via
    set_input) and forbid plugging in its own output."""

    def test_key_mode_output_forbids_plug(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T5"], ws["U5"] = 1000.0, 900.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [],
                "key_rows": [{"sheet": "Model", "row": 5,
                              "name": "investing cash flow"}]}
        targets = [_mock_target("Model", 5, "investing activities", 1000.0),
                   _mock_target("Model", 6, "anchor", 480.0)]
        led = _mock_ledger([
            _mock_item("AR", 5, "investing activities", [1200.0, 1000.0]),
            _mock_item("AR", 5, "anchor", [600.0, 480.0])])
        loop = AgentLoop(wb, spec, 2025, led, targets, {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_diagnose_balance({"key": "investing"})
        self.assertIn("FORBIDDEN", out)
        self.assertIn("set_input", out)


class PacketArchitectureLaw(unittest.TestCase):
    """REDESIGN (council 2026-08-18): the unit of work is a packet; the
    queue derives from the workbook itself; compile converts columns;
    surgeon requires decisions[]; 'I looked' is schema-invalid."""

    def _setup(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T1"], ws["U1"] = 100.0, 100.0       # open stale row
        ws["T2"], ws["U2"] = 50.0, 50.0         # open stale row
        ws["T3"], ws["U3"] = 20.0, 30.0
        ws["U9"], ws["T9"] = "=U3-30", "=T3-20"  # check dep only on U3; passes
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 9}],
                "key_rows": [{"sheet": "Model", "row": 1, "name": "revenue"}]}
        targets = [_mock_target("Model", 2, "beta line", 50.0)]
        led = _mock_ledger([_mock_item("AR", 7, "beta line", [80.0, 50.0])])
        tk = AgentLoop(wb, spec, 2025, led, targets, {}, Writer(wb),
                       EvidenceBook(), client=None)
        return wb, ws, spec, tk

    def test_queue_derives_from_workbook(self):
        from updater import packets
        wb, ws, spec, tk = self._setup()
        ws["U3"] = 25.0            # break the check -> residual packet
        q = packets.derive_queue(wb, spec, "2025", {}, tk.writer.log)
        self.assertIn("compile:Model", q)
        self.assertTrue(any(p.startswith("residual:Model!9") for p in q))
        self.assertEqual(q[-1], "deliver")

    def test_surgeon_schema_gate(self):
        from updater.closer import PacketCloser
        _wb_, _ws, _spec, tk = self._setup()
        pc = PacketCloser(tk, client=None, log=lambda s: None)
        self.assertTrue(pc._val_surgeon({"observation": "I looked"}))
        self.assertTrue(pc._val_surgeon({"decisions": []}))
        self.assertTrue(pc._val_surgeon(
            {"decisions": [{"leaf": "Model!U2", "do": "ponder"}]}))
        self.assertEqual(pc._val_surgeon(
            {"decisions": [{"leaf": "Model!U2", "do": "flag",
                            "why": "x"}]}), [])

    def test_compile_applies_through_guards(self):
        from updater.closer import PacketCloser

        class _Client:
            def __init__(self):
                self.n = 0

            def json(self, system, user, validate, repair_retries=1):
                self.n += 1
                return {"writes": [{"cell": "Model!U2", "value": 80.0,
                                    "why": "p7: beta line 80.0"}],
                        "not_disclosed": [], "flags": [], "skips": []}
        wb, ws, spec, tk = self._setup()
        pc = PacketCloser(tk, client=_Client(), log=lambda s: None)
        report = pc.run_compile("Model")
        self.assertIn("1 written", report)
        self.assertEqual(ws["U2"].value, 80.0)

    def test_compile_rejection_gets_repair_round(self):
        from updater.closer import PacketCloser

        class _Client:
            """First write breaks the passing check (U9 depends on U2-U3);
            repair round flags instead."""
            def __init__(self):
                self.rounds = []

            def json(self, system, user, validate, repair_retries=1):
                self.rounds.append(user)
                if len(self.rounds) == 1:
                    return {"writes": [{"cell": "Model!U3", "value": 900.0,
                                        "why": "p7: wrong read"}],
                            "not_disclosed": [], "flags": [], "skips": []}
                return {"writes": [],
                        "not_disclosed": [], "skips": [],
                        "flags": [{"cell": "Model!U3",
                                   "why": "cannot prove; leaving flagged"}]}
        wb, ws, spec, tk = self._setup()
        # make check U9 PASS first so the transactional guard has a baseline
        ws["U3"] = 30.0
        ws["U9"] = "=U2-U3-20"
        client = _Client()
        pc = PacketCloser(tk, client=client, log=lambda s: None)
        report = pc.run_compile("Model")
        self.assertEqual(ws["U3"].value, 30.0)      # reverted, not corrupted
        self.assertEqual(len(client.rounds), 2)     # repair round happened
        self.assertIn("APPLY REPORT", client.rounds[1])
        self.assertIn("1 flagged", report)

    def test_l0_invalid_packet_falls_back(self):
        from updater.closer import PacketCloser

        class _Client:
            def json(self, system, user, validate, repair_retries=1):
                errs = validate({"packet": "explore:the-formula-graph"})
                assert errs                      # validator refuses inventions
                return {"packet": "deliver", "situation": "done"}
        _wb_, _ws, _spec, tk = self._setup()
        pc = PacketCloser(tk, client=_Client(), log=lambda s: None)
        self.assertEqual(pc.pick_packet(["compile:Model"]), "deliver")


class TableIslandLaw(unittest.TestCase):
    """Council wall-1: grid geometry is evidence. The renderer attaches
    headers to every cell; selection is number-anchored (>=2 ties)."""

    def test_renderer_attaches_headers(self):
        from updater.islands import _render_table
        out = _render_table([
            ["项目", "2025年", "同比增减(%)"],
            ["清洁高效能源装备", "31,780.0", "12.07"],
            ["可再生能源装备", "18,500.0", "-3.20"]])
        self.assertIn("清洁高效能源装备 | 2025年: 31,780.0 | 同比增减(%): 12.07",
                      out)

    def test_selection_is_number_anchored(self):
        from updater.islands import relevant
        seg = ("清洁高效能源装备 | 2025年: 31,780.0 | 同比增减(%): 12.07\n"
               "可再生能源装备 | 2025年: 18,500.0 | 同比增减(%): -3.20")
        prose = ("行业展望 | 装机容量: 43.0 | 增长: 10.5\n"
                 "市场份额 | 比例: 2.41 | 变动: 0.10")
        picked = relevant([(12, seg), (29, prose)],
                          [28358.2, 19111.4])       # implied priors of seg
        self.assertEqual([p for p, _t in picked], [12])


class ClosingBellLaw(unittest.TestCase):
    """Council wall-2: the endgame is a decision, not a draw — one
    terminal disposition per residual generator."""

    def _setup(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T1"], ws["U1"] = 100.0, 100.0
        ws["T2"], ws["U2"] = 100.0, 76.0            # residual cause
        ws["U3"], ws["T3"] = "=U1-U2-24", "=T1-T2"   # check fails at 0? U3=0
        ws["U3"] = "=U1-U2-48"                       # residual = -24
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 3}],
                "key_rows": []}
        return wb, ws, spec, AgentLoop(wb, spec, 2025, _mock_ledger([]), [],
                                       {}, Writer(wb), EvidenceBook(),
                                       client=None)

    def test_bell_executes_plug_disposition(self):
        from updater.closer import PacketCloser

        class _Client:
            def json(self, system, user, validate, repair_retries=1):
                assert "residual vector" in user
                return {"disposition": "plug", "into": "Model!U2",
                        "why": "no provable leaf; absorbing into misc"}
        wb, ws, spec, tk = self._setup()
        pc = PacketCloser(tk, client=_Client(), log=lambda s: None)
        pc.closing_bell()
        from updater.evaluator import Evaluator
        self.assertAlmostEqual(Evaluator(wb).cell("Model", "U3"), 0.0,
                               places=6)

    def test_bell_flag_disposition_is_reasoned(self):
        from updater.closer import PacketCloser

        class _Client:
            def json(self, system, user, validate, repair_retries=1):
                assert validate({"disposition": "flag"})   # why required
                return {"disposition": "flag",
                        "why": "plug would move a disclosed value"}
        wb, ws, spec, tk = self._setup()
        pc = PacketCloser(tk, client=_Client(), log=lambda s: None)
        pc.closing_bell()
        self.assertIn("Model!U3", tk.writer.log["flags"])


class AtomicReclassLaw(unittest.TestCase):
    """Council wall-3: the twin signature triggers one bound question;
    the move is two-legged and atomic — both keys tie or nothing is
    written."""

    def _setup(self, disclosed_a, disclosed_b):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        # key A = SUM(U2:U3); key B = SUM(U6:U7); item 594 misbooked in A
        ws["T2"], ws["U2"] = 1000.0, 1594.0
        ws["T3"], ws["U3"] = 500.0, 500.0
        ws["U4"], ws["T4"] = "=SUM(U2:U3)", "=SUM(T2:T3)"
        ws["T6"], ws["U6"] = 2000.0, 2000.0
        ws["T7"], ws["U7"] = 300.0, 306.0
        ws["U8"], ws["T8"] = "=SUM(U6:U7)", "=SUM(T6:T7)"
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [],
                "key_rows": [
                    {"sheet": "Model", "row": 4, "name": "investing cash flow"},
                    {"sheet": "Model", "row": 8, "name": "financing cash flow"}]}
        targets = [
            _mock_target("Model", 4, "investing activities", 1500.0),
            _mock_target("Model", 8, "financing activities", 2300.0),
            _mock_target("Model", 2, "alpha", 1000.0),
            _mock_target("Model", 6, "beta", 2000.0)]
        led = _mock_ledger([
            _mock_item("AR", 5, "investing activities",
                       [disclosed_a, 1500.0]),
            _mock_item("AR", 5, "financing activities",
                       [disclosed_b, 2300.0])])
        tk = AgentLoop(wb, spec, 2025, led, targets, {}, Writer(wb),
                       EvidenceBook(), client=None)
        return wb, ws, tk

    def test_correct_move_commits_atomically(self):
        from updater.closer import PacketCloser
        wb, ws, tk = self._setup(1500.0, 2900.0)

        class _Client:
            def json(self, system, user, validate, repair_retries=1):
                assert "SECTION" in user
                return {"move": {"from": "Model!U2", "to": "Model!U7",
                                 "amount": 594.0,
                                 "why": "p101: booked under financing"}}
        pc = PacketCloser(tk, client=_Client(), log=lambda s: None)
        r = pc.atomic_reclass("investing cash flow", "financing cash flow",
                              594.0)
        self.assertIn("both keys tie", r)
        self.assertEqual(ws["U2"].value, 1000.0)
        self.assertEqual(ws["U7"].value, 900.0)

    def test_wrong_move_reverts_both_legs(self):
        from updater.closer import PacketCloser
        wb, ws, tk = self._setup(1500.0, 2900.0)

        class _Client:
            def json(self, system, user, validate, repair_retries=1):
                return {"move": {"from": "Model!U3", "to": "Model!U6",
                                 "amount": 100.0, "why": "guess"}}
        pc = PacketCloser(tk, client=_Client(), log=lambda s: None)
        r = pc.atomic_reclass("investing cash flow", "financing cash flow",
                              594.0)
        self.assertIn("reverted", r)
        self.assertEqual(ws["U3"].value, 500.0)     # untouched
        self.assertEqual(ws["U6"].value, 2000.0)


class SegmentShapeLaw(unittest.TestCase):
    """Owner ruling: segments are mappable (ChatGPT evidence). Where
    numbers cannot anchor (analyst segmentation), SHAPE selects: revenue+
    cost/margin+change headers = a segment table in any language."""

    def test_revenue_shaped_selection(self):
        from updater.islands import revenue_shaped
        seg = ("能源装备制造 | 营业收入: 5,800,544.42 | 营业成本: 4,989,711.73 | "
               "毛利率（%）: 13.98 | 营业收入比上年增减（%）: 22.00\n"
               "工程与服务 | 营业收入: 1,200,000.00 | 营业成本: 900,000.00 | "
               "毛利率（%）: 25.00 | 营业收入比上年增减（%）: 5.00\n"
               "现代制造服务 | 营业收入: 800,000.00 | 营业成本: 700,000.00 | "
               "毛利率（%）: 12.50 | 营业收入比上年增减（%）: -2.00")
        holdings = ("中国西电 | 账面余额: 1,010.77 | 期末数: 1,098.27\n"
                    "某公司 | 账面余额: 2,762,482.00 | 坏账准备: 552,496.40\n"
                    "另一家 | 账面余额: 180,000.00 | 坏账准备: 18,000.00")
        picked = revenue_shaped([(13, seg), (254, holdings)])
        self.assertEqual([p for p, _t in picked], [13])


class DefinitionalAlignmentLaw(unittest.TestCase):
    """Owner ruling: model CF sometimes deviates from the statement BY
    DESIGN. Prior year ties -> definitions align, must tie now; prior
    year deviates -> designed presentation, never force equality."""

    def _closer(self, model_prior, stmt_prior):
        from updater.loop import AgentLoop
        from updater.closer import PacketCloser
        wb, ws = _wb()
        raw = wb.create_sheet("Raw")
        ws["T5"], ws["U5"] = model_prior, -6082.7
        raw["T9"], raw["U9"] = stmt_prior, -10587.3
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}},
                              "Raw": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [],
                "key_rows": [
                    {"sheet": "Model", "row": 5, "name": "investing cash flow"},
                    {"sheet": "Raw", "row": 9, "name": "investing cash flow"}]}
        tk = AgentLoop(wb, spec, 2025, _mock_ledger([]), [], {}, Writer(wb),
                       EvidenceBook(), client=None)
        return PacketCloser(tk, client=None, log=lambda s: None)

    def test_aligned_priors_report_aligned(self):
        pc = self._closer(-2773.7, -2773.7)
        self.assertTrue(pc._prior_alignment("investing cash flow"))

    def test_deviating_priors_block_forced_equality(self):
        pc = self._closer(-2773.7, -3500.0)
        self.assertFalse(pc._prior_alignment("investing cash flow"))
        r = pc.atomic_reclass("investing cash flow", "investing cash flow",
                              594.0)
        self.assertIn("definitional deviation", r)


class LookElsewhereLaw(unittest.TestCase):
    """Owner skill ruling: one table will not have all the answers — the
    agent may ASK for other places, and the runtime serves doc-wide
    number hits + unseen islands; only then is not_disclosed honest."""

    def test_need_gets_other_places_then_write_lands(self):
        from updater.loop import AgentLoop
        from updater.closer import PacketCloser
        wb, ws = _wb()
        ws["T1"], ws["U1"] = 5100.0, 5100.0     # stale segment-ish row
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}
        targets = [_mock_target("Model", 1, "hydro segment", 5100.0)]
        # the answer lives on a page NOT in the compile card's islands:
        note = _mock_item("AR", 154, "水电分部", [6200.0, 5100.0])
        led = _mock_ledger([note])

        class _Client:
            def __init__(self):
                self.rounds = []

            def json(self, system, user, validate, repair_retries=1):
                self.rounds.append(user)
                if len(self.rounds) == 1:
                    return {"writes": [], "need": [
                        {"cell": "Model!U1",
                         "looking_for": "hydro segment revenue"}],
                        "not_disclosed": [], "flags": [], "skips": []}
                assert "OTHER PLACES" in user and "p154" in user
                return {"writes": [{"cell": "Model!U1", "value": 6200.0,
                                    "why": "p154: 水电分部 6,200.0"}],
                        "not_disclosed": [], "flags": [], "skips": []}
        tk = AgentLoop(wb, spec, 2025, led, targets, {}, Writer(wb),
                       EvidenceBook(), client=None)
        client = _Client()
        pc = PacketCloser(tk, client=client, log=lambda s: None)
        report = pc.run_compile("Model")
        self.assertEqual(len(client.rounds), 2)
        self.assertIn("1 written", report)
        self.assertEqual(ws["U1"].value, 6200.0)


class StatementTranscriptionLaw(unittest.TestCase):
    """Owner issue 1: a statement tab is a TRANSCRIPTION task — the card
    carries the ordered statement pages, not per-row snippets."""

    def test_transcript_ordered_faces_only(self):
        from updater.packets import statement_transcript
        it1 = _mock_item("AR", 96, "资产总计", [162674.2, 148917.4])
        it2 = _mock_item("AR", 101, "经营活动现金流量", [2014.3, 10059.5])
        it3 = _mock_item("AR", 21, "存货 md&a", [26171.2, 21685.3])
        led = _mock_ledger([it1, it2, it3])
        led.faces = {("AR", 96): "bs", ("AR", 101): "cf", ("AR", 21): None}
        out = statement_transcript(led)
        self.assertIn("STATEMENT PAGE p96 (bs)", out)
        self.assertIn("STATEMENT PAGE p101 (cf)", out)
        self.assertNotIn("md&a", out)                 # non-face excluded
        self.assertLess(out.index("p96"), out.index("p101"))   # ordered


class PlugFullScorecardLaw(unittest.TestCase):
    """Owner issue 2: the plug zeroed its check and silently broke five
    forecast years. Plugs are transactional against the WHOLE scorecard."""

    def test_plug_reverts_when_it_breaks_another_year(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        # check row 3 in both years; V3 depends on U2 (roll-forward):
        ws["T1"], ws["U1"], ws["V1"] = 100.0, 100.0, 100.0
        ws["T2"], ws["U2"], ws["V2"] = 100.0, 76.0, "=U2"
        ws["U3"] = "=U1-U2-48"                       # 2025 residual -24
        ws["V3"] = "=V1-V2-24"                       # 2026 passes at 0
        ws["T3"] = "=T1-T2"
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U",
                                                    "2026": "V"}}},
                "check_rows": [{"sheet": "Model", "row": 3}],
                "key_rows": []}
        loop = AgentLoop(wb, spec, 2025, _mock_ledger([]), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_plug_residual({"check": "Model!3", "into": "Model!U2",
                                    "why": "test"})
        self.assertIn("REVERTED", out)
        self.assertIn("broke", out)
        self.assertEqual(ws["U2"].value, 76.0)       # restored — no sweep


class PrintedLandLaw(unittest.TestCase):
    """Owner issue 1/2 root: statement detail rows are printed facts —
    a cell whose neighbors tie face evidence is never a plug site."""

    def test_plug_refused_inside_printed_section(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T4"], ws["U4"] = 1000.0, 1200.0          # ties print
        ws["T5"], ws["U5"] = 480.0, 700.0            # ties print
        ws["T6"], ws["U6"] = 300.0, 320.0            # the target between them
        ws["U9"] = "=U6-300"                         # failing check
        ws["T9"] = "=T6-300"
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [{"sheet": "Model", "row": 9}],
                "key_rows": []}
        targets = [_mock_target("Model", 4, "alpha detail", 1000.0),
                   _mock_target("Model", 5, "beta detail", 480.0),
                   _mock_target("Model", 6, "gamma detail", 300.0)]
        led = _mock_ledger([
            _mock_item("AR", 5, "alpha detail", [1200.0, 1000.0]),
            _mock_item("AR", 5, "beta detail", [700.0, 480.0])])
        loop = AgentLoop(wb, spec, 2025, led, targets, {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_plug_residual({"check": "Model!9", "into": "Model!U6",
                                    "why": "test"})
        self.assertIn("REFUSED", out)
        self.assertIn("printed statement section", out)


class DetailTieOutLaw(unittest.TestCase):
    """Owner fundamental: totals-only checking is blind — EVERY row with
    unique print evidence must tie, key or not."""

    def test_non_key_detail_off_print_is_a_finding(self):
        from updater.police import verify
        wb, ws = _wb()
        ws["T5"], ws["U5"] = 1000.0, 900.0           # detail off print
        ws["T6"], ws["U6"] = 480.0, 600.0            # ties
        spec = {"year_axis": {"Model": {"columns": {"2024": "T", "2025": "U"}}},
                "check_rows": [], "key_rows": []}
        targets = [_mock_target("Model", 5, "alpha detail", 1000.0),
                   _mock_target("Model", 6, "beta detail", 480.0)]
        led = _mock_ledger([
            _mock_item("AR", 5, "alpha detail", [1200.0, 1000.0]),
            _mock_item("AR", 5, "beta detail", [600.0, 480.0])])
        out = verify(wb, spec, "2025", led, targets, {}, EvidenceBook(),
                     {"flags": []})
        self.assertTrue(any("detail off print" in str(f)
                            for f in out["findings"]))


class VintageIsALedgerPropertyLaw(unittest.TestCase):
    """run-19 fundamental: doc vintage was a join side-effect that
    silently degraded to 'nothing excluded' and never survived
    serialization — every offline view was vintage-blind."""

    def test_classification_survives_serialization(self):
        from updater.ledger import Ledger
        led = Ledger()
        led._doc_periods = {"AR25.pdf": "current", "AR24.pdf": "prior"}
        led2 = Ledger.from_json(led.to_json())
        self.assertEqual(led2.prior_period_docs(), {"AR24.pdf"})

    def test_unknown_multi_doc_safe_excluded_loudly(self):
        from updater.ledger import Ledger
        led = Ledger()
        led._doc_periods = None
        # classify will return unknown (no items/no deep priors) — force
        # the multi-doc path via a stub
        led.classify_doc_periods = lambda p, d: {"AR25.pdf": "current",
                                                 "AR24.pdf": "unknown"}
        msgs = []
        out = led.ensure_vintage([1000.0], [], log=msgs.append)
        self.assertEqual(out["AR24.pdf"], "prior")     # safe direction
        self.assertTrue(any("VINTAGE UNRESOLVED" in m for m in msgs))

    def test_single_doc_trivially_current(self):
        from updater.ledger import Ledger
        led = Ledger()
        led.classify_doc_periods = lambda p, d: {"AR25.pdf": "unknown"}
        out = led.ensure_vintage([1000.0], [], log=lambda s: None)
        self.assertEqual(out, {"AR25.pdf": "current"})


class OraclesObserveExecutorsMutateLaw(unittest.TestCase):
    """Council #4 (unanimous, after the run-21 net-profit corruption):
    Oracles observe; executors mutate. The verification oracle's write
    authority is REVOKED — the run never calls the retired writer, and
    unique-in-pool is never treated as identified."""

    def test_run_never_calls_the_retired_writer(self):
        import updater.run as run_mod
        import inspect
        src = inspect.getsource(run_mod)
        self.assertNotIn("reconcile_details", src)

    def test_retired_writer_still_refuses_ambiguity(self):
        # the function is kept only to pin its semantics; ambiguity has
        # never been writable and never will be
        from updater import ops
        wb, ws = _wb()
        ws["T5"], ws["U5"] = 1000.0, 900.0
        ws["T6"], ws["U6"] = 480.0, 600.0
        targets = [_mock_target("Model", 5, "alpha detail", 1000.0),
                   _mock_target("Model", 6, "anchor", 480.0)]
        led = _mock_ledger([
            _mock_item("AR", 5, "alpha detail", [1200.0, 1000.0]),
            _mock_item("AR", 6, "alpha other scope", [1450.0, 1000.0]),
            _mock_item("AR", 5, "anchor", [600.0, 480.0]),
            _mock_item("AR", 6, "anchor", [600.0, 480.0])])
        led.faces[("AR", 6)] = "bs"
        spec = {"year_axis": {"Model": {"columns": {"2024": "T",
                                                    "2025": "U"}}},
                "check_rows": [], "key_rows": []}
        n = ops.reconcile_details(wb, spec, 2025, targets, led, Writer(wb),
                                  EvidenceBook(), lambda s: None)
        self.assertEqual(ws["U5"].value, 900.0)     # ambiguity untouched


class SamePageRecoveryLaw(unittest.TestCase):
    """Owner (run 23): if TA maps, TL must map — vision-missed lines are
    recoverable under the fablemode checksum (identity prior-anchor),
    not blocked by the circular copied-check."""

    def test_missed_line_recovered_by_identity_anchor(self):
        from updater.ingest import _verify
        rows = [{"label": "负债合计", "current": 113881000000.0,
                 "prior": 98867040000.0}]
        # page extraction MISSED this line entirely (empty page numbers)
        out = _verify(rows, [], [98867.04])
        self.assertEqual(len(out), 1)              # recovered

    def test_recovery_needs_identity_not_row_tol(self):
        from updater.ingest import _verify
        rows = [{"label": "junk", "current": 5.0,
                 "prior": 99360000000.0}]          # 0.5% off — NOT identity
        out = _verify(rows, [], [98867.04])
        self.assertEqual(out, [])


class LastYearMapLaw(unittest.TestCase):
    """Owner (run 23): the prior report is the location map — each open
    row's prior value found there becomes a 'find the counterpart' hint."""

    def test_prior_doc_hit_becomes_hint(self):
        from updater.packets import prior_map_hints
        it = _mock_item("AR24", 273, "清洁高效能源装备", [28358.2, 26000.0])
        led = _mock_ledger([it])
        led.prior_period_docs = lambda: {"AR24"}
        rows = [{"cell": "Driver!J6", "label": "High-eff clean energy",
                 "prior": 28358.2}]
        hints = prior_map_hints(led, rows)
        self.assertIn("Driver!J6", hints)
        self.assertIn("p273", hints["Driver!J6"][0])


def _closure_item(doc, page, tid, ordn, label, nums, channel="vision"):
    from updater.ledger import Item
    return Item(doc=doc, page=page, table_id=tid, row_ord=ordn, label=label,
                nums=list(nums), channel=channel,
                source_line=f"{label} " + " ".join(f"{n:,.2f}" for n in nums))


def _closure_ledger(items, face="cf"):
    class L:
        pass
    led = L()
    led.items = list(items)
    led.faces = {(it.doc, it.page): face for it in items}
    led.prior_period_docs = lambda: set()
    return led


class SectionClosureLaw(unittest.TestCase):
    """run-24 twin (the ±593.5 CFI/CFF): a printed subtotal is an
    equation over its section — a single-number row's column placement
    is PROVEN by which placement closes, and a section that will not
    close derives the missing row by difference."""

    def test_absent_line_proves_zero(self):
        # the actual FY25 CFF-inflow section, to the yuan
        from updater.closure import closure_sweep
        items = [
            _closure_item("AR25", 101, 0, 0, "吸收投资收到的现金",
                          [5236179223.0, 110017500.0]),
            _closure_item("AR25", 101, 0, 1, "其中：子公司吸收少数股东投资收到的现金",
                          [138080000.0, 110017500.0]),
            _closure_item("AR25", 101, 0, 2, "取得借款收到的现金",
                          [5569616084.0, 2511723871.0]),
            _closure_item("AR25", 101, 0, 3, "收到其他与筹资活动有关的现金",
                          [593536698.0]),
            _closure_item("AR25", 101, 0, 4, "筹资活动现金流入小计",
                          [10805795307.0, 3215278069.0]),
        ]
        led = _closure_ledger(items)
        closure_sweep(led, lambda *_: None)
        z = [it for it in led.items
             if getattr(it, "channel", "") == "closure"]
        self.assertEqual(len(z), 1)
        self.assertEqual(z[0].nums, [0.0, 593536698.0])   # proven zero
        self.assertTrue(items[0].verified)     # section members verified

    def test_missing_row_derived_by_difference(self):
        from updater.closure import closure_sweep
        items = [
            _closure_item("AR25", 101, 0, 0, "收到的税费返还",
                          [340943742.0, 24819327.0]),
            _closure_item("AR25", 101, 0, 1, "收到其他与经营活动有关的现金",
                          [6561912668.0, 4960367306.0]),
            # 销售商品 (the first row) was dropped by the extraction
            _closure_item("AR25", 101, 0, 2, "经营活动现金流入小计",
                          [93418210494.0, 79843123509.0]),
        ]
        led = _closure_ledger(items)
        closure_sweep(led, lambda *_: None)
        g = [it for it in led.items
             if getattr(it, "channel", "") == "closure-gap"]
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0].nums[0], 86515354084.0, places=1)
        self.assertAlmostEqual(g[0].nums[1], 74857936876.0, places=1)

    def test_one_column_closure_proves_placements(self):
        # the confined-run fail (2026-08-19): the current column closes
        # UNIQUELY on its own; the prior column is vision-gapped. The
        # placements are still proven: the excluded single is the
        # comparative (zero this year), the included one is current.
        from updater.closure import closure_sweep
        items = [
            _closure_item("AR25", 101, 0, 0, "收回投资收到的现金",
                          [25155704810.83]),
            _closure_item("AR25", 101, 0, 1, "取得投资收益收到的现金",
                          [131301256.0, 120011125.0]),
            _closure_item("AR25", 101, 0, 2, "处置固定资产收回的现金净额",
                          [808222.0, 1147462.0]),
            _closure_item("AR25", 101, 0, 3, "处置子公司收到的现金净额",
                          [492572075.62]),
            _closure_item("AR25", 101, 0, 4, "收到其他与投资活动有关的现金",
                          [19078348.0]),
            _closure_item("AR25", 101, 0, 5, "投资活动现金流入小计",
                          [25306892636.83, 35876000880.0]),
        ]
        led = _closure_ledger(items)
        closure_sweep(led, lambda *_: None)
        z = {it.label: it.nums for it in led.items
             if getattr(it, "channel", "") == "closure"}
        self.assertEqual(z.get("处置子公司收到的现金净额"),
                         [0.0, 492572075.62])          # proven comparative
        self.assertEqual(z.get("收回投资收到的现金")[1], 0.0)
        self.assertEqual(z.get("收到其他与投资活动有关的现金"),
                         [19078348.0, 0.0])            # proven current
        # per-column closure must NOT verify the section's two-num rows
        self.assertFalse(items[1].verified)

    def test_note_pages_never_admitted(self):
        # an aging table closes over [carrying, provision] — column
        # semantics are NOT [current, prior]; faces only (run-21 class)
        from updater.closure import closure_sweep
        items = [
            _closure_item("AR25", 232, 0, 0, "应收账款",
                          [19168891258.0, 3975096357.0]),
            _closure_item("AR25", 232, 0, 1, "其他应收款",
                          [665327272.0, 283641267.0]),
            _closure_item("AR25", 232, 0, 2, "合计",
                          [19834218530.0, 4258737624.0]),
        ]
        led = _closure_ledger(items, face=None)
        led.faces = {}                          # a note page — no face
        closure_sweep(led, lambda *_: None)
        self.assertFalse(any(getattr(it, "verified", False)
                             for it in led.items))


class ProvenZeroJoinLaw(unittest.TestCase):
    """A zero may serve ONLY from a closure item (absence proven by the
    statement's own arithmetic); any other zero stays a non-read."""

    def test_closure_zero_passes_other_zero_refused(self):
        from updater.stage2_join import _proven_zero

        class ItA:
            channel = "closure"

        class ItB:
            channel = "vision"
        self.assertTrue(_proven_zero(0.0, ItA()))
        self.assertFalse(_proven_zero(0.0, ItB()))
        self.assertFalse(_proven_zero(5.0, ItA()))


class CounterpartMapLaw(unittest.TestCase):
    """Owner (run 23/24): the last-year map must WALK ACROSS — the hint
    carries the current report's counterpart row, and a re-based
    comparative triggers the analyst method, not staleness."""

    def _leds(self):
        prior_it = _mock_item("AR24", 209, "水电", [2955.37, 2361.55])
        prior_it.table_id, prior_it.row_ord = 1, 0
        kin1 = _mock_item("AR24", 209, "火电", [9000.0, 8000.0])
        kin1.table_id, kin1.row_ord = 1, 1
        kin2 = _mock_item("AR24", 209, "风电", [4000.0, 3500.0])
        kin2.table_id, kin2.row_ord = 1, 2
        cur_it = _mock_item("AR25", 207, "水电", [3902.82, 2854.08])
        cur_it.table_id, cur_it.row_ord = 2, 0
        ck1 = _mock_item("AR25", 207, "火电", [9500.0, 9100.0])
        ck1.table_id, ck1.row_ord = 2, 1
        ck2 = _mock_item("AR25", 207, "风电", [4400.0, 4100.0])
        ck2.table_id, ck2.row_ord = 2, 2
        led = _mock_ledger([prior_it, kin1, kin2, cur_it, ck1, ck2])
        led.prior_period_docs = lambda: {"AR24"}
        return led

    def test_rebased_counterpart_names_the_analyst_method(self):
        from updater.packets import prior_map_hints
        rows = [{"cell": "Driver!J11", "label": "Hydro", "prior": 2955.37}]
        hints = prior_map_hints(self._leds(), rows)
        h = hints["Driver!J11"][0]
        self.assertIn("COUNTERPART in CURRENT report p207", h)
        self.assertIn("RE-BASED", h)
        self.assertIn("RED-flag", h)


class SightingsLaw(unittest.TestCase):
    """run-24 (应收股利): a note line printing the model's prior beside
    the current value is surfaced as a SIGHTING for the agent's judgment
    — never a machine write."""

    def test_prior_anchored_note_line_sighted(self):
        from updater.packets import current_sightings
        it = _mock_item("AR25", 159, "应收股利",
                        [4210670.09, 23297096.99])
        led = _mock_ledger([it])
        rows = [{"cell": "Raw financials!U64", "label": "应收股利",
                 "prior": 23.2971}]
        s = current_sightings(led, rows)
        self.assertIn("Raw financials!U64", s)
        self.assertIn("p159", s["Raw financials!U64"][0])


class SecondPrintingLaw(unittest.TestCase):
    """The Fable pass as code (应收股利 class): a value printed on TWO
    pages, each time on a line whose label matches the model row exactly
    with the row's prior beside it, is disclosed — served grade C (red).
    One printing alone never serves."""

    def _tgt(self):
        return _mock_target("Raw", 64, "应收股利", 23.2971)

    def test_two_agreeing_printings_serve(self):
        from updater.ops import note_anchored_serves
        a = _mock_item("AR25", 159, "应收股利", [4210670.09, 23297096.99])
        b = _mock_item("AR25", 266, "应收股利", [4210670.09, 23297096.99])
        led = _mock_ledger([a, b])
        out = note_anchored_serves(led, [self._tgt()], {},
                                   lambda *_: None)
        self.assertIn(("Raw", 64), out)
        self.assertAlmostEqual(out[("Raw", 64)]["value"], 4.2107, places=3)
        self.assertEqual(out[("Raw", 64)]["conf"], 3)      # red, reviewed

    def test_single_printing_refused(self):
        from updater.ops import note_anchored_serves
        a = _mock_item("AR25", 159, "应收股利", [4210670.09, 23297096.99])
        led = _mock_ledger([a])
        out = note_anchored_serves(led, [self._tgt()], {},
                                   lambda *_: None)
        self.assertEqual(out, {})

    def test_disagreeing_printings_refused(self):
        from updater.ops import note_anchored_serves
        a = _mock_item("AR25", 159, "应收股利", [4210670.09, 23297096.99])
        b = _mock_item("AR25", 266, "应收股利", [9999999.0, 23297096.99])
        led = _mock_ledger([a, b])
        out = note_anchored_serves(led, [self._tgt()], {},
                                   lambda *_: None)
        self.assertEqual(out, {})


class OracleIdentityTolLaw(unittest.TestCase):
    """run-24 false positive: 5e-4 relative tolerance let wrong-scale
    junk (665,327,272 at /1e4 = 66,532.73 with a 28,364 'prior') tie a
    28,358 segment prior and 'prove' a wrong print. The oracle demands
    the cent-exact identity; near-misses belong to the hint channels."""

    def test_near_miss_prior_no_longer_ties(self):
        from updater.stage2_join import unique_evidence_value
        it = _mock_item("AR25", 232, "其他应收款",
                        [665327272.0, 283641267.0])
        it2 = _mock_item("AR25", 232, "债权投资",
                         [400000000.0, 100000000.0])
        for i, x in enumerate((it, it2)):
            x.table_id, x.row_ord, x.disputed = 0, i, False
            x.verified = True
        led = _mock_ledger([it, it2])
        t = _mock_target("Driver", 6, "High-eff clean energy", 28358.2)
        t2 = _mock_target("Raw", 98, "anchor a", 66532.7272)
        t3 = _mock_target("Raw", 99, "anchor b", 10000.0)
        # the page ratifies at 1e4 through the two exact anchors — yet the
        # 5.93-off "prior" may NOT tie the segment row any more
        got = unique_evidence_value(led, [t, t2, t3], t)
        self.assertIsNone(got)
        # the exact anchor itself still proves
        self.assertIsNotNone(unique_evidence_value(led, [t, t2, t3], t3))


class EmbeddedHardcodeLaw(unittest.TestCase):
    """Run-28 owner review: '=16602.97-J11' is an input wearing a formula
    costume — the numeric-only census made the whole class invisible.
    Embedded constants are exposed as open work, and the write is a
    constant SWAP that keeps the formula (transactional)."""

    def _spec(self):
        return {"year_axis": {"Model": {"columns": {"2024": "T",
                                                    "2025": "U"}}},
                "check_rows": [], "key_rows": []}

    def test_census_exposes_embedded_constants(self):
        from updater.packets import open_rows
        wb, ws = _wb()
        ws["A1"] = "Wind"
        ws["T1"], ws["U1"] = "=16602.97-T2", "=16602.97-U2"
        ws["T2"], ws["U2"] = 2955.37, 2955.37
        rows = open_rows(wb, self._spec(), "2025", "Model", {},
                         {"written": []})
        emb = {r["row"]: r for r in rows if r.get("embedded")}
        self.assertIn(1, emb)
        self.assertEqual(emb[1]["embedded"], [16602.97])
        self.assertEqual(emb[1]["prior"], 16602.97)   # constant anchors
        # cell refs are never constants
        self.assertNotIn(2955.37,
                         [c for r in rows for c in (r.get("embedded") or [])
                          if r["row"] == 1])

    def test_new_line_blank_cell_is_visible_work(self):
        # owner ruling 2026-08-19: a row blank last year and printed this
        # year is normal — the census must SHOW the blank cell
        from updater.packets import open_rows
        wb, ws = _wb()
        ws["A1"], ws["T1"], ws["U1"] = "row a", 10.0, 10.0
        ws["A2"] = "收到其他与投资活动有关的现金"      # blank both years
        ws["A3"], ws["T3"], ws["U3"] = "row c", 5.0, 5.0
        ws["A9"] = "far away spacer"                  # outside the span
        rows = open_rows(wb, self._spec(), "2025", "Model", {},
                         {"written": []})
        by_row = {r["row"]: r for r in rows}
        self.assertIn(2, by_row)                      # new-line visible
        self.assertIsNone(by_row[2]["value"])
        self.assertNotIn(9, by_row)                   # spacer stays out

    def test_swap_rewrites_constant_keeps_formula(self):
        from updater.ledger import Item
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["T1"], ws["U1"] = "=16602.97-T2", "=16602.97-U2"
        ws["T2"], ws["U2"] = 2955.37, 3902.82
        printed = Item(doc="AR", page=9, table_id=0, row_ord=0,
                       label="category total", nums=[18224190000.0],
                       channel="text", source_line="x")

        class _Ledger:
            items = [printed]
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, self._spec(), 2025, _Ledger(), [], {},
                         Writer(wb), EvidenceBook(), client=None)
        out = loop.t_set_input({"cell": "Model!U1",
                                "swap_constant": {"old": 16602.97,
                                                  "new": 18224.19},
                                "why": "p9: this year's category total"})
        self.assertIn("WRITTEN", out)
        self.assertEqual(ws["U1"].value, "=18224.19-U2")
        self.assertEqual(ws["T1"].value, "=16602.97-T2")   # prior untouched


class EntityQuarantineLaw(unittest.TestCase):
    """Council + run-24 (police cited a parent-company CF page as
    'print'): parent-entity pages lose face authority and leave the
    pool. Banner pages evict; anchorless twins far from an anchored
    sibling evict; adjacent continuations (the EPS tail) are spared."""

    def _led(self):
        cons = [_mock_item("AR", 3, f"row{i}", [v * 1.1, v])
                for i, v in enumerate((50000.0, 60000.0, 70000.0))]
        tail = [_mock_item("AR", 4, "每股收益", [1.15, 0.94])]
        twin = [_mock_item("AR", 9, "twinrow", [123.0, 456.0])]
        banner = [_mock_item("AR", 10, "hdr", [1.0, 2.0])]
        banner[0].source_line = "母公司资产负债表 2025年12月31日"
        items = cons + tail + twin + banner
        led = _mock_ledger(items, face="bs")
        led.parent_pages = set()
        for it in items:
            it.table_id, it.row_ord, it.disputed = 0, 0, False
        return led

    def test_banner_twin_evicted_continuation_spared(self):
        from updater.reading import entity_quarantine
        led = self._led()
        ts = [_mock_target("Raw", i, f"r{i}", v)
              for i, v in enumerate((50000.0, 60000.0, 70000.0))]
        q = entity_quarantine(led, ts, lambda *_: None)
        self.assertIn(10, q)                     # banner page evicted
        self.assertIn(9, q)                      # far anchorless twin
        self.assertNotIn(4, q)                   # adjacent EPS tail spared
        self.assertNotIn(3, q)                   # the anchored spine
        self.assertNotIn(("AR", 9), led.faces)
        self.assertTrue(all(it.disputed for it in led.items
                            if it.page == 9))


class ArticulationGateLaw(unittest.TestCase):
    """Council: an internally closed table can still be the wrong entity
    or a swapped year — the extracted columns must share ONE reality:
    CA+NCA = CL+NCL+equity, and CF ending cash ties BS cash."""

    def _world(self, equity_cur):
        rows = [("total current assets", 93779.78, 101683.68),
                ("total non-current assets", 48229.50, 60990.51),
                ("total current liabilities", 88912.97, 102323.47),
                ("total non-current liabilities", 9954.07, 12182.47),
                ("total equity", 43142.24, equity_cur),
                ("cash balance", 22502.86, 18980.96),
                ("cash year end", 22502.80, 18980.96)]
        items, targets, key_rows = [], [], []
        for i, (name, pv, cv) in enumerate(rows):
            it = _mock_item("AR", 5, name, [cv * 1e6, pv * 1e6])
            it.table_id, it.row_ord, it.disputed = 0, i, False
            it.verified = True
            items.append(it)
            t = _mock_target("Model", 10 + i, name, pv)
            targets.append(t)
            key_rows.append({"sheet": "Model", "row": 10 + i,
                             "name": name})
        led = _mock_ledger(items, face="bs")
        return led, targets, key_rows

    def test_articulating_world_passes(self):
        from updater.reading import _articulation
        led, ts, kr = self._world(equity_cur=48168.25)
        checks, _vals = _articulation(led, ts, kr)
        self.assertTrue(checks.get("bs_articulates"))
        self.assertTrue(checks.get("cash_ties"))

    def test_sheared_world_fails(self):
        from updater.reading import _articulation
        led, ts, kr = self._world(equity_cur=43142.24)   # stale column
        checks, _vals = _articulation(led, ts, kr)
        self.assertFalse(checks.get("bs_articulates", True))


class SufficiencyLaw(unittest.TestCase):
    """Council phase D: every open-row prior is LOCATED in the filing or
    listed unlocated — nothing downstream may claim the document lacks a
    figure the inventory locates."""

    def test_locate_identity_only(self):
        from updater.reading import _locate
        it = _mock_item("AR", 44, "line", [4210670.09, 23297096.99])
        led = _mock_ledger([it])
        self.assertEqual(_locate(led, 23.2971, set()), 44)
        self.assertIsNone(_locate(led, 25.0, set()))     # not identity
        it.disputed = True                               # quarantined
        self.assertIsNone(_locate(led, 23.2971, set()))


class YearTokenFilter(unittest.TestCase):
    """run-60: a bare 4-digit year is a header, not data."""

    def test_years_skipped(self):
        self.assertEqual(line_numbers("Revenue 2024 2025 1,234.5"), [1234.5])

    def test_space_grouped_scanned_numbers(self):
        self.assertEqual(parse_number("48 168 255 333.72"), 48168255333.72)


class RowWorldTolerance(unittest.TestCase):
    """run-112: EPS-sized rows tie at cents, aggregates at absolute base."""

    def test_per_share_world(self):
        self.assertLess(row_tol(1.15), 0.02)

    def test_aggregate_world(self):
        self.assertGreaterEqual(row_tol(3831.3), 0.6)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ShowYourWorkingLaw(unittest.TestCase):
    """Owner (2026-08-19): teach the reasoning and make it the PRODUCT —
    a compile write without its filled acceptance check is invalid."""

    def test_write_without_check_rejected(self):
        from updater.closer import PacketCloser
        v = PacketCloser.__dict__["_val_compile"]

        class _Self:
            pass
        errs = v(_Self(), {"writes": [{"cell": "Model!U4", "value": 1.0,
                                       "why": "p1: x"}]})
        self.assertTrue(errs and "check" in errs[0])
        errs2 = v(_Self(), {"writes": [{
            "cell": "Model!U4", "value": 1.0, "why": "p1: x",
            "check": {"section": "s", "sums": "1+2=3 printed",
                      "prior_tie": "ties 0.9"}}]})
        self.assertEqual(errs2, [])


class NeighbourBandLaw(unittest.TestCase):
    """Confined test 4: a NEW line has no prior for the world band — the
    column's neighbours judge the unit world instead. Raw-yuan into a
    millions model is refused with the conversion named."""

    def test_raw_units_refused_converted_accepted(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["A2"] = "收到其他与投资活动有关的现金"
        ws["T1"], ws["U1"] = 25155.70, 25155.70
        ws["T3"], ws["U3"] = 131.30, 131.30
        spec = {"year_axis": {"Model": {"columns": {"2024": "T",
                                                    "2025": "U"}}},
                "check_rows": [], "key_rows": []}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_set_input({"cell": "Model!U2", "value": 19078348.0,
                                "why": "p101: the printed line"})
        self.assertIn("REFUSED", out)
        self.assertIn("units", out)
        out2 = loop.t_set_input({"cell": "Model!U2", "value": 19.08,
                                 "why": "p101: the printed line, millions"})
        self.assertIn("WRITTEN", out2)


class LazyNDGuardLaw(unittest.TestCase):
    """Mindmap law enforced: 'not disclosed' is a PROVEN claim — refused
    when the current document prints the line (by exact name, or by the
    row's prior at identity)."""

    def test_nd_refused_when_line_prints(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["A1"], ws["U1"] = "收到其他与投资活动有关的现金", 1.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T",
                                                    "2025": "U"}}},
                "check_rows": [], "key_rows": []}
        it = _mock_item("AR25", 101, "收到其他与投资活动有关的现金",
                        [19078348.0])

        class _Ledger:
            items = [it]
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        t = _mock_target("Model", 1, "收到其他与投资活动有关的现金", None)
        t.prior_value = None
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [t], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_not_disclosed({"cell": "Model!U1",
                                    "looked": ["statement", "notes",
                                               "five-year summary"]})
        self.assertIn("REFUSED", out)
        self.assertIn("p101", out)


class NewLineServeLaw(unittest.TestCase):
    """Owner's name-first ruling, machine grade: an exact-name statement
    line with closure-PROVEN placement fills a model row blank in BOTH
    year columns — grade C (red). Unratified page scale serves nothing."""

    def test_blank_row_filled_from_proven_closure(self):
        from updater.ledger import Item
        from updater.ops import new_line_serves
        wb, ws = _wb()
        ws["A2"] = "收到其他与投资活动有关的现金"        # blank T2/U2
        spec = {"year_axis": {"Model": {"columns": {"2024": "T",
                                                    "2025": "U"}}}}
        cl = Item(doc="AR", page=101, table_id=910, row_ord=0,
                  label="收到其他与投资活动有关的现金",
                  nums=[19078348.0, 0.0], channel="closure", verified=True,
                  source_line="x")
        # two anchor items ratify p101 at 1e6
        a1 = Item(doc="AR", page=101, table_id=0, row_ord=1, label="anchor a",
                  nums=[131301256.0, 120011125.0], channel="vision",
                  verified=True, source_line="a")
        a2 = Item(doc="AR", page=101, table_id=0, row_ord=2, label="anchor b",
                  nums=[808222000.0, 555000000.0], channel="vision",
                  verified=True, source_line="b")
        led = _mock_ledger([cl, a1, a2])
        t1 = _mock_target("Model", 8, "a", 120.011125)
        t2 = _mock_target("Model", 9, "b", 555.0)
        out = new_line_serves(wb, spec, 2025, led, [t1, t2], {},
                              lambda *_: None)
        self.assertIn(("Model", 2), out)
        self.assertAlmostEqual(out[("Model", 2)]["value"], 19.078348,
                               places=4)
        self.assertEqual(out[("Model", 2)]["conf"], 3)


class SegmentEstimateRefusalLaw(unittest.TestCase):
    """Owner law enforced where run 29 broke it: a DERIVED (constructed)
    value may never land on a revenue/GP segment leaf — stale + red is
    the terminal state."""

    def test_derived_write_on_segment_leaf_refused(self):
        from updater.loop import AgentLoop
        wb, ws = _wb()
        ws["A1"], ws["T1"], ws["U1"] = "Total revenue", "=T2+T3", "=U2+U3"
        ws["A2"], ws["T2"], ws["U2"] = "Segment A", 100.0, 100.0
        ws["A3"], ws["T3"], ws["U3"] = "Segment B", 50.0, 50.0
        spec = {"year_axis": {"Model": {"columns": {"2024": "T",
                                                    "2025": "U"}}},
                "check_rows": [],
                "key_rows": [{"sheet": "Model", "row": 1,
                              "name": "revenue"}]}

        class _Ledger:
            items = []
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_set_input({"cell": "Model!U2", "value": 123.0,
                                "why": "p9: derived as coal 加 gas 加 "
                                       "nuclear combination"})
        self.assertIn("REFUSED", out)
        self.assertIn("estimate", out.lower())
        # a plain printed write on the same leaf still passes
        out2 = loop.t_set_input({"cell": "Model!U3", "value": 60.0,
                                 "why": "ties Model!T3 basis, p9 line"})
        self.assertIn("WRITTEN", out2)


class SwapMustBePrintedLaw(unittest.TestCase):
    """Run 29: the engine swapped a constructed total into a formula —
    a swapped-in constant must be a PRINTED number at a legal scale."""

    def test_unprinted_swap_refused(self):
        from updater.loop import AgentLoop
        from updater.ledger import Item
        wb, ws = _wb()
        ws["T1"], ws["U1"] = "=16602.97-T2", "=16602.97-U2"
        ws["T2"], ws["U2"] = 2955.37, 3902.82
        spec = {"year_axis": {"Model": {"columns": {"2024": "T",
                                                    "2025": "U"}}},
                "check_rows": [], "key_rows": []}
        it = Item(doc="AR", page=9, table_id=0, row_ord=0, label="cat",
                  nums=[18224190000.0], channel="text", source_line="x")

        class _Ledger:
            items = [it]
            faces = {}

            def prior_period_docs(self):
                return set()

            def join_pool(self):
                return []
        loop = AgentLoop(wb, spec, 2025, _Ledger(), [], {}, Writer(wb),
                         EvidenceBook(), client=None)
        out = loop.t_set_input({"cell": "Model!U1",
                                "swap_constant": {"old": 16602.97,
                                                  "new": 17443.29},
                                "why": "p9: constructed renewables total"})
        self.assertIn("REFUSED", out)
        out2 = loop.t_set_input({"cell": "Model!U1",
                                 "swap_constant": {"old": 16602.97,
                                                   "new": 18224.19},
                                 "why": "p9: the printed category total"})
        self.assertIn("WRITTEN", out2)


class ConsensusOverridesStage3Law(unittest.TestCase):
    """Run 30: a lone stage-3 read may never contradict the pool's
    agreeing print — the oracle's value overrides it, cited."""

    def test_contradicting_read_overridden(self):
        from updater.ops import consensus_filter
        a = _mock_item("AR25", 20, "吸收投资收到的现金",
                       [5236179223.0, 110017500.0])
        b = _mock_item("AR25", 101, "吸收投资收到的现金",
                       [5236179223.0, 110017500.0])
        a2 = _mock_item("AR25", 20, "取得借款收到的现金",
                        [5569616084.0, 2511723871.0])
        b2 = _mock_item("AR25", 101, "取得借款收到的现金",
                        [5569616084.0, 2511723871.0])
        for i, x in enumerate((a, b, a2, b2)):
            x.table_id, x.row_ord, x.disputed = 0, i, False
            x.verified = True
        led = _mock_ledger([a, b, a2, b2])
        t = _mock_target("Raw", 221, "吸收投资收到的现金", 110.0175)
        t2 = _mock_target("Raw", 222, "取得借款收到的现金", 2511.723871)
        gap = {("Raw", 221): {"value": 138.08, "conf": 3,
                              "note": "stage-3 read"}}
        out = consensus_filter(gap, led, [t, t2], lambda *_: None)
        self.assertAlmostEqual(out[("Raw", 221)]["value"], 5236.179223,
                               places=3)
        self.assertIn("OVERRODE", out[("Raw", 221)]["note"])


class BilingualClosureLaw(unittest.TestCase):
    """CLP prep: an English statement section closes under the same law
    as a CJK one — 'Total ...' is a subtotal, 'of which' skips, and the
    activity-net rows are barriers."""

    def test_english_section_closes(self):
        from updater.closure import closure_sweep
        items = [
            _closure_item("AR", 7, 0, 0, "Trade receivables",
                          [1000.0, 900.0]),
            _closure_item("AR", 7, 0, 1, "of which: from associates",
                          [200.0, 150.0]),
            _closure_item("AR", 7, 0, 2, "Bank deposits", [500.0]),
            _closure_item("AR", 7, 0, 3, "Total current assets",
                          [1500.0, 900.0]),
        ]
        led = _closure_ledger(items, face="bs")
        closure_sweep(led, lambda *_: None)
        z = [it for it in led.items
             if getattr(it, "channel", "") == "closure"]
        self.assertEqual(len(z), 1)
        self.assertEqual(z[0].nums, [500.0, 0.0])   # deposits are current
        self.assertTrue(items[0].verified)
