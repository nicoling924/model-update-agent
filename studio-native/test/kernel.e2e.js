// End-to-end kernel exhibit: PREFLIGHT -> APPLY -> POLICE on a mock
// workbook. Pins the council's Phase 1 success criterion: "if the staging
// data breaks an arithmetic tie, Phase 1 must successfully abort the
// write and turn the row red." Runs on JavaScriptCore via run_core_tests.sh
// (mock_excel.js + core laws + kernel.js are concatenated before this).
// Concat-only: run via tools/run_core_tests.sh, which prepends
// mock_excel.js + core laws + kernel.js (Node and JSC take the same bundle).

let ePass = 0, eFail = 0;
function et(name, cond) {
  if (cond) { ePass++; }
  else { eFail++; console.log("  FAIL " + name); }
}

function fixtureWorkbook() {
  const wb = new MockWorkbook();
  const ws = wb.addWorksheet("Model");
  // header row: years 2022..2025 in B..E (target 2025 = forecast col)
  ws.getRange("B1").setValue(2022); ws.getRange("C1").setValue(2023);
  ws.getRange("D1").setValue(2024); ws.getRange("E1").setValue(2025);
  const put = (a1, v) => ws.getRange(a1).setValue(v);
  put("A5", "Revenue");           put("D5", 4976.2);
  put("A6", "Cost of sales");     put("D6", -3000.0);
  put("A7", "Operating profit");  put("D7", 1976.2);
  put("A9", "Total assets");      put("D9", 8000.0);
  put("A10", "Total liabilities"); put("D10", 3000.0);
  put("A11", "Total equity");     put("D11", 5000.0);
  put("A12", "Balance check");    put("D12", 0);
  ws.cell(11, 3).f = "=D9-D10-D11";      // D12 is the model's own check
  return wb;
}

function stage(wb, rows) {              // through the kernel's own door
  const r = JSON.parse(main(wb, JSON.stringify(
    { mode: "STAGE", rows: rows })));
  et("stage ok (" + r.staged + " rows)", r.ok === true && r.staged === rows.length);
}

// ---- run 1: the happy-and-hostile path ------------------------
const wb1 = fixtureWorkbook();
const pre = JSON.parse(main(wb1, JSON.stringify(
  { mode: "PREFLIGHT", sheet: "Model", periodKind: "FY", targetYear: 2025 })));
et("preflight ok", pre.ok === true);
et("preflight axis: prior D target E", pre.priorCol === "D" && pre.targetCol === "E");
et("anatomy captured labelled rows", pre.anatomyRows >= 7);

stage(wb1, [
  ["Revenue", 5321.0, 4976.2, "p3", "", ""],          // ties -> accept
  ["Cost of sales", -3200.0, -3000.0, "p3", "", ""],  // ties -> accept
  ["Operating profit", 2121.0, 1990.0, "p3", "", ""], // prior mismatch!
  ["Total assets", 8500.0, 8000.0, "p5", "", ""],
  ["Total liabilities", 3200.0, 3000.0, "p5", "", ""],
  ["Total equity", 5300.0, 5000.0, "p5", "", ""],
  ["Other income", 42.0, 40.0, "p4", "", ""],         // no such model row
]);
const ap = JSON.parse(main(wb1, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("apply ok", ap.ok === true);
et("5 accepted writes", ap.written === 5);
et("1 refused (the broken tie)", ap.refused === 1);
et("refusal names the mismatch",
  /prior mismatch/.test((ap.refusals[0] || {}).why || ""));
et("unmapped label surfaced", String(ap.unmappedLabels) === "Other income");

const ws1 = wb1.getWorksheet("Model");
et("accepted value written (E5)", ws1.getRange("E5").getValues()[0][0] === 5321.0);
et("REFUSED row NOT written (E7 keeps prior)",
  ws1.getRange("E7").getValues()[0][0] === 1976.2);
et("refused row turned red", ws1.cell(6, 4).fill === "FFC7CE");
et("check formula copied+shifted (E12 = =E9-E10-E11)",
  ws1.cell(11, 4).f === "=E9-E10-E11");
et("year header survived the column copy",
  ws1.getRange("E1").getValues()[0][0] === 2025);
et("_PLAN holds verdicts",
  JSON.stringify(wb1.getWorksheet("_PLAN").getUsedRange().getValues()).indexOf("REFUSE") >= 0);
et("_LEDGER appended",
  wb1.getWorksheet("_LEDGER").getUsedRange().getRowCount() >= 6);

const po = JSON.parse(main(wb1, JSON.stringify(
  { mode: "POLICE", sheet: "Model" })));
et("police ok when balanced (8500-3200-5300=0)", po.ok === true);
et("police checks exactly the check row ('liabiliTIEs' is not a check)",
  po.checks === 1);

// ---- run 2: police catches an unbalanced delivery -------------
const wb2 = fixtureWorkbook();
main(wb2, JSON.stringify(
  { mode: "PREFLIGHT", sheet: "Model", periodKind: "FY", targetYear: 2025 }));
stage(wb2, [
  ["Total assets", 8500.0, 8000.0, "p5", "", ""],
  ["Total liabilities", 3200.0, 3000.0, "p5", "", ""],
  ["Total equity", 5290.0, 5000.0, "p5", "", ""],     // 10 short
]);
main(wb2, JSON.stringify({ mode: "APPLY", sheet: "Model", targetYear: 2025 }));
const po2 = JSON.parse(main(wb2, JSON.stringify(
  { mode: "POLICE", sheet: "Model" })));
et("police FAILS the unbalanced model", po2.ok === false);
et("police names the check row", po2.failed.length === 1 && po2.failed[0].row === 12);

// ---- run 3: flags -------------------------------------------
const wb3 = fixtureWorkbook();
main(wb3, JSON.stringify(
  { mode: "PREFLIGHT", sheet: "Model", periodKind: "FY", targetYear: 2025 }));
stage(wb3, [
  ["Revenue", 5321.0, null, "p3", "orange", "=total-SUM(mapped segs)"],
  ["Cost of sales", -3200.0, null, "p3", "red", ""],  // flag, no note
]);
const ap3 = JSON.parse(main(wb3, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("orange backout accepted + written", ap3.written === 1);
et("orange fill applied", wb3.getWorksheet("Model").cell(4, 4).fill === "FFC000");
et("red flag without note refused", ap3.refused === 1);

// ---- run 4: SEED — the practice model travels as code ---------
const wb4 = new MockWorkbook();
const sd = JSON.parse(main(wb4, ""));            // bare run = seed
et("bare run seeds the practice model", sd.ok === true && sd.seeded >= 30);
const pre4 = JSON.parse(main(wb4, JSON.stringify(
  { mode: "PREFLIGHT", sheet: "Model", periodKind: "FY", targetYear: 2025 })));
et("seeded model binds FY axis", pre4.ok === true && pre4.targetCol === "E");
et("seeded anatomy is rich", pre4.anatomyRows >= 25);
stage(wb4, [
  ["营业总收入", 75000.0, 69695.14, "p3", "", ""],
  ["营业成本", 62000.0, 58999.99, "p3", "", ""],   // sabotage: wrong prior
]);
const ap4 = JSON.parse(main(wb4, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("seeded honest row accepted", ap4.written === 1);
et("seeded sabotage refused", ap4.refused === 1);
const po4 = JSON.parse(main(wb4, JSON.stringify(
  { mode: "POLICE", sheet: "Model" })));
et("seeded model passes police", po4.ok === true && po4.checks === 1);

console.log(`\nkernel e2e: ${ePass} pass, ${eFail} fail`);
if (typeof process !== "undefined") process.exit(eFail ? 1 : 0);
`E2E ${ePass} pass ${eFail} fail`;
