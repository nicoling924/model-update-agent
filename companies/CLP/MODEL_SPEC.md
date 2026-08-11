# MODEL_SPEC — CLP Holdings (2 HK)

> Design contract for this model — STRUCTURAL knowledge only. Deliberately contains
> no current-period disclosed figures, so every update run must source all numbers
> from the attached disclosures alone (benchmark fairness).

## 1. Model basics

- Fiscal year end: 31 Dec. Full detail (segment notes, SoC 5-yr statistics, project
  capacity table, amortisation note, CF reconciliation note) is in the **Annual
  Report**; the results presentation carries segment EBITDAF waterfalls and tariff
  charts.
- Currency/units: **HK$ million**. Per-share HK$; tariffs HK cents/kWh; capacity MW;
  generation GWh; gas TJ.
- Sheet map: `Final` consolidated P&L+BS+CF · `Driver` segment rollup + BS
  roll-forward engine · `SOC`/`SOC Accounts`/`HK Sales`/`ROAFNA` HK Scheme-of-Control
  block · `CN`/`Aus`/`India`/`SEA` regional sheets (local currency, FX in top rows) ·
  `DCF` valuation, calculation-only, never edit (pre-existing #REF! at row 130 is
  known; leave as-is) · `VA-Disclaimer` untouched.

## 2. Layout conventions

- Time axis: one column per year, uniform across data sheets; actual-year headers
  are **plain numbers** (never "2025A" text — DCF reads the year numerically).
- Mark-to-actual recipe: copy the prior actual column's formulas + formats into the
  target column, overwrite only disclosed inputs, and REWRITE any formula embedding
  a prior-year numeric constant.
- **Sign convention: `Final` balance sheet stores liabilities as POSITIVE numbers.**
- Flag colors: orange FFC000 = backed-out/derived; light-red FFC7CE = uncertain.
- Model ships in manual calc with full-recalc-on-load.

## 3. Drivers & logic

- `Driver` rows ~30–36 pull regional JV/associate earnings from regional sheets.
- `Driver` rows 70–71 = fixed-asset base (gross cost + ROU; accumulated
  depreciation) — re-anchor to actual closings from the AR fixed-asset note after
  marking to actual; the forecast BS chains off them.
- Regional sheets convert via FX in the top rows. House FX rulings: `Aus` and `CN`
  KEEP the model's stored assumption (do not repoint to the disclosed average);
  `SEA` carries prior year via formula; `India` average is analyst hand-set and the
  India year-end rate is hand-set + red-flagged (never disclosed).
- After writing actuals, scan the first forecast column for one-off actual-year
  items that must not propagate (hedging/FV-derivative row on `Final` resets to 0);
  the one-off gains row on `Final` (row 16 area) DOES propagate per analyst practice.

## 4. Back-out rules (when detail is missing)

| Item | Method |
|---|---|
| HK tariff & fuel-cost-adjustment rows on `HK Sales` | Disclosed in AR 5-yr SoC statistics — use directly; NEVER derive from revenue/volume. |
| `HK Sales` SoC revenue / sundry rows | Sundry = SoC total revenue − electricity sales (2023 formula pattern; apply to prior column too). |
| `SOC Accounts` Black Point power sales | Scale prior-year GWh by the disclosed group "gas consumed for power generation" ratio; Castle Peak = own sent-out − Black Point. |
| CN capacity block | Bottom-up from the AR project table, CLP-share of in-operation projects; bottom-up rows only — others carry prior year; under-construction rows stay 0. |
| Amortisation splits (CN/Aus) | AR amortisation note; plug to segment D&A totals. |
| Aus per-plant gas generation volumes | Coal plants are disclosed in the AR generation table; gas/wind rows are not — carry prior year and flag red. |

## 5. Known quirks & landmines

- Prior-year hardcodes can themselves be wrong — validate the prior actual column's
  balance checks before trusting the new year's (a known mis-built FY24 cell on
  `ROAFNA` is recorded as a machine-actionable fix in spec.yaml).
- `India` sheet has one deliberate reference to a non-adjacent year column — never
  re-pattern it.
- SEA components must reconcile to the segment note.
- CF allocation: perpetual/NCI dividend terms sit in the row-135 area of `Final`;
  small adjustment plugs in the row-124 area — match analyst allocation.
- The dividends-from-associates line on `Driver` should be mapped from the CF
  statement normally (a prior reference model held a transcription error here).

## 6. Tie-out anchors (must match the CURRENT disclosure exactly — no values here)

- P&L: PBT, profit for the year, attributable profit, operating earnings, EPS.
- BS: total assets; the `Final` row-99 balance-check row = 0 every year.
- `ROAFNA` row-31 check = 0 for recent years.
- Segments: HK operating earnings; SEA EBITDAF/earnings; CN operational capacity
  total; SoC generation splits.
- DCF recomputes without new errors.
