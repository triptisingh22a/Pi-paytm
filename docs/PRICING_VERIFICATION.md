# Repricing: verification report

Own-item regular-price decisions: exact break-even, an evidence check, a stock-constrained forecast only where the price history supports one, and grounded chat access. Everything here is read-only; no price is changed anywhere.

## What is real data and what is synthetic

| Piece | Source | Status |
|---|---|---|
| Break-even arithmetic | Exact integer-paise maths on any item | Verified by tests (the 100 / 120 / 130 / 115 example gives 174 units) |
| Live history (all 7 shops, 58 items) | `data/billing.sqlite3` | Every item has exactly one price and one cost: break-even only, forecast withheld |
| Price-test pilot (Asha Hypermarket, 6 items) | `data/pricing_pilot.sqlite3`, generated | Synthetic. Randomized price blocks, hidden true response, stockouts, promotions, one confounded item, one sparse item |
| Model accuracy | `eval/pricing_eval.py` on the pilot | Measured only against the generator's truth; says nothing about real merchants |

The pilot is separate and opt-in (the "Price-test pilot" switch). Live billing data is never modified; tests assert the real database files are untouched. The generator's true parameters are written to `eval/pricing_pilot_truth.json`, which only the evaluation and tests read.

## Tests

- Backend: `make test` equivalent run from `api/`: **218 passed**, 94% coverage over engine, billing, pricing and Sarvam adapters; ruff clean. 73 tests are new for pricing (arithmetic, ties, zero/negative margin, variable cost, money validation, evidence states, zero-sale days, extrapolation, censoring, E[min(D,S)] vs min(E[D],S), timed replenishment, paired reproducibility, scenario-specific prices, merchant/dataset isolation, API and planner argument rejection, hidden-truth isolation, Windows SQLite file replacement).
- Browser (Playwright, existing servers): the repricing journey (break-even, withheld state, assumption label, pilot forecast, comparison table and chart, confounded and sparse items), repricing through chat, and a 390 px phone check all pass.
- Frontend: `tsc --noEmit` clean.
- The earlier Playwright journeys that mutate live stock were not re-run in this pass.

## Evaluation (synthetic pilot, 150 days, seed 2026)

| Measure | Result |
|---|---|
| Price sensitivity recovery, 4 randomized items | mean absolute error 0.39 (true 1.1 / 4.0 / 3.2 / 0.8; estimated 1.05 / 5.1 / 3.2 / 0.40). The 4.0 item is 1.6 standard errors high |
| Holdout demand forecast, last 28 days | MAE 12.98 vs 13.86 for "repeat the last 28 days' average" |
| 80% predictive interval coverage, holdout days | 75% (nominal 80%): slightly too narrow |
| 80% interval coverage of the true contribution change | 71% over 28 candidate prices on 4 items (cases are correlated; small sample) |
| Mean regret per 7-day decision, rupees | model's top price 71; Pi's rule (act only on "likely improves") 467; keep price 898; always cut 5% 1,357 |
| Confounded item (true sensitivity 2.5) | estimated -0.18 with a very wide interval; no price received a confident label; overall "trial recommended" |

Reading these honestly: the model recovers the planted response roughly, beats a naive forecast modestly, and is mildly over-confident. Pi's gating gives up some value (regret 467 vs 71 for always taking the model's top price) because it refuses to act on weak evidence; the confounded item shows why that trade is deliberate. Regret and forecast error are reported separately because a good forecast does not validate a counterfactual price decision.

## Demo cases

| Case | Where | What you see |
|---|---|---|
| Price cut raises sales, lowers contribution | Pilot, Branded biscuits 100 g, 38 | More units, contribution down, "likely reduces" |
| Price cut pays for itself | Pilot, Cooking oil 1 L, 140 | Contribution up, "likely improves" or "trial" depending on horizon |
| Stock blocks the needed volume | Pilot, Toor dal 1 kg, 155 | "Stock is the limit", units lost to stock shown |
| No price variation | Live, Rice 5 kg, 500 | Needs 146 sales; forecast withheld; trial plan |
| Weak or confounded history | Pilot, Premium tea 250 g, 240 | Scenario only, widened uncertainty, never "likely improves" |
| Price rise helps | Pilot, Instant coffee 50 g, 200 | Fewer units, higher contribution |
| Sparse history | Pilot, Soap bar | Forecast withheld, experiment plan |
| Spillover (own gain offset by substitutes) | Not built | Out of scope for v1 |

## How to run and use

1. `make seed` (or `python -m pricing.pilot` from `api/`) creates the pilot; it is also created on first use.
2. Start the app (`Start-Local.ps1`), open `/demo`.
3. Inventory -> **Change price** on any row, or Digital twin -> **Change a price**.
4. Enter a price and **Check this price**, or **Compare prices** for a grid or your own list. Open "Stock, costs and your own numbers" to add other costs, a delivery or the units you expect.
5. Switch to **Price-test pilot** to see supported forecasts. Ask in chat, for example "If I reduce Rice 5 kg from 520 to 500, will I make more profit?" or "Compare 480, 500, 520 and 540 for Rice 5 kg".
6. **Show calculation** opens the receipt. Saving a scenario or experiment plan writes a local row only.

API: `POST /v2/pricing/{merchant}/reprice`, `/recommend`, `/scenarios`; `GET /v2/pricing/{merchant}/products`. Chat tools: `reprice`, `recommend_price` (the pilot is selected by the UI, never by the model).

## Remaining limitations

- No live evidence of price response exists; the whole forecast path is demonstrated on synthetic data only.
- Category spillovers, store-traffic effects, clearance/expiry and batch-cost layers are not modelled.
- Intervals under-cover modestly on the pilot; thresholds are product choices, not guarantees.
- Sarvam tool selection for the new tools is covered by mocked tests only; no live provider call was made.
- Baseline for break-even on live items is a recent historical average (labelled), unless you supply expected units.