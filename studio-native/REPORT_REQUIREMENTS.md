# _REPORT tab — owner's requirements (recorded 2026-08-28)

The spec the agent must be taught. Source: owner, verbatim intent.

## Objective

An executive-readable summary page. "Easy to read and understand for
the analyst (or else they will just skip it)." No clutter. Insightful.
The whole summary is for an executive to read.

## Required content

**1. Earnings summary** — the key numbers, each shown as:
- change YoY (and QoQ, when the run is an interim period)
- actual vs our previous estimate (2025E vs 2025A)
- our new estimate vs the roll-forward (2026E before the update vs
  2026E after actuals flowed through)

**2. Reason for the change — THE KEY PART.** For each key number that
moved, a simple decomposition of why. Owner's example: "gross profit
increased by 200mn → +100mn from SG&A, +100mn from GPM increase."
A very simple showcase so the analyst gains insight, not just a delta.

**3. Key numbers that need the analyst's attention** — key uncertain
items and backed-out numbers.

## Implementation notes (design discussion 2026-08-28)

- Two-tier "why": (a) arithmetic P&L bridge computed deterministically
  by the kernel (ΔGP = ΔRev x prior GPM + new Rev x ΔGPM, and
  line-by-line bridges down the P&L); (b) narrative cause read by the
  agent from the disclosure's MD&A, always with a page reference,
  presented as the company's explanation — never invented.
- QoQ column appears only on interim runs.
- 2026E before-vs-after is pure flow-through (drivers are untouchable),
  and should be captioned as such — that IS the insight.
- Attention list: ranked by materiality, one row per cell (no
  duplication), broken checks first, then red, then orange, then key
  drivers. Capped; detail lists live below the executive screen.
- Banner keeps: verdict (DELIVERED / WITH EXCEPTIONS / STOPPED) +
  coverage line (X of Y lines updated).

## Block 2 ruling (owner, 2026-08-28)

Bridges as a simple calc table, not sentences — signed contributions
that sum exactly to the total (volume/margin split for GP; line walk
for NP; operating CF bridge only when it moved materially). Kernel
computes all numbers; agent contributes only the cited company
explanation line.

## Block 3 ruling (owner, 2026-08-28) — grouped by importance

1. **Balance & plugs** — the model must arrive balanced (the agent is
   forced to solve or plug it). Every PLUG made to balance the model
   is listed here so the analyst knows exactly where and can resolve
   it properly. Failing checks (if any survive) sit here too.
2. **Red** — key numbers the agent is highly unsure about (the
   operating-profit-definition example). Key numbers only.
3. **Orange** — backed-out key numbers.

Only the most important items in the top list. Everything else (minor
red/orange lines, key drivers not touching a key number, carried-over,
not-updated) goes in an "Other" part further down the tab.

## Note length ruling (owner, 2026-08-28)

Notes on the _REPORT page as short as possible — many cells, the
analyst cannot read paragraphs. A few words each; the cell link is
there for anyone who wants the detail.

## Division-of-labour ruling (owner, 2026-08-28) — FINAL DESIGN LOCK

Layout approved (banner / snapshot / why it moved / attention tiers /
other line). Split of work:

- **Script builds the format** — layout, links, live values, colors.
- **The AGENT'S BRAIN composes the content** of "Why it moved" and
  "Needs your attention": which lines are the key drivers of the
  change, what the bridge lines are, how each attention item is
  phrased. This is deliberate — reasoning adapts to different models
  and different teams; a hardcoded bridge recipe would not.
- Kernel still REFEREES the agent's content: every bridge must sum to
  its total, every cited number must match the model/staging; refuse
  what does not tie. Teaching over code, referee keeps it honest.

## Scope ruling (owner, 2026-08-28)

"Why it moved" covers more than profit: also the balance sheet
(what moved assets/liabilities) and the cash flow statement. The agent
judges which BS/CF moves matter for THIS company this period.

## Snapshot & bridge scope rulings (owner, 2026-08-28, second pass)

- Top section renamed **"Key number snapshot"** — the key numbers are
  EXACTLY the mindmap objective list (BOSS_MINDMAP.md): sales (+
  segmental breakdown), gross profit (+breakdown), net profit, cash,
  current & non-current assets and liabilities, equity, operating /
  investing / financing cash flow.
- **"Why it moved" selection is the agent's REASONING AND JUDGMENT —
  never a mechanical word search.** The agent thinks about what
  actually drove the change and names those drivers.
- Bridge scope: **P&L key numbers get a bridge EVERY time.** Non-P&L
  key numbers (BS & CF) get one only when the move is significant —
  **threshold ~20%** — e.g. current assets flat → no bridge; operating
  cash flow down 80% → the analyst must know what drove it. Skipped
  lines are named so the omission reads as deliberate.

## v3 rulings (owner, 2026-08-28)

- **Executive formatting**: a management presentation readable in 1
  minute — generous spacing, soft colour tones, nothing clustered.
- **Bridge lines are FORMULAS**, referencing the model/raw rows they
  came from, so the analyst can trace every walk line back into the
  model. Each bridge's residual line is a self-balancing formula
  (= anchor − SUM(lines)), so the walk always ties AND shows itself
  as the remainder.
- Confirmed: current DFE page is a Fable-built prototype; Luna
  generates it only after the layout is signed off and the generator
  is ported into the agent.
- v3 addendum (owner): NO detail tab — nobody reads it. The _REPORT
  page is the only report; everything else stays as colour-marked
  cells in the model itself.

## Boss feedback round 1 (owner, 2026-08-30) — mini-P&L old vs new

After the boss review of the page:
- New **section 2 · Mini P&L** (snapshot stays section 1; bridges move
  to section 3): a fixed Core-8 item list — revenue, gross profit,
  GPM%, operating profit, net profit, NPM%, EPS, DPS — spanning FY-1
  to FY+3 **in the model's own forecast grain** (halves/quarters when
  that is what the model forecasts).
- Shown twice, side by side: **OLD** (the archived pre-update model,
  static values) vs **NEW** (live formulas into the updated model),
  with a **WHAT'S CHANGED** table next to them: % change for values,
  pp change for margins, absolute for per-share; big moves tinted.
  Purpose: the boss reviews the whole forecast path — an update that
  quietly bent the out-years shows up immediately.
- Next planned stage (owner): the agent READS the Δ table and
  sense-checks its own update — investigates any change it cannot
  justify. The Δ table is built machine-readable for exactly this.

## Boss feedback round 2 (owner, 2026-08-30) — mini-P&L refinements

- Block order: **WHAT'S CHANGED leftmost → NEW → OLD**, one spacer
  column between the three tables.
- A **roll-over sanity flag** per line, next to the Δ block, comparing
  the updated period's Δ against the NEXT forecast period's Δ:
  (a) **sign flip** (2025A up vs old E but 2026E down vs old E =
  suspected bad roll-over), (b) **big gap** between the two Δs
  (>30pp for values). Live formulas so they keep watching.
- **Header roll-forward**: after marking a period to actual, the
  period header must roll like the rest of the column — prior actual
  column's header FORMAT copied across, stale duplicated header text
  (e.g. Raw financials!U1 still `2024-12-31`) advanced. NOTE: a
  literal `2025E` header on an actual-vs-estimate comparison panel
  (Model!AC2, where AC holds the frozen estimate) is CORRECT and must
  not be renamed.
