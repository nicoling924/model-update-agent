// Minimal ExcelScript mock — just enough API surface for the kernel.
// Cells hold {v: value, f: formulaOrNull, fill: colorOrNull}. copyFrom
// copies value+formula+fill (the recipe contract). calculate() re-derives
// values for the simple =A1-B1 / =A1+B1 formula shapes used in fixtures.
function makeCell() { return { v: "", f: null, fill: null }; }

function colToIdx(letters) {
  let n = 0;
  for (const ch of letters) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n - 1;
}

function parseA1(a1) {                       // "AI98" -> [97, 34]
  const m = a1.match(/^([A-Z]+)(\d+)$/);
  return [parseInt(m[2], 10) - 1, colToIdx(m[1])];
}

class MockSheet {
  constructor(wb, name) {
    this.wb = wb; this.name = name; this.cells = {}; this.hidden = false;
  }
  key(r, c) { return r + ":" + c; }
  cell(r, c) {
    const k = this.key(r, c);
    if (!this.cells[k]) this.cells[k] = makeCell();
    return this.cells[k];
  }
  extent() {
    let mr = -1, mc = -1;
    for (const k in this.cells) {
      const [r, c] = k.split(":").map(Number);
      const cell = this.cells[k];
      if (cell.v !== "" || cell.f !== null) {
        if (r > mr) mr = r;
        if (c > mc) mc = c;
      }
    }
    return [mr, mc];
  }
  getUsedRange() {
    const [mr, mc] = this.extent();
    if (mr < 0) return null;
    return new MockRange(this, 0, 0, mr + 1, mc + 1);
  }
  getRange(a1) {
    if (a1.indexOf(":") >= 0) {
      const [a, b] = a1.split(":");
      const [r1, c1] = parseA1(a), [r2, c2] = parseA1(b);
      return new MockRange(this, r1, c1, r2 - r1 + 1, c2 - c1 + 1);
    }
    const [r, c] = parseA1(a1);
    return new MockRange(this, r, c, 1, 1);
  }
  getRangeByIndexes(r, c, nr, nc) { return new MockRange(this, r, c, nr, nc); }
  setVisibility(v) { this.hidden = true; }
}

class MockRange {
  constructor(ws, r, c, nr, nc) {
    this.ws = ws; this.r = r; this.c = c; this.nr = nr; this.nc = nc;
  }
  getValues() {
    const out = [];
    for (let i = 0; i < this.nr; i++) {
      const row = [];
      for (let j = 0; j < this.nc; j++)
        row.push(this.ws.cell(this.r + i, this.c + j).v);
      out.push(row);
    }
    return out;
  }
  setValues(vals) {
    for (let i = 0; i < vals.length; i++)
      for (let j = 0; j < vals[i].length; j++) {
        const cell = this.ws.cell(this.r + i, this.c + j);
        cell.v = vals[i][j]; cell.f = null;
      }
  }
  setValue(v) { this.setValues([[v]]); }
  setFormula(f) {
    const cell = this.ws.cell(this.r, this.c);
    cell.f = f; cell.v = 0;
  }
  getRowCount() { return this.nr; }
  getColumnIndex() { return this.c; }
  clear() {
    for (let i = 0; i < this.nr; i++)
      for (let j = 0; j < this.nc; j++) {
        const k = this.ws.key(this.r + i, this.c + j);
        delete this.ws.cells[k];
      }
  }
  copyFrom(src) {                     // values + formulas + formats
    for (let i = 0; i < src.nr; i++)
      for (let j = 0; j < src.nc; j++) {
        const s = src.ws.cell(src.r + i, src.c + j);
        const d = this.ws.cell(this.r + i, this.c + j);
        d.v = s.v; d.fill = s.fill;
        // relative formula shift: =XN op YN with column offset applied
        d.f = s.f === null ? null : s.f.replace(/([A-Z]+)(\d+)/g,
          (m, L, N) => {
            const idx = colToIdx(L) + (this.c - src.c);
            let letters = "", n = idx + 1;
            while (n > 0) { letters = String.fromCharCode(65 + (n - 1) % 26) + letters; n = Math.floor((n - 1) / 26); }
            return letters + N;
          });
      }
  }
  getFormat() {
    const self = this;
    return { getFill() { return { setColor(c) {
      for (let i = 0; i < self.nr; i++)
        for (let j = 0; j < self.nc; j++)
          self.ws.cell(self.r + i, self.c + j).fill = c;
    } }; } };
  }
}

class MockWorkbook {
  constructor() { this.sheets = {}; }
  addWorksheet(name) {
    this.sheets[name] = new MockSheet(this, name);
    return this.sheets[name];
  }
  getWorksheet(name) { return this.sheets[name] || null; }
  getApplication() {
    const wb = this;
    return { calculate() {
      // fixture formulas: =A9-B9 style refs within the same sheet
      for (const sn in wb.sheets) {
        const ws = wb.sheets[sn];
        for (const k in ws.cells) {
          const cell = ws.cells[k];
          if (cell.f === null) continue;
          const expr = cell.f.slice(1).replace(/([A-Z]+)(\d+)/g, (m, L, N) => {
            const v = ws.cell(parseInt(N, 10) - 1, colToIdx(L)).v;
            return String(typeof v === "number" ? v : 0);
          });
          if (/^[-+0-9(). ]+$/.test(expr)) cell.v = eval(expr);
        }
      }
    } };
  }
}

var ExcelScript = {
  SheetVisibility: { hidden: "hidden" },
  ClearApplyTo: { all: "all" },
  RangeCopyType: { all: "all" },
  CalculationType: { full: "full" },
};

if (typeof module !== "undefined")
  module.exports = { MockWorkbook, ExcelScript };
