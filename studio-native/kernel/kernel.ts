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
// Modes (input = JSON string; EMPTY input = SEED):
//   SEED      build the Phase 1 practice model into sheet 'Model'
//   PREFLIGHT {"mode":"PREFLIGHT","sheet":"Model","periodKind":"FY","targetYear":2025}
//   STAGE     {"mode":"STAGE","rows":[[label,value,prior,page,flag,note],...]}
//   APPLY     {"mode":"APPLY","sheet":"Model","targetYear":2025}
//   POLICE    {"mode":"POLICE","sheet":"Model"}
// The pure-law section below (axis + ties) is generated from
// studio-native/core/*.ts — edit THOSE files, run build.sh,
// never edit the laws inside this file.
// ============================================================

// __CORE_LAWS__ (build.sh splices core/axis.ts + core/ties.ts here)

// ---------- shared helpers (ExcelScript side) ----------------

interface Params {
  mode: string;
  sheet?: string;
  periodKind?: string;
  targetYear?: number;
  rows?: (string | number | null)[][];
}

const FLAG_RED: string = "FFC7CE";     // uncertain — analyst review
const FLAG_ORANGE: string = "FFC000";  // backed-out — awaiting true-up

function getOrCreate(wb: ExcelScript.Workbook,
                     name: string): ExcelScript.Worksheet {
  let ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(name);
  if (!ws) {
    ws = wb.addWorksheet(name);
    ws.setVisibility(ExcelScript.SheetVisibility.hidden);
  }
  return ws;
}

function sheetGrid(ws: ExcelScript.Worksheet): CellValue[][] {
  const ur: ExcelScript.Range | undefined = ws.getUsedRange();
  if (!ur) return [];
  return ur.getValues() as CellValue[][];
}

function ledgerAppend(wb: ExcelScript.Workbook,
                      rows: (string | number)[][]): void {
  const ws: ExcelScript.Worksheet = getOrCreate(wb, "_LEDGER");
  const ur: ExcelScript.Range | undefined = ws.getUsedRange();
  const start: number = ur ? ur.getRowCount() : 0;
  if (start === 0)
    ws.getRange("A1:H1").setValues([[
      "utc", "mode", "sheet", "address", "before", "after", "flag", "why"]]);
  const r0: number = Math.max(start, 1);
  ws.getRangeByIndexes(r0, 0, rows.length, 8).setValues(rows);
}

// label column: first column holding text among the row's first cells
function labelOf(grid: CellValue[][], row: number): string {
  const cells: CellValue[] = grid[row] ? grid[row] : [];
  for (let c: number = 0; c < Math.min(4, cells.length); c++) {
    const v: CellValue = cells[c];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return "";
}

// ---------- SEED ---------------------------------------------
// Build the Phase 1 practice model from data baked into the script —
// company walls allow code text in but not files, so the workbook
// travels AS the code. Run the kernel with EMPTY input on a blank
// workbook and the practice sheet appears: DFE's real FY22-24 actuals,
// announcement-exact Chinese labels, and the model's own check row.
const SEED_ROWS: (string | number)[][] = [["报告期","FY2022","FY2023","FY2024","FY2025"],["","","","",""],["P&L (Rmb m)","","","",""],["    营业总收入",55353.14,60676.61,69695.14,""],["    营业收入",54179.06,59566.53,68592.74,""],["        其他类金融业务收入",1174.08,1110.09,1102.4,""],["营业总成本",52452.27,57338.36,66679.76,""],["        营业成本",45244.94,49253.17,58876.11,""],["    税金及附加",325.82,303.47,378.53,""],["    销售费用",1483.43,1587.51,822.36,""],["    管理费用",3116.97,3403.9,3523.05,""],["    研发费用",2274.63,2749.53,3009.01,""],["    财务费用",-97.81,7.45,44.55,""],["        其中：利息费用",79.42,64.44,82.97,""],["                    减：利息收入",42.43,120.75,132.71,""],["        其他业务成本(金融类)",104.28,33.33,26.15,""],["    加：其他收益",150.75,438.8,769.92,""],["    投资净收益",480.56,748.15,1577.06,""],["        其中：对联营企业和合营企业的投资收益",301.77,320.69,186.94,""],["    公允价值变动净收益",-61.54,85.06,-204.16,""],["    资产减值损失",-480.48,-495.92,-1148.01,""],["    信用减值损失",277.44,-175.68,-146.04,""],["    资产处置收益",50.19,9.77,16.45,""],["    汇兑净收益",3.07,28.24,6.84,""],["营业利润",3320.87,3976.68,3887.45,""],["","","","",""],["Balance sheet","","","",""],["资产总计",115265.06,121108.37,142009.28,""],["    负债合计",76640.19,79888.5,98867.04,""],["    所有者权益合计",38624.87,41219.87,43142.25,""],["Check 平衡校验","=B28-B29-B30","=C28-C29-C30","=D28-D29-D30","=E28-E29-E30"]];

function modeSeed(wb: ExcelScript.Workbook): string {
  let ws: ExcelScript.Worksheet | undefined = wb.getWorksheet("Model");
  if (!ws) ws = wb.addWorksheet("Model");
  const ur: ExcelScript.Range | undefined = ws.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  for (let r: number = 0; r < SEED_ROWS.length; r++)
    for (let c: number = 0; c < SEED_ROWS[r].length; c++) {
      const v: string | number = SEED_ROWS[r][c];
      if (v === "") continue;
      const cell: ExcelScript.Range = ws.getRangeByIndexes(r, c, 1, 1);
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
function modePreflight(wb: ExcelScript.Workbook, p: Params): string {
  const sheetName: string = String(p.sheet);
  const ty: number = Number(p.targetYear);
  const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(sheetName);
  if (!ws) return JSON.stringify({ ok: false, why: "no sheet " + sheetName });
  const grid: CellValue[][] = sheetGrid(ws);
  const axis: AxisMap | null = findYearAxis(grid, String(p.periodKind || "FY"));
  if (!axis) return JSON.stringify({ ok: false, why: "no year axis found" });
  const tCol: number | undefined = axis[String(ty)];
  const pCol: number | undefined = axis[String(ty - 1)];
  if (tCol === undefined || pCol === undefined)
    return JSON.stringify({
      ok: false,
      why: "axis lacks " + ty + " or prior; axis=" + JSON.stringify(axis)
    });
  // locate the axis header row (the row whose target cell marks the year)
  // — APPLY must restore this cell after the bulk column copy, or the
  // prior year's header stamps over the target's (a header is data too).
  let axisRow: number = -1;
  for (let r: number = 0; r < Math.min(grid.length, SCAN_ROWS); r++) {
    const yt: YearMark = yearOf(grid[r][tCol]);
    if (yt[0] === ty) { axisRow = r; break; }
  }
  const headerVal: CellValue = (axisRow >= 0 && grid[axisRow])
    ? grid[axisRow][tCol] : "";
  const rows: (string | number)[][] = [
    ["__meta__", axisRow, String(headerVal), 0, n2col(pCol), n2col(tCol)]];
  for (let r: number = 0; r < grid.length; r++) {
    const lab: string = labelOf(grid, r);
    if (!lab) continue;
    const pv: CellValue = grid[r][pCol];
    if (typeof pv !== "number") continue;
    rows.push([sheetName, r + 1, lab, pv, n2col(pCol), n2col(tCol)]);
  }
  const an: ExcelScript.Worksheet = getOrCreate(wb, "_ANATOMY");
  const ur: ExcelScript.Range | undefined = an.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  an.getRange("A1:F1").setValues([[
    "sheet", "row", "label", "priorValue", "priorCol", "targetCol"]]);
  if (rows.length > 0)
    an.getRangeByIndexes(1, 0, rows.length, 6).setValues(rows);
  return JSON.stringify({
    ok: true, axis: axis, priorCol: n2col(pCol), targetCol: n2col(tCol),
    anatomyRows: rows.length - 1
  });
}

// ---------- STAGE --------------------------------------------
// Land the Agent's extraction in _STAGING. rows: array of
// [label, value, priorDisclosed, sourcePage, flag, note] arrays, exactly
// as the extraction prompt instructs the Agent to emit them. Extraction
// is FACTS ONLY — mapping/judgment happens in APPLY where code referees.
function modeStage(wb: ExcelScript.Workbook, p: Params): string {
  const st: ExcelScript.Worksheet = getOrCreate(wb, "_STAGING");
  const ur: ExcelScript.Range | undefined = st.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  st.getRange("A1:F1").setValues([[
    "label", "value", "priorDisclosed", "sourcePage", "flag", "note"]]);
  const rows: (string | number | null)[][] = p.rows ? p.rows : [];
  const norm: (string | number)[][] = [];
  for (let i: number = 0; i < rows.length; i++) {
    const r: (string | number | null)[] = rows[i];
    const val: string | number =
      (typeof r[1] === "number") ? r[1] : "";
    const pri: string | number =
      (typeof r[2] === "number") ? r[2] : "";
    norm.push([String(r[0] === null || r[0] === undefined ? "" : r[0]),
      val, pri, String(r[3] === null || r[3] === undefined ? "" : r[3]),
      String(r[4] === null || r[4] === undefined ? "" : r[4]),
      String(r[5] === null || r[5] === undefined ? "" : r[5])]);
  }
  if (norm.length > 0)
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
function modeApply(wb: ExcelScript.Workbook, p: Params): string {
  const sheetName: string = String(p.sheet);
  const anWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_ANATOMY");
  const stWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_STAGING");
  if (!anWs || !stWs)
    return JSON.stringify({ ok: false, why: "run PREFLIGHT first / no _STAGING" });
  const an: CellValue[][] = sheetGrid(anWs);
  const st: CellValue[][] = sheetGrid(stWs);
  // anatomy: label -> {row, prior}; priors keyed Sheet!row for the referee
  const byLabel: { [k: string]: { row: number; prior: number } } = {};
  const priors: { [k: string]: number } = {};
  let priorCol: string = "";
  let targetCol: string = "";
  let axisRow: number = -1;
  let axisHeader: string = "";
  for (let i: number = 1; i < an.length; i++) {
    const sh: CellValue = an[i][0];
    const row: number = Number(an[i][1]);
    const lab: string = String(an[i][2]);
    const pv: CellValue = an[i][3];
    if (sh === "__meta__") {                 // axis header bookkeeping
      axisRow = row; axisHeader = lab;
      priorCol = String(an[i][4]); targetCol = String(an[i][5]);
      continue;
    }
    if (sh !== sheetName) continue;
    if (typeof pv !== "number") continue;
    byLabel[lab.toLowerCase()] = { row: row, prior: pv };
    priors[sheetName + "!" + row] = pv;
    priorCol = String(an[i][4]); targetCol = String(an[i][5]);
  }
  if (!priorCol)
    return JSON.stringify({ ok: false, why: "_ANATOMY empty for " + sheetName });
  // staging: label | value | priorDisclosed | sourcePage | flag | note
  const entries: PlanEntry[] = [];
  const unmapped: string[] = [];
  for (let i: number = 1; i < st.length; i++) {
    const lab: string = String(st[i][0] === undefined ? "" : st[i][0]).trim();
    if (!lab) continue;
    const hit: { row: number; prior: number } | undefined =
      byLabel[lab.toLowerCase()];
    if (!hit) { unmapped.push(lab); continue; }
    const rawV: CellValue = st[i][1];
    const rawP: CellValue = st[i][2];
    entries.push({
      sheet: sheetName, row: hit.row,
      value: (typeof rawV === "number") ? rawV : null,
      priorDisclosed: (typeof rawP === "number") ? rawP : null,
      flag: String(st[i][4] === undefined ? "" : st[i][4]),
      note: String(st[i][5] === undefined ? "" : st[i][5]),
      label: lab,
      page: String(st[i][3] === undefined ? "" : st[i][3])
    });
  }
  const verdict: PlanVerdict = validateWritePlan(entries, priors);
  // ---- write _PLAN (the transactional boundary: plan ≠ apply) ----
  const plWs: ExcelScript.Worksheet = getOrCreate(wb, "_PLAN");
  const pur: ExcelScript.Range | undefined = plWs.getUsedRange();
  if (pur) pur.clear(ExcelScript.ClearApplyTo.all);
  const planRows: (string | number)[][] = [[
    "sheet", "row", "label", "value", "verdict", "why", "page"]];
  for (let i: number = 0; i < verdict.accepted.length; i++) {
    const e: PlanEntry = verdict.accepted[i];
    planRows.push([e.sheet, e.row, e.label ? e.label : "",
      (typeof e.value === "number") ? e.value : "",
      "ACCEPT", e.flag, e.page ? e.page : ""]);
  }
  for (let i: number = 0; i < verdict.refused.length; i++) {
    const r: Refusal = verdict.refused[i];
    planRows.push([r.entry.sheet, r.entry.row,
      r.entry.label ? r.entry.label : "",
      (typeof r.entry.value === "number") ? r.entry.value : "",
      "REFUSE", r.why, r.entry.page ? r.entry.page : ""]);
  }
  plWs.getRangeByIndexes(0, 0, planRows.length, 7).setValues(planRows);
  // ---- mutate the model ----
  const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(sheetName);
  if (!ws) return JSON.stringify({ ok: false, why: "no sheet " + sheetName });
  const grid: CellValue[][] = sheetGrid(ws);
  const nRows: number = grid.length;
  // mark-to-actual recipe: bulk copy prior column (values+formulas+formats)
  const src: ExcelScript.Range =
    ws.getRange(priorCol + "1:" + priorCol + nRows);
  const dst: ExcelScript.Range =
    ws.getRange(targetCol + "1:" + targetCol + nRows);
  dst.copyFrom(src, ExcelScript.RangeCopyType.all);
  // restore the target year header the bulk copy just stamped over —
  // never change a header's data type: numeric stays numeric
  if (axisRow >= 0) {
    const hNum: number = Number(axisHeader);
    const hCell: ExcelScript.Range = ws.getRange(targetCol + (axisRow + 1));
    if (axisHeader !== "" && !isNaN(hNum)) hCell.setValue(hNum);
    else hCell.setValue(axisHeader);
  }
  const led: (string | number)[][] = [];
  const utc: string = new Date().toISOString();
  for (let i: number = 0; i < verdict.accepted.length; i++) {
    const e: PlanEntry = verdict.accepted[i];
    const addr: string = targetCol + e.row;
    const cell: ExcelScript.Range = ws.getRange(addr);
    const before: CellValue = cell.getValues()[0][0] as CellValue;
    if (typeof e.value === "number") cell.setValue(e.value);
    if (e.flag === "red") cell.getFormat().getFill().setColor(FLAG_RED);
    if (e.flag === "orange") cell.getFormat().getFill().setColor(FLAG_ORANGE);
    const after: CellValue = cell.getValues()[0][0] as CellValue;
    led.push([utc, "APPLY", e.sheet, addr, String(before), String(after),
      e.flag, ""]);
  }
  for (let i: number = 0; i < verdict.refused.length; i++) {
    const r: Refusal = verdict.refused[i];
    const addr: string = targetCol + r.entry.row;
    ws.getRange(addr).getFormat().getFill().setColor(FLAG_RED);
    led.push([utc, "APPLY", r.entry.sheet, addr, "", "", "red", r.why]);
  }
  if (led.length > 0) ledgerAppend(wb, led);
  const refusals: { row: number; why: string }[] = [];
  for (let i: number = 0; i < verdict.refused.length; i++)
    refusals.push({ row: verdict.refused[i].entry.row,
      why: verdict.refused[i].why });
  return JSON.stringify({
    ok: true, written: verdict.accepted.length,
    refused: verdict.refused.length, unmappedLabels: unmapped,
    refusals: refusals
  });
}

// ---------- POLICE -------------------------------------------
// Force a full recalc, then read every model-native check row (rows
// whose label matches the check pattern) in the target column. Any
// non-zero check = the model does not balance = the run FAILED.
function modePolice(wb: ExcelScript.Workbook, p: Params): string {
  const sheetName: string = String(p.sheet);
  wb.getApplication().calculate(ExcelScript.CalculationType.full);
  const anWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_ANATOMY");
  if (!anWs) return JSON.stringify({ ok: false, why: "run PREFLIGHT first" });
  const an: CellValue[][] = sheetGrid(anWs);
  const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(sheetName);
  if (!ws) return JSON.stringify({ ok: false, why: "no sheet " + sheetName });
  const grid: CellValue[][] = sheetGrid(ws);
  // same pattern as updater/discover.py _CHECK_LABEL — deliberately NOT
  // matching bare 'balance'/'tie' ('liabiliTIEs', 'Balance sheet' rows)
  const CHECK: RegExp = /check|差额|平衡|balance test|检验|校验/i;
  interface CheckVerdict { row: number; label: string; value: number;
    pass: boolean; }
  const verdicts: CheckVerdict[] = [];
  for (let i: number = 1; i < an.length; i++) {
    if (an[i][0] !== sheetName) continue;
    const targetCol: string = String(an[i][5]);
    const lab: string = String(an[i][2]);
    if (!CHECK.test(lab)) continue;
    const row: number = Number(an[i][1]);
    const colIdx: number = ws.getRange(targetCol + "1").getColumnIndex();
    const v: CellValue | null =
      grid[row - 1] ? grid[row - 1][colIdx] : null;
    if (typeof v === "number")
      verdicts.push({ row: row, label: lab, value: v,
        pass: Math.abs(v) <= 0.02 });
  }
  const failed: CheckVerdict[] = [];
  for (let i: number = 0; i < verdicts.length; i++)
    if (!verdicts[i].pass) failed.push(verdicts[i]);
  return JSON.stringify({
    ok: failed.length === 0, checks: verdicts.length, failed: failed
  });
}

// ---------- entry --------------------------------------------
function main(workbook: ExcelScript.Workbook, input?: string): string {
  let p: Params;
  if (input === undefined || input === null || String(input).trim() === "")
    p = { mode: "SEED" };          // bare manual Run = build the practice model
  else {
    try { p = JSON.parse(input) as Params; }
    catch (err) {
      return JSON.stringify({ ok: false, why: "bad input JSON" });
    }
  }
  try {
    if (p.mode === "SEED") return modeSeed(workbook);
    if (p.mode === "PREFLIGHT") return modePreflight(workbook, p);
    if (p.mode === "STAGE") return modeStage(workbook, p);
    if (p.mode === "APPLY") return modeApply(workbook, p);
    if (p.mode === "POLICE") return modePolice(workbook, p);
    return JSON.stringify({ ok: false, why: "unknown mode " + p.mode });
  } catch (err) {
    return JSON.stringify({ ok: false, why: "kernel error: " + String(err) });
  }
}
