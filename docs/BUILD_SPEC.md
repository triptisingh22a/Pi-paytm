# Current implementation scope

The 2026-10-02 revision supersedes the mobile phone-frame layout and makes POS-grounded overview plus peer-informed assortment replacement the primary demos. See `REVISION_PLAN.md`, `DEMO_SCRIPT.md`, and the current README. The original specification below is retained as provenance; original financial tools remain in the separately labeled Decision lab. Sarvam is used for separately enabled STT/TTS; optional Gemini is a validated tool router. Neither broad live integrations nor calibrated causal uplift are claimed.

---

## 0. YOUR ROLE

Act as a combined team: Principal AI Engineer, Applied Data Scientist / Operations-Research engineer, Senior Full-Stack Engineer, DevOps engineer, Product Designer, and QA lead. Build a complete, runnable hackathon project from an empty folder to a polished, demo-ready product. Make decisions yourself; do not stop to ask questions. Where something is unknown, choose the safest reasonable default, record it in `docs/ASSUMPTIONS.md`, and keep going.

## 1. CONTEXT AND POSITIONING

- Event: Paytm AI Hackathon, Mumbai. Judges include Paytm people and partner companies (Sarvam, n8n, cognee, MochaTrade, HackBriven).
- Product: **Pi** (the traditional shopkeeper's accountant). A voice-first AI built on a **digital twin of the merchant's shop** (stock, cash, demand, customers). The merchant tests a decision on the twin before spending real money, and Pi recommends where the next rupee earns the most, with the math shown.
- Pitch line: "Paytm already has the merchant's data. Pi turns it into a twin that can test decisions before the merchant spends money."
- Strategic premise: if merchants sell through Paytm POS, Paytm receives item-level data (bills, stock, costs, settlements). Plain UPI payments contain only amounts, not items, so the twin has two data tiers: **Tier A = payments only (coarse)** and **Tier B = POS item-level**. Features degrade gracefully and the UI always says which tier an answer used.
- Important: Paytm already ships AI insights (e.g., AI Soundbox voice assistant), analytics, Billing POS (stock alerts, purchase orders), Connect Plus and m'Loyal campaigns. Pi must NOT be framed as "AI that explains your sales" or "a POS" or "a campaign platform". It is the **decision layer on top of the twin**. Voice is the interface, not the pitch. Business overview is a supporting output, not the headline.
- Core principle: **the system calculates, the LLM explains, the merchant acts.** The LLM never invents a number.
- Target user: kirana / sweet shop / electronics / vegetable merchants; Hinglish and Marathi speakers; low typing tolerance.

## 2. NON-NEGOTIABLE HONESTY RULES (anti-hallucination)

1. All merchant data is **synthetic**. Label it "Simulated data" in the UI, README, and demo. Never imply real Paytm data or real Paytm API integration. The Paytm POS is a **simulated adapter** (`PaytmPOSAdapter`).
2. Do not invent statistics, market sizes, benchmarks, or claims about Paytm products or lending logic. If a number is needed for the pitch, put it in `docs/ASSUMPTIONS.md` as a labeled assumption with the formula that uses it.
3. Do not guess third-party API shapes. Before coding each integration (Sarvam, n8n, cognee, Telegram), read the official docs or the installed package's source/README and code against what you verified. If you cannot verify something, wrap it behind an adapter, implement a clearly named mock, and record it in `docs/INTEGRATION_STATUS.md` as `VERIFIED`, `MOCKED`, or `UNVERIFIED`.
4. Every integration has a working fallback: `DEMO_MODE=live` uses real APIs, `DEMO_MODE=cached` uses recorded responses. The demo must never die on a network failure.
5. Every number shown to the user comes from the deterministic engine (section 5), enforced in code by the number guard, not by prompting alone.
6. Run what you build. Do not claim a feature works unless a test or scripted run proved it. End with a verified status table.
7. The loan nudge is a **lending-partner flow shown as an illustration**: no claim about how Paytm underwrites, no claim of real offers. Show a consent note. Trigger it only when the twin shows a genuine cash gap and the expected return of the proposed spend exceeds the borrowing cost; otherwise show nothing.
8. Lookalike data is **anonymized aggregates only**. No single merchant's data is ever shown to another.

## 3. TECH STACK (free tier or open source; swap only with a stated reason)

- Backend: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, Alembic (or plain SQL migrations)
- DB: PostgreSQL via Docker (SQLite fallback for tests)
- Data/ML: pandas or polars, numpy, scipy, statsforecast (or Prophet if install is smooth), scikit-learn (clustering and nearest neighbours for lookalikes)
- Optimization: scipy / PuLP / OR-Tools (pick one; marginal-analysis greedy is acceptable if optimality conditions are proven in a comment and tested)
- LLM and voice (verify models and endpoints in docs): Sarvam AI for speech-to-text, text-to-speech, chat LLM with tool calling, translation, and Sarvam Vision for supplier-bill OCR. Fallback LLM adapter: any free OpenAI-compatible endpoint chosen by env var.
- Automation: n8n self-hosted via Docker; workflows exported as JSON into `/n8n/workflows`
- Memory: cognee (open source, local), behind an adapter with a simple SQLite/JSON fallback
- Real approval channel: Telegram Bot API (free; real inline Approve / Skip buttons). WhatsApp is **simulated** in the UI and labeled as such.
- Frontend: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts + Framer Motion. Mobile-first PWA, phone-frame layout on desktop.
- Browser voice fallback: Web Speech API and `speechSynthesis`
- Infra: Docker Compose (postgres, api, n8n, web), Makefile, `.env.example`
- Quality: pytest, ruff, light mypy, Playwright (e2e smoke test and recording a backup demo video)
- Observability (optional): structured logs with request IDs, optional Langfuse
- Deploy (optional): Vercel (web), Render/Railway/Fly (api), Cloudflare Tunnel or ngrok for webhooks. `docker compose up` with `DEMO_MODE=cached` must always work.

## 4. REPO STRUCTURE (create exactly; extend if needed)

```
munshi/
  README.md                 # 10-minute setup, Mermaid architecture diagram, screenshots
  Makefile                  # make up | seed | test | demo | record
  docker-compose.yml
  .env.example
  docs/
    ASSUMPTIONS.md
    INTEGRATION_STATUS.md
    MATH_SPEC.md            # every formula, notation, edge case
    DEMO_SCRIPT.md          # 3-minute script, exact clicks and lines, fallback per live dependency
    PITCH_NOTES.md          # claims we can defend vs cannot; likely judge Q&A
  api/
    app/ (main.py, config.py, db.py, models.py, schemas.py)
    twin/                   # DIGITAL TWIN
      state.py              # stock, cash, demand, customers per merchant
      simulator.py          # apply an action to the twin, roll forward N days, return distributions
      lookalikes.py         # merchant feature vectors, nearest neighbours, cold-start priors
    engine/                 # DETERMINISTIC. No LLM imports allowed (enforced by a test).
      cash_runway.py
      demand.py
      margins.py
      allocator.py
      promo_uplift.py
      ranker.py
      overview.py           # day / week / month / festival summaries from twin data
      loan_nudge.py         # eligibility logic for the illustrative nudge (rules in section 5.9)
      receipts.py
    ai/
      llm_adapter.py        # sarvam | openai_compat | mock
      tools.py              # engine and twin functions exposed as LLM tools
      number_guard.py
      prompts/ (en.md, hi.md, mr.md)
      voice_adapter.py      # sarvam | browser | cached
      vision_adapter.py     # bill photo -> structured purchases (P2)
    memory/ (memory_adapter.py, cognee_store.py, fallback_store.py)
    integrations/
      paytm_pos_sim.py      # PaytmPOSAdapter: SIMULATED item-level bills, stock, costs, settlements
      telegram.py
      whatsapp_sim.py
      n8n_client.py
      paytm_tools_stub.py   # stub for Connect Plus / m'Loyal / Billing POS actions; real access unverified
    simulate/
      generator.py          # synthetic merchants with ground truth
      scenarios.py          # personas and +7 day scenarios
    tests/
  n8n/workflows/            # exported JSON: daily_briefing, restock_alert, approval_action, outcome_measure
  web/                      # Next.js app
  eval/
    hinglish_questions.jsonl   # 50+ questions with expected tool calls
    effect_recovery.py         # proves the estimator recovers planted effects
    wrapper_vs_munshi.py       # plain-LLM baseline vs Pi on same questions
  demo/ (cached_responses/, recordings/)
```

## 5. THE TWIN AND THE ENGINE (the intellectual core; build with real rigor)

Write `docs/MATH_SPEC.md` first, then implement and test each item. Every engine function returns a **Receipt** (Pydantic): `{inputs, assumptions, formula_text, steps[], output, p10, p50, p90, data_tier, data_quality_flags[]}`.

### 5.1 Synthetic data with planted ground truth (the simulated Paytm POS)

Generate 12 months of daily data for 4 personas (seeded RNG, reproducible):

1. Kirana (staples, snacks, a few perishables; thin margins \~5-12%)
2. Sweet shop (festival spikes, short shelf life)
3. Electronics accessories (higher margin, slow turnover)
4. Vegetable seller (very thin margin, 1-3 day shelf life)

Also generate a population of \~200 background merchants across these types so lookalike logic has something to work on. Include: weekday seasonality, Indian festival spikes (Diwali, Ganesh Chaturthi, Eid, Holi; configurable calendar file), payday effects, settlement lag (T+1 to T+2), supplier lead times and payment terms, stock-outs that censor observed demand, expiry, promo events with **known true uplift and known pull-forward**, churning customers. Persist planted parameters in `ground_truth.json` so tests can check the engine against them. The `PaytmPOSAdapter` exposes this data through the same interface a real POS feed would, and can be flipped to Tier A (amounts only) to demonstrate graceful degradation.

### 5.2 Digital twin (`twin/`)

- State per merchant: SKU stock levels with expiry, cash balance and pending settlements, demand model parameters, customer cohorts (new, repeat, at-risk, inactive).
- `simulator.simulate(action, horizon_days, n_paths)`: apply an action (restock order, promo, hold cash, take small credit) to a copy of the state and roll forward with stochastic demand, lead times and settlement lags. Return distributions for profit, cash balance, stock-outs and expiry loss, versus the do-nothing baseline.
- The what-if simulator and the +7 days feature are thin wrappers over this function.

### 5.3 Cash runway (works on Tier A)

Monte Carlo (>= 2,000 paths) over the next 14 days: inflows = forecast sales shifted by settlement lag; outflows = supplier dues, rent, wages, planned restock. Output: probability cash < 0 within 14 days, earliest likely gap date, P10/P50/P90 balance path, and "cash safely committable to restock today at a chosen risk level".

### 5.4 Demand model

Per-category (Tier A) and per-SKU (Tier B) forecasts with quantiles (statsforecast or equivalent), festival regressors, and stock-out censoring (zero sales during a stock-out is not zero demand). Report backtest error (MAPE or pinball loss) in the receipt. Cold start: if history is short, borrow a prior from lookalikes (5.7) and flag it.

### 5.5 Restock budget allocator (Tier B)

Given budget B, lead times, shelf life, unit cost, price, and demand quantiles, choose order quantities per SKU to maximize expected profit net of expected expiry loss and stock-out loss, subject to spend <= B. Use newsvendor-style marginal analysis (expected marginal profit per extra rupee is non-increasing per SKU, so greedy-by-marginal-return is optimal; state and test this) or LP/MIP. Also return the budget's shadow price: expected extra profit from the next Rs 1,000. Include stale-stock and hot-seller flags as outputs.

### 5.6 Incremental-profit promo engine

Question: "Does this offer beat doing nothing?" Compute a counterfactual baseline from the demand model, estimate uplift with an explicit method (difference-in-differences against comparable days/categories, or a simple uplift model), subtract discount cost on units that would have sold anyway, subtract pull-forward from future days, and report expected incremental profit with P10-P90 via bootstrap. Verdict: `DO`, `DON'T`, or `INSUFFICIENT_DATA` with the reason. Under the same 10% discount it must give opposite verdicts for a 35%-margin item and a 7%-margin item when data supports it.

### 5.7 Lookalike merchants (anonymized)

Build merchant feature vectors (category mix, ticket size, volume, weekday/festival profile, margin profile, customer repeat rate). Use clustering and nearest neighbours to define peer groups. Uses: (a) cold-start priors for new merchants, (b) "shops like yours restock X before Diwali" as an anonymized aggregate insight, (c) internal segmentation view. Enforce privacy: minimum group size (e.g., k >= 10) before any aggregate is shown; no raw rows ever cross merchants; test this.

### 5.8 Decision ranker and business overview

- Ranker: normalize candidate actions (restock lines, promos, hold cash) into expected incremental profit per Rs committed over a common horizon, attach probability of loss, return the top 5 with receipts.
- Overview: day / week / month / festival summary computed from twin data (sales, margin movement, top and stale items, customer health). This is a supporting output; keep it short.

### 5.9 Responsible loan nudge (illustrative)

Show only if ALL hold: twin shows P(cash gap within 14 days) above a configured threshold; a specific restock action has expected return above an assumed borrowing cost (config value, labeled as an assumption); data tier supports the estimate. Output: gap size, suggested amount no larger than the gap, expected return vs cost, and a consent note ("offered by a lending partner; terms apply"). No invented rates or approvals.

### 5.10 Proof of rigor

- `eval/effect_recovery.py`: plant uplifts, run the engine, show it recovers them within tolerance, and show a **naive "sales went up" method getting it wrong**. Produce a chart for the demo.
- Unit tests for every engine function, including edge cases (zero budget, tiny history, missing costs, Tier A only).
- A test that fails if anything under `engine/` or `twin/` imports an LLM library.
- A privacy test for lookalikes (min group size, no raw leakage).

## 6. AI LAYER

- The LLM may only (a) choose which tools to call and (b) explain returned receipts in the merchant's language and tone.
- **Number guard** (`ai/number_guard.py`): extract every number, currency amount, percentage and date from the LLM reply; verify each appears in that turn's tool outputs (tolerant of formatting: Rs 42,300 vs 42.3K). Otherwise regenerate once with an error hint, then fall back to a template built directly from the receipt. Unit-test with adversarial cases.
- Languages: Hinglish, Hindi, Marathi first. Default reply = 2-3 short sentences; detail lives in the math drawer.
- Tone and preferred language come from memory (section 7).
- Voice flow: mic -> STT -> LLM with tools -> TTS -> audio. Small debug drawer shows transcript and latency. Fallbacks per section 2.
- Bill-photo flow (P2): image -> vision adapter -> structured purchase lines -> user confirmation screen -> update Tier B data. Never auto-trust OCR.
- `eval/hinglish_questions.jsonl`: 50+ realistic questions (restock, discount, cash, "aaj kaisa raha", festival prep, lookalike, loan, out-of-scope) with expected tool calls; a script reports tool-selection accuracy and number-guard violations.

## 7. MEMORY (cognee, with adapter and fallback)

Store per merchant: preferred language and tone, past recommendations and whether approved, measured 7-day outcomes, festival history ("diyas ran out on day 3 last Diwali"), supplier reliability (observed lead-time delays), discount-response estimates. Before each recommendation, recall relevant memories and pass them as **context for the explanation only**; numeric inputs still come from the engine and database. After each measured outcome, write back. Show one clear "Memory moment" in the demo. Document in `INTEGRATION_STATUS.md` exactly which cognee calls were verified.

## 8. AUTOMATION (n8n) AND CHANNELS

Build and export these workflows (n8n calls FastAPI via webhooks; business logic stays in the API, orchestration in n8n):

1. `daily_briefing`: cron -> `/briefing/{merchant}` -> TTS -> send (Telegram real, WhatsApp simulated)
2. `restock_alert`: when forecast cover < lead time -> proposal with Approve / Skip
3. `approval_action`: on approve -> execute through `paytm_tools_stub` (clearly labeled stub)
4. `outcome_measure`: after N days or on simulated time advance -> realized vs counterfactual -> write to memory

Real one-tap approval: Telegram bot with inline buttons. WhatsApp-style screens are simulated and labeled.

## 9. FRONTEND / DEMO EXPERIENCE (this decides whether it impresses)

Design: premium consumer-app feel; navy and blue palette consistent with the pitch deck; large type; generous spacing; subtle motion; no clutter. Mobile-first inside a phone frame on desktop. Accessible contrast and tap targets. Everything must work in `cached` mode.

**P0 screens**

1. **Home**: twin snapshot (cash, stock health), 14-day cash-gap probability, ranked "Next best Rs" actions, big voice button, persistent **"Rs earned vs doing nothing"** counter, "Simulated data" and data-tier tags.
2. **Ask (text first)**: answer card with 2-3 lines, confidence band, and a **"Show math" drawer** rendering the receipt.
3. **Persona switcher**: Kirana, Sweet shop, Electronics, Vegetables. The same discount question visibly gives different, correct verdicts.

**P1 screens** 4. **What-if and +7 days**: test an action on the twin, approve, press "+7 days", animate followed vs ignored vs do-nothing; update the counter. Labeled as simulation. 5. **Voice in/out** with language flip (Marathi, Hindi, Hinglish). 6. **Lookalikes view**: anonymized peer group insight and a cold-start example for a brand-new shop. 7. **Overview**: day / week / month / festival. 8. **Memory moment** card and Telegram one-tap approval flow. 9. **Loan nudge card** (only appears when conditions in 5.9 hold, with consent note). 10. **Proof page** (effect-recovery chart) and **wrapper-vs-Pi duel** (real plain-LLM baseline or its cached recording, not a strawman).

**P2 screens** 11. Bill-photo capture and confirm; 12. Field-agent "first win in one visit" view; 13. Cost-per-merchant dashboard (measured call counts from logs; unit prices in a config file marked "verify"); 14. Integration status page (VERIFIED / MOCKED / UNVERIFIED); 15. Backup demo video via Playwright.

## 10. FINAL FEATURE SCOPE AND BUILD ORDER

**P0 (must work and be verified before anything else)**

1. Simulated Paytm POS feed with planted ground truth (4 personas + background merchants)
2. Digital twin state and simulator
3. Restock allocator
4. Promo check (DO / DON'T / INSUFFICIENT_DATA)
5. Cash-runway warning
6. Ranked action list
7. Math receipts and number guard
8. Chat UI with persona switch and the Rs counter Also: `docker compose up`, `make seed`, `make test`.

**P1** 9. What-if simulator and +7 days 10. Voice in/out (Sarvam, browser fallback) 11. Lookalike merchants 12. Business overview 13. Memory (cognee) 14. Telegram one-tap approval via n8n and 7-day outcome write-back 15. Responsible loan nudge 16. Proof page and duel

**P2** 17. Bill-photo reading; 18. Field-agent view; 19. Cost dashboard; 20. Integration status page; 21. Recorded backup demo video; deployment.

**Explicitly out of scope:** building a real POS, a campaign platform, a loyalty program, a udhaar ledger, real WhatsApp, MochaTrade integration, and any claim of real Paytm API access or real lending offers.

Do P0 fully, tested, and demo-able before starting P1. Do P1 before P2.

## 11. QUALITY BARS

- `make test` green; engine coverage >= 85%; ruff clean.
- Deterministic: same seed, same outputs; snapshot tests for receipts.
- Text answer < 3 s in cached mode; voice round trip reported honestly.
- No secrets committed; `.env.example` complete; human-readable error messages.
- README lets a stranger run the demo in under 10 minutes.
- Playwright e2e: open home, ask a question, open the math drawer, switch persona, run +7 days.

## 12. DELIVERABLES

1. Complete repo as specified, runnable with `docker compose up`
2. `docs/DEMO_SCRIPT.md`: 3-minute script (judge asks by voice, answer, show math, persona flip, duel, approve, +7 days, memory callback, one lookalike moment), with a fallback line for every live dependency
3. `docs/PITCH_NOTES.md`: (a) claims defensible with evidence from the repo, (b) claims we must not make, (c) answers to likely judge questions: Paytm overlap (Billing POS, AI Soundbox, analytics), data access and the two data tiers, adoption of item-level billing, lending compliance and consent, privacy of lookalikes, cost per merchant, why not just an LLM wrapper
4. Recorded backup demo video via Playwright (`make record`)
5. Final report: table of every feature with status `WORKING / PARTIAL / MOCKED / NOT DONE`, the commands run to verify it, known limitations, and the top 5 risks for demo day

## 13. HOW TO WORK

- Start by writing `docs/ASSUMPTIONS.md`, `docs/MATH_SPEC.md`, and the repo skeleton; then implement in the priority order above.
- After each module: run tests, fix, commit with a clear message.
- Prefer boring, reliable choices, except in the engine and twin where rigor is the point.
- If a partner tool is unavailable or fails, use the adapter fallback and keep moving. Never block the project on one integration.
- Do not add features outside this spec unless they directly improve the demo's clarity or credibility.

Begin now.