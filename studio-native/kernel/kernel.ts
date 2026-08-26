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
//   PREFLIGHT {"mode":"PREFLIGHT","sheets":["Model","BS"],"periodKind":"FY","targetYear":2025}
//   STAGE     {"mode":"STAGE","rows":[[label,value,prior,page,flag,note,sheet,row],...]}
//   RESTATE   {"mode":"RESTATE"}                    scan comparatives, may STOP
//   APPLY     {"mode":"APPLY","sheet":"Model","targetYear":2025}
//   POLICE    {"mode":"POLICE"}                     all preflighted sheets
//   REPORT    {"mode":"REPORT"}   analyst page (first tab) + _SPEC memory
// Phase 2 (2026-08-26) adds: the mapping cascade (core/mapping.ts) so a
// line is found by meaning and by its prior-year figure, not by an exact
// label; several sheets in one run (P&L + BS + CF); the boss-mandated
// RESTATEMENT FULL STOP; and refusal messages that never quote the
// model's own numbers back to the Agent.
// The pure-law section below (axis + ties) is generated from
// studio-native/core/*.ts — edit THOSE files, run build.sh,
// never edit the laws inside this file.
// ============================================================

// __CORE_LAWS__ (build.sh splices core/axis.ts + core/ties.ts here)

// ---------- shared helpers (ExcelScript side) ----------------

interface Params {
  mode: string;
  sheet?: string;
  sheets?: string[];
  periodKind?: string;
  targetYear?: number;
  rows?: (string | number | null)[][];
  acknowledgeRestatement?: boolean;
}

interface CheckVerdict { sheet: string; row: number; label: string;
  value: number; pass: boolean; }

// One sheet's slice of _ANATOMY: the labelled rows with the prior values
// the referee triangulates against, plus that sheet's column recipe.
interface AnatomyView {
  rows: AnatomyRow[];
  priorCol: string; targetCol: string;
  axisRow: number; axisHeader: string; nextCol: string;
  // the model's OWN forecast for the period we are about to overwrite,
  // and for the year after it — captured at PREFLIGHT because after
  // APPLY it no longer exists anywhere. This is what makes the _REPORT's
  // "actual vs the estimate you had" possible.
  beforeT: { [k: string]: number };
  beforeN: { [k: string]: number };
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

// _ANATOMY layout: [sheet, row, label, priorValue, priorCol, targetCol].
// One row per labelled model row, plus ONE meta row per sheet keyed
// '__meta__:<sheet>' carrying the axis header cell (Phase 2: per sheet,
// because a run now covers P&L + BS + CF at once).
function metaKey(sheet: string): string { return "__meta__:" + sheet; }

function readAnatomy(wb: ExcelScript.Workbook,
                     sheetName: string): AnatomyView | null {
  const anWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_ANATOMY");
  if (!anWs) return null;
  const an: CellValue[][] = sheetGrid(anWs);
  const view: AnatomyView = { rows: [], priorCol: "", targetCol: "",
    axisRow: -1, axisHeader: "", nextCol: "", beforeT: {}, beforeN: {} };
  const mk: string = metaKey(sheetName);
  for (let i: number = 1; i < an.length; i++) {
    const sh: string = String(an[i][0]);
    if (sh === mk) {
      view.axisRow = Number(an[i][1]);
      view.axisHeader = String(an[i][2]);
      view.priorCol = String(an[i][4]);
      view.targetCol = String(an[i][5]);
      view.nextCol = String(an[i][6] === undefined ? "" : an[i][6]);
      continue;
    }
    if (sh !== sheetName) continue;
    const pv: CellValue = an[i][3];
    if (typeof pv !== "number") continue;
    const rowNo: string = String(Number(an[i][1]));
    if (typeof an[i][6] === "number") view.beforeT[rowNo] = an[i][6] as number;
    if (typeof an[i][7] === "number") view.beforeN[rowNo] = an[i][7] as number;
    view.rows.push({ sheet: sh, row: Number(an[i][1]),
      label: String(an[i][2]), prior: pv });
    if (!view.priorCol) {
      view.priorCol = String(an[i][4]); view.targetCol = String(an[i][5]);
    }
  }
  return view.priorCol ? view : null;
}

// Every model sheet the current _ANATOMY covers, in the order preflighted.
function anatomySheets(wb: ExcelScript.Workbook): string[] {
  const anWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_ANATOMY");
  if (!anWs) return [];
  const an: CellValue[][] = sheetGrid(anWs);
  const seen: { [k: string]: boolean } = {};
  const out: string[] = [];
  for (let i: number = 1; i < an.length; i++) {
    const sh: string = String(an[i][0]);
    if (sh.indexOf("__meta__:") !== 0) continue;
    const name: string = sh.substring(9);
    if (seen[name]) continue;
    seen[name] = true; out.push(name);
  }
  return out;
}

// ---------- _SPEC: what this model taught us last time --------
// Per-company memory, text only, one fact per line, living in the
// workbook so it travels with the file (CLAUDE.md: no central store).
// The line that earns its keep is the ALIAS: a mapping an earlier run
// had to REASON out, written disclosure-label -> MODEL LABEL. Never a
// row number — the analyst inserts rows, and a remembered row number
// would then point at the wrong line while a label still finds it.
function specLines(wb: ExcelScript.Workbook): string[] {
  const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet("_SPEC");
  if (!ws) return [];
  const g: CellValue[][] = sheetGrid(ws);
  const out: string[] = [];
  for (let i: number = 0; i < g.length; i++) {
    const v: string = String(g[i][0] === undefined ? "" : g[i][0]).trim();
    if (v) out.push(v);
  }
  return out;
}

function readAliases(wb: ExcelScript.Workbook,
                     sheetName: string): { [k: string]: string } {
  const lines: string[] = specLines(wb);
  const out: { [k: string]: string } = {};
  for (let i: number = 0; i < lines.length; i++) {
    const parts: string[] = lines[i].split("|");
    if (parts.length < 4) continue;
    if (parts[0].trim() !== "ALIAS") continue;
    if (parts[2].trim() !== sheetName) continue;
    out[normLabel(parts[1].trim())] = parts[3].trim();
  }
  return out;
}

const SPEC_MAX: number = 500;            // text-only; never let it bloat

function writeSpec(wb: ExcelScript.Workbook, add: string[]): number {
  const have: string[] = specLines(wb);
  const seen: { [k: string]: boolean } = {};
  const merged: string[] = [];
  const push = (line: string): void => {
    const parts: string[] = line.split("|");
    const key: string = parts.length >= 3
      ? (parts[0].trim() + "|" + parts[1].trim() + "|" + parts[2].trim())
      : line;
    if (seen[key]) return;
    seen[key] = true; merged.push(line);
  };
  for (let i: number = 0; i < add.length; i++) push(add[i]);   // newest wins
  for (let i: number = 0; i < have.length; i++) push(have[i]);
  const keep: string[] = merged.slice(0, SPEC_MAX);
  const ws: ExcelScript.Worksheet = getOrCreate(wb, "_SPEC");
  const ur: ExcelScript.Range | undefined = ws.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  const rows: string[][] = [];
  for (let i: number = 0; i < keep.length; i++) rows.push([keep[i]]);
  if (rows.length > 0) ws.getRangeByIndexes(0, 0, rows.length, 1).setValues(rows);
  return keep.length;
}

// ---------- SEED ---------------------------------------------
// Build the Phase 1 practice model from data baked into the script —
// company walls allow code text in but not files, so the workbook
// travels AS the code. Run the kernel with EMPTY input on a blank
// workbook and the practice sheet appears: DFE's real FY22-24 actuals,
// announcement-exact Chinese labels, and the model's own check row.
const SEED_ROWS: (string | number)[][] = [["报告期","FY2022","FY2023","FY2024","FY2025"],["","","","",""],["P&L (Rmb m)","","","",""],["    营业总收入",55353.14,60676.61,69695.14,""],["    营业收入",54179.06,59566.53,68592.74,""],["        其他类金融业务收入",1174.08,1110.09,1102.4,""],["营业总成本",52452.27,57338.36,66679.76,""],["        营业成本",45244.94,49253.17,58876.11,""],["    税金及附加",325.82,303.47,378.53,""],["    销售费用",1483.43,1587.51,822.36,""],["    管理费用",3116.97,3403.9,3523.05,""],["    研发费用",2274.63,2749.53,3009.01,""],["    财务费用",-97.81,7.45,44.55,""],["        其中：利息费用",79.42,64.44,82.97,""],["                    减：利息收入",42.43,120.75,132.71,""],["        其他业务成本(金融类)",104.28,33.33,26.15,""],["    加：其他收益",150.75,438.8,769.92,""],["    投资净收益",480.56,748.15,1577.06,""],["        其中：对联营企业和合营企业的投资收益",301.77,320.69,186.94,""],["    公允价值变动净收益",-61.54,85.06,-204.16,""],["    资产减值损失",-480.48,-495.92,-1148.01,""],["    信用减值损失",277.44,-175.68,-146.04,""],["    资产处置收益",50.19,9.77,16.45,""],["    汇兑净收益",3.07,28.24,6.84,""],["营业利润",3320.87,3976.68,3887.45,""],["","","","",""],["Balance sheet","","","",""],["资产总计",115265.06,121108.37,142009.28,""],["    负债合计",76640.19,79888.5,98867.04,""],["    所有者权益合计",38624.87,41219.87,43142.25,""],["Check 平衡校验","=B28-B29-B30","=C28-C29-C30","=D28-D29-D30","=E28-E29-E30"]];

function modeSeed(wb: ExcelScript.Workbook): string {
  // GUARD (added after the owner nearly ran SEED inside the real
  // Dongfang model, 2026-08-26): seeding may only touch a BLANK
  // workbook or re-seed a workbook that is already the practice file
  // (recognised by its marker cell). A real model can never be hit.
  const existing: ExcelScript.Worksheet | undefined = wb.getWorksheet("Model");
  let isPractice: boolean = false;
  if (existing) {
    const a1: CellValue =
      existing.getRange("A1").getValues()[0][0] as CellValue;
    isPractice = String(a1) === "报告期";
  }
  if (!isPractice) {
    const all: ExcelScript.Worksheet[] = wb.getWorksheets();
    for (let i: number = 0; i < all.length; i++) {
      if (all[i].getName().charAt(0) === "_") continue;  // kernel's own tabs
      if (all[i].getUsedRange()) {
        return JSON.stringify({ ok: false,
          why: "SEED refused: this workbook is not blank. Open a NEW " +
               "blank workbook for practice — never a real model." });
      }
    }
  }
  let ws: ExcelScript.Worksheet | undefined = existing;
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
// Phase 2: takes ONE sheet or MANY ({"sheets":["Model","BS","CF"]}) and
// APPENDS to _ANATOMY — preflighting the balance sheet must not erase what
// was learned about the P&L. Only the sheets in this call are rebuilt.
function preflightSheet(wb: ExcelScript.Workbook, sheetName: string,
                        periodKind: string, ty: number,
                        out: (string | number)[][]): string {
  const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(sheetName);
  if (!ws) return "no sheet " + sheetName;
  const grid: CellValue[][] = sheetGrid(ws);
  const axis: AxisMap | null = findYearAxis(grid, periodKind);
  if (!axis) return "no year axis found on " + sheetName;
  const tCol: number | undefined = axis[String(ty)];
  const pCol: number | undefined = axis[String(ty - 1)];
  if (tCol === undefined || pCol === undefined)
    return "axis on " + sheetName + " lacks " + ty + " or prior; axis=" +
      JSON.stringify(axis);
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
  const nCol: number | undefined = axis[String(ty + 1)];
  out.push([metaKey(sheetName), axisRow, String(headerVal), 0,
    n2col(pCol), n2col(tCol), (nCol === undefined) ? "" : n2col(nCol), ""]);
  // the analyst's own forecast for the year we are about to overwrite,
  // and the year after — snapshot NOW or it is lost forever (_REPORT's
  // "what you projected vs what came in" depends on it)
  for (let r: number = 0; r < grid.length; r++) {
    const lab: string = labelOf(grid, r);
    if (!lab) continue;
    const pv: CellValue = grid[r][pCol];
    if (typeof pv !== "number") continue;
    const bt: CellValue = grid[r][tCol];
    const bn: CellValue = (nCol === undefined) ? "" : grid[r][nCol];
    out.push([sheetName, r + 1, lab, pv, n2col(pCol), n2col(tCol),
      (typeof bt === "number") ? bt : "", (typeof bn === "number") ? bn : ""]);
  }
  return "";
}

function modePreflight(wb: ExcelScript.Workbook, p: Params): string {
  const names: string[] = (p.sheets && p.sheets.length > 0)
    ? p.sheets : [String(p.sheet)];
  const ty: number = Number(p.targetYear);
  const kind: string = String(p.periodKind || "FY");
  const an: ExcelScript.Worksheet = getOrCreate(wb, "_ANATOMY");
  // keep what other sheets already taught us; rebuild only these sheets
  const old: CellValue[][] = sheetGrid(an);
  const keep: (string | number)[][] = [];
  for (let i: number = 1; i < old.length; i++) {
    const sh: string = String(old[i][0]);
    let inScope: boolean = false;
    for (let j: number = 0; j < names.length; j++)
      if (sh === names[j] || sh === metaKey(names[j])) inScope = true;
    if (inScope) continue;
    keep.push([sh, Number(old[i][1]), String(old[i][2]),
      (typeof old[i][3] === "number") ? (old[i][3] as number) : 0,
      String(old[i][4]), String(old[i][5]),
      (typeof old[i][6] === "number") ? (old[i][6] as number) : "",
      (typeof old[i][7] === "number") ? (old[i][7] as number) : ""]);
  }
  const fresh: (string | number)[][] = [];
  const problems: { sheet: string; why: string }[] = [];
  const done: { sheet: string; priorCol: string; targetCol: string;
    rows: number }[] = [];
  for (let i: number = 0; i < names.length; i++) {
    const before: number = fresh.length;
    const err: string = preflightSheet(wb, names[i], kind, ty, fresh);
    if (err) { problems.push({ sheet: names[i], why: err }); continue; }
    const meta: (string | number)[] = fresh[before];
    done.push({ sheet: names[i], priorCol: String(meta[4]),
      targetCol: String(meta[5]), rows: fresh.length - before - 1 });
  }
  const rows: (string | number)[][] = keep.concat(fresh);
  const ur: ExcelScript.Range | undefined = an.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  an.getRange("A1:H1").setValues([[
    "sheet", "row", "label", "priorValue", "priorCol", "targetCol",
    "targetBefore", "nextBefore"]]);
  if (rows.length > 0)
    an.getRangeByIndexes(1, 0, rows.length, 8).setValues(rows);
  let labelled: number = 0;
  for (let i: number = 0; i < done.length; i++) labelled += done[i].rows;
  const res: { [k: string]: CellValue | object } = {
    ok: problems.length === 0, sheets: done, anatomyRows: labelled
  };
  if (done.length > 0) {                    // single-sheet convenience
    res["priorCol"] = done[0].priorCol; res["targetCol"] = done[0].targetCol;
  }
  if (problems.length > 0) {
    res["why"] = problems[0].why; res["problems"] = problems;
  }
  return JSON.stringify(res);
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
  st.getRange("A1:H1").setValues([[
    "label", "value", "priorDisclosed", "sourcePage", "flag", "note",
    "sheet", "row"]]);
  const rows: (string | number | null)[][] = p.rows ? p.rows : [];
  const norm: (string | number)[][] = [];
  const txt = (v: string | number | null | undefined): string =>
    String(v === null || v === undefined ? "" : v);
  for (let i: number = 0; i < rows.length; i++) {
    const r: (string | number | null)[] = rows[i];
    const val: string | number = (typeof r[1] === "number") ? r[1] : "";
    const pri: string | number = (typeof r[2] === "number") ? r[2] : "";
    // cols 7-8 are Phase 2 and optional: an explicit sheet, and a row
    // number when the Agent wants to name the row itself (still refereed)
    const hintRow: number = (typeof r[7] === "number") ? r[7] : 0;
    norm.push([txt(r[0]), val, pri, txt(r[3]), txt(r[4]), txt(r[5]),
      txt(r[6]), hintRow]);
  }
  if (norm.length > 0)
    st.getRangeByIndexes(1, 0, norm.length, 8).setValues(norm);
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
  const stWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_STAGING");
  const view: AnatomyView | null = readAnatomy(wb, sheetName);
  if (!view || !stWs)
    return JSON.stringify({ ok: false, why: "run PREFLIGHT first / no _STAGING" });
  // BOSS LAW (restatement = the past changed): once the comparatives scan
  // says the prior year was restated, NOTHING is written until the analyst
  // rules. The Agent cannot wave this through on its own — it must come
  // back with acknowledgeRestatement after a human answers.
  const rsWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_RESTATE");
  if (rsWs) {
    const banner: CellValue = rsWs.getRange("A1").getValues()[0][0] as CellValue;
    if (/SUSPECT/i.test(String(banner)) && p.acknowledgeRestatement !== true)
      return JSON.stringify({ ok: false, stop: true,
        why: "restatement suspected — nothing written. The analyst must " +
             "rule first (open the _RESTATE tab, and ask them for the " +
             "prior-year report). Re-run APPLY with " +
             "\"acknowledgeRestatement\":true only after they answer." });
  }
  const st: CellValue[][] = sheetGrid(stWs);
  const priors: { [k: string]: number } = {};
  for (let i: number = 0; i < view.rows.length; i++)
    priors[sheetName + "!" + view.rows[i].row] = view.rows[i].prior;
  const priorCol: string = view.priorCol;
  const targetCol: string = view.targetCol;
  const axisRow: number = view.axisRow;
  const axisHeader: string = view.axisHeader;
  // staging: label|value|priorDisclosed|page|flag|note|sheet|row
  // Rows naming another sheet are left for that sheet's APPLY.
  const reqs: MapReq[] = [];
  const staged: number[] = [];
  for (let i: number = 1; i < st.length; i++) {
    const lab: string = String(st[i][0] === undefined ? "" : st[i][0]).trim();
    if (!lab) continue;
    const hintSheet: string = String(st[i][6] === undefined ? "" : st[i][6]).trim();
    if (hintSheet && hintSheet !== sheetName) continue;
    reqs.push({ label: lab,
      prior: (typeof st[i][2] === "number") ? (st[i][2] as number) : null,
      rowHint: (typeof st[i][7] === "number") ? (st[i][7] as number) : 0 });
    staged.push(i);
  }
  // THE CASCADE: exact -> remembered alias -> normalised -> prior-value
  // triangulation -> the Agent's own hint
  const hits: MapHit[] = mapAll(reqs, view.rows, readAliases(wb, sheetName));
  const entries: PlanEntry[] = [];
  const unmapped: { label: string; why: string }[] = [];
  const via: { [k: string]: number } = {};
  const viaByRow: { [k: string]: string } = {};
  for (let k: number = 0; k < reqs.length; k++) {
    const i: number = staged[k];
    if (hits[k].row <= 0) {
      unmapped.push({ label: reqs[k].label, why: hits[k].why });
      continue;
    }
    via[hits[k].via] = (via[hits[k].via] === undefined ? 0 : via[hits[k].via]) + 1;
    viaByRow[String(hits[k].row)] = hits[k].via;
    const rawV: CellValue = st[i][1];
    const rawP: CellValue = st[i][2];
    entries.push({
      sheet: sheetName, row: hits[k].row,
      value: (typeof rawV === "number") ? rawV : null,
      priorDisclosed: (typeof rawP === "number") ? rawP : null,
      flag: String(st[i][4] === undefined ? "" : st[i][4]),
      note: String(st[i][5] === undefined ? "" : st[i][5]),
      label: reqs[k].label,
      page: String(st[i][3] === undefined ? "" : st[i][3])
    });
  }
  const verdict: PlanVerdict = validateWritePlan(entries, priors);
  // ---- write _PLAN (the transactional boundary: plan ≠ apply) ----
  const plWs: ExcelScript.Worksheet = getOrCreate(wb, "_PLAN");
  const pur: ExcelScript.Range | undefined = plWs.getUsedRange();
  if (pur) pur.clear(ExcelScript.ClearApplyTo.all);
  const planRows: (string | number)[][] = [[
    "sheet", "row", "label", "value", "verdict", "why", "page", "mappedVia",
    "flag"]];
  for (let i: number = 0; i < verdict.accepted.length; i++) {
    const e: PlanEntry = verdict.accepted[i];
    planRows.push([e.sheet, e.row, e.label ? e.label : "",
      (typeof e.value === "number") ? e.value : "",
      "ACCEPT", e.note ? e.note : "", e.page ? e.page : "",
      viaByRow[String(e.row)], e.flag]);
  }
  for (let i: number = 0; i < verdict.refused.length; i++) {
    const r: Refusal = verdict.refused[i];
    // _PLAN carries the FULL reason (the analyst reads it here); the
    // Agent only ever sees the sanitized `brief`.
    planRows.push([r.entry.sheet, r.entry.row,
      r.entry.label ? r.entry.label : "",
      (typeof r.entry.value === "number") ? r.entry.value : "",
      "REFUSE", r.why, r.entry.page ? r.entry.page : "",
      viaByRow[String(r.entry.row)], r.entry.flag]);
  }
  plWs.getRangeByIndexes(0, 0, planRows.length, 9).setValues(planRows);
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
  if (p.acknowledgeRestatement === true)
    led.push([utc, "APPLY", sheetName, "", "", "", "",
      "analyst acknowledged the restatement scan before this write"]);
  if (led.length > 0) ledgerAppend(wb, led);
  // What the Agent is told: sanitized. Refusals name the row and the
  // disclosure label it staged, never the model's stored figure.
  const refusals: { row: number; label: string; why: string }[] = [];
  for (let i: number = 0; i < verdict.refused.length; i++) {
    const r: Refusal = verdict.refused[i];
    refusals.push({ row: r.entry.row, label: r.entry.label ? r.entry.label : "",
      why: r.brief });
  }
  const shown: { label: string; why: string }[] = unmapped.slice(0, 25);
  return JSON.stringify({
    ok: true, written: verdict.accepted.length,
    refused: verdict.refused.length,
    unmappedCount: unmapped.length, unmapped: shown,
    mappedVia: via, refusals: refusals
  });
}

// ---------- RESTATE ------------------------------------------
// BOSS LAW (mindmap section B): when the disclosure's comparatives no
// longer agree with the model's history, the PAST changed — the agent
// STOPS COMPLETELY and asks the analyst (for the prior-year report, and
// for permission to restate, with the warning that restating financials
// can break reconciliation with unrestated operational data).
// This mode is the detector. It maps the staged lines with the same
// cascade APPLY uses, compares every prior-year comparative against what
// the model holds, and writes the evidence to a VISIBLE _RESTATE tab for
// the analyst. The Agent is told only WHICH lines differ, never by how
// much — the numbers are the analyst's to read, and telling the Agent
// would hand it the answer key.
function modeRestate(wb: ExcelScript.Workbook, p: Params): string {
  const names: string[] = p.sheet ? [String(p.sheet)] : anatomySheets(wb);
  const stWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_STAGING");
  if (names.length === 0 || !stWs)
    return JSON.stringify({ ok: false, why: "run PREFLIGHT and STAGE first" });
  const st: CellValue[][] = sheetGrid(stWs);
  const detail: (string | number)[][] = [];
  const labels: string[] = [];
  let compared: number = 0;
  let noComparative: number = 0;
  for (let s: number = 0; s < names.length; s++) {
    const sheetName: string = names[s];
    const view: AnatomyView | null = readAnatomy(wb, sheetName);
    if (!view) continue;
    const reqs: MapReq[] = [];
    for (let i: number = 1; i < st.length; i++) {
      const lab: string = String(st[i][0] === undefined ? "" : st[i][0]).trim();
      if (!lab) continue;
      const hintSheet: string =
        String(st[i][6] === undefined ? "" : st[i][6]).trim();
      if (hintSheet && hintSheet !== sheetName) continue;
      reqs.push({ label: lab,
        prior: (typeof st[i][2] === "number") ? (st[i][2] as number) : null,
        rowHint: (typeof st[i][7] === "number") ? (st[i][7] as number) : 0 });
    }
    const hits: MapHit[] = mapAll(reqs, view.rows,
      readAliases(wb, sheetName));
    for (let k: number = 0; k < reqs.length; k++) {
      if (hits[k].row <= 0) continue;
      const dp: number | string | null = reqs[k].prior;
      if (typeof dp !== "number") { noComparative++; continue; }
      let held: number | null = null;
      for (let j: number = 0; j < view.rows.length; j++)
        if (view.rows[j].row === hits[k].row) held = view.rows[j].prior;
      if (held === null) continue;
      compared++;
      if (tieOk(held, dp)) continue;
      labels.push(reqs[k].label);
      const diff: number = dp - held;
      detail.push([sheetName, hits[k].row, reqs[k].label, held, dp, diff,
        held === 0 ? "" : Math.round(diff / Math.abs(held) * 1000) / 10]);
    }
  }
  const many: boolean = detail.length >= 3 ||
    (compared > 0 && detail.length >= 2 && detail.length / compared >= 0.25);
  let banner: string = "Comparatives scan: clean — every prior-year " +
    "comparative ties to the model.";
  if (detail.length > 0 && !many)
    banner = "Comparatives scan: isolated mismatches — most likely misreads " +
      "on those lines, not a restatement. Check the rows below.";
  if (many)
    banner = "RESTATEMENT SUSPECTED — analyst ruling required before any " +
      "write. Ask the analyst for the prior-year report, and whether to " +
      "restate the model's history. WARNING: restating financials can break " +
      "reconciliation with operational data that was not restated.";
  const rs: ExcelScript.Worksheet = getOrCreate(wb, "_RESTATE");
  rs.setVisibility(ExcelScript.SheetVisibility.visible);   // the analyst reads this
  const ur: ExcelScript.Range | undefined = rs.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  rs.getRange("A1").setValue(banner);
  rs.getRange("A2:G2").setValues([["sheet", "row", "line",
    "model holds", "disclosure comparative", "difference", "% of model"]]);
  if (detail.length > 0)
    rs.getRangeByIndexes(2, 0, detail.length, 7).setValues(detail);
  return JSON.stringify({
    ok: true, stop: many, verdict: many ? "RESTATEMENT SUSPECTED"
      : (detail.length > 0 ? "isolated mismatches" : "clean"),
    compared: compared, mismatches: detail.length,
    noComparative: noComparative, lines: labels.slice(0, 15),
    next: many ? "STOP. Do not APPLY. Tell the analyst what the _RESTATE " +
      "tab shows and ask them to rule."
      : "proceed to APPLY"
  });
}

// ---------- POLICE -------------------------------------------
// Force a full recalc, then read every model-native check row (rows
// whose label matches the check pattern) — in the target column AND in
// the prior actual column, across every preflighted sheet. Any non-zero
// check = the model does not balance = the run FAILED. Checking the prior
// column too is deliberate: the boss map asks for ALL years balanced, and
// an inherited break must surface as the analyst's, not as ours.
function modePolice(wb: ExcelScript.Workbook, p: Params): string {
  wb.getApplication().calculate(ExcelScript.CalculationType.full);
  const names: string[] = p.sheet ? [String(p.sheet)] : anatomySheets(wb);
  if (names.length === 0)
    return JSON.stringify({ ok: false, why: "run PREFLIGHT first" });
  // same pattern as updater/discover.py _CHECK_LABEL — deliberately NOT
  // matching bare 'balance'/'tie' ('liabiliTIEs', 'Balance sheet' rows)
  const CHECK: RegExp = /check|差额|平衡|balance test|检验|校验/i;
  const verdicts: CheckVerdict[] = [];
  const failed: CheckVerdict[] = [];
  for (let s: number = 0; s < names.length; s++) {
    const sheetName: string = names[s];
    const view: AnatomyView | null = readAnatomy(wb, sheetName);
    const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(sheetName);
    if (!view || !ws) continue;
    const grid: CellValue[][] = sheetGrid(ws);
    const cols: string[] = [view.targetCol, view.priorCol];
    for (let i: number = 0; i < view.rows.length; i++) {
      const lab: string = view.rows[i].label;
      if (!CHECK.test(lab)) continue;
      for (let c: number = 0; c < cols.length; c++) {
        const colIdx: number = ws.getRange(cols[c] + "1").getColumnIndex();
        const row: number = view.rows[i].row;
        const v: CellValue | null = grid[row - 1] ? grid[row - 1][colIdx] : null;
        if (typeof v !== "number") continue;
        const cv: CheckVerdict = { sheet: sheetName + "!" + cols[c] + row,
          row: row, label: lab, value: v, pass: Math.abs(v) <= 0.02 };
        verdicts.push(cv);
        if (!cv.pass) failed.push(cv);
      }
    }
  }
  // GENERICITY GUARD: not every analyst's model carries a labelled check
  // row. Zero checks is NOT a pass — it means we verified nothing, and
  // silence would read as "balanced" to the agent and the analyst alike.
  if (verdicts.length === 0)
    return JSON.stringify({ ok: false, checks: 0, failed: [],
      why: "no balance-check row found on " + names.join(", ") +
           " — this model does not carry one, so the balance could NOT be " +
           "verified. Tell the analyst: check the balance sheet by hand, " +
           "or add a check row to the model." });
  return JSON.stringify({
    ok: failed.length === 0, checks: verdicts.length, failed: failed
  });
}

// ---------- REPORT -------------------------------------------
// The analyst's page. A VISIBLE first sheet so the workbook opens on it,
// every listed cell a clickable link sitting next to its LIVE value
// (CLAUDE.md's four sections). Then _SPEC is updated with the mappings
// this run had to reason out, so the next run inherits them.
interface ReportRow { addr: string; sheet: string;
  a: string; c: string; d: string; e: string; k: number; }

function quoteSheet(name: string): string {
  return /^[A-Za-z0-9_]+$/.test(name) ? name
    : "'" + name.split("'").join("''") + "'";
}

function pct(from: number, to: number): string {
  if (Math.abs(from) < 1e-9) return "n/a";
  const p: number = (to - from) / Math.abs(from) * 100;
  return (p >= 0 ? "+" : "") + String(Math.round(p * 10) / 10) + "%";
}

function modeReport(wb: ExcelScript.Workbook, p: Params): string {
  const names: string[] = p.sheet ? [String(p.sheet)] : anatomySheets(wb);
  if (names.length === 0)
    return JSON.stringify({ ok: false, why: "run PREFLIGHT first" });
  const plWs: ExcelScript.Worksheet | undefined = wb.getWorksheet("_PLAN");
  const pl: CellValue[][] = plWs ? sheetGrid(plWs) : [];
  const red: ReportRow[] = [];
  const orange: ReportRow[] = [];
  const core: ReportRow[] = [];
  const moves: ReportRow[] = [];
  const aliasLines: string[] = [];
  const utc: string = new Date().toISOString().substring(0, 10);
  let period: string = "";
  let written: number = 0;
  let refused: number = 0;
  for (let s: number = 0; s < names.length; s++) {
    const sheetName: string = names[s];
    const view: AnatomyView | null = readAnatomy(wb, sheetName);
    const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(sheetName);
    if (!view || !ws) continue;
    const grid: CellValue[][] = sheetGrid(ws);
    if (!period) period = view.axisHeader;
    const tIdx: number = ws.getRange(view.targetCol + "1").getColumnIndex();
    const nIdx: number = view.nextCol
      ? ws.getRange(view.nextCol + "1").getColumnIndex() : -1;
    const labelByRow: { [k: string]: string } = {};
    for (let i: number = 0; i < view.rows.length; i++)
      labelByRow[String(view.rows[i].row)] = view.rows[i].label;
    const liveAt = (row: number, col: number): number | null => {
      const v: CellValue | null = (col >= 0 && grid[row - 1])
        ? grid[row - 1][col] : null;
      return (typeof v === "number") ? v : null;
    };
    // sections 1, 2 and 4 read the verdicts this run recorded
    for (let i: number = 1; i < pl.length; i++) {
      if (String(pl[i][0]) !== sheetName) continue;
      const row: number = Number(pl[i][1]);
      const staged: string = String(pl[i][2]);
      const verdict: string = String(pl[i][4]);
      const why: string = String(pl[i][5]);
      const via: string = String(pl[i][7] === undefined ? "" : pl[i][7]);
      const flag: string = String(pl[i][8] === undefined ? "" : pl[i][8]);
      const addr: string = view.targetCol + row;
      const modelLabel: string = labelByRow[String(row)]
        ? labelByRow[String(row)] : staged;
      const asRead: string = (normLabel(staged) === normLabel(modelLabel))
        ? "" : "read in the disclosure as: " + staged;
      if (verdict === "REFUSE") {
        refused++;
        red.push({ addr: addr, sheet: sheetName, a: "", c: modelLabel,
          d: "REFUSED — not written: " + why, e: asRead, k: 0 });
        continue;
      }
      written++;
      if (flag === "red")
        red.push({ addr: addr, sheet: sheetName, a: "", c: modelLabel,
          d: "flagged uncertain: " + why, e: asRead, k: 0 });
      if (flag === "orange")
        orange.push({ addr: addr, sheet: sheetName, a: "", c: modelLabel,
          d: "derived — true up from the detailed report: " + why,
          e: asRead, k: 0 });
      // mappings that needed reasoning become _SPEC memory
      if (via && via !== "exact" && via !== "alias" &&
          normLabel(staged) !== normLabel(modelLabel))
        aliasLines.push("ALIAS | " + staged + " | " + sheetName + " | " +
          modelLabel + " | matched by " + via + " on " + utc);
      const est: number | undefined = view.beforeT[String(row)];
      const act: number | null = liveAt(row, tIdx);
      if (typeof est === "number" && act !== null) {
        const oldN: number | undefined = view.beforeN[String(row)];
        const newN: number | null = liveAt(row, nIdx);
        core.push({ addr: addr, sheet: sheetName, a: "", c: modelLabel,
          d: "you forecast " + est + " · actual " + act + " (" +
             pct(est, act) + ")",
          e: (typeof oldN === "number" && newN !== null)
            ? ("next year: " + oldN + " -> " + newN + " (" + pct(oldN, newN) + ")")
            : "", k: Math.abs(act) });
      }
    }
    // section 3: QC scan — a >50% swing is often a mapping error
    for (let i: number = 0; i < view.rows.length; i++) {
      const prior: number = view.rows[i].prior;
      const now: number | null = liveAt(view.rows[i].row, tIdx);
      if (now === null || Math.abs(prior) < 1) continue;
      const move: number = Math.abs((now - prior) / prior);
      if (move <= 0.5) continue;
      moves.push({ addr: view.targetCol + view.rows[i].row, sheet: sheetName,
        a: "", c: view.rows[i].label,
        d: "moved " + pct(prior, now) + " (was " + prior + ", now " + now + ")",
        e: "", k: move });
    }
  }
  moves.sort((x: ReportRow, y: ReportRow): number => y.k - x.k);
  const movesShown: ReportRow[] = moves.slice(0, 15);
  // headline lines = the biggest lines. Ranking by size surfaces revenue,
  // profit and the balance-sheet totals without knowing their names — the
  // same instinct as the cascade: judge by magnitude, not by label.
  core.sort((x: ReportRow, y: ReportRow): number => y.k - x.k);
  const coreShown: ReportRow[] = core.slice(0, 8);
  // ---- lay the page out ----
  const po: { ok: boolean; checks: number } =
    JSON.parse(modePolice(wb, { mode: "POLICE" })) as
      { ok: boolean; checks: number };
  const head = (t: string): ReportRow =>
    ({ addr: "", sheet: "", a: t, c: "", d: "", e: "", k: 0 });
  const lines: ReportRow[] = [];
  lines.push(head("MODEL UPDATE REPORT — " + names.join(", ")));
  lines.push(head(written + " lines written · " + refused + " refused · " +
    red.length + " red · " + orange.length + " orange · balance checks: " +
    (po.checks === 0 ? "NONE FOUND" : (po.ok ? "PASS" : "FAIL"))));
  lines.push(head(""));
  lines.push(head("1. RED — uncertain, needs your ruling (" +
    red.length + ")"));
  for (let i: number = 0; i < red.length; i++) lines.push(red[i]);
  lines.push(head(""));
  lines.push(head("2. ORANGE — derived, awaiting true-up (" +
    orange.length + ")"));
  for (let i: number = 0; i < orange.length; i++) lines.push(orange[i]);
  lines.push(head(""));
  lines.push(head("3. BIG MOVES >50% year on year — check for mapping errors" +
    (moves.length > movesShown.length
      ? " (showing 15 of " + moves.length + ")" : "")));
  for (let i: number = 0; i < movesShown.length; i++) lines.push(movesShown[i]);
  lines.push(head(""));
  lines.push(head("4. YOUR FORECAST vs THE ACTUAL" +
    (period ? " — " + period : "") + " (biggest lines first)"));
  for (let i: number = 0; i < coreShown.length; i++) lines.push(coreShown[i]);
  const rpt: ExcelScript.Worksheet = getOrCreate(wb, "_REPORT");
  rpt.setVisibility(ExcelScript.SheetVisibility.visible);
  rpt.setPosition(0);                      // the workbook opens on it
  const ur: ExcelScript.Range | undefined = rpt.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  const vals: (string | number)[][] = [];
  for (let i: number = 0; i < lines.length; i++)
    vals.push([lines[i].a, "", lines[i].c, lines[i].d, lines[i].e]);
  if (vals.length > 0)
    rpt.getRangeByIndexes(0, 0, vals.length, 5).setValues(vals);
  for (let i: number = 0; i < lines.length; i++) {
    if (!lines[i].addr) continue;
    const ref: string = quoteSheet(lines[i].sheet) + "!" + lines[i].addr;
    rpt.getRangeByIndexes(i, 0, 1, 1).setHyperlink({
      documentReference: ref,
      textToDisplay: lines[i].sheet + "!" + lines[i].addr });
    rpt.getRangeByIndexes(i, 1, 1, 1).setFormula("=" + ref);
  }
  const specCount: number = writeSpec(wb, aliasLines);
  return JSON.stringify({ ok: true, sheets: names, written: written,
    refused: refused, red: red.length, orange: orange.length,
    bigMoves: moves.length, coreLines: coreShown.length,
    balance: po.checks === 0 ? "NOT VERIFIED" : (po.ok ? "PASS" : "FAIL"),
    specLines: specCount, aliasesLearned: aliasLines.length,
    note: "_REPORT is now the first tab — the analyst reviews there" });
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
  let res: string = "";
  try {
    if (p.mode === "SEED") res = modeSeed(workbook);
    else if (p.mode === "PREFLIGHT") res = modePreflight(workbook, p);
    else if (p.mode === "STAGE") res = modeStage(workbook, p);
    else if (p.mode === "RESTATE") res = modeRestate(workbook, p);
    else if (p.mode === "APPLY") res = modeApply(workbook, p);
    else if (p.mode === "POLICE") res = modePolice(workbook, p);
    else if (p.mode === "REPORT") res = modeReport(workbook, p);
    else res = JSON.stringify({ ok: false, why: "unknown mode " + p.mode });
  } catch (err) {
    res = JSON.stringify({ ok: false, why: "kernel error: " + String(err) });
  }
  // Speak loudly (owner's tenant hides return values): log to the
  // editor's Output console AND echo into a visible _OUT tab, newest on
  // top, so the report is always one glance away inside the workbook.
  console.log(res);
  try {
    let outWs: ExcelScript.Worksheet | undefined = workbook.getWorksheet("_OUT");
    if (!outWs) {
      outWs = workbook.addWorksheet("_OUT");
      outWs.getRange("A1").setValue("kernel reports — newest first");
    }
    outWs.getRange("2:2").insert(ExcelScript.InsertShiftDirection.down);
    outWs.getRange("A2").setValue(new Date().toISOString() + "  " +
      p.mode + "  " + res);
  } catch (err2) { /* echo must never break the run */ }
  return res;
}
