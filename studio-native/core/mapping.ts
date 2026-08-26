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
