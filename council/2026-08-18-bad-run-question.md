# Question: run 22 missed every requirement — assess and rank the actions

The owner has stopped the line. Before ANY change is made, assess this
state strategically. Do not assume the next fix is a rule — the owner
explicitly suspects patch-reflex, and has been right twice before.

## The requirements (the owner's mindmap, condensed)

1. Model balances, all periods (or the residual named and marked).
2. Key numbers correct: sales + segment breakdown, GP + breakdown, NP,
   cash, CA/NCA/CL/NCL, equity, CFO/CFI/CFF. Full annual report =>
   NEVER back out keys; they are all printed.
3. Analyst adjustments honored (prior-year tie => likely no adjustment).
4. Segment rows: search multiple tables in all documents; terminal state
   stale+red-flag, never estimates.
5. Always deliver; wrong-unflagged is the one unforgivable output.

## Where 4 consecutive runs landed (same head lineage, ~40-46 min each)

| Run | Balance | Keys | Notes |
|---|---|---|---|
| 19 | PASS all years | NP exact; CFI/CFF twin open | best card |
| 20 | FAIL — truth-write exposed an inherited 12,116 BS reclass hole | NP 3,834 (slightly off) | honest but unbalanced |
| 21 | FAIL(6) | **NP corrupted to 3,969 (print 3,831) by MY new fixed-point writer** | first fixed-point run |
| 22 | FAIL(7) | NP still wrong; CFI/CFF still open; segments 16/33 | ingestion pass live |

## The self-inflicted disease (fully diagnosed)

I added deterministic "fixed-point reconciliation": any row where the
evidence oracle held a UNIQUE prior-anchored tie got auto-written to
print. The flaw: UNIQUE-IN-POOL != IDENTIFIED. Coincidental ties passed:
an interest row was written from a receivables-by-company junk table; the
net-profit chain took a +134 MI-sized hit. The verification oracle
(designed to SUSPECT on one source) was given WRITE authority, which the
deterministic join only ever earned with corroboration gates (kinship,
block ratification, twin-dropping, locality). The whole-page ingestion
pass (owner-approved, checksummed) then enriched the pool and amplified
the coincidence surface. The police caught every wrong write as findings
(nothing silent; runs restart from the clean base model) — but wrong
machine writes happened, violating requirement 5's spirit.

## Also structurally relevant

- The LEGACY stack had a pre-dispatch REGRESSION GATE: offline replay of
  bindings against a pinned baseline; ANY changed binding blocked
  release. The redesign LOST this. Run 21's NP corruption shipped
  undetected because nothing diffs a new head's writes against the last
  known-good run before spending an owner-hour.
- Remaining genuine model gaps: the 12,116 BS reclass hole (inherited,
  needs the destination row — no unique evidence anywhere); the CFI/CFF
  ±593 twin (item NAMED: bond issuance cash — agent flags rather than
  moves; model-side rows are formulas, so the fix must land in Raw
  detail rows which are printed land); segments 16/33 written, rest
  honestly flagged after multi-table search.
- 22 runs total; the packet architecture halved cost and killed
  trace-spam; behavior is honest; convergence QUALITY is the failure.

## The question

Rank the actions. Candidates (challenge or replace them):
A. Withdraw write authority from the oracle entirely (verification-only;
   fixed point becomes a findings generator for the agent) — accept
   slower convergence.
B. Keep machine writes with join-grade corroboration (e.g. >=2
   independent agreeing sources) — the owner suspects this is another
   patch.
C. Rebuild the pre-dispatch REGRESSION GATE (offline scoring of every
   head against pinned artifacts + headline-key panel) so no owner-hour
   is ever spent on a regressed head again.
D. Declare the remaining DFE gaps analyst-decision items, ship the
   flags, and move to CLP genericity.
E. Something structurally different we are not seeing (state it).

Constraints: pure gpt-5.6-luna; <60 min; generic across models; teach
thinking not compliance; no patches — design-level only; every
dispatched run costs the owner one hour, so the plan must minimize live
runs. Answer with a ranked action plan and what NOT to do.
