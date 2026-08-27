# Phase 1 assembly guide — Studio-native Model Update Agent

Everything you paste comes from this kit. Nothing here needs IT, admin
rights, or anything outside Copilot Studio + SharePoint + Excel Online.
Budget: ~45 minutes of clicking, once.

**What Phase 1 proves** (council-set success bar): the plumbing runs
end-to-end, and — the important half — **a bad number cannot get in.**
If the AI misreads the PDF, the kernel refuses the write and turns the
cell red instead. If it cannot refuse a bad write, we do not build
Phase 2.

## Piece 1 — the kernel script (10 min)

1. Open any Excel file **in the browser** → **Automate** tab →
   **New script**.
2. Delete the sample code, paste the ENTIRE contents of
   `dist/kernel.paste.ts`, rename the script **Model Update Kernel**,
   Save.

That's the whole "install". One script, four modes — the flow tells it
what to do each call: `PREFLIGHT` (learn the model), `STAGE` (receive
what the AI read), `APPLY` (referee + write + flag), `POLICE` (recalc +
balance verdict).

## Piece 2 — the test workbook (5 min)

1. In your SharePoint/OneDrive, make folder `ModelAgent/` with
   subfolders `models/` and `runs/`.
2. Put the practice model in `models/` (Phase 1: the one-sheet DFE
   practice copy — or any model sheet with a year header row and a
   prior actual column).

## Piece 3 — the flow (25 min)

Workflows → New workflow → name it `model-update-phase1`.

| # | Node (search this) | Set it to |
|---|---|---|
| 1 | **Manually trigger a flow** | (Phase 1 trigger; SharePoint trigger comes later) |
| 2 | **Copy file** (SharePoint/OneDrive) | `models/<model>.xlsx` → `runs/`, new name — every run works on a CLONE, never the live model |
| 3 | **Run script** (Excel Online Business) | file = the clone from step 2, script = Model Update Kernel, `input`: `{"mode":"PREFLIGHT","sheet":"Model","periodKind":"FY","targetYear":2025}` |
| 4 | **Agent** | the extraction step — paste the prompt from `prompts/extract.md`, attach the disclosure PDF (Phase 1: the 2-page P&L). Its output is a JSON array of rows. |
| 5 | **Run script** | same file/script, `input`: `{"mode":"STAGE","rows":` + Agent output + `}` |
| 6 | **Run script** | `{"mode":"APPLY","sheet":"Model","targetYear":2025}` |
| 7 | **If/Else** on step 6 result: `refused > 0` or `unmappedLabels` non-empty | THEN → **Start and wait for an approval** (Human review): paste the `refusals` text into the approval body — this is the analyst-ruling moment. |
| 8 | **Run script** | `{"mode":"POLICE","sheet":"Model"}` |
| 9 | **If/Else** on step 8: `ok == true` | THEN → post/email "DELIVERED + link to the clone". ELSE → "FAILED BALANCE — check rows: ..." with the `failed` list. **A failing POLICE never announces success.** |

The one fiddly step is 5 (wrapping the Agent's output into the STAGE
input). In the `input` box of step 5's Run script, switch to the
expression editor (fx) and enter:

    concat('{"mode":"STAGE","rows":', outputs('Agent')?['body/text'], '}')

(pick your Agent step's text output from the dynamic-content list if the
path autocompletes differently — the goal is simply
`{"mode":"STAGE","rows": <the Agent's JSON array> }`). If the expression
fights you, photograph the screen and send it — one look is enough.

## What to look at after a run

Open the clone in `runs/`:
- Target column filled; refused/uncertain cells **red**, backed-out
  cells **orange**.
- Hidden sheets (right-click a tab → Unhide): `_ANATOMY` (what the model
  expects), `_STAGING` (what the AI read), `_PLAN` (every verdict with
  its reason), `_LEDGER` (every touched cell, before/after).
- `_PLAN` is your review page for Phase 1 — REFUSE rows show exactly why
  a number was rejected.

## Phase 1 acceptance test (do this before trusting anything)

Run twice:
1. **Honest run** — real 2-page P&L. Expect: values land, POLICE ok.
2. **Sabotage run** — edit one number in the Agent's output (step 4→5)
   to a wrong value, e.g. change the prior-year comparative of Revenue
   by 2. Expect: that row is REFUSED, the cell turns red, `_PLAN` names
   the mismatch. **If the sabotage gets through, stop and report — do
   not proceed.**

## Explicitly NOT in Phase 1 (council ruling — resist the temptation)

300-page documents, notes/segments, restatements, roll-forward,
interim panels, multi-sheet, k=2 double-checking, live-file runs.
Phase 1 is the referee's proof, not the product.

---

# Phase 2 — what changed (2026-08-26)

Phase 1 passed in your tenant: the sabotage was refused, and the real
Dongfang P&L run wrote 10 lines with zero bad numbers. But 55 of the 65
lines you read never found a home, because Phase 1 matched labels
letter-for-letter. Phase 2 fixes that and adds the two things a real run
needs. **The paste-in step is the same: replace the script with the new
`dist/kernel.txt` and save.** Nothing else in your setup changes.

**1. The mapping cascade.** A disclosure line now finds its model row
four ways, strongest first: the same label · the same label once
`其中：` / `一、` / `减：` / indentation are stripped · **the prior-year
figure** (if the model holds 3,009.01 on exactly one row and your
comparative reads 3,009.01, that is the row — no name needed) · finally
your own row number, if you gave one. If two rows could match and the
prior-year figure does not single one out, it maps nothing and tells
you — it never guesses. One model row can only be claimed once.

**2. The restatement full stop.** New call `{"mode":"RESTATE"}` after
STAGE. It compares every comparative you read against the model's
history. Three or more disagreements = the past changed: the run stops,
a visible **_RESTATE** tab shows the analyst exactly which lines and by
how much, and APPLY refuses to write anything until a human rules. This
is your boss's rule, enforced in code rather than in a prompt.

**3. Three statements in one run.** PREFLIGHT now takes
`"sheets":["Model","BS","CF"]` and remembers each; APPLY runs once per
sheet; POLICE sweeps them all — and it now checks the balance rows in
the prior year as well as the new one, so a model that arrived broken
says so.

**4. Refusals no longer quote the model back at you.** The agent is told
"this comparative does not tie — re-read the row", never the model's own
figure. An agent that is shown the number it failed to match can simply
echo it back and walk through the referee. The full detail still goes to
`_PLAN` for you.

**Updated Instructions for the agent** are in `prompts/instructions.md`
— paste the whole file into the agent's Instructions box, replacing what
is there.

Order of a Phase 2 run: PREFLIGHT → read → STAGE → **RESTATE** → APPLY
(per sheet) → POLICE → report.

---

# Phase 3 — the analyst's page and the model's memory

**5. `_REPORT`.** New call `{"mode":"REPORT"}` at the end. It writes a
visible **first tab** so the workbook opens on it, with four sections —
what needs your ruling (red), what was derived (orange), every line that
moved more than 50% year on year (a mapping-error scan), and **your own
forecast against the actual**, biggest lines first. Every line is a
clickable link sitting next to that cell's live value.

The forecast comparison only works because PREFLIGHT now photographs
your estimate for the target year *and* the year after, before anything
is overwritten. It also shows how next year moved once the actuals
flowed through.

**6. `_SPEC` — the model remembers.** A hidden text tab inside the
workbook. When the agent has to reason out a mapping (the report calls a
line "Turnover", your model calls it "Revenue"), that decision is saved
as `ALIAS | Turnover | Model | Revenue`, label to label — never a row
number, because you insert rows and labels survive that. The next run
looks there first, so a model gets faster and steadier the more it is
used. No central database; the memory travels inside the file.

**7. No check row = not verified.** If a model carries no balance-check
row, POLICE now says so instead of returning a quiet pass.

Full run: PREFLIGHT → read → STAGE → RESTATE → APPLY → POLICE →
**REPORT**.

---

# Phase 4 — real models: wiring, hardcodes, and the missing column

Testing on your actual Dongfang model taught us three things the practice
file could not.

**8. Some sheets have no column for the new year.** `Raw financials`
holds reported history only, so there is no 2025 column to write into.
PREFLIGHT no longer fails on that — it comes back with a **proposal**
naming the sheet, the last year, and the exact column that would be used.
The agent must ask you in chat, and `EXTEND` refuses to add anything
unless the answer comes back as `analystApproved: true`. The new column
copies the previous year's **formats only** — never its numbers, because
a blank cell reads as "not filled in yet" while last year's number
copied forward reads as this year's actual.

**9. A formula is never typed over.** On a wired sheet, rolling the
column forward makes the 2025 formulas point at the 2025 source
automatically. The kernel leaves them alone and instead **checks what
they compute against the disclosure**. If they disagree, the cell turns
red and the run reports a `conflict` — usually meaning the source sheet
has not been updated yet.

**10. Hardcodes are the normal case, and there are two kinds.**
- *Typed numbers* are input slots — the actual is written straight in.
  Any that this disclosure did not cover are listed in the report as
  "not updated this period" (your boss's rule: no cell flag, but never
  silent).
- *Numbers baked inside formulas* (`=Raw!E12+36`) are the **key
  drivers** your boss's mindmap asks for. Rolling the column forward
  carries last year's constant into this year, where it is invisible.
  Every one of them is flagged red and listed in the report's KEY DRIVERS
  section with the formula spelled out, so you can judge it. The agent
  never rewrites a formula's insides on its own.

The `_REPORT` tab now has six sections: red rulings · orange back-outs ·
key drivers · not updated this period · big moves · your forecast vs the
actual.

---

# Phase 5 — external links, and errors that were not ours

Your real model pulls from other workbooks ("Trust workbook links?").
Nobody can promise Microsoft will resolve every one of those after a
copy — so the kernel now proves it instead.

**11. A health baseline, taken before anything is touched.** PREFLIGHT
counts, per sheet, how many formulas reach outside the workbook and how
many cells are already showing `#REF!` / `#VALUE!`. Both numbers come
back in the reply.

**12. A sweep at the end.** POLICE re-scans and compares:
- an error that was already there → reported as pre-existing, does not
  fail the run
- an error copied forward into the new column from a row that was
  already broken → also pre-existing
- an error in a cell that was **healthy before** → **the run FAILS**,
  names the cells, and says the model must not be delivered

So a broken link cannot slip through quietly, and a link that was already
broken never gets blamed on the agent.

**Practical note on copies:** copy the model *inside* OneDrive
(right-click → Copy). Links are stored as absolute addresses, so a copy
made that way still points at the same source workbooks. Uploading a file
from a laptop is the risky path — that is when links break. Either way,
the run now tells you.
