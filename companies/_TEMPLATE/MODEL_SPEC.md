# MODEL_SPEC — <Company> (<ticker>)

> Prose contract for this model: conventions, quirks, and analyst rulings the agent
> must respect. The machine-readable anatomy lives in spec.yaml; this file is
> appended to the LLM system prompt. Keep it concise — one line per fact.

## 1. Model basics
- File, fiscal year end, currency/units, where full detail lives (AR vs presentation).

## 2. Layout conventions
- Anything the layout demands beyond spec.yaml (header types, sign conventions,
  fonts/flag colors if they deviate from house defaults).

## 3. Drivers & logic
- How forecasts chain off actuals; what must be re-anchored after marking to actual;
  known one-off rows that must not propagate into forecast years.

## 4. Back-out rules (when detail is missing)
| Item | Method |
|---|---|
|  |  |

## 5. Known quirks & landmines
- Pre-existing errors to leave alone, definition traps, segment-basis changes.

## 6. Tie-out anchors
- The figures that must match the disclosure exactly each period.
