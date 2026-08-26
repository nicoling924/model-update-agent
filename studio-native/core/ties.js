// CORE LAW: tie acceptance — the referee that makes GPT-read numbers safe.
// A mapped figure is accepted because it RECONCILES, not because a label
// looked right. Ported from the acceptance laws in prompts/compile.md and
// updater/loop.py; this is the layer that catches OCR misreads and
// wrong-row mappings before they touch the model.

// Tolerance law: a tie must survive disclosure ROUNDING (a model holding
// full precision vs a disclosure printed to 1dp/whole units differs by up
// to ~0.5) but must NOT absorb real drift — 0.1%+ of a large figure is a
// restatement or a misread, never rounding.
var ABS_TOL = 0.5;
var REL_TOL = 1e-4;

function tol(v) {
  var a = Math.abs(typeof v === "number" ? v : 0);
  return Math.max(ABS_TOL, a * REL_TOL);
}

function tieOk(a, b) {
  if (typeof a !== "number" || typeof b !== "number") return false;
  return Math.abs(a - b) <= Math.max(tol(a), tol(b));
}

// One write-plan entry, as produced by the mapping Agent node:
// { sheet, row, value,                  -- what to write where
//   priorDisclosed,                     -- prior-year figure the Agent read
//                                          in the SAME disclosure row
//   flag,                               -- '', 'red', 'orange'
//   note }                             -- methodology, required when flagged
// priors: { "Sheet!row": priorModelValue } from the snapshot script.
//
// LAW (triangulation acceptance): an unflagged entry is accepted only when
// the disclosure's own prior-year figure ties to what the model already
// holds for that row — proof the Agent read the RIGHT ROW. No tie -> the
// write is refused and downgraded to a red flag, never silently written.
function validateWritePlan(entries, priors) {
  var accepted = [];
  var refused = [];
  for (var i = 0; i < entries.length; i++) {
    var e = entries[i];
    var key = e.sheet + "!" + e.row;
    var prior = priors[key];
    var flagged = e.flag === "red" || e.flag === "orange";
    if (typeof e.value !== "number" && !flagged) {
      refused.push({ entry: e, why: "non-numeric value without a flag" });
      continue;
    }
    if (flagged && !(e.note && String(e.note).trim())) {
      refused.push({ entry: e, why: "flagged cell missing methodology note" });
      continue;
    }
    if (!flagged) {
      if (typeof prior !== "number" || typeof e.priorDisclosed !== "number") {
        refused.push({ entry: e, why: "no prior-year tie proof (" + key + ")" });
        continue;
      }
      if (!tieOk(prior, e.priorDisclosed)) {
        refused.push({
          entry: e,
          why: "prior mismatch: model holds " + prior +
               ", disclosure comparative reads " + e.priorDisclosed +
               " — wrong row, restatement, or misread"
        });
        continue;
      }
    }
    accepted.push(e);
  }
  return { accepted: accepted, refused: refused };
}

// Subtotal law: group of entries whose values must sum to a disclosed
// total (segment sums, member rows). checks: [{keys:[...], totalKey}].
function checkSubtotals(valueByKey, checks) {
  var failures = [];
  for (var i = 0; i < checks.length; i++) {
    var ch = checks[i];
    var s = 0, ok = true;
    for (var j = 0; j < ch.keys.length; j++) {
      var v = valueByKey[ch.keys[j]];
      if (typeof v !== "number") { ok = false; break; }
      s += v;
    }
    var t = valueByKey[ch.totalKey];
    if (!ok || typeof t !== "number") continue;   // incomplete cone: no verdict
    if (!tieOk(s, t))
      failures.push({ totalKey: ch.totalKey, sum: s, total: t });
  }
  return failures;
}

/* @node-only */
if (typeof module !== "undefined")
  module.exports = { tol: tol, tieOk: tieOk, validateWritePlan: validateWritePlan, checkSubtotals: checkSubtotals };
