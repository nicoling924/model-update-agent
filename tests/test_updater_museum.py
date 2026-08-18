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
