// ============================================================
// MODEL UPDATE AGENT — Studio-native kernel (Phase 1)
// ONE Office Script, mode-driven (council ruling 2026-08-26:
// one kernel beats six scripts — a law fixed once is fixed
// everywhere). The flow calls Run script repeatedly with a small
// JSON control message; ALL state lives in hidden sheets inside
// the workbook (the workbook is the bus):
//   _ANATOMY  what the model expects (rows, labels, prior values)
//   _STAGING  what the Agent read from the disclosure
//   _PLAN     validated write plan (refused rows carry the reason)
//   _LEDGER   append-only forensic trail
// Modes:
//   PREFLIGHT {sheet, periodKind, targetYear}
//   APPLY     {sheet, targetYear}
//   POLICE    {sheet}
// Input/output: JSON strings (Power Automate friendly).
// The pure-law section below (axis + ties) is generated from
// studio-native/core/*.js — edit THOSE files, run build.sh,
// never edit the laws inside this file.
// ============================================================

// __CORE_LAWS__ (build.sh splices core/axis.js + core/ties.js here)

// ---------- shared helpers (ExcelScript side) ----------------

const FLAG_RED = "FFC7CE";     // uncertain — analyst review
const FLAG_ORANGE = "FFC000";  // backed-out — awaiting true-up

function getOrCreate(wb, name) {
  let ws = wb.getWorksheet(name);
  if (!ws) {
    ws = wb.addWorksheet(name);
    ws.setVisibility(ExcelScript.SheetVisibility.hidden);
  }
  return ws;
}

function sheetGrid(ws) {
  const ur = ws.getUsedRange();
  return ur ? ur.getValues() : [];
}

function ledgerAppend(wb, rows) {
  const ws = getOrCreate(wb, "_LEDGER");
  const ur = ws.getUsedRange();
  const start = ur ? ur.getRowCount() : 0;
  if (start === 0)
    ws.getRange("A1:H1").setValues([[
      "utc", "mode", "sheet", "address", "before", "after", "flag", "why"]]);
  const r0 = Math.max(start, 1);
  ws.getRangeByIndexes(r0, 0, rows.length, 8).setValues(rows);
}

// label column: first column holding text in most target rows
function labelOf(grid, row) {
  for (let c = 0; c < Math.min(4, (grid[row] || []).length); c++) {
    const v = grid[row][c];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return "";
}

// ---------- SEED ---------------------------------------------
// Build the Phase 1 practice model from data baked into the script —
// company walls allow code text in but not files, so the workbook
// travels AS the code. Run the kernel with empty input (or
// {"mode":"SEED"}) on a blank workbook and the practice sheet appears:
// DFE's real FY22-24 actuals, announcement-exact Chinese labels, and
// the model's own balance-check row.
var SEED_ROWS = [["报告期","FY2022","FY2023","FY2024","FY2025"],["","","","",""],["P&L (Rmb m)","","","",""],["    营业总收入",55353.14,60676.61,69695.14,""],["    营业收入",54179.06,59566.53,68592.74,""],["        其他类金融业务收入",1174.08,1110.09,1102.4,""],["营业总成本",52452.27,57338.36,66679.76,""],["        营业成本",45244.94,49253.17,58876.11,""],["    税金及附加",325.82,303.47,378.53,""],["    销售费用",1483.43,1587.51,822.36,""],["    管理费用",3116.97,3403.9,3523.05,""],["    研发费用",2274.63,2749.53,3009.01,""],["    财务费用",-97.81,7.45,44.55,""],["        其中：利息费用",79.42,64.44,82.97,""],["                    减：利息收入",42.43,120.75,132.71,""],["        其他业务成本(金融类)",104.28,33.33,26.15,""],["    加：其他收益",150.75,438.8,769.92,""],["    投资净收益",480.56,748.15,1577.06,""],["        其中：对联营企业和合营企业的投资收益",301.77,320.69,186.94,""],["    公允价值变动净收益",-61.54,85.06,-204.16,""],["    资产减值损失",-480.48,-495.92,-1148.01,""],["    信用减值损失",277.44,-175.68,-146.04,""],["    资产处置收益",50.19,9.77,16.45,""],["    汇兑净收益",3.07,28.24,6.84,""],["营业利润",3320.87,3976.68,3887.45,""],["","","","",""],["Balance sheet","","","",""],["资产总计",115265.06,121108.37,142009.28,""],["    负债合计",76640.19,79888.5,98867.04,""],["    所有者权益合计",38624.87,41219.87,43142.25,""],["Check 平衡校验","=B28-B29-B30","=C28-C29-C30","=D28-D29-D30","=E28-E29-E30"]];

function modeSeed(wb) {
  let ws = wb.getWorksheet("Model");
  if (!ws) ws = wb.addWorksheet("Model");
  const ur = ws.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  for (let r = 0; r < SEED_ROWS.length; r++)
    for (let c = 0; c < SEED_ROWS[r].length; c++) {
      const v = SEED_ROWS[r][c];
      if (v === "") continue;
      const cell = ws.getRangeByIndexes(r, c, 1, 1);
      if (typeof v === "string" && v.charAt(0) === "=") cell.setFormula(v);
      else cell.setValue(v);
    }
  return JSON.stringify({ ok: true, seeded: SEED_ROWS.length,
    note: "practice model built — sheet 'Model'" });
}

// ---------- PREFLIGHT ----------------------------------------
// Discover the sheet's year axis (the 1H-trap law applies), find the
// prior actual column and the target column, and write every labelled
// row's prior value into _ANATOMY. _ANATOMY becomes the oracle the
// APPLY mode triangulates against.
function modePreflight(wb, p) {
  const ws = wb.getWorksheet(p.sheet);
  if (!ws) return JSON.stringify({ ok: false, why: "no sheet " + p.sheet });
  const grid = sheetGrid(ws);
  const axis = findYearAxis(grid, p.periodKind);
  if (!axis) return JSON.stringify({ ok: false, why: "no year axis found" });
  const tCol = axis[String(p.targetYear)];
  const pCol = axis[String(p.targetYear - 1)];
  if (tCol === undefined || pCol === undefined)
    return JSON.stringify({
      ok: false,
      why: "axis lacks " + p.targetYear + " or prior; axis=" + JSON.stringify(axis)
    });
  // locate the axis header row (the row whose target cell marks the year)
  // — APPLY must restore this cell after the bulk column copy, or the
  // prior year's header stamps over the target's (a header is data too).
  let axisRow = -1;
  for (let r = 0; r < Math.min(grid.length, SCAN_ROWS); r++) {
    const yt = yearOf(grid[r][tCol]);
    if (yt[0] === p.targetYear) { axisRow = r; break; }
  }
  const rows = [["__meta__", axisRow, String(grid[axisRow] ? grid[axisRow][tCol] : ""), 0, n2col(pCol), n2col(tCol)]];
  for (let r = 0; r < grid.length; r++) {
    const lab = labelOf(grid, r);
    if (!lab) continue;
    const pv = grid[r][pCol];
    if (typeof pv !== "number") continue;
    rows.push([p.sheet, r + 1, lab, pv, n2col(pCol), n2col(tCol)]);
  }
  const an = getOrCreate(wb, "_ANATOMY");
  const ur = an.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  an.getRange("A1:F1").setValues([[
    "sheet", "row", "label", "priorValue", "priorCol", "targetCol"]]);
  if (rows.length)
    an.getRangeByIndexes(1, 0, rows.length, 6).setValues(rows);
  return JSON.stringify({
    ok: true, axis: axis, priorCol: n2col(pCol), targetCol: n2col(tCol),
    anatomyRows: rows.length
  });
}

// ---------- STAGE --------------------------------------------
// Land the Agent's extraction in _STAGING. rows: array of
// [label, value, priorDisclosed, sourcePage, flag, note] arrays, exactly
// as the extraction prompt instructs the Agent to emit them. Extraction
// is FACTS ONLY — mapping/judgment happens in APPLY where code referees.
function modeStage(wb, p) {
  const st = getOrCreate(wb, "_STAGING");
  const ur = st.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  st.getRange("A1:F1").setValues([[
    "label", "value", "priorDisclosed", "sourcePage", "flag", "note"]]);
  const rows = p.rows || [];
  const norm = [];
  for (const r of rows)
    norm.push([String(r[0] || ""), r[1], r[2], String(r[3] || ""),
      String(r[4] || ""), String(r[5] || "")]);
  if (norm.length)
    st.getRangeByIndexes(1, 0, norm.length, 6).setValues(norm);
  return JSON.stringify({ ok: true, staged: norm.length });
}

// ---------- APPLY --------------------------------------------
// Transactional: read _STAGING (the Agent's extraction), triangulate
// every entry against _ANATOMY (validateWritePlan — the referee),
// write _PLAN with accept/refuse verdicts, and only then mutate the
// model: copy the prior actual column (values+formats+formulas, the
// mark-to-actual recipe), overwrite accepted inputs, flag colors,
// ledger every touch. Refused rows are NEVER written — they turn the
// target cell red with the refusal reason in _PLAN.
function modeApply(wb, p) {
  const anWs = wb.getWorksheet("_ANATOMY");
  const stWs = wb.getWorksheet("_STAGING");
  if (!anWs || !stWs)
    return JSON.stringify({ ok: false, why: "run PREFLIGHT first / no _STAGING" });
  const an = sheetGrid(anWs);
  const st = sheetGrid(stWs);
  // anatomy: label -> {row, prior}; priors keyed Sheet!row for the referee
  const byLabel = {};
  const priors = {};
  let priorCol = "", targetCol = "";
  let axisRow = -1, axisHeader = "";
  for (let i = 1; i < an.length; i++) {
    const sh = an[i][0], row = an[i][1], lab = an[i][2], pv = an[i][3];
    const pc = an[i][4], tc = an[i][5];
    if (sh === "__meta__") {                 // axis header bookkeeping
      axisRow = row; axisHeader = lab;
      priorCol = String(pc); targetCol = String(tc);
      continue;
    }
    if (sh !== p.sheet) continue;
    byLabel[String(lab).toLowerCase()] = { row: row, prior: pv };
    priors[p.sheet + "!" + row] = pv;
    priorCol = String(pc); targetCol = String(tc);
  }
  if (!priorCol)
    return JSON.stringify({ ok: false, why: "_ANATOMY empty for " + p.sheet });
  // staging: label | value | priorDisclosed | sourcePage | flag | note
  const entries = [];
  const unmapped = [];
  for (let i = 1; i < st.length; i++) {
    const lab = String(st[i][0] || "").trim();
    if (!lab) continue;
    const hit = byLabel[lab.toLowerCase()];
    if (!hit) { unmapped.push(lab); continue; }
    entries.push({
      sheet: p.sheet, row: hit.row,
      value: st[i][1],
      priorDisclosed: st[i][2],
      flag: String(st[i][4] || ""), note: String(st[i][5] || ""),
      label: lab, page: String(st[i][3] || "")
    });
  }
  const verdict = validateWritePlan(entries, priors);
  // ---- write _PLAN (the transactional boundary: plan ≠ apply) ----
  const plWs = getOrCreate(wb, "_PLAN");
  const pur = plWs.getUsedRange();
  if (pur) pur.clear(ExcelScript.ClearApplyTo.all);
  const planRows = [[
    "sheet", "row", "label", "value", "verdict", "why", "page"]];
  for (const e of verdict.accepted)
    planRows.push([e.sheet, e.row, e.label || "",
      e.value, "ACCEPT", e.flag || "", e.page || ""]);
  for (const r of verdict.refused)
    planRows.push([r.entry.sheet, r.entry.row,
      r.entry.label || "", r.entry.value ?? "",
      "REFUSE", r.why, r.entry.page || ""]);
  plWs.getRangeByIndexes(0, 0, planRows.length, 7).setValues(planRows);
  // ---- mutate the model ----
  const ws = wb.getWorksheet(p.sheet);
  const grid = sheetGrid(ws);
  const nRows = grid.length;
  // mark-to-actual recipe: bulk copy prior column (values+formulas+formats)
  const src = ws.getRange(priorCol + "1:" + priorCol + nRows);
  const dst = ws.getRange(targetCol + "1:" + targetCol + nRows);
  dst.copyFrom(src, ExcelScript.RangeCopyType.all);
  // restore the target year header the bulk copy just stamped over —
  // never change a header's data type: numeric stays numeric
  if (axisRow >= 0) {
    const hNum = Number(axisHeader);
    ws.getRange(targetCol + (axisRow + 1)).setValue(
      axisHeader !== "" && !isNaN(hNum) ? hNum : axisHeader);
  }
  const led = [];
  const utc = new Date().toISOString();
  for (const e of verdict.accepted) {
    const addr = targetCol + e.row;
    const cell = ws.getRange(addr);
    const before = cell.getValues()[0][0];
    cell.setValue(e.value);
    if (e.flag === "red") cell.getFormat().getFill().setColor(FLAG_RED);
    if (e.flag === "orange") cell.getFormat().getFill().setColor(FLAG_ORANGE);
    const after = cell.getValues()[0][0];   // verify by read-back
    led.push([utc, "APPLY", e.sheet, addr, String(before), String(after),
      e.flag || "", ""]);
  }
  for (const r of verdict.refused) {
    const addr = targetCol + r.entry.row;
    ws.getRange(addr).getFormat().getFill().setColor(FLAG_RED);
    led.push([utc, "APPLY", r.entry.sheet, addr, "", "", "red", r.why]);
  }
  if (led.length) ledgerAppend(wb, led);
  return JSON.stringify({
    ok: true, written: verdict.accepted.length,
    refused: verdict.refused.length, unmappedLabels: unmapped,
    refusals: verdict.refused.map(r => ({
      row: r.entry.row, why: r.why
    }))
  });
}

// ---------- POLICE -------------------------------------------
// Force a full recalc, then read every model-native check row (rows
// whose label matches the check pattern) in the target column. Any
// non-zero check = the model does not balance = the run FAILED.
function modePolice(wb, p) {
  wb.getApplication().calculate(ExcelScript.CalculationType.full);
  const anWs = wb.getWorksheet("_ANATOMY");
  if (!anWs) return JSON.stringify({ ok: false, why: "run PREFLIGHT first" });
  const an = sheetGrid(anWs);
  const ws = wb.getWorksheet(p.sheet);
  const grid = sheetGrid(ws);
  // same pattern as updater/discover.py _CHECK_LABEL — deliberately NOT
  // matching bare 'balance'/'tie' ('liabiliTIEs', 'Balance sheet' rows)
  const CHECK = /check|差额|平衡|balance test|检验|校验/i;
  const verdicts = [];
  let targetCol = "";
  for (let i = 1; i < an.length; i++) {
    if (an[i][0] !== p.sheet) continue;
    targetCol = String(an[i][5]);
    const lab = String(an[i][2]);
    if (!CHECK.test(lab)) continue;
    const row = an[i][1];
    const v = grid[row - 1] ?
      grid[row - 1][ws.getRange(targetCol + "1").getColumnIndex()] : null;
    if (typeof v === "number")
      verdicts.push({ row: row, label: lab, value: v, pass: Math.abs(v) <= 0.02 });
  }
  const failed = verdicts.filter(v => !v.pass);
  return JSON.stringify({
    ok: failed.length === 0, checks: verdicts.length,
    failed: failed
  });
}

// ---------- entry --------------------------------------------
function main(workbook, input) {
  let p;
  if (input === undefined || input === null || String(input).trim() === "")
    p = { mode: "SEED" };            // bare manual Run = build the practice model
  else {
    try { p = JSON.parse(input); }
    catch { return JSON.stringify({ ok: false, why: "bad input JSON" }); }
  }
  try {
    if (p.mode === "SEED")
      return modeSeed(workbook);
    if (p.mode === "PREFLIGHT")
      return modePreflight(workbook, p );
    if (p.mode === "STAGE")
      return modeStage(workbook, p);
    if (p.mode === "APPLY")
      return modeApply(workbook, p );
    if (p.mode === "POLICE")
      return modePolice(workbook, p );
    return JSON.stringify({ ok: false, why: "unknown mode " + p.mode });
  } catch (e) {
    return JSON.stringify({ ok: false, why: "kernel error: " + String(e) });
  }
}
