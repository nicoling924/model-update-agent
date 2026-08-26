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
et("refusal tells the Agent what to do",
  /does not tie/i.test((ap.refusals[0] || {}).why || ""));
// anti-gaming: the Agent must not be shown the model's own figure, or it
// can echo it back as the comparative and walk through the referee.
et("refusal leaks no model number to the Agent",
  JSON.stringify(ap.refusals).indexOf("1976.2") === -1);
et("_PLAN keeps the full reason for the analyst",
  JSON.stringify(wb1.getWorksheet("_PLAN").getUsedRange().getValues())
    .indexOf("1976.2") >= 0);
et("unmapped label surfaced with a reason",
  ap.unmappedCount === 1 && ap.unmapped[0].label === "Other income" &&
  ap.unmapped[0].why.length > 0);

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
// Phase 2: the check row is read in the target column AND the prior
// actual column — the boss map asks for ALL years balanced, and an
// inherited break must surface as the analyst's, not as ours.
et("police checks the check row in both years ('liabiliTIEs' is not a check)",
  po.checks === 2);

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
et("seeded model passes police", po4.ok === true && po4.checks === 2);

// ---- run 5: SEED guard — a real model can never be hit --------
const wb5 = new MockWorkbook();
const real = wb5.addWorksheet("Model");
real.getRange("A1").setValue("Rmb m");          // looks like a real model
real.getRange("B4").setValue(55353);
const sd5 = JSON.parse(main(wb5, ""));
et("SEED refused on non-blank workbook", sd5.ok === false &&
  /refused/.test(sd5.why));
et("real content untouched", wb5.getWorksheet("Model")
  .getRange("B4").getValues()[0][0] === 55353);
const wb6 = new MockWorkbook();
main(wb6, "");                                   // seed a blank one
const rs = JSON.parse(main(wb6, ""));            // re-seed the practice file
et("re-seeding the practice file is allowed", rs.ok === true);

// ---- run 6: the kernel speaks — _OUT echo ---------------------
const outWs = wb6.getWorksheet("_OUT");
et("_OUT tab exists and holds the newest report",
  outWs !== null &&
  String(outWs.getRange("A2").getValues()[0][0]).indexOf("SEED") >= 0);
const wb7 = new MockWorkbook();
main(wb7, JSON.stringify({ mode: "PREFLIGHT", sheet: "Model",
  periodKind: "FY", targetYear: 2025 }));      // error: nothing seeded
et("errors echo to _OUT too", String(wb7.getWorksheet("_OUT")
  .getRange("A2").getValues()[0][0]).indexOf("no sheet Model") >= 0);
const sd7 = JSON.parse(main(wb7, ""));         // _OUT alone must not block SEED
et("_OUT does not block seeding a blank book", sd7.ok === true);

// ---- run 7: the cascade on real disclosure labels -------------
// Phase 1 matched labels exactly and left 55 of 65 Dongfang lines on the
// floor. These are the shapes that were lost: 其中：/一、prefixes, depth
// indentation, and a line the annual report simply names differently.
function seeded() {
  const wb = new MockWorkbook();
  main(wb, "");
  main(wb, JSON.stringify({ mode: "PREFLIGHT", sheets: ["Model"],
    periodKind: "FY", targetYear: 2025 }));
  return wb;
}
const wb8 = seeded();
stage(wb8, [
  ["一、营业总收入", 78000.0, 69695.14, "p12", "", ""],       // 一、stripped
  ["其中：营业收入", 76500.0, 68592.74, "p12", "", ""],       // 其中：stripped
  ["营业成本", 62000.0, 58876.11, "p12", "", ""],             // depth ignored
  ["研究开发费用", 3300.0, 3009.01, "p12", "", ""],           // renamed line
  ["资产总计", 150000.0, 142009.28, "p20", "", ""],
  ["负债合计", 104000.0, 98867.04, "p20", "", ""],
  ["所有者权益合计", 46000.0, 43142.25, "p20", "", ""],
]);
const rs7 = JSON.parse(main(wb8, JSON.stringify({ mode: "RESTATE" })));
et("comparatives scan clean -> no stop",
  rs7.ok === true && rs7.stop === false && rs7.verdict === "clean");
const ap7 = JSON.parse(main(wb8, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("cascade absorbs every disclosure label",
  ap7.written === 7 && ap7.refused === 0 && ap7.unmappedCount === 0);
et("cascade reports HOW each line was found",
  ap7.mappedVia.norm >= 2 && ap7.mappedVia.prior === 1);
const m8 = wb8.getWorksheet("Model");
et("其中：营业收入 landed on the model's 营业收入 row (E5)",
  m8.getRange("E5").getValues()[0][0] === 76500.0);
et("renamed line landed by its prior value (研发费用, E12)",
  m8.getRange("E12").getValues()[0][0] === 3300.0);
const po7 = JSON.parse(main(wb8, JSON.stringify({ mode: "POLICE" })));
et("seeded model still balances after the cascade run",
  po7.ok === true && po7.checks === 2);

// ---- run 8: the restatement full stop -------------------------
// Boss law: the past changed -> STOP COMPLETELY and ask the analyst.
const wb9 = seeded();
stage(wb9, [
  ["营业总收入", 78000.0, 70500.0, "p12", "", ""],   // model holds 69695.14
  ["营业成本", 62000.0, 59500.0, "p12", "", ""],     // model holds 58876.11
  ["研发费用", 3300.0, 3100.0, "p12", "", ""],       // model holds 3009.01
]);
const rsScan = JSON.parse(main(wb9, JSON.stringify({ mode: "RESTATE" })));
et("three broken comparatives = restatement suspected",
  rsScan.stop === true && rsScan.verdict === "RESTATEMENT SUSPECTED" &&
  rsScan.mismatches === 3);
et("restatement scan tells the Agent WHICH lines, not the figures",
  rsScan.lines.length === 3 && JSON.stringify(rsScan.lines).indexOf("69695") === -1);
const rsWs = wb9.getWorksheet("_RESTATE");
et("_RESTATE tab is visible and holds the evidence for the analyst",
  rsWs.hidden === false &&
  /RESTATEMENT SUSPECTED/.test(String(rsWs.getRange("A1").getValues()[0][0])) &&
  rsWs.getRange("D3").getValues()[0][0] === 69695.14);
const apBlocked = JSON.parse(main(wb9, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("APPLY is blocked until a human rules",
  apBlocked.ok === false && apBlocked.stop === true &&
  /restatement suspected/i.test(apBlocked.why));
et("nothing was written while blocked",
  wb9.getWorksheet("Model").getRange("E4").getValues()[0][0] === "");
const apAck = JSON.parse(main(wb9, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025,
    acknowledgeRestatement: true })));
et("analyst acknowledgement unblocks the write", apAck.ok === true);
et("but the broken comparatives are still refused, not written",
  apAck.written === 0 && apAck.refused === 3);
et("the acknowledgement is on the record in _LEDGER",
  JSON.stringify(wb9.getWorksheet("_LEDGER").getUsedRange().getValues())
    .indexOf("acknowledged") >= 0);

// ---- run 9: three statements in one run ------------------------
const wb10 = fixtureWorkbook();
const bs = wb10.addWorksheet("BS");
bs.getRange("B1").setValue(2022); bs.getRange("C1").setValue(2023);
bs.getRange("D1").setValue(2024); bs.getRange("E1").setValue(2025);
bs.getRange("A3").setValue("Total assets");      bs.getRange("D3").setValue(500);
bs.getRange("A4").setValue("Total liabilities"); bs.getRange("D4").setValue(200);
bs.getRange("A5").setValue("Total equity");      bs.getRange("D5").setValue(300);
bs.getRange("A6").setValue("Balance check");     bs.getRange("D6").setValue(0);
bs.cell(5, 3).f = "=D3-D4-D5";
const pre10 = JSON.parse(main(wb10, JSON.stringify(
  { mode: "PREFLIGHT", sheets: ["Model", "BS"], periodKind: "FY",
    targetYear: 2025 })));
et("preflight covers both sheets",
  pre10.ok === true && pre10.sheets.length === 2 &&
  pre10.sheets[1].sheet === "BS");
stage(wb10, [
  ["Revenue", 5321.0, 4976.2, "p3", "", "", "Model"],
  ["Total assets", 620.0, 500.0, "p9", "", "", "BS"],
  ["Total liabilities", 250.0, 200.0, "p9", "", "", "BS"],
  ["Total equity", 370.0, 300.0, "p9", "", "", "BS"],
]);
const apM = JSON.parse(main(wb10, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
const apB = JSON.parse(main(wb10, JSON.stringify(
  { mode: "APPLY", sheet: "BS", targetYear: 2025 })));
et("each sheet applies only the lines addressed to it",
  apM.written === 1 && apM.unmappedCount === 0 &&
  apB.written === 3 && apB.unmappedCount === 0);
et("preflighting the second sheet did not erase the first",
  wb10.getWorksheet("Model").getRange("E5").getValues()[0][0] === 5321.0);
const po10 = JSON.parse(main(wb10, JSON.stringify({ mode: "POLICE" })));
et("police sweeps every sheet it preflighted",
  po10.ok === true && po10.checks === 4);
main(wb10, JSON.stringify({ mode: "STAGE", rows: [
  ["Total equity", 999.0, 300.0, "p9", "", "", "BS"]] }));
main(wb10, JSON.stringify({ mode: "APPLY", sheet: "BS", targetYear: 2025 }));
const po11 = JSON.parse(main(wb10, JSON.stringify({ mode: "POLICE" })));
et("a break on ANY sheet fails the whole run",
  po11.ok === false && po11.failed[0].sheet.indexOf("BS!") === 0);

console.log(`\nkernel e2e: ${ePass} pass, ${eFail} fail`);
if (typeof process !== "undefined") process.exit(eFail ? 1 : 0);
`E2E ${ePass} pass ${eFail} fail`;
