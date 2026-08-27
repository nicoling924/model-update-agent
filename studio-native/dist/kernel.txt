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
//   EXTEND    {"mode":"EXTEND","sheet":"Raw","targetYear":2025,"analystApproved":true}
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

// CORE LAW: year-axis discovery — faithful port of updater/discover.py
// (_year_of + find_year_axis). Pure functions, no Excel API: the adapter
// feeds getValues() grids in, gets {year: columnIndex} out.
//
// Fully typed: Office Scripts' checker refuses implicit types (measured
// on the owner's tenant, 2026-08-26 — 123 inference complaints).
//
// ExcelScript difference vs openpyxl, handled here: dates arrive as Excel
// SERIAL NUMBERS (2025-06-30 ≈ 45838), not date objects. Serials in the
// plausible window are decoded to (year, month) before the annual/interim
// ruling. Everything else mirrors the Python law line-for-line, including
// the 1H-panel trap: an FY update must NEVER bind an interim column.

type CellValue = string | number | boolean;
type YearMark = [number | null, string | null];
type AxisMap = { [year: string]: number };
type Mark = [number, number, boolean];            // [colIdx, year, isInterim]

const YEAR_MIN: number = 1990;
const YEAR_MAX: number = 2100;
const SCAN_ROWS: number = 12;
const MIN_RUN: number = 3;
const INTERIM_TEXT: RegExp = /[1-4]Q|Q[1-4]|[12]H|H[12]|半年|中期|interim/i;

// Excel serial -> {y, m} (1900 date system, the Excel Online default).
function serialToYM(n: number): { y: number; m: number } {
  const days: number = Math.floor(n) - 25569; // serial 25569 = 1970-01-01
  const d: Date = new Date(days * 86400000);
  return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1 };
}

// (year, tag) for a cell's year mark; [null, null] when not a year mark.
// tag: null = annual column, '1H'/'2H'/'1Q'..'4Q' = interim column.
function yearOf(v: CellValue | null | undefined): YearMark {
  if (typeof v === "boolean") return [null, null];
  if (typeof v === "number") {
    const y: number = Math.round(v);
    if (y >= YEAR_MIN && y <= YEAR_MAX && Math.abs(v - y) < 0.5)
      return [y, null];
    // date serial window 1990-01-01 (32874) .. 2100 (73415)
    if (v >= 32874 && v <= 73415) {
      const ym: { y: number; m: number } = serialToYM(v);
      if (ym.y >= YEAR_MIN && ym.y <= YEAR_MAX)
        return [ym.y, (ym.m === 6 || ym.m === 9) ? "1H" : null];
    }
    return [null, null];
  }
  if (typeof v === "string") {
    const t: string = v.trim().toUpperCase();
    let m: RegExpMatchArray | null = t.match(/^H([12])(\d{2})E?$/); // H125
    if (m) return [2000 + parseInt(m[2], 10), m[1] + "H"];
    m = t.match(/^Q([1-4])(\d{2})E?$/);                 // Q106
    if (m) return [2000 + parseInt(m[2], 10), m[1] + "Q"];
    m = t.match(/^([12])H(19\d{2}|20\d{2})$/);          // 1H2025
    if (m) return [parseInt(m[2], 10), m[1] + "H"];
    m = t.match(/^(19\d{2}|20\d{2})H([12])$/);          // 2025H1
    if (m) return [parseInt(m[1], 10), m[2] + "H"];
    m = t.match(/^([1-4])Q(19\d{2}|20\d{2})$/);         // 3Q2025
    if (m) return [parseInt(m[2], 10), m[1] + "Q"];
    m = t.match(/^(19\d{2}|20\d{2})Q([1-4])$/);         // 2025Q3
    if (m) return [parseInt(m[1], 10), m[2] + "Q"];
    // two-digit fiscal-year conventions: FY22, FY24E, F25. Only with the
    // FY/F prefix — a bare '24' in a header is far too likely to be a
    // quantity. 00-79 reads as 2000s, 80-99 as 1900s.
    m = t.match(/^FY?([0-9]{2})[AEF]?$/);
    if (m) {
      const yy: number = parseInt(m[1], 10);
      return [yy <= 79 ? 2000 + yy : 1900 + yy, null];
    }
    m = t.match(/(19\d{2}|20\d{2})/);                   // '2025A', 'FY2025'
    if (m) {
      const interim: boolean = INTERIM_TEXT.test(v) ||
        /[-\/](?:06|6)[-\/]30|[-\/](?:09|9)[-\/]30/.test(v);
      return [parseInt(m[1], 10), interim ? "1H" : null];
    }
  }
  return [null, null];
}

// grid: rows of raw cell values (row 1 first). periodKind: 'FY','1H','3Q'...
// Returns {year(string): zero-based column index} for the winning panel,
// or null. Scoring mirrors Python: kind-match first, then run length,
// then topmost row.
function findYearAxis(grid: CellValue[][], periodKind: string): AxisMap | null {
  const pk: string = (periodKind || "FY").toUpperCase();
  let wantTag: string | null = pk === "FY" ? null : pk;
  if (wantTag === "H1" || wantTag === "H2") wantTag = wantTag.charAt(1) + "H";
  if (wantTag === "Q1" || wantTag === "Q2" || wantTag === "Q3" ||
      wantTag === "Q4") wantTag = wantTag.charAt(1) + "Q";
  const wantInterim: boolean = wantTag !== null;
  const minRun: number = wantInterim ? 2 : MIN_RUN;
  const cands: [number, number, number, Mark[]][] = [];
  const nRows: number = Math.min(grid.length, SCAN_ROWS);
  for (let r: number = 0; r < nRows; r++) {
    const marks: Mark[] = [];
    for (let c: number = 0; c < grid[r].length; c++) {
      const yt: YearMark = yearOf(grid[r][c]);
      if (yt[0] === null) continue;
      if (wantInterim) {
        if (yt[1] !== wantTag) continue;     // H1 runs see H1 columns only
        marks.push([c, yt[0], true]);
      } else {
        if (yt[1] !== null) continue;        // FY runs never see interim cols
        marks.push([c, yt[0], false]);
      }
    }
    if (marks.length < minRun) continue;
    // A panel is a run of consecutive years across neighbouring columns —
    // in EITHER direction. Most models put the newest year on the right,
    // but newest-first models exist and were invisible to this law until
    // 2026-08-27. A run must keep one direction throughout: 2022,2023,2024
    // or 2024,2023,2022, never a mixture.
    let run: Mark[] = [marks[0]];
    let dir: number = 0;
    const runs: Mark[][] = [];
    for (let i: number = 1; i < marks.length; i++) {
      const prev: Mark = marks[i - 1];
      const cur: Mark = marks[i];
      const step: number = cur[1] - prev[1];
      const ok: boolean = cur[0] > prev[0] &&
        (step === 1 || step === -1) && (dir === 0 || step === dir);
      if (ok) { run.push(cur); dir = step; }
      else {
        if (run.length >= minRun) runs.push(run);
        run = [cur]; dir = 0;
      }
    }
    if (run.length >= minRun) runs.push(run);
    for (let j: number = 0; j < runs.length; j++) {
      const rn: Mark[] = runs[j];
      let nInterim: number = 0;
      for (let k: number = 0; k < rn.length; k++) if (rn[k][2]) nInterim++;
      const kindMatch: boolean = (nInterim / rn.length >= 0.5) === wantInterim;
      cands.push([kindMatch ? 1 : 0, rn.length, -r, rn]);
    }
  }
  if (cands.length === 0) return null;
  // Office Scripts law (owner's tenant, 2026-08-26): array-method
  // callbacks MUST be arrow functions — function expressions are refused.
  cands.sort((a: [number, number, number, Mark[]],
              b: [number, number, number, Mark[]]): number =>
    b[0] - a[0] || b[1] - a[1] || b[2] - a[2]);
  const best: Mark[] = cands[0][3];
  const out: AxisMap = {};
  for (let b: number = 0; b < best.length; b++)
    out[String(best[b][1])] = best[b][0];
  return out;
}

// zero-based column index -> Excel letters (0 -> A, 26 -> AA).
function n2col(n: number): string {
  let s: string = "";
  let x: number = n + 1;
  while (x > 0) {
    const rem: number = (x - 1) % 26;
    s = String.fromCharCode(65 + rem) + s;
    x = Math.floor((x - 1) / 26);
  }
  return s;
}
// CORE LAW: tie acceptance — the referee that makes GPT-read numbers safe.
// A mapped figure is accepted because it RECONCILES, not because a label
// looked right. Ported from the acceptance laws in prompts/compile.md and
// updater/loop.py; this is the layer that catches OCR misreads and
// wrong-row mappings before they touch the model. Fully typed for the
// Office Scripts checker.

interface PlanEntry {
  sheet: string;
  row: number;
  value: number | string | null;    // what to write (numeric unless flagged)
  priorDisclosed: number | string | null;  // prior-year figure the Agent
                                    // read in the SAME disclosure row
  flag: string;                     // '', 'red', 'orange'
  note: string;                     // methodology, required when flagged
  label?: string;
  page?: string;
}

// A refusal speaks twice. `why` is the FULL reason and goes to _PLAN /
// _LEDGER, where the analyst reads it. `brief` is all the Agent is told —
// deliberately stripped of the model's own stored figure, because an
// Agent that is shown the number it failed to match can simply echo that
// number back and walk straight through the referee (anti-gaming law,
// 2026-08-26). Never widen `brief` to include model values.
interface Refusal { entry: PlanEntry; why: string; brief: string; }
interface PlanVerdict { accepted: PlanEntry[]; refused: Refusal[]; }
interface SubtotalCheck { keys: string[]; totalKey: string; }
interface SubtotalFailure { totalKey: string; sum: number; total: number; }

// Tolerance law: a tie must survive disclosure ROUNDING (a model holding
// full precision vs a disclosure printed to 1dp/whole units differs by up
// to ~0.5) but must NOT absorb real drift — 0.1%+ of a large figure is a
// restatement or a misread, never rounding.
const ABS_TOL: number = 0.5;
const REL_TOL: number = 1e-4;

function tol(v: number): number {
  const a: number = Math.abs(typeof v === "number" ? v : 0);
  return Math.max(ABS_TOL, a * REL_TOL);
}

function tieOk(a: number | string | null | undefined,
               b: number | string | null | undefined): boolean {
  if (typeof a !== "number" || typeof b !== "number") return false;
  return Math.abs(a - b) <= Math.max(tol(a), tol(b));
}

// LAW (triangulation acceptance): an unflagged entry is accepted only when
// the disclosure's own prior-year figure ties to what the model already
// holds for that row — proof the Agent read the RIGHT ROW. No tie -> the
// write is refused and downgraded to a red flag, never silently written.
function validateWritePlan(entries: PlanEntry[],
                           priors: { [k: string]: number }): PlanVerdict {
  const accepted: PlanEntry[] = [];
  const refused: Refusal[] = [];
  for (let i: number = 0; i < entries.length; i++) {
    const e: PlanEntry = entries[i];
    const key: string = e.sheet + "!" + e.row;
    const prior: number | undefined = priors[key];
    const flagged: boolean = e.flag === "red" || e.flag === "orange";
    if (typeof e.value !== "number" && !flagged) {
      refused.push({ entry: e, why: "non-numeric value without a flag",
        brief: "no number and no flag — give a number, or flag it red " +
               "with a methodology note" });
      continue;
    }
    if (flagged && !(e.note && String(e.note).trim())) {
      refused.push({ entry: e, why: "flagged cell missing methodology note",
        brief: "flagged cell has no methodology note — say how the " +
               "figure was derived" });
      continue;
    }
    if (!flagged) {
      if (typeof prior !== "number" || typeof e.priorDisclosed !== "number") {
        refused.push({ entry: e, why: "no prior-year tie proof (" + key + ")",
          brief: "no prior-year tie proof — also read this line's " +
                 "prior-year comparative from the same disclosure row" });
        continue;
      }
      if (!tieOk(prior, e.priorDisclosed)) {
        refused.push({
          entry: e,
          why: "prior mismatch: model holds " + prior +
               ", disclosure comparative reads " + e.priorDisclosed +
               " — wrong row, restatement, or misread",
          brief: "prior-year comparative does not tie to the model — you " +
                 "likely read the wrong row, or this line was restated. " +
                 "Re-read the disclosure; NEVER change a number to make " +
                 "this pass"
        });
        continue;
      }
    }
    accepted.push(e);
  }
  return { accepted: accepted, refused: refused };
}

// Subtotal law: group of entries whose values must sum to a disclosed
// total (segment sums, member rows). Incomplete cones give no verdict.
function checkSubtotals(valueByKey: { [k: string]: number | null },
                        checks: SubtotalCheck[]): SubtotalFailure[] {
  const failures: SubtotalFailure[] = [];
  for (let i: number = 0; i < checks.length; i++) {
    const ch: SubtotalCheck = checks[i];
    let s: number = 0;
    let ok: boolean = true;
    for (let j: number = 0; j < ch.keys.length; j++) {
      const v: number | null = valueByKey[ch.keys[j]];
      if (typeof v !== "number") { ok = false; break; }
      s += v;
    }
    const t: number | null = valueByKey[ch.totalKey];
    if (!ok || typeof t !== "number") continue;
    if (!tieOk(s, t))
      failures.push({ totalKey: ch.totalKey, sum: s, total: t });
  }
  return failures;
}
// CORE LAW: the mapping cascade — "map by triangulation, not by label".
// Phase 1 matched labels exactly and left 55 of 65 real Dongfang rows
// unmapped (其中：营业收入 is the SAME row as 营业收入 to a human, and a
// different string to a computer). CLAUDE.md's cascade, in code:
//
//   tier 1 'exact'  same label once width/case/whitespace are levelled
//   tier 2 'norm'   same label once disclosure furniture is stripped
//                   (其中：/ 减：/ 加：/ 一、/ 1. / trailing colons)
//   tier 3 'prior'  NO name match needed: the model's stored prior value
//                   for exactly one row equals the prior-year comparative
//                   the Agent read in that disclosure row — matching on a
//                   number we already know, immune to naming entirely
//   tier 4 'hint'   the Agent's own judgment (an explicit row number),
//                   deliberately LAST so numeric evidence always wins
//
// Two hard guards, because a confident wrong map is the expensive error:
//   * AMBIGUITY NEVER GUESSES. Several rows match -> the prior-value tie
//     must single one out, or the entry stays unmapped and is reported.
//   * ONE ROW, ONE CLAIM. A model row already taken by another entry is
//     out of the running (two disclosure lines cannot be the same row).
// Passes run tier-by-tier across ALL entries, so a weak tier can never
// steal a row that a stronger tier needs later.
// Mapping only proposes; ties.ts still referees every write.

interface AnatomyRow { sheet: string; row: number; label: string;
  prior: number; }
interface MapReq { label: string; prior: number | string | null;
  rowHint: number; }
interface MapHit { row: number; via: string; why: string; }

// Full-width -> ASCII (：（） and full-width digits are everywhere in
// mainland filings), ideographic space -> space.
function widen(s: string): string {
  let out: string = "";
  for (let i: number = 0; i < s.length; i++) {
    const c: number = s.charCodeAt(i);
    if (c >= 0xFF01 && c <= 0xFF5E) out += String.fromCharCode(c - 0xFEE0);
    else if (c === 0x3000) out += " ";
    else out += s.charAt(i);
  }
  return out;
}

// tier-1 key: the label with only presentation noise removed.
function rawKey(s: string): string {
  return widen(String(s)).toLowerCase().replace(/\s+/g, "");
}

// Disclosure furniture that carries no meaning for row identity.
const LEAD: RegExp = new RegExp("^(?:" + [
  "\\(?[0-9]+\\)[.、:]?",        // (1) / (1).
  "[0-9]+[.、:]",                // 1. / 1、
  "[一二三四五六七八九十]+[、.:]",  // 一、
  "\\([一二三四五六七八九十]+\\)",  // (一)
  "其中:", "减:", "加:",
  "less:", "add:", "ofwhich:?", "including:?"
].join("|") + ")");

// tier-2 key: strip the furniture, then the trailing colon/period.
function normLabel(s: string): string {
  let t: string = rawKey(s);
  for (let i: number = 0; i < 4; i++) {
    const nt: string = t.replace(LEAD, "");
    if (nt === t) break;
    t = nt;
  }
  return t.replace(/[:.]+$/, "");
}

// Candidates for one entry at one tier. Uniqueness is judged by the
// caller; this only proposes.
function tierCandidates(tier: string, req: MapReq, rows: AnatomyRow[],
                        aliases: { [k: string]: string }): AnatomyRow[] {
  const out: AnatomyRow[] = [];
  if (tier === "alias") {
    // A mapping a previous run had to reason out, remembered in _SPEC as
    // disclosure-label -> MODEL-LABEL (never a row number: rows move when
    // the analyst inserts a line, labels do not).
    const target: string | undefined = aliases[normLabel(req.label)];
    if (target === undefined) return out;
    for (let i: number = 0; i < rows.length; i++)
      if (normLabel(rows[i].label) === normLabel(target)) out.push(rows[i]);
    return out;
  }
  if (tier === "exact") {
    const k: string = rawKey(req.label);
    if (!k) return out;
    for (let i: number = 0; i < rows.length; i++)
      if (rawKey(rows[i].label) === k) out.push(rows[i]);
    return out;
  }
  if (tier === "norm") {
    const k: string = normLabel(req.label);
    if (!k) return out;
    for (let i: number = 0; i < rows.length; i++)
      if (normLabel(rows[i].label) === k) out.push(rows[i]);
    return out;
  }
  if (tier === "prior") {
    // Guard: only a MATERIAL prior can identify a row. Small figures (and
    // zeros above all) tie to half the model and would map by accident.
    if (typeof req.prior !== "number") return out;
    if (Math.abs(req.prior) < 1) return out;
    for (let i: number = 0; i < rows.length; i++)
      if (tieOk(rows[i].prior, req.prior)) out.push(rows[i]);
    return out;
  }
  if (tier === "hint") {
    if (!req.rowHint || req.rowHint <= 0) return out;
    for (let i: number = 0; i < rows.length; i++)
      if (rows[i].row === req.rowHint) out.push(rows[i]);
    return out;
  }
  return out;
}

// 'alias' sits second: an exact label match still wins (the model may
// have gained the very row the alias was invented to stand in for).
const TIERS: string[] = ["exact", "alias", "norm", "prior", "hint"];

function mapAll(reqs: MapReq[], rows: AnatomyRow[],
                aliases?: { [k: string]: string }): MapHit[] {
  const al: { [k: string]: string } = aliases ? aliases : {};
  const out: MapHit[] = [];
  for (let i: number = 0; i < reqs.length; i++)
    out.push({ row: -1, via: "", why: "no model row carries this line" });
  const claimed: { [k: string]: string } = {};
  for (let t: number = 0; t < TIERS.length; t++) {
    for (let i: number = 0; i < reqs.length; i++) {
      if (out[i].row > 0) continue;
      const cands: AnatomyRow[] = tierCandidates(TIERS[t], reqs[i], rows, al);
      if (cands.length === 0) continue;
      const free: AnatomyRow[] = cands.filter(
        (r: AnatomyRow): boolean => claimed[String(r.row)] === undefined);
      if (free.length === 0) {
        out[i].why = "the matching model row is already taken by '" +
          claimed[String(cands[0].row)] + "'";
        continue;
      }
      let pick: AnatomyRow | null = free.length === 1 ? free[0] : null;
      if (pick === null && typeof reqs[i].prior === "number") {
        const tied: AnatomyRow[] = free.filter(
          (r: AnatomyRow): boolean => tieOk(r.prior, reqs[i].prior));
        if (tied.length === 1) pick = tied[0];
      }
      if (pick === null) {
        out[i].why = "ambiguous: " + free.length +
          " model rows match and the prior-year figure does not single " +
          "one out";
        continue;
      }
      out[i] = { row: pick.row, via: TIERS[t], why: "" };
      claimed[String(pick.row)] = reqs[i].label;
    }
  }
  return out;
}

// ---------- shared helpers (ExcelScript side) ----------------

interface Params {
  mode: string;
  sheet?: string;
  sheets?: string[];
  periodKind?: string;
  targetYear?: number;
  rows?: (string | number | null)[][];
  acknowledgeRestatement?: boolean;
  analystApproved?: boolean;
}

// What PREFLIGHT hands back when a sheet has no column for the period yet.
// The kernel only ever PROPOSES this: adding a column is structural, and
// structure is the analyst's to change (boss mindmap). EXTEND refuses to
// act until the answer comes back as analystApproved.
interface ExtendProposal { sheet: string; lastYear: number; lastCol: string;
  newCol: string; newColEmpty: boolean; hardcodeShare: number; ask: string; }

interface PreflightOutcome { err: string; proposal: ExtendProposal | null;
  priorCol: string; targetCol: string; rows: number; hardcodeShare: number;
  externalLinks: number; errorsBefore: number; }

interface CheckVerdict { sheet: string; row: number; label: string;
  value: number; pass: boolean; when: string; }

// One sheet's slice of _ANATOMY: the labelled rows with the prior values
// the referee triangulates against, plus that sheet's column recipe.
interface AnatomyView {
  rows: AnatomyRow[];
  priorCol: string; targetCol: string;
  axisRow: number; axisHeader: string; nextCol: string;
  errorsBefore: number; externalLinks: number;
  // was the target column BLANK when we first looked? If so this is a
  // brand-new period column, and copying last year's typed numbers into
  // it would not be "leaving a cell stale" — it would be inventing an
  // actual that nobody disclosed. The owner caught exactly this on the
  // real model: a 2025 column that was a pixel-perfect copy of 2024.
  targetWasEmpty: boolean;
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

// Which cells in a column are typed-in numbers rather than formulas?
// The share is how the kernel tells an INPUT sheet (raw financials: almost
// all typed) from a WIRED sheet (the model: almost all formulas) — the same
// hardcode-density signal the boss mindmap uses to find the year to update.
function columnFormulas(ws: ExcelScript.Worksheet, col: string,
                        nRows: number): string[] {
  const f: string[][] = ws.getRange(col + "1:" + col + nRows).getFormulas();
  const out: string[] = [];
  for (let i: number = 0; i < f.length; i++)
    out.push(String(f[i][0] === undefined ? "" : f[i][0]));
  return out;
}

function isFormula(s: string): boolean { return s.charAt(0) === "="; }

function hardcodeShareOf(ws: ExcelScript.Worksheet, grid: CellValue[][],
                         colIdx: number): number {
  const f: string[] = columnFormulas(ws, n2col(colIdx), grid.length);
  let typed: number = 0;
  let total: number = 0;
  for (let r: number = 0; r < grid.length; r++) {
    if (typeof grid[r][colIdx] !== "number") continue;
    if (!labelOf(grid, r)) continue;        // header rows are not data
    total++;
    if (!isFormula(f[r] === undefined ? "" : f[r])) typed++;
  }
  return total === 0 ? 0 : Math.round(typed / total * 100) / 100;
}

// Excel's error values. CLAUDE.md's integrity checklist: no #REF!/#VALUE!/
// #DIV0! anywhere in the workbook. A broken external link surfaces here.
const ERR: RegExp = /^#(REF|VALUE|DIV\/0|N\/A|NAME\?|NUM|NULL)!?$/i;

function isErrCell(v: CellValue | undefined): boolean {
  return typeof v === "string" && ERR.test(v.trim());
}

// skipCol lets the caller exclude the column being rewritten, so a
// before/after count compares like with like.
function errorCells(grid: CellValue[][], cap: number,
                    skipCol?: number): string[] {
  const skip: number = (skipCol === undefined) ? -1 : skipCol;
  const out: string[] = [];
  for (let r: number = 0; r < grid.length; r++)
    for (let c: number = 0; c < grid[r].length; c++) {
      if (c === skip) continue;
      const v: CellValue = grid[r][c];
      if (isErrCell(v)) {
        if (out.length < cap) out.push(n2col(c) + (r + 1));
        else return out;
      }
    }
  return out;
}

// Formulas that reach OUTSIDE this workbook: [Book.xlsx]Sheet!A1 or a
// SharePoint/OneDrive URL. Counted so the analyst knows how much of the
// model depends on files we are not touching.
const SWEEP_ROWS: number = 5000;         // keep huge sheets from stalling

function externalLinkCount(ws: ExcelScript.Worksheet,
                           grid: CellValue[][]): number {
  if (grid.length > SWEEP_ROWS) return -1;   // -1 = not counted
  const ur: ExcelScript.Range | undefined = ws.getUsedRange();
  if (!ur) return 0;
  const f: string[][] = ur.getFormulas();
  let n: number = 0;
  for (let r: number = 0; r < f.length; r++)
    for (let c: number = 0; c < f[r].length; c++) {
      const t: string = String(f[r][c] === undefined ? "" : f[r][c]);
      if (t.charAt(0) !== "=") continue;
      if (t.indexOf("[") >= 0 || t.indexOf("https://") >= 0 ||
          t.indexOf("http://") >= 0) n++;
    }
  return n;
}

// fromRow lets the caller ignore the header rows: a freshly added period
// column already carries its year header, and that must not make it look
// occupied when we ask "did this column hold any data before?"
// "Did this column ever hold DATA?" — numbers or formulas only. Text does
// not count: a real model stacks header rows (a date row AND an 'FY2025'
// row), and the owner's cleared 2025 column still carried its text label,
// which made a freshly emptied column look occupied and brought last
// year's numbers straight back.
function columnHasData(ws: ExcelScript.Worksheet, grid: CellValue[][],
                       colIdx: number, fromRow: number): boolean {
  const f: string[] = columnFormulas(ws, n2col(colIdx), grid.length);
  for (let r: number = fromRow; r < grid.length; r++) {
    if (typeof grid[r][colIdx] === "number") return true;
    if (isFormula(f[r] === undefined ? "" : f[r])) return true;
  }
  return false;
}

function columnIsEmpty(grid: CellValue[][], colIdx: number,
                       fromRow?: number): boolean {
  const start: number = (fromRow === undefined) ? 0 : fromRow;
  for (let r: number = start; r < grid.length; r++) {
    const v: CellValue | undefined = grid[r][colIdx];
    if (v !== undefined && v !== "") return false;
  }
  return true;
}

// A new period header must keep the neighbour's data TYPE and wording:
// 2024 -> 2025, "FY2024" -> "FY2025", a date -> the same date a year on.
function nextHeader(prev: CellValue, lastYear: number,
                    ty: number): string | number | null {
  if (typeof prev === "number") {
    if (Math.abs(prev - Math.round(prev)) < 0.5 && Math.round(prev) === lastYear)
      return ty;
    if (prev >= 32874 && prev <= 73415) {         // a date serial
      const ms: number = (Math.floor(prev) - 25569) * 86400000;
      const d: Date = new Date(ms);
      const nd: number = Date.UTC(d.getUTCFullYear() + 1, d.getUTCMonth(),
        d.getUTCDate());
      return Math.round(nd / 86400000) + 25569;
    }
    return null;
  }
  if (typeof prev === "string") {
    if (prev.indexOf(String(lastYear)) >= 0)
      return prev.split(String(lastYear)).join(String(ty));
    // two-digit conventions ('FY24', 'H124', '24E') — only when the pair
    // appears exactly once, so nothing else in the label is mangled
    const two: string = String(lastYear % 100);
    const parts: string[] = prev.split(two);
    if (parts.length === 2)
      return parts.join(String(ty % 100 < 10 ? "0" : "") + String(ty % 100));
  }
  return null;
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
    axisRow: -1, axisHeader: "", nextCol: "", errorsBefore: 0,
    externalLinks: 0, targetWasEmpty: false, beforeT: {}, beforeN: {} };
  const mk: string = metaKey(sheetName);
  for (let i: number = 1; i < an.length; i++) {
    const sh: string = String(an[i][0]);
    if (sh === mk) {
      view.axisRow = Number(an[i][1]);
      view.axisHeader = String(an[i][2]);
      view.priorCol = String(an[i][4]);
      view.targetCol = String(an[i][5]);
      view.nextCol = String(an[i][6] === undefined ? "" : an[i][6]);
      view.targetWasEmpty = String(an[i][7]) === "EMPTY";
      view.errorsBefore = (typeof an[i][8] === "number")
        ? (an[i][8] as number) : 0;
      view.externalLinks = (typeof an[i][9] === "number")
        ? (an[i][9] as number) : 0;
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
function blankOutcome(err: string): PreflightOutcome {
  return { err: err, proposal: null, priorCol: "", targetCol: "", rows: 0,
    hardcodeShare: 0, externalLinks: 0, errorsBefore: 0 };
}

function preflightSheet(wb: ExcelScript.Workbook, sheetName: string,
                        periodKind: string, ty: number,
                        out: (string | number)[][]): PreflightOutcome {
  const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(sheetName);
  if (!ws) return blankOutcome("no sheet " + sheetName);
  const grid: CellValue[][] = sheetGrid(ws);
  const axis: AxisMap | null = findYearAxis(grid, periodKind);
  if (!axis) return blankOutcome("no year axis found on " + sheetName);
  const tCol: number | undefined = axis[String(ty)];
  const pCol: number | undefined = axis[String(ty - 1)];
  if (tCol === undefined) {
    // No column for this period yet. Rather than fail, work out whether one
    // could be added and hand the analyst a proposal (Phase 4).
    let lastYear: number = -1;
    for (const k in axis) if (Number(k) > lastYear) lastYear = Number(k);
    if (lastYear < 0)
      return blankOutcome("no usable year axis on " + sheetName);
    const lastIdx: number = axis[String(lastYear)];
    const prevIdx: number | undefined = axis[String(lastYear - 1)];
    const desc: boolean = (prevIdx !== undefined) && (prevIdx > lastIdx);
    const newIdx: number = desc ? lastIdx : lastIdx + 1;
    const empty: boolean = !desc && columnIsEmpty(grid, newIdx);
    const share: number = hardcodeShareOf(ws, grid, lastIdx);
    const gap: boolean = ty !== lastYear + 1;
    const prop: ExtendProposal = { sheet: sheetName, lastYear: lastYear,
      lastCol: n2col(lastIdx), newCol: n2col(newIdx), newColEmpty: empty,
      hardcodeShare: share,
      ask: gap
        ? ("'" + sheetName + "' ends at " + lastYear + ", so reaching " + ty +
           " would skip a year. Ask the analyst what to do — do NOT extend.")
        : ("'" + sheetName + "' has no " + ty + " column. " + lastYear +
           " sits in column " + n2col(lastIdx) + " and " + n2col(newIdx) +
           " is " + (empty ? "empty" : "NOT empty (a column would be " +
           "inserted, shifting everything right)") +
           ". Ask the analyst: add a " + ty + " column there?") };
    const outc: PreflightOutcome = blankOutcome("");
    outc.proposal = gap ? null : prop;
    outc.hardcodeShare = share;
    outc.err = gap ? prop.ask : ("'" + sheetName + "' has no " + ty +
      " column yet — see the proposal");
    return outc;
  }
  if (pCol === undefined)
    return blankOutcome("axis on " + sheetName + " has " + ty +
      " but no prior year to copy from; axis=" + JSON.stringify(axis));
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
  // baseline the sheet's health BEFORE we touch it: errors that are
  // already here are the model's, and external links tell us how much of
  // it depends on workbooks we cannot see.
  const errsBefore: number = errorCells(grid, 500, tCol).length;
  const links: number = externalLinkCount(ws, grid);
  out.push([metaKey(sheetName), axisRow, String(headerVal), 0,
    n2col(pCol), n2col(tCol), (nCol === undefined) ? "" : n2col(nCol),
    columnHasData(ws, grid, tCol, axisRow + 1) ? "" : "EMPTY",
    errsBefore, links]);
  // the analyst's own forecast for the year we are about to overwrite,
  // and the year after — snapshot NOW or it is lost forever (_REPORT's
  // "what you projected vs what came in" depends on it)
  let labelled: number = 0;
  for (let r: number = 0; r < grid.length; r++) {
    const lab: string = labelOf(grid, r);
    if (!lab) continue;
    const pv: CellValue = grid[r][pCol];
    if (typeof pv !== "number") continue;
    const bt: CellValue = grid[r][tCol];
    const bn: CellValue = (nCol === undefined) ? "" : grid[r][nCol];
    out.push([sheetName, r + 1, lab, pv, n2col(pCol), n2col(tCol),
      (typeof bt === "number") ? bt : "", (typeof bn === "number") ? bn : "",
      "", ""]);
    labelled++;
  }
  const res: PreflightOutcome = blankOutcome("");
  res.priorCol = n2col(pCol); res.targetCol = n2col(tCol);
  res.rows = labelled;
  res.hardcodeShare = hardcodeShareOf(ws, grid, pCol);
  res.errorsBefore = errsBefore;
  res.externalLinks = links;
  return res;
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
      (typeof old[i][7] === "number") ? (old[i][7] as number) : "",
      (typeof old[i][8] === "number") ? (old[i][8] as number) : "",
      (typeof old[i][9] === "number") ? (old[i][9] as number) : ""]);
  }
  const fresh: (string | number)[][] = [];
  const problems: { sheet: string; why: string }[] = [];
  const done: { sheet: string; priorCol: string; targetCol: string;
    rows: number; typedShare: number; externalLinks: number;
    errorsBefore: number }[] = [];
  const proposals: ExtendProposal[] = [];
  for (let i: number = 0; i < names.length; i++) {
    const outc: PreflightOutcome =
      preflightSheet(wb, names[i], kind, ty, fresh);
    if (outc.proposal !== null) proposals.push(outc.proposal);
    if (outc.err) { problems.push({ sheet: names[i], why: outc.err }); continue; }
    done.push({ sheet: names[i], priorCol: outc.priorCol,
      targetCol: outc.targetCol, rows: outc.rows,
      typedShare: outc.hardcodeShare, externalLinks: outc.externalLinks,
      errorsBefore: outc.errorsBefore });
  }
  const rows: (string | number)[][] = keep.concat(fresh);
  const ur: ExcelScript.Range | undefined = an.getUsedRange();
  if (ur) ur.clear(ExcelScript.ClearApplyTo.all);
  an.getRange("A1:J1").setValues([[
    "sheet", "row", "label", "priorValue", "priorCol", "targetCol",
    "targetBefore", "nextBefore", "errorsBefore", "externalLinks"]]);
  if (rows.length > 0)
    an.getRangeByIndexes(1, 0, rows.length, 10).setValues(rows);
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
  if (proposals.length > 0) {
    res["needsExtend"] = proposals;
    res["next"] = "One or more sheets have no column for this period. ASK " +
      "THE ANALYST first, then call EXTEND with analystApproved:true. " +
      "Never add a column on your own authority.";
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
  // stamp the batch. APPLY will refuse to write until RESTATE has scanned
  // THIS batch — on the real model the agent wrote 33 cash-flow lines and
  // only then discovered the balance sheet had been restated.
  const stamp: string = new Date().toISOString() + "-" + norm.length + "-" +
    String(Math.floor(Math.random() * 1000000));   // unique per batch
  st.getRange("J1").setValue(stamp);
  return JSON.stringify({ ok: true, staged: norm.length,
    next: "run RESTATE next — nothing can be written until the " +
      "comparatives have been checked" });
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
  const stamp: CellValue = stWs.getRange("J1").getValues()[0][0] as CellValue;
  const scanned: CellValue = rsWs
    ? (rsWs.getRange("I1").getValues()[0][0] as CellValue) : "";
  if (String(stamp) !== "" && String(scanned) !== String(stamp))
    return JSON.stringify({ ok: false,
      why: "RESTATE has not scanned this staging batch. Nothing is " +
        "written until the prior-year comparatives have been checked — " +
        "call {\"mode\":\"RESTATE\"} first, then APPLY." });
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
  // WHAT KIND OF CELL IS THIS? (Phase 4, after the owner's ruling that
  // hardcodes are the normal case, not the exception.) Every row in the
  // rolled-forward column is one of three things, and each needs opposite
  // treatment:
  //   typed number  -> an INPUT slot: the actual belongs here, type it in
  //   pure formula  -> WIRING: never type over it; it now points at the new
  //                    period's source. Check its result instead.
  //   formula with a number baked inside -> an EMBEDDED HARDCODE: last
  //                    year's constant has just been copied into this year
  //                    (=raw!X12+36). Cannot be fixed blind — always surface.
  const priorF: string[] = columnFormulas(ws, priorCol, nRows);
  const pIdxPre: number = ws.getRange(priorCol + "1").getColumnIndex();
  const formulaOf = (row: number): string =>
    (priorF[row - 1] === undefined) ? "" : priorF[row - 1];
  // a numeric literal that is NOT part of a cell reference (T12, $B$4) and
  // not part of a function name — the tell-tale of a baked-in number
  const LITERAL: RegExp = /(^|[-+*\/(,=\s])([0-9]+(\.[0-9]+)?)/;
  const stripRefs = (f: string): string =>
    f.split("$").join("").replace(/\b[A-Z]{1,3}[0-9]{1,5}\b/g, "@");
  // A BRAND-NEW column keeps the wiring and the formats, but starts with
  // NO typed numbers: a blank says "nobody disclosed this yet", while
  // last year's figure sitting in this year's column is a lie that reads
  // as an actual. (An EXISTING column keeps the house mark-to-actual
  // recipe — there we are replacing the analyst's own forecast, and the
  // boss ruling says leave what this period did not disclose.)
  if (view.targetWasEmpty) {
    const tIdxPre: number = ws.getRange(targetCol + "1").getColumnIndex();
    for (let r: number = 1; r <= nRows; r++) {
      if (r === axisRow + 1) continue;               // never the header
      if (isFormula(formulaOf(r))) continue;         // wiring stays
      // ONLY undo cells the copy filled with last year's typed number.
      // Where the prior column held text (a unit, a section label, an
      // analyst note) the copy brought text, not a fake actual — and
      // whatever the target held before is restored rather than wiped,
      // so no model ever loses content it came in with.
      if (typeof (grid[r - 1] ? grid[r - 1][pIdxPre] : "") !== "number")
        continue;
      const was: CellValue = (grid[r - 1] && grid[r - 1][tIdxPre] !== undefined)
        ? grid[r - 1][tIdxPre] : "";
      if (was === "" || was === undefined)
        ws.getRange(targetCol + r).clear(ExcelScript.ClearApplyTo.contents);
      else ws.getRange(targetCol + r).setValue(was);
    }
  }
  const wired: { row: number; label: string; value: number }[] = [];
  const embedded: { row: number; label: string; formula: string }[] = [];
  const writtenRows: { [k: string]: boolean } = {};
  for (let i: number = 0; i < verdict.accepted.length; i++) {
    const e: PlanEntry = verdict.accepted[i];
    const addr: string = targetCol + e.row;
    const cell: ExcelScript.Range = ws.getRange(addr);
    const before: CellValue = cell.getValues()[0][0] as CellValue;
    const f: string = formulaOf(e.row);
    writtenRows[String(e.row)] = true;
    if (isFormula(f)) {
      // WIRED: leave the formula alone. Its own source must produce the
      // disclosed figure — verified after the recalc below.
      if (typeof e.value === "number")
        wired.push({ row: e.row, label: e.label ? e.label : "",
          value: e.value });
      led.push([utc, "APPLY", e.sheet, addr, String(before), "(formula kept)",
        e.flag, "wired cell — actual belongs on its source sheet"]);
    } else {
      if (typeof e.value === "number") cell.setValue(e.value);
      const after: CellValue = cell.getValues()[0][0] as CellValue;
      led.push([utc, "APPLY", e.sheet, addr, String(before), String(after),
        e.flag, ""]);
    }
    if (e.flag === "red") cell.getFormat().getFill().setColor(FLAG_RED);
    if (e.flag === "orange") cell.getFormat().getFill().setColor(FLAG_ORANGE);
  }
  for (let i: number = 0; i < verdict.refused.length; i++) {
    const r: Refusal = verdict.refused[i];
    const addr: string = targetCol + r.entry.row;
    ws.getRange(addr).getFormat().getFill().setColor(FLAG_RED);
    led.push([utc, "APPLY", r.entry.sheet, addr, "", "", "red", r.why]);
  }
  // sweep the whole rolled-forward column for the two silent diseases
  const carried: { row: number; label: string; value: number }[] = [];
  let blanks: number = 0;
  for (let i: number = 0; i < view.rows.length; i++) {
    const row: number = view.rows[i].row;
    const f: string = formulaOf(row);
    if (isFormula(f)) {
      if (LITERAL.test(stripRefs(f.substring(1))))
        embedded.push({ row: row, label: view.rows[i].label, formula: f });
      continue;
    }
    if (writtenRows[String(row)]) continue;
    if (view.targetWasEmpty) { blanks++; continue; }  // left honestly blank
    // a typed number copied from last year, sitting in this year's column
    // and not disclosed this period. Boss ruling: no cell flag, but it MUST
    // appear in the report as "not updated this period".
    carried.push({ row: row, label: view.rows[i].label,
      value: view.rows[i].prior });
  }
  // embedded hardcodes are the boss map's KEY DRIVERS — never silent
  for (let i: number = 0; i < embedded.length; i++) {
    const addr: string = targetCol + embedded[i].row;
    ws.getRange(addr).getFormat().getFill().setColor(FLAG_RED);
    led.push([utc, "APPLY", sheetName, addr, embedded[i].formula, "", "red",
      "embedded hardcode carried from last year — check the number inside"]);
  }
  // did the wired rows actually produce the disclosed figures?
  wb.getApplication().calculate(ExcelScript.CalculationType.full);
  const after: CellValue[][] = sheetGrid(ws);
  const tIdx: number = ws.getRange(targetCol + "1").getColumnIndex();
  const conflicts: { row: number; label: string }[] = [];
  for (let i: number = 0; i < wired.length; i++) {
    const live: CellValue | null = after[wired[i].row - 1]
      ? after[wired[i].row - 1][tIdx] : null;
    if (typeof live !== "number") continue;
    if (tieOk(live, wired[i].value)) continue;
    conflicts.push({ row: wired[i].row, label: wired[i].label });
    ws.getRange(targetCol + wired[i].row).getFormat().getFill()
      .setColor(FLAG_RED);
    led.push([utc, "APPLY", sheetName, targetCol + wired[i].row, "", "", "red",
      "wired cell computes " + live + " but the disclosure says " +
      wired[i].value + " — the source sheet is not updated, or the mapping " +
      "is wrong"]);
  }
  const extra: (string | number)[][] = [];
  for (let i: number = 0; i < conflicts.length; i++)
    extra.push([sheetName, conflicts[i].row, conflicts[i].label, "",
      "CONFLICT", "this cell is a formula; its result does not match the " +
      "disclosed figure — check the source sheet", "", "", "red"]);
  for (let i: number = 0; i < embedded.length; i++)
    extra.push([sheetName, embedded[i].row, embedded[i].label, "",
      "EMBEDDED", "formula carries a number baked in from last year: " +
      embedded[i].formula, "", "", "red"]);
  for (let i: number = 0; i < carried.length && i < 200; i++)
    extra.push([sheetName, carried[i].row, carried[i].label,
      carried[i].value, "CARRIED",
      "typed number copied from last year — not disclosed this period", "",
      "", ""]);
  if (extra.length > 0)
    plWs.getRangeByIndexes(planRows.length, 0, extra.length, 9)
      .setValues(extra);
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
    ok: true, written: verdict.accepted.length - wired.length,
    keptWired: wired.length,
    refused: verdict.refused.length,
    unmappedCount: unmapped.length, unmapped: shown,
    mappedVia: via, refusals: refusals,
    conflicts: conflicts, embeddedHardcodes: embedded.length,
    carriedOver: carried.length, awaitingFigures: blanks,
    newColumn: view.targetWasEmpty,
    note: view.targetWasEmpty
      ? (blanks + " input rows on this sheet are still BLANK — this " +
         "disclosure did not cover them. The update is not complete until " +
         "they are filled or the analyst accepts them empty.")
      : ((embedded.length > 0 || carried.length > 0)
        ? "some cells carry last year's numbers — see _REPORT" : "")
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
  const stStamp: CellValue = stWs.getRange("J1").getValues()[0][0] as CellValue;
  rs.getRange("I1").setValue(String(stStamp));
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
        // Say WHICH year broke. A break in the prior actual column was
        // already in the model when we opened it — the analyst needs to
        // know that is theirs, not ours.
        const cv: CheckVerdict = { sheet: sheetName + "!" + cols[c] + row,
          row: row, label: lab, value: v, pass: Math.abs(v) <= 0.02,
          when: (c === 0) ? "this period"
            : "prior period — ALREADY broken before this run" };
        verdicts.push(cv);
        if (!cv.pass) failed.push(cv);
      }
    }
  }
  // EXTERNAL-LINK / ERROR SWEEP. The model links to workbooks we never
  // see; if a copy, a recalc or our own write breaks one, the cell turns
  // #REF!/#VALUE!. Errors that were already there when we opened the file
  // are the model's; errors that appear after are OURS and must fail the
  // run loudly (CLAUDE.md integrity checklist).
  const newErrors: { sheet: string; cells: string[] }[] = [];
  let errorsNow: number = 0;
  let errorsPre: number = 0;
  let links: number = 0;
  for (let s2: number = 0; s2 < names.length; s2++) {
    const vw: AnatomyView | null = readAnatomy(wb, names[s2]);
    const ws2: ExcelScript.Worksheet | undefined = wb.getWorksheet(names[s2]);
    if (!vw || !ws2) continue;
    const g2: CellValue[][] = sheetGrid(ws2);
    const tIdx2: number = ws2.getRange(vw.targetCol + "1").getColumnIndex();
    const pIdx2: number = ws2.getRange(vw.priorCol + "1").getColumnIndex();
    // outside the rewritten column: compare like with like
    const outside: string[] = errorCells(g2, 20, tIdx2);
    const fresh: string[] = [];
    // inside it: an error is only OURS if the same row was healthy in the
    // prior column. An error copied forward from a row that was already
    // broken is the model's, not the run's.
    for (let r: number = 0; r < g2.length; r++) {
      if (!isErrCell(g2[r] ? g2[r][tIdx2] : undefined)) continue;
      if (isErrCell(g2[r] ? g2[r][pIdx2] : undefined)) continue;
      if (fresh.length < 20) fresh.push(vw.targetCol + (r + 1));
    }
    errorsNow += outside.length + fresh.length;
    errorsPre += vw.errorsBefore;
    links += vw.externalLinks;
    const grew: boolean = outside.length > vw.errorsBefore;
    if (grew || fresh.length > 0)
      newErrors.push({ sheet: names[s2],
        cells: (grew ? outside : []).concat(fresh) });
  }

  // GENERICITY GUARD: not every analyst's model carries a labelled check
  // row. Zero checks is NOT a pass — it means we verified nothing, and
  // silence would read as "balanced" to the agent and the analyst alike.
  if (newErrors.length > 0)
    return JSON.stringify({ ok: false, checks: verdicts.length,
      failed: failed, newErrors: newErrors, externalLinks: links,
      why: "cells that were fine before this run now show Excel errors " +
        "(#REF!/#VALUE!). Something the run touched — or a broken link to " +
        "an outside workbook — is the cause. Do NOT deliver this model." });
  if (verdicts.length === 0)
    return JSON.stringify({ ok: false, checks: 0, failed: [],
      externalLinks: links, preExistingErrors: errorsPre,
      why: "no balance-check row found on " + names.join(", ") +
           " — this model does not carry one, so the balance could NOT be " +
           "verified. Tell the analyst: check the balance sheet by hand, " +
           "or add a check row to the model." });
  let inherited: number = 0;
  for (let i: number = 0; i < failed.length; i++)
    if (failed[i].when !== "this period") inherited++;
  return JSON.stringify({
    ok: failed.length === 0, checks: verdicts.length, failed: failed,
    inheritedFailures: inherited, externalLinks: links,
    preExistingErrors: errorsPre, newErrors: [],
    note: inherited > 0 ? "some checks were already failing in the prior " +
      "year column — those are pre-existing model errors, not this run's" : ""
  });
}


// ---------- EXTEND -------------------------------------------
// Add the new period's column to a sheet that has none (a raw-financials
// history sheet usually only carries reported years). Structural, so it
// is LOCKED: the kernel refuses unless analystApproved comes back true —
// the agent has to ask a human, and cannot vote for itself.
// It copies the previous year's FORMATS only, never its values: a blank
// cell reads as "not filled in yet", last year's number copied forward
// reads as this year's actual, and that lie is the whole disease.
function modeExtend(wb: ExcelScript.Workbook, p: Params): string {
  const sheetName: string = String(p.sheet);
  const ty: number = Number(p.targetYear);
  const ws: ExcelScript.Worksheet | undefined = wb.getWorksheet(sheetName);
  if (!ws) return JSON.stringify({ ok: false, why: "no sheet " + sheetName });
  const grid: CellValue[][] = sheetGrid(ws);
  const axis: AxisMap | null = findYearAxis(grid, String(p.periodKind || "FY"));
  if (!axis) return JSON.stringify({ ok: false,
    why: "no year axis found on " + sheetName });
  // Already there? That is success, not an error — a second run on the same
  // workbook must sail through this step rather than stall the agent.
  if (axis[String(ty)] !== undefined)
    return JSON.stringify({ ok: true, alreadyPresent: true,
      sheet: sheetName, newCol: n2col(axis[String(ty)]),
      note: sheetName + " already has a " + ty + " column — nothing to do" });
  let lastYear: number = -1;
  for (const k in axis) if (Number(k) > lastYear) lastYear = Number(k);
  if (ty !== lastYear + 1)
    return JSON.stringify({ ok: false, why: sheetName + " ends at " +
      lastYear + "; adding " + ty + " would skip a year. The analyst must " +
      "say what belongs in between." });
  const lastIdx: number = axis[String(lastYear)];
  // Which way does time run on this sheet? Most models put the newest year
  // on the right, but plenty run newest-first. Read the direction from the
  // axis itself instead of assuming.
  const prevIdx: number | undefined = axis[String(lastYear - 1)];
  const descending: boolean = (prevIdx !== undefined) && (prevIdx > lastIdx);
  const newIdx: number = descending ? lastIdx : lastIdx + 1;
  if (p.analystApproved !== true)
    return JSON.stringify({ ok: false, needsApproval: true,
      why: "structural change — not done. Ask the analyst whether to add a " +
        ty + " column to '" + sheetName + "' (after " + n2col(lastIdx) +
        "), then call EXTEND again with \"analystApproved\":true." });
  // find the header row for the last year, so the new header sits with it
  let axisRow: number = -1;
  for (let r: number = 0; r < Math.min(grid.length, SCAN_ROWS); r++) {
    const yt: YearMark = yearOf(grid[r][lastIdx]);
    if (yt[0] === lastYear) { axisRow = r; break; }
  }
  if (axisRow < 0) return JSON.stringify({ ok: false,
    why: "could not locate the header row for " + lastYear });
  const header: string | number | null =
    nextHeader(grid[axisRow][lastIdx], lastYear, ty);
  if (header === null) return JSON.stringify({ ok: false,
    why: "cannot write a " + ty + " header safely — " + lastYear +
      "'s header is in a form I do not recognise. Ask the analyst to add " +
      "the column header, then re-run PREFLIGHT." });
  // newest-first sheets always need the insert: the new period goes where
  // the current newest sits, pushing the history right.
  const shifted: boolean = descending || !columnIsEmpty(grid, newIdx);
  const newCol: string = n2col(newIdx);
  if (shifted)
    ws.getRange(newCol + ":" + newCol).insert(
      ExcelScript.InsertShiftDirection.right);
  const nRows: number = grid.length;
  const lastCol: string = n2col(lastIdx);
  const srcCol: string = descending ? n2col(lastIdx + 1) : lastCol;
  ws.getRange(newCol + "1:" + newCol + nRows).copyFrom(
    ws.getRange(srcCol + "1:" + srcCol + nRows),
    ExcelScript.RangeCopyType.formats);
  const hCell: ExcelScript.Range = ws.getRange(newCol + (axisRow + 1));
  // carry the neighbour's number format across, or a date header lands as
  // a raw serial (the owner saw 46022 where 2025-12-31 belonged)
  const hFmt: string = ws.getRange(lastCol + (axisRow + 1)).getNumberFormat();
  hCell.setValue(header);
  if (hFmt) hCell.setNumberFormat(hFmt);
  ledgerAppend(wb, [[new Date().toISOString(), "EXTEND", sheetName,
    newCol + (axisRow + 1), "", String(header), "",
    "analyst-approved new period column" +
      (shifted ? " (inserted, columns shifted right)" : "")]]);
  return JSON.stringify({ ok: true, sheet: sheetName, newCol: newCol,
    header: header, inserted: shifted,
    note: "column added, formats copied from " + lastCol +
      ", values left EMPTY. Run PREFLIGHT again to pick it up." });
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
  const drivers: ReportRow[] = [];      // embedded hardcodes — key drivers
  const carried: ReportRow[] = [];      // last year's typed numbers, kept
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
      if (verdict === "CONFLICT") {
        red.push({ addr: addr, sheet: sheetName, a: "", c: modelLabel,
          d: why, e: asRead, k: 0 });
        continue;
      }
      if (verdict === "EMBEDDED") {
        drivers.push({ addr: addr, sheet: sheetName, a: "", c: modelLabel,
          d: why, e: "", k: 0 });
        continue;
      }
      if (verdict === "CARRIED") {
        carried.push({ addr: addr, sheet: sheetName, a: "", c: modelLabel,
          d: why, e: "", k: 0 });
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
    red.length + " red · " + orange.length + " orange · " +
    drivers.length + " embedded hardcodes · " + carried.length +
    " not updated · balance checks: " +
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
  lines.push(head("3. KEY DRIVERS — formulas carrying a number baked in " +
    "from last year (" + drivers.length + ")"));
  for (let i: number = 0; i < drivers.length && i < 25; i++)
    lines.push(drivers[i]);
  if (drivers.length > 25)
    lines.push(head("   ... and " + (drivers.length - 25) +
      " more — see the _PLAN tab"));
  lines.push(head(""));
  lines.push(head("4. NOT UPDATED THIS PERIOD — last year's typed numbers " +
    "still standing (" + carried.length + ")"));
  for (let i: number = 0; i < carried.length && i < 25; i++)
    lines.push(carried[i]);
  if (carried.length > 25)
    lines.push(head("   ... and " + (carried.length - 25) +
      " more — see the _PLAN tab"));
  lines.push(head(""));
  lines.push(head("5. BIG MOVES >50% year on year — check for mapping errors" +
    (moves.length > movesShown.length
      ? " (showing 15 of " + moves.length + ")" : "")));
  for (let i: number = 0; i < movesShown.length; i++) lines.push(movesShown[i]);
  lines.push(head(""));
  lines.push(head("6. YOUR FORECAST vs THE ACTUAL" +
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
    keyDrivers: drivers.length, notUpdated: carried.length,
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
    else if (p.mode === "EXTEND") res = modeExtend(workbook, p);
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
