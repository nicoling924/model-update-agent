// Museum exhibits for the studio-native core — each test is a shipped
// disease class from the Python engine's history, re-pinned in JS.
// Run: tools/run_core_tests.sh  (concatenates core + this file, runs it
// on macOS JavaScriptCore via osascript; Node works too if present).
if (typeof require !== "undefined") {
  const a = require("../core/axis.js"), s = require("../core/ties.js");
  var yearOf = a.yearOf, findYearAxis = a.findYearAxis, n2col = a.n2col;
  var tieOk = s.tieOk, validateWritePlan = s.validateWritePlan,
      checkSubtotals = s.checkSubtotals;
}

let pass = 0, fail = 0;
function t(name, cond) {
  if (cond) { pass++; }
  else { fail++; console.log("  FAIL " + name); }
}

// --- yearOf: compact interim forms measured on live models -------------
t("H125 -> 2025 1H", String(yearOf("H125")) === "2025,1H");
t("H225E -> 2025 2H", String(yearOf("H225E")) === "2025,2H");
t("Q106 -> 2006 1Q", String(yearOf("Q106")) === "2006,1Q");
t("1H2025", String(yearOf("1H2025")) === "2025,1H");
t("2025H1", String(yearOf("2025H1")) === "2025,1H");
t("3Q2025", String(yearOf("3Q2025")) === "2025,3Q");
t("plain 2025 number", String(yearOf(2025)) === "2025,");
t("'2025A' string", String(yearOf("2025A")) === "2025,");
t("'FY2025'", String(yearOf("FY2025")) === "2025,");
t("bool ignored", yearOf(true)[0] === null);
t("small number ignored", yearOf(42)[0] === null);
// ExcelScript adaptation: date serials (1900 system)
t("serial 2025-06-30 -> interim", String(yearOf(45838)) === "2025,1H");
t("serial 2024-12-31 -> annual", String(yearOf(45657)) === "2024,");

// --- findYearAxis: the 1H-panel trap (annual + interim side by side) ---
const trapGrid = [
  ["", "", "", "", "", "", "", "", ""],
  ["", 2022, 2023, 2024, 2025, "H124", "H224", "H125", "H225E"],
];
const fy = findYearAxis(trapGrid, "FY");
t("FY binds annual panel", fy && fy["2025"] === 4 && fy["2022"] === 1);
t("FY never binds interim col", fy && Object.values(fy).indexOf(7) === -1);
const h1 = findYearAxis(trapGrid, "1H");
t("1H binds interim panel (min-run 2)", h1 && h1["2025"] === 7);
t("1H run: 2024 col is H124", h1 && h1["2024"] === 5);

// two-digit fiscal years — the common convention outside the mainland
t("'FY24' -> 2024", String(yearOf("FY24")) === "2024,");
t("'FY25E' -> 2025", String(yearOf("FY25E")) === "2025,");
t("'F99' -> 1999", String(yearOf("F99")) === "1999,");
t("a bare '24' is NOT a year", yearOf("24")[0] === null);
t("two-digit panel binds",
  (() => { const a = findYearAxis([["", "FY22", "FY23", "FY24"]], "FY");
    return a && a["2024"] === 3; })());

// newest-first panels: plenty of analysts write time right-to-left
const descGrid = [["", 2025, 2024, 2023, 2022]];
const dsc = findYearAxis(descGrid, "FY");
t("newest-first panel binds", dsc && dsc["2025"] === 1 && dsc["2022"] === 4);
t("a mixed-direction row is not a panel",
  findYearAxis([["", 2022, 2024, 2023]], "FY") === null);

// FY with year-marks as text headers
const txtGrid = [["x", "FY2023", "FY2024", "FY2025"]];
const fy2 = findYearAxis(txtGrid, "FY");
t("text FY headers bind", fy2 && fy2["2025"] === 3);

// no axis -> null
t("no marks -> null", findYearAxis([["a", "b"], [1, 2]], "FY") === null);

// --- n2col: the two-letter-column disease (AI98 parsed as sheet 'A') ---
t("n2col 0 -> A", n2col(0) === "A");
t("n2col 25 -> Z", n2col(25) === "Z");
t("n2col 26 -> AA", n2col(26) === "AA");
t("n2col 34 -> AI", n2col(34) === "AI");
t("n2col 701 -> ZZ", n2col(701) === "ZZ");

// --- tie laws ----------------------------------------------------------
t("tie exact", tieOk(4976.2, 4976.2));
t("tie within rounding", tieOk(10000, 10000.4));
t("no tie (1.8 apart)", !tieOk(4976.2, 4978.0));
t("0.15% drift is NOT a tie", !tieOk(10000, 10015));

const priors = { "Model!10": 4976.2, "Model!11": 380.0 };
const plan = [
  { sheet: "Model", row: 10, value: 5321.0, priorDisclosed: 4976.2, flag: "", note: "" },
  { sheet: "Model", row: 11, value: 410.0, priorDisclosed: 355.0, flag: "", note: "" },
  { sheet: "Model", row: 12, value: 99.0, priorDisclosed: null, flag: "orange", note: "=total-SUM(mapped)" },
  { sheet: "Model", row: 13, value: 7.0, priorDisclosed: null, flag: "red", note: "" },
  { sheet: "Model", row: 14, value: 1.0, priorDisclosed: null, flag: "", note: "" },
];
const v = validateWritePlan(plan, priors);
t("tied write accepted", v.accepted.some(e => e.row === 10));
t("prior mismatch refused (wrong row / restatement)",
  v.refused.some(r => r.entry.row === 11 && /prior mismatch/.test(r.why)));
t("orange backout with note accepted", v.accepted.some(e => e.row === 12));
t("flag without note refused", v.refused.some(r => r.entry.row === 13));
t("unflagged without tie proof refused", v.refused.some(r => r.entry.row === 14));

// anti-gaming law: the Agent-facing brief must never quote the model's
// own stored figure back (an Agent shown the number can echo it and walk
// straight through the referee).
const mm = v.refused.filter(r => r.entry.row === 11)[0];
t("refusal detail names both numbers (for _PLAN)",
  /4976|380/.test(mm.why) || /model holds/.test(mm.why));
t("agent-facing brief leaks NO model number",
  !/380|4976|355/.test(mm.brief) && /do not tie|does not tie/i.test(mm.brief));

// --- the mapping cascade (Phase 2) -------------------------------------
const anat = [
  { sheet: "Model", row: 4, label: "    营业总收入", prior: 69695.14 },
  { sheet: "Model", row: 5, label: "    营业收入", prior: 68592.74 },
  { sheet: "Model", row: 8, label: "        营业成本", prior: 58876.11 },
  { sheet: "Model", row: 12, label: "    研发费用", prior: 3009.01 },
  { sheet: "Model", row: 14, label: "        其中：利息费用", prior: 82.97 },
  { sheet: "Model", row: 20, label: "    资产减值损失", prior: -1148.01 },
];
const mreq = (label, prior, rowHint) =>
  ({ label: label, prior: prior === undefined ? null : prior,
     rowHint: rowHint === undefined ? 0 : rowHint });
const M = mapAll([
  mreq("    营业总收入", 69695.14),          // exact, indentation levelled
  mreq("其中：营业收入", 68592.74),          // the Phase 1 killer: prefix
  mreq("营业成本", 58876.11),                // depth stripped
  mreq("利息费用", 82.97),                   // model side carries the prefix
  mreq("研究开发费用", 3009.01),             // NO name match — prior finds it
  mreq("资产减值损失（损失以“－”号填列）", -1148.01),  // full-width furniture
], anat);
t("cascade: exact match", M[0].row === 4 && M[0].via === "exact");
t("cascade: 其中： prefix stripped", M[1].row === 5 && M[1].via === "norm");
t("cascade: indentation/depth ignored", M[2].row === 8 && M[2].via === "exact");
t("cascade: model-side prefix stripped", M[3].row === 14 && M[3].via === "norm");
t("cascade: unknown name found by prior value",
  M[4].row === 12 && M[4].via === "prior");
t("cascade: full-width suffix line still maps", M[5].row === 20);

// guards: never guess, never double-claim
const dup = [
  { sheet: "M", row: 2, label: "Revenue", prior: 100 },
  { sheet: "M", row: 9, label: "revenue", prior: 250 },
];
t("ambiguous label resolved by the prior figure",
  mapAll([mreq("Revenue", 250)], dup)[0].row === 9);
const G = mapAll([mreq("Revenue", 999)], dup)[0];
t("ambiguity with no tie is NOT guessed",
  G.row === -1 && /ambiguous/.test(G.why));
const C = mapAll([mreq("Revenue", 100), mreq("营业收入", 100, 2)],
  [{ sheet: "M", row: 2, label: "Revenue", prior: 100 }]);
t("one row, one claim", C[0].row === 2 && C[1].row === -1 &&
  /already taken/.test(C[1].why));
t("zero-ish priors never map by value",
  mapAll([mreq("mystery line", 0)],
    [{ sheet: "M", row: 3, label: "other", prior: 0 }])[0].row === -1);
t("agent row hint is the LAST resort, not the first",
  mapAll([mreq("其中：营业收入", 68592.74, 99)], anat)[0].row === 5);

const sums = checkSubtotals(
  { a: 100, b: 200, tot: 301, c: 50, d: null, tot2: 60 },
  [{ keys: ["a", "b"], totalKey: "tot" }, { keys: ["c", "d"], totalKey: "tot2" }]);
t("subtotal breach caught", sums.length === 1 && sums[0].totalKey === "tot");
t("incomplete cone gives no verdict", !sums.some(s => s.totalKey === "tot2"));

console.log(`\ncore museum: ${pass} pass, ${fail} fail`);
if (typeof process !== "undefined") process.exit(fail ? 1 : 0);
`RESULT ${pass} pass ${fail} fail`;
