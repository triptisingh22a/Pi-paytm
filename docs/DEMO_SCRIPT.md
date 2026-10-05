# Standalone demo script — two core demos, about three minutes

Run local API + Next, or Compose; open http://localhost:3000. All observations and future paths are simulated. Voice is optional; text works without credentials.

1. **0:00–0:15 — Fullscreen landing.** “Pi helps a merchant test a decision before spending.” Press **Enter demo**. There is no phone frame.
2. **0:15–0:55 — Hypermarket overview.** Day is default. Show revenue and contribution, Week/Month, revenue chart, most sold versus revenue leader, Oats rising, Fruit juice declining, and Digestive biscuits with no recorded sales. Basket profiles are purchases, not demographics. Open **View evidence** and show the line-level formula and assumptions.
3. **0:55–1:10 — Inventory.** Show coverage/restock nudges. Open **Review sample supplier bill**, point out **cached extraction**, review editable canonical SKU/quantity/cost, then **Confirm quantities & import**. This changes local stock, never sends a purchase order. Repeat the same invoice identity to demonstrate no double import.
4. **1:10–1:55 — Hypermarket replacement.** Digestive biscuits row → **Try replacement** → Millet cookies, 50 units, ₹20,000 budget, 7 days → **Run on digital twin**. Show modeled revenue delta and P10/P90, upfront purchase cash, displaced sales, unsold cost value and outside-option sensitivity. **Show the math** includes exact stock caps/seeds. **Inspect lookalikes** shows canonical identity, eligibility, 30 anonymized donors, ESS and exposure-adjusted rates.
5. **1:55–2:35 — Restaurant replacement through chat.** Switch to Annapurna Kitchen, press Day. Use **What should replace my dead stock?** or type `What should I replace Cream pasta with to increase revenue?`. Show both candidates, including a negative candidate. The twin includes recipe ingredients; Paneer grain bowl consumes rice, vegetables and paneer and can displace other dishes. Outside sensitivity may change the sign; this motivates a small measured trial.
6. **2:35–2:50 — Grounded conversation.** Ask `Which products sold most this week and what customers bought them?`. The tool selects the requested week and explains exact recorded totals with a calculation receipt. No model-generated arithmetic.
7. **2:50–3:00 — Voice and conclusion.** If live voice is deliberately enabled, press the mic, stop, review STT transcript, send, and optionally press Read answer aloud for TTS. No paid call is automatic. If voice is disabled, show the text fallback and the final voice report instead. “POS builds the shop; lookalikes inform a conditional trial; the merchant decides.”

## Optional retained tools

Decision lab: start on **Payments only** (takings, peak hours, 7-day inflow; five locked insights each naming the data that unlocks it), then switch to **Item-level bills** for the decision queue (replenish, check shelf, losing traction), each with its evidence.

## Backup

`demo/munshi-demo.webm` records the two core journeys. Screenshots are under `demo/screenshots/`. `make record` regenerates the single selected recording. Provider outages fall back to text; no automatic paid retries. If a scenario is negative or sensitive, discuss the downside rather than changing seeds to obtain a favorable answer.
