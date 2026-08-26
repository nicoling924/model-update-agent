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

Notes for the two JSON glue steps (5 and 6): use the expression editor's
`concat()` to wrap the Agent's output into the STAGE input, or add a
small **Compose** node — the assembly photos in `assembly-photos/`
(coming with the kit) show the exact clicks.

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
