# Updated local verification — October 3, 2026

Source: C:/Users/tript/Downloads/Pi.zip, 20,794,421 bytes, saved October 3 at 10:51:56 IST. This replaces the older 5 MB core archive in the same local checkout. 71 new or changed release files were applied. The earlier missing-feature findings are superseded by this report.

## Checks on this Windows machine

| Check | Result |
|---|---|
| Updated backend suite | 106 passed in isolated rerun |
| Engine coverage | 99.43% on completed runs |
| Backend lint and schema types | Passed |
| Production Next build and frontend types | Passed, including /demo |
| Updated browser journeys | 4 passed, zero failed/skipped |
| Live local dashboard/proxy smoke checks | 9/9 across 3 main merchants and day/week/month |
| Data/agent discovery | 7 merchant types, 6 tools exposed |
| Synthetic peer-transfer evaluation | 490 cases completed; weighted-peer RMSE 2.648 vs type-item mean 3.075 |
| Windows start/stop/restart | Verified |

The browser journeys cover standalone overview and both assortment demos, periods, inventory, receipt evidence, supplier-bill review/confirmation, legacy approve/advance/memory, payments-only abstention, apparel at small viewport, and explicit speech UI through mocked STT/TTS. Screenshots and current results are in demo/ and demo/e2e-results.json.

The synthetic transfer result is an implementation diagnostic, not evidence of real-shop forecasting accuracy or causal intervention uplift.

## Integrated locally

- Fullscreen landing and standalone merchant workspace.
- Hypermarket, restaurant, apparel and four supporting merchant types with 365 days of synthetic POS bills, stock and availability.
- Sales/stock overview, restocking nudges, trends, purchased-basket summaries, day/week/month charts.
- Canonical catalogue, eligible weighted lookalikes, replacement trials and rankings, retail stock and restaurant recipe constraints.
- Grounded constrained chat, receipts, visible evidence, and legacy decision lab.
- Cached editable supplier-bill extraction with explicit idempotent local stock confirmation.
- Sarvam-only bounded tool planner, STT, TTS, language detection/localization adapters. Mock transport/orchestration tests verify wiring; live behavior is unverified.
- SQLite billing plus persistent legacy sessions/memory.

## Remaining external limitations

Sarvam credentials are not configured locally. The running demo reports agent.enabled=false and voice.enabled=false, uses the labeled constrained local router, and makes no billed requests in this validation. Live LLM tool selection, microphone capture, real speech quality and localization fidelity have not been tested here.

Live image OCR is unconnected; supplier-bill extraction is a cached fixture. Real Paytm access/actions, Telegram delivery, WhatsApp delivery, n8n execution, cognee, PostgreSQL and Docker runtime are not verified. External actions remain simulated. See docs/INTEGRATION_STATUS.md for release details.

## Local compatibility changes

Preserved Windows startup scripts, virtual environment, installed JavaScript dependencies and Git repository. Added python-multipart required by the updated upload routes. Kept SQLAlchemy's supported pure-Python installation. Updated browser-test commands for Windows and optional reuse of script-owned servers. Fixed an open SQLite connection in a fixture before replacing its database on Windows. Isolated legacy backend-test state to prevent browser/test session collisions. No test assertions were removed.

JavaScript dependencies are locked with pnpm, including Next 15.5.27. Reported checks use this installed dependency set, which can differ from the archive's older npm lock.

