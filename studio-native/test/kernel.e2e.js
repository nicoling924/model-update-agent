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
et("police says WHICH year broke (this run's, not inherited)",
  po2.failed[0].when === "this period" && po2.inheritedFailures === 0);
// an error the analyst's model arrived with must be named as pre-existing
const wbInh = fixtureWorkbook();
wbInh.getWorksheet("Model").getRange("D11").setValue(4990);   // 2024 is 10 out
main(wbInh, JSON.stringify({ mode: "PREFLIGHT", sheets: ["Model"],
  periodKind: "FY", targetYear: 2025 }));
const poInh = JSON.parse(main(wbInh, JSON.stringify({ mode: "POLICE" })));
et("a break inherited from the prior year is labelled as pre-existing",
  poInh.ok === false && poInh.inheritedFailures === 1 &&
  /ALREADY broken/.test(poInh.failed[0].when));

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

// ---- run 10: the analyst's page, and the model's memory --------
// A model that HAS a forecast in the target column: only then can the
// report say "you forecast X, the actual came in at Y".
function fixtureForecast() {
  const wb = new MockWorkbook();
  const ws = wb.addWorksheet("Model");
  const cols = ["B", "C", "D", "E", "F"];
  for (let i = 0; i < 5; i++) ws.getRange(cols[i] + "1").setValue(2022 + i);
  const line = (r, label, prior, est, next) => {
    ws.getRange("A" + r).setValue(label);
    ws.getRange("D" + r).setValue(prior);
    ws.getRange("E" + r).setValue(est);
    ws.getRange("F" + r).setValue(next);
  };
  line(5, "Revenue", 4976.2, 5200.0, 5600.0);
  line(6, "Cost of sales", -3000.0, -3100.0, -3300.0);
  line(7, "Operating profit", 1976.2, 2000.0, 2100.0);
  line(8, "Other gains", 100.0, 120.0, 130.0);
  line(9, "Total assets", 8000.0, 8200.0, 8400.0);
  line(10, "Total liabilities", 3000.0, 3100.0, 3200.0);
  line(11, "Total equity", 5000.0, 5100.0, 5200.0);
  line(12, "Balance check", 0, 0, 0);
  ws.cell(11, 3).f = "=D9-D10-D11";
  ws.cell(11, 4).f = "=E9-E10-E11";
  ws.cell(11, 5).f = "=F9-F10-F11";
  return wb;
}
const wb11 = fixtureForecast();
main(wb11, JSON.stringify({ mode: "PREFLIGHT", sheets: ["Model"],
  periodKind: "FY", targetYear: 2025 }));
stage(wb11, [
  ["Turnover", 5321.0, 4976.2, "p3", "", ""],          // no such label
  ["Cost of sales", -3200.0, -3000.0, "p3", "", ""],
  ["Operating profit", 2121.0, 1990.0, "p3", "", ""],  // sabotage -> red
  ["Other gains", 500.0, 100.0, "p4", "orange",
    "backed out: total less mapped items"],            // big move + orange
  ["Total assets", 8600.0, 8000.0, "p5", "", ""],
  ["Total liabilities", 3200.0, 3000.0, "p5", "", ""],
  ["Total equity", 5400.0, 5000.0, "p5", "", ""],
]);
const ap11 = JSON.parse(main(wb11, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("unnamed line 'Turnover' found by its prior figure",
  ap11.written === 6 && ap11.mappedVia.prior === 1);
const rep = JSON.parse(main(wb11, JSON.stringify({ mode: "REPORT" })));
et("report written", rep.ok === true && rep.red === 1 && rep.orange === 1);
et("report counts the big mover", rep.bigMoves === 1);
et("report compares forecast vs actual", rep.coreLines >= 5);
const rw = wb11.getWorksheet("_REPORT");
const flat = JSON.stringify(rw.getUsedRange().getValues());
et("_REPORT is the visible first tab",
  rw.hidden === false && rw.position === 0 &&
  /MODEL UPDATE REPORT/.test(String(rw.getRange("A1").getValues()[0][0])));
et("report has all six sections",
  /1\. RED/.test(flat) && /2\. ORANGE/.test(flat) &&
  /3\. KEY DRIVERS/.test(flat) && /4\. NOT UPDATED/.test(flat) &&
  /5\. BIG MOVES/.test(flat) && /6\. YOUR FORECAST/.test(flat));
et("report speaks the analyst's language",
  /you forecast 5200 · actual 5321 \(\+2\.3%\)/.test(flat) &&
  /moved \+400%/.test(flat) && /next year: 5600/.test(flat));
et("every listed cell is a link next to its live value", (() => {
  for (const k in rw.cells) {
    const c = rw.cells[k];
    if (c.link === "Model!E7") {
      const row = Number(k.split(":")[0]);
      return rw.cell(row, 1).f === "=Model!E7";
    }
  }
  return false;
})());
et("refused row is on the page as REFUSED, not as a number",
  /REFUSED — not written/.test(flat));
// the model remembers what it had to reason out
const spec = JSON.stringify(wb11.getWorksheet("_SPEC").getUsedRange().getValues());
et("_SPEC learned the alias, as label -> label (rows move, labels do not)",
  /ALIAS \| Turnover \| Model \| Revenue/.test(spec) && spec.indexOf("!E5") === -1);
stage(wb11, [["Turnover", 5400.0, 4976.2, "p3", "", ""]]);
const ap12 = JSON.parse(main(wb11, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("a warm run inherits the alias instead of re-deriving it",
  ap12.written === 1 && ap12.mappedVia.alias === 1);

// ---- run 11: a model with no check row cannot be called balanced
const wb12 = new MockWorkbook();
const nc = wb12.addWorksheet("Model");
nc.getRange("B1").setValue(2023); nc.getRange("C1").setValue(2024);
nc.getRange("D1").setValue(2025);
nc.getRange("A3").setValue("Revenue"); nc.getRange("C3").setValue(100);
main(wb12, JSON.stringify({ mode: "PREFLIGHT", sheets: ["Model"],
  periodKind: "FY", targetYear: 2025 }));
const po12 = JSON.parse(main(wb12, JSON.stringify({ mode: "POLICE" })));
et("no check row = NOT verified, never a silent pass",
  po12.ok === false && po12.checks === 0 &&
  /could NOT be verified/.test(po12.why));


// ---- run 12: a REAL model's shape — wired sheets, hardcodes, drivers
// The owner's Dongfang model: a 'Model' tab of formulas pointing at a
// 'Raw' history tab that has no column for the new year yet, plus typed
// analyst numbers and formulas with constants baked in. Everything the
// practice file could not teach us.
function fixtureWired() {
  const wb = new MockWorkbook();
  const raw = wb.addWorksheet("Raw");
  raw.getRange("B1").setValue(2022); raw.getRange("C1").setValue(2023);
  raw.getRange("D1").setValue(2024);          // history stops at 2024
  raw.getRange("A3").setValue("Revenue");     raw.getRange("D3").setValue(4976.2);
  raw.getRange("A4").setValue("Cost of sales"); raw.getRange("D4").setValue(-3000.0);
  raw.getRange("B3").setValue(4000); raw.getRange("C3").setValue(4500);
  raw.getRange("B4").setValue(-2500); raw.getRange("C4").setValue(-2800);
  const m = wb.addWorksheet("Model");
  for (let i = 0; i < 4; i++)
    m.getRange(["B", "C", "D", "E"][i] + "1").setValue(2022 + i);
  m.getRange("A3").setValue("Revenue");
  m.getRange("A4").setValue("Cost of sales");
  m.getRange("A5").setValue("Adjusted profit");
  m.getRange("A6").setValue("Analyst overlay");
  m.getRange("A7").setValue("Balance check");
  // formula cells carry their last computed value, as a saved file does
  const wire = (r, f, v) => { m.cell(r, 3).f = f; m.cell(r, 3).v = v; };
  wire(2, "='Raw'!D3", 4976.2);                 // wired to the raw tab
  wire(3, "='Raw'!D4", -3000.0);                // wired
  wire(4, "=D3+36", 5012.2);                    // 36 baked into the formula
  m.getRange("D6").setValue(250);               // typed analyst overlay
  wire(6, "=D3-D3", 0);                         // the model's check row
  return wb;
}
const wb13 = fixtureWired();
const pre13 = JSON.parse(main(wb13, JSON.stringify({ mode: "PREFLIGHT",
  sheets: ["Model", "Raw"], periodKind: "FY", targetYear: 2025 })));
et("the wired model tab reads as formulas, the raw tab as typed numbers",
  pre13.sheets[0].typedShare === 0.2 && pre13.needsExtend[0].hardcodeShare === 1);
et("missing year column becomes a PROPOSAL, not a failure",
  pre13.needsExtend.length === 1 && pre13.needsExtend[0].sheet === "Raw" &&
  pre13.needsExtend[0].newCol === "E" &&
  pre13.needsExtend[0].newColEmpty === true &&
  /Ask the analyst/.test(pre13.needsExtend[0].ask));
const ex1 = JSON.parse(main(wb13, JSON.stringify({ mode: "EXTEND",
  sheet: "Raw", targetYear: 2025 })));
et("EXTEND refuses to add a column on its own authority",
  ex1.ok === false && ex1.needsApproval === true);
et("nothing was added while unapproved",
  wb13.getWorksheet("Raw").getRange("E1").getValues()[0][0] === "");
const ex2 = JSON.parse(main(wb13, JSON.stringify({ mode: "EXTEND",
  sheet: "Raw", targetYear: 2025, analystApproved: true })));
et("approved EXTEND adds the column with the right header",
  ex2.ok === true && ex2.newCol === "E" &&
  wb13.getWorksheet("Raw").getRange("E1").getValues()[0][0] === 2025);
et("the new column starts EMPTY (a blank is honest, last year's number lies)",
  wb13.getWorksheet("Raw").getRange("E3").getValues()[0][0] === "");
const ex3 = JSON.parse(main(wb13, JSON.stringify({ mode: "EXTEND",
  sheet: "Raw", targetYear: 2025, analystApproved: true })));
et("a repeat run sails through EXTEND instead of stalling",
  ex3.ok === true && ex3.alreadyPresent === true &&
  wb13.getWorksheet("Raw").getRange("F1").getValues()[0][0] === "");
main(wb13, JSON.stringify({ mode: "PREFLIGHT", sheets: ["Model", "Raw"],
  periodKind: "FY", targetYear: 2025 }));
stage(wb13, [
  ["Revenue", 5321.0, 4976.2, "p3", "", "", "Raw"],
  ["Cost of sales", -3200.0, -3000.0, "p3", "", "", "Raw"],
  ["Revenue", 5321.0, 4976.2, "p3", "", "", "Model"],
]);
const apRaw = JSON.parse(main(wb13, JSON.stringify(
  { mode: "APPLY", sheet: "Raw", targetYear: 2025 })));
et("actuals are typed into the input sheet", apRaw.written === 2 &&
  wb13.getWorksheet("Raw").getRange("E3").getValues()[0][0] === 5321.0);
const apMod = JSON.parse(main(wb13, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("a wired cell is NEVER typed over — the link is kept",
  apMod.written === 0 && apMod.keptWired === 1 &&
  wb13.getWorksheet("Model").cell(2, 4).f === "='Raw'!E3");
et("the kept link now feeds the new period's actual",
  wb13.getWorksheet("Model").getRange("E3").getValues()[0][0] === 5321.0);
et("a formula with a number baked in is surfaced as a key driver",
  apMod.embeddedHardcodes === 1 &&
  wb13.getWorksheet("Model").cell(4, 4).fill === "FFC7CE");
et("last year's typed number is reported, not silently kept as this year's",
  apMod.carriedOver === 1);
const rep13 = JSON.parse(main(wb13, JSON.stringify({ mode: "REPORT" })));
et("report carries the two new sections",
  rep13.keyDrivers === 1 && rep13.notUpdated === 1);
const flat13 = JSON.stringify(
  wb13.getWorksheet("_REPORT").getUsedRange().getValues());
et("the report names the baked-in formula so the analyst can judge it",
  /=D3\+36/.test(flat13) && /Analyst overlay/.test(flat13));

// a wired cell whose source disagrees with the disclosure must shout
stage(wb13, [["Revenue", 9999.0, 4976.2, "p3", "", "", "Model"]]);
const apConf = JSON.parse(main(wb13, JSON.stringify(
  { mode: "APPLY", sheet: "Model", targetYear: 2025 })));
et("wired result vs disclosure mismatch is caught",
  apConf.conflicts.length === 1 && apConf.conflicts[0].row === 3 &&
  wb13.getWorksheet("Model").cell(2, 4).fill === "FFC7CE");
et("and the link is STILL not overwritten",
  wb13.getWorksheet("Model").cell(2, 4).f === "='Raw'!E3");

console.log(`\nkernel e2e: ${ePass} pass, ${eFail} fail`);
if (typeof process !== "undefined") process.exit(eFail ? 1 : 0);
`E2E ${ePass} pass ${eFail} fail`;
