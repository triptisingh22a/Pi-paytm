# Integration status — revised standalone release

Schema verification and runtime validation are distinct. All merchant data is simulated. No real external message, loan or order is created. See `VOICE_TEST.md` for the final bounded speech test outcome.

| Component | Schema / implementation | Runtime / fallback |
|---|---|---|
| POS/Paytm | Simulated item-level billing adapter; no real Paytm API | Complete generated 365-day bills, stock and availability; no credentials needed |
| Overview/stock | Deterministic SQL totals and templates | Reconciliation tests across seven types and three periods; browser verified |
| Lookalikes | Curated canonical aliases, exact category rerank, eligibility, weights, conjugate transfer | Cohort suppression, future-leakage tests and held-out synthetic diagnostic; no production ANN |
| Assortment twin | Paired conditional choices, dynamic stock, explicit supplied costs | Retail and shared-ingredient restaurant tests + browser journeys; no causal uplift claim |
| Sarvam STT | Verified POST `/speech-to-text`, `api-subscription-key`, multipart file/model/language | Mock request, format/auth-failure/no-retry tests; live STT skipped after TTS connection failure |
| Sarvam TTS | Verified POST `/text-to-speech`; `text`, `language_code`, `bulbul:v3`, `shubh`, WAV | Validated base64/container and mocked errors; one final live connection attempt failed; key not validated |
| Browser voice | MediaRecorder ≤20s; transcript review before send; explicit TTS button | Offline fallback visible in browser; actual microphone and code-mixed quality unverified |
| Gemini | Official GenerateContent function declarations; one-call validated allowlist | Mocked route validation; no key, no live call; local exact-alias fallback |
| Supplier-bill OCR | Live OCR unconnected; clearly labeled cached extraction fixture | Editable review; atomic, explicit and idempotent local inventory import tested |
| Legacy Sarvam chat | Earlier official v1 explanation adapter retained | Mocked transport + numeric guard; disabled in default cached mode; supplied speech key never used for chat test |
| Telegram | Earlier official inline buttons and authenticated single-use callbacks retained | Mock transport/API tests; no real send or webhook exercised |
| WhatsApp | Simulation only | Local preview; no delivery |
| n8n | Earlier inactive workflow JSON exports retained | Schema/source inspected; Docker/import/execution not verified |
| cognee | Disabled experimental adapter | Per-merchant SQL memory fallback verified; cognee runtime not verified |
| Database | Billing SQLite plus legacy SQLAlchemy SQLite/PostgreSQL dialect | Local SQLite tested; PostgreSQL runtime not tested |
| Repricing | Break-even, evidence gate, censored NB demand model, paired stock-constrained simulation; `reprice` / `recommend_price` tools | Verified locally: live history gives break-even only; a synthetic price-test pilot gives forecasts. No live price-response evidence, no POS write |
| Docker Compose | Supplied API/web/postgres/optional n8n configuration | Docker unavailable; local servers and production Next build verified |

Official references read before integration:

- https://docs.sarvam.ai/api-reference/speech-to-text/transcribe
- https://docs.sarvam.ai/api-reference/text-to-speech/convert
- https://docs.sarvam.ai/api-reference/authentication
- https://ai.google.dev/gemini-api/docs/generate-content/function-calling?authuser=0&hl=en
- https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
- https://core.telegram.org/bots/api#sendmessage
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/
- https://docs.cognee.ai/api-reference/introduction

Sarvam speech is separately opt-in through `SARVAM_VOICE_ENABLED`. Key and optional private key file are server-only. A model selects tools, not business numbers: responses use input-bound templates behind the numeric guard. Gemini errors revert to local routing. Speech errors return a redacted status and text fallback with no retry. Hindi/Marathi STT mode requests translation; Saaras v4's public reference has inconsistent mode prose, so multilingual behavior remains runtime-unverified.

### 2026-10-03 voice routing fix

HTTP(S) proxies and `NO_PROXY` are now handled explicitly; unrelated SOCKS settings remain ignored. The optional `SARVAM_HTTP_PROXY` override can configure a permitted proxy, or an empty value can select direct access. Configuration and transport mocks were tested; there was no additional Sarvam request. The current network allowlist still excludes the provider endpoint, and the key remains unvalidated.


## Sarvam merchant agent revision — 2026-10-03

Merchant chat now uses a Sarvam-only bounded planner, with six named tools, optional catalogue tool messages, strict canonical-role/tenant/argument validation, receipt-owned answers and execution traces. Auto-detected original-language STT is carried through answer localization and answer-language TTS. Mock wire/guard tests are separate from the new opt-in live tool-selection evaluation. No live Sarvam accuracy, multilingual semantic fidelity or native speech-to-speech capability is claimed. See SARVAM_AGENT.md; older Gemini/translated-STT descriptions above are historical and superseded for the merchant flow.
