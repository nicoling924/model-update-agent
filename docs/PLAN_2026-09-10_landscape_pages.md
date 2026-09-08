# Plan — landscape pages and roll-forward schedules (night of 2026-09-10)

Owner's brief: "having a rotated page is very common among financial reports … make sure the agent can read
normal portrait pages and also landscape pages", then map the Driver-tab PP&E / CIP / intangible schedules
that only print one year of movements.

## 0. What is true today (measured)

| Fact | Evidence |
|---|---|
| DFE 2025 annual report: 43 of 280 pages are landscape (PDF rotation 270°) | pdfplumber page.rotation; pages 153–193 incl. segment note, fixed assets p184–185, CIP p187–190, intangibles p192–193 |
| CLP 2025 documents: 0 landscape pages | same check on all four CLP PDFs |
| On landscape pages the text layer is intact but characters run vertically; the extractor lines them up on the wrong axis and every string comes out reversed | p184: "53.552,755,368,81" is 18,863,557,255.35 backwards; chars carry `upright=False`, constant x, decreasing y |
| Consequence: the ledger holds no usable lines from those pages; the reader (Luna) gets the same broken text; the Driver schedule is held at last year's values (red) and depreciation is plugged (−257.86, a 5% rate vs 15% last year) | run 34196724937 Driver rows 95–107 |
| The schedules ARE fully printed for 2025 — hand-mapped answer key in §5 | p184, p185, p187, p191, p192–193 |

Two faults, in order: (1) reading — rotated pages are unreadable; (2) mapping — a movement table has no
prior-year column, so the horizontal prior tie can never fire on it.

## 1. Phase 1 — read landscape pages (stage 1)

Rule (generic, no fence): *a page is read in its displayed orientation.* The PDF says how it is displayed
(`/Rotate`), and every character carries its position and an upright flag; that is the evidence.

Steps
1. `stage1_read.page_texts`: when `page.rotation` is 90 or 270, rebuild lines from character geometry —
   cluster characters on the fixed axis (that is a line), order them along the running axis in the direction
   the rotation implies, order lines top-to-bottom in the displayed frame; join characters into words by gap.
   180°: reverse both axes. Portrait pages: current path, untouched.
2. Vision path (`_page_image` / stage-1 votes, the reader's page images): rotate the rendered image by the page
   rotation before it is sent, so a scanned landscape page is seen as landscape.
3. Cache: the text cache is keyed by content hash — add an extractor version to the key so the 43 pages are
   re-extracted, not served from the old cache.
4. The reader stage and the gap reader get the corrected text for free (both read through `page_texts`).

Proof (before Phase 2 starts)
- Museum exhibit on the real DFE page 184: the extracted lines must contain
  `（1）上年年末余额 17,915,996.06 7,375,145,834.43 9,030,745,014.97 330,302,283.92 2,109,448,125.97 18,863,557,255.35`
  (numbers left-to-right as printed, total last) and the page header reads `东方电气股份有限公司`.
- Count of numeric lines from the 43 landscape pages before/after (today: ~0 usable).
- Portrait regression: the DFE and CLP text extractions for every non-rotated page are byte-identical
  before/after (the change must not touch them).
- Bench + the four offline floors delivered.

Expected side effect worth watching: the DFE segment note (landscape) becomes readable, so the Driver segment
rows (Wind / Hydro) that varied run to run should find printed lines with a prior tie.

## 2. Phase 2 — the vertical prior tie (stage 2 walk)

A movement table prints one year: rows = opening / increases / decreases / closing, columns = asset classes,
last column = total. It has no prior-year column, but its **opening row is last year's closing** — the prior tie
runs down the page instead of across it.

Rules (each an evidence rule, each pinned)
1. **Identify the block by the opening tie on the total column.** A table whose opening row's total equals a
   model prior (the prior-year *ending* cell of a schedule block) is that block's movement table. The class
   columns are a matrix and are never paired; only the total column is read. (DFE: cost opening 18,863.56 vs
   model 18,863.33; accumulated depreciation 13,244.44 vs 13,244.38; CIP 1,427.33 exact; intangibles + ROU
   2,479.38 exact by composition.)
2. **Discover the model's block from its formulas.** A schedule block is a Beginning cell that links to last
   year's Ending, movement rows, and an Ending that sums them (or = beginning + rows). No labels needed to find
   the shape; labels only name the roles.
3. **Map rows by role, not by name.** Roles: opening, increase, decrease, closing. A printed sub-line lands in
   the model row whose *last-year value* it reproduces (购置 211.93 → Addition; 在建工程转入 1,053.09 → Transfer;
   the same trick as the horizontal tie, applied to the 2024 sub-lines when the prior-year report is on hand),
   else by kinship of role words (购置/增加 → addition; 转入 → transfer; 处置/报废/减少 → disposal; 计提 → charge).
   Sub-lines with no model row (其他) ride with the nearest role and are named in the note. Sign follows the
   model's convention (its 2024 disposal is negative).
4. **Compositions from sums of openings.** When no single opening ties the model's prior but a sum of two
   blocks' openings does (无形资产 1,924.69 + 使用权资产 554.69 = 2,479.38), the model row is the composite and
   its movements are the sum of both blocks' movements (amortisation 158.40 + ROU depreciation 152.71).
   Likewise 2024 impairment 122.11 = 128.29 − 固定资产清理 6.18 tells that the model nets the disposal account
   into the impairment line.
5. **Verify down and across, then decide the colour.** Opening + increases − decreases must equal the printed
   closing (own-table check); the block's net must reach the balance sheet through the model's own check row.
   Opening ties exactly and the arithmetic closes → served plain. Opening differs (a restated prior) → served,
   red on the Beginning cell with the difference named ("report opens at 18,863.56; model closes 2024 at
   18,863.33"), never forced, never a pause (the statements' comparatives are not what changed).
6. **Never a plug when the schedule is printed.** The ladder's depreciation plug (−257.86) and the held
   additions disappear because the rows are served before the ladder runs.

Proof
- Museum exhibit: a fixture of the DFE PP&E block + a synthetic movement table; expected values from §5.
- Offline: rebuild the DFE FY25 ledger locally (text only — these pages need no vision), replay, compare Driver
  rows 94–122 against §5 (tolerance: the printed closings; the 0.22 / 0.06 opening differences show as red
  notes, not as errors).
- Live: one DFE annual run; CLP annual as the regression check (its path must not change: zero rotated pages).

## 3. Sequence tonight

1. Phase 1 build → exhibit → portrait byte-identity check → bench → four floors → commit.
2. Rebuild the DFE FY25 ledger offline with the new stage 1; report how many landscape lines now carry numbers
   and which Driver rows the existing laws already serve (the segment note may serve rows before Phase 2).
3. Phase 2 build → exhibit → bench → floors → offline replay against §5 → commit.
4. Live: DFE FY25, then CLP FY25. Grade; morning report.

Walk-away rule applies: if Phase 2's role mapping needs a judgment the evidence does not settle, the row is
served red with the candidates named, and the run still delivers.

## 4. Questions to brainstorm before I start

1. **其他 (other) movements** — ride with Addition / Disposal as proposed, or a separate red memo? (Proposal:
   ride, note them.)
2. **企业合并增加 / 在建工程转入 printed as one line (1,712.24)** — Transfer from CIP takes it all, so CIP
   additions absorb the difference (1,508.23). The CIP note's own 本期转入固定资产 column (p189–190) could split it
   — worth the extra mapping, or a note? (Proposal: note this year; map the CIP project table later.)
3. **Restated opening (0.22 on cost)** — red note on Beginning as proposed, or restate the model's 2024 column
   to the report's opening? (Proposal: note; the 2024 statements did not change.)
4. **Depreciation charge vs total increase** — the model has one Depreciation row; the note prints 计提 849.36 and
   其他 4.61. Serve the total (853.97, closes the roll) or the charge (849.36, the P&L number)? (Proposal: total,
   note the split — the roll must close; the P&L D&A row has its own tie.)
5. **Colour of a served movement row** — plain when the opening ties exactly and the roll closes? Or always
   orange because no comparative column exists? (Proposal: plain — the vertical tie *is* a comparative.)
6. Anything else in the DFE Driver tab you want treated as a schedule (working-capital days, borrowings roll)?

## 5. Answer key — DFE Driver 2025 (RMB m), hand-mapped from the 2025 annual report

| Row | Value | Source |
|---|---|---|
| J94 Gross PPE beginning | 18,863.33 (= I98; report opens 18,863.56) | p184 |
| J95 Addition | 249.56 (购置 244.41 + 其他 5.15) | p184 |
| J96 Transfer from CIP | 1,712.24 (在建工程转入/企业合并增加) | p184 |
| J97 Disposal | −607.39 (处置或报废 322.91 + 其他 284.47) | p184 |
| J98 Gross PPE ending | 20,217.74 (printed 20,217.97) | p184 |
| J101 Acc. dep. beginning | −13,244.38 (report 13,244.44) | p184 |
| J102 Depreciation | −853.97 (计提 849.36 + 其他 4.61) | p184 |
| J104 Disposal | +434.56 (处置 254.55 + 其他 180.01) | p184 |
| J105 Acc. dep. ending | −13,663.79 (printed 13,663.85) | p184 |
| J107 Impairment | −88.69 (减值 100.68 − 固定资产清理 11.99) | p185, p186 |
| J108 Net PPE | 6,465.26 (BS 6,465.43; check row rounds to 0) | p95 |
| J103 Depreciation rate | 15.5% (2024: 15%) | derived |
| J112 / J115 CIP beginning / ending | 1,427.33 / 1,223.32 (exact) | p187 |
| J114 / J113 CIP transfer / addition | −1,712.24 / 1,508.23 | derived |
| J118 / J122 Intangibles+ROU beginning / ending | 2,479.38 / 2,473.44 (exact) | p95 |
| J119 Amortisation | −311.11 (无形资产 摊销 158.40 + 使用权资产 折旧 152.71) | p192, p191 |
| J121 Increase in intangibles | 305.17 | derived |
