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

const sums = checkSubtotals(
  { a: 100, b: 200, tot: 301, c: 50, d: null, tot2: 60 },
  [{ keys: ["a", "b"], totalKey: "tot" }, { keys: ["c", "d"], totalKey: "tot2" }]);
t("subtotal breach caught", sums.length === 1 && sums[0].totalKey === "tot");
t("incomplete cone gives no verdict", !sums.some(s => s.totalKey === "tot2"));

console.log(`\ncore museum: ${pass} pass, ${fail} fail`);
if (typeof process !== "undefined") process.exit(fail ? 1 : 0);
`RESULT ${pass} pass ${fail} fail`;
