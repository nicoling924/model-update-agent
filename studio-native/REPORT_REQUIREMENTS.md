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
