# MODEL_SPEC — CLP Holdings (2 HK)

> Design contract for this model. Drafted from the FY2025 update session (pre/post model diff + Claude-in-Excel transcript). Analyst to review and correct.

## 1. Model basics

- File: `model/CLP Model - Claude Fable 5.xlsx`
- Fiscal year end: 31 Dec. Full detail (segment notes, SoC 5-yr statistics, project capacity table, note 13 amortisation, note 30A CF reconciliations) is in the **Annual Report**; the results presentation carries segment EBITDAF waterfalls and tariff charts.
- Currency/units: **HK$ million**. Per-share HK$; tariffs HK cents/kWh; capacity MW; generation GWh; gas TJ.
- Sheet map:
  - `Final` — consolidated P&L + BS + CF (primary statements)
  - `Driver` — segment earnings rollup + BS roll-forward engine (NFA, JV/associates, debt) feeding forecasts
  - `SOC`, `SOC Accounts`, `HK Sales`, `ROAFNA` — HK Scheme-of-Control regulated block
  - `CN`, `Aus`, `India`, `SEA` — regional segment sheets (local currency, FX rate in row 2)
  - `DCF` — valuation, **calculation-only, never edit** (pre-existing `#REF!` at row 130 is known; leave as-is)
  - `VA-Disclaimer` — untouched

## 2. Layout conventions

- Time axis: columns, one per year, uniform across all data sheets: **AC=2019 … AG=2023, AH=2024A, AI=2025A, AJ=2026E … AN=2030E**. Year header: row 2 on Final/SOC/HK Sales/ROAFNA; row 1 on Driver/CN/Aus/India/SEA/SOC Accounts. Row labels sit in frozen left columns A–F.
- Actuals end at AI; AJ onward are forecasts ("E" suffix). Actual-year headers are **plain numbers** (`2025`, never `2025A` text — DCF references the year numerically; text breaks discount math).
- **Mark-to-actual recipe**: copy the prior actual column's formulas + formats across into the target column, then overwrite only the disclosed input values. Rewrite any formula embedding a prior-year numeric constant with the new constant, preserving structure. No blanket font-color scheme — each row keeps whatever font the prior actual column used.
- Flag colors (house convention): **orange fill `FFC000`** = backed-out/derived (as formulas, awaiting true-up); **light-red fill `FFC7CE`** = uncertain/needs analyst review. Methodology note on flagged cells; notes otherwise only on material inputs.
- **Sign convention: `Final` balance sheet stores liabilities as POSITIVE numbers.** Check stored signs before writing.
- Restore calc mode to Automatic before delivery.

## 3. Drivers & logic

- `Driver` rows ~30–36 pull regional JV/associate earnings from CN/Aus/India/SEA sheets.
- `Driver!AI70:AI71` = net fixed asset base; the forecast BS chains off it — **re-anchor to the actual closing NFA** after marking to actual (FY25: net 176,128 / −143,161−370).
- Regional sheets convert via FX in row 2 (`Aus!AI2` AUD avg, model style is reciprocal e.g. `=1/0.19865`; `India!AI2` INR; CN RMB). Repoint chained FX formulas to disclosed average rates; flag red if not disclosed.
- After writing actuals, scan the first forecast column for one-off/non-cash items that shouldn't propagate (FY25 example: `Final!AJ107` hedging −352 reset to 0 so 2026E+ balanced).

## 4. Back-out rules (when detail is missing)

| Item | Method |
|---|---|
| HK tariff (`HK Sales` row 13) & FCA (row 16) | **Disclosed** in AR 5-yr SoC statistics (~p260). Use directly; NEVER derive from revenue/volume. |
| `HK Sales` rows 7–8 (SoC revenue / sundry) | Row 8 = `SOC!AI4`; row 7 = row 8 − row 6. Mirror the **2023** formula pattern. |
| `SOC Accounts` row 58 (Black Point / Castle Peak power sales) | Scale by disclosed "gas consumed for power generation" ratio (AR ~p238), replicating prior-year method. Never free-calculate. |
| CN capacity (rows ~125/132/135) | **Bottom-up** from AR project table (~p263): sum CLP-share capacity of in-operation projects (JV-only stakes at equity share). Never roll forward top-down. |
| Amortisation splits (China/Aus) | AR note 13; plug to segment D&A total. |
| Aus gas-plant generation volumes (rows 62–63, 71–74) | Not disclosed — estimate and flag red. |
| Year-end FX rates not disclosed | Estimate, flag red (analyst hand-sets; e.g. FY25 India FX set to 0.09401). |

## 4b. Cell-level rules learned from replay validation (FY25)

- **FX rows**: `Aus!AI2` — KEEP the model's existing assumption (do not repoint to disclosed avg; analyst kept 5.1462). `SEA!AI2:AI3` — carry prior year via formula (`=AH2`/`=AH3`), do not hardcode disclosed rates. `India!AI2` — analyst hand-sets; flag red.
- **HK Sales rows 7–8**: apply the 2023 formula pattern to BOTH the prior year (AH) and current year (AI) — the 2024 column needs restating to the same pattern.
- **CN capacity block**: bottom-up-from-AR rows are 125/132/135 ONLY. Rows 128 and 136 carry prior year (`=AH…`); rows 143/147 stay 0. Do not fill every capacity row.
- **`Aus!AI9`**: carry (`=AH9`), not a hardcode.
- **`Final!AJ16`**: keep `=AI16` (one-off gains DO propagate here per analyst practice); the reset-to-0 rule applies to `AJ107`-type hedging only.
- **`Driver!AI127`**: the FY25 reference model held `=-1659-15` (−1,674) — analyst confirmed this was a MISTAKE in the reference; the correct disclosed value was −1,762 (as the replay computed). No special rule; map from disclosure normally.
- **`India!AI37`**: first component is the segment-note figure (FY25: 923), check mapping. **`India!AI60`**: references AF (deliberate quirk), don't re-pattern to AH.
- **CF line allocation** (`Final` rows 124/127 and 135/136): perpetual/NCI dividend terms sit in row 135; small adjustments (−4 type) in row 124 — match analyst allocation.

## 4c. Additional cell-level rules (learned FY25 full-model rebuild, Aug 2026 run)

- **`CN!AI2` RMB/HKD**: KEEP the model's existing assumption (analyst kept 1.07711 vs disclosed avg 1.08715) — same ruling as `Aus!AI2`. Of the four regions, only SEA carries via formula; CN/Aus keep stored assumptions; India avg (`India!AI3`) is analyst hand-set (FY25: 0.0933 vs disclosed 0.08936).
- **CN 2025-column formula rewrites** (analyst practice, not pristine roll-forward): `AI8=SUM(AI4:AI7)`; `AI11=AI9-AI10` (NEVER leave pristine `=AI158` — combined with `AI158=AI11` it goes circular); utilisation rows back-solve from earnings: `AI79:AI81,AI83:AI84,AI87 = =AI2x/AI6x/AI$2` pattern; `AI35`, `AI86`, `AI88` = 0.
- **Aus plant capacities rows 58/59/61**: update as hardcodes from AR project table (FY25: Yallourn 1,480 / Mount Piper 1,430 / Hallett 235).
- **Aus generation rows 69–70 (Yallourn / Mount Piper)**: DISCLOSED in the AR "generation performance" table (~p18) — map directly, no flag (FY25: 7,087 / 6,314 GWh). Rows 71–74 remain undisclosed: carry prior year, red-flag.
- **Open analyst question (FY25 reviewer)**: the §4b keep-assumption FX rulings leave actual-year segment FX at odds with disclosed averages (Aus 5.034, CN 1.08715, India 0.08936, SEA 0.2504/0.2378) — confirm the rulings apply to actual columns; also re-check hand-set `India!AI2` YE 0.09401 (reviewer: INR ended 2025 nearer 0.087–0.089).

## 5. Known quirks & landmines

- `Final` liabilities stored positive (see §2).
- Prior-year hardcodes can themselves be wrong — validate the prior actual column balances before trusting the new year's check (FY24 `ROAFNA!AH19` was mis-built; correct is `=36+5487` per AR p250).
- SEA segment: components must reconcile to the segment note (FY25 note EBITDAF 181 / earnings 179 caught a −63 vs −66 opex error).
- `DCF`: hundreds of cells change on recalc — normal; zero formula edits allowed there.

## 6. Tie-out anchors (must match disclosure exactly)

- P&L: PBT, net profit, profit attributable to shareholders, operating earnings, EPS (FY25: 14,201 / 11,546 / 10,468 / 10,909 / HK$4.14)
- BS: total assets (FY25: 238,644); **`Final!AI99:AN99` balance-check row = 0 for every actual AND forecast year** — the primary integrity gate
- `ROAFNA` row 31 check = 0 for all recent years
- Segments: HK energy operating earnings (FY25: 9,418); SEA EBITDAF/earnings; CN total operational capacity (FY25: 6,934 MW); SOC Accounts Black Point / Castle Peak GWh (FY25: 14,534 / 9,412)
- DCF recomputes without new errors; `Final!AD1` tie to DCF output intact
