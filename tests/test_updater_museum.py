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
