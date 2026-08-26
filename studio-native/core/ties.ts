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
