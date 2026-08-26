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
    let run: Mark[] = [marks[0]];
    const runs: Mark[][] = [];
    for (let i: number = 1; i < marks.length; i++) {
      const prev: Mark = marks[i - 1];
      const cur: Mark = marks[i];
      if (cur[1] === prev[1] + 1 && cur[0] > prev[0]) run.push(cur);
      else {
        if (run.length >= minRun) runs.push(run);
        run = [cur];
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
