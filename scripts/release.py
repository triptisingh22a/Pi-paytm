"""Package only reproducible project inputs, data, evidence and requested deliverables."""

import filecmp
import json
import re
import shutil
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root.parent / "deliverables"
output.mkdir(exist_ok=True)
manifest = json.loads((root / "data/billing_manifest.json").read_text())
peers = json.loads((root / "eval/peer_transfer.json").read_text())
voice_path = root / "demo/verification/sarvam-voice.json"
voice = (
    json.loads(voice_path.read_text())
    if voice_path.exists()
    else {"status": "PENDING", "live_calls_attempted": 0}
)
test_log = (root / "demo/verification/make-test.txt").read_text()
test_count = re.search(r"(\d+) passed", test_log)
coverage = re.search(r"Total coverage: ([\d.]+)%", test_log)
if not test_count or not coverage:
    raise SystemExit(
        "Completed test-count and coverage evidence are required before release."
    )
rows = "\n".join(
    f"| {m['name']} | {m['merchant']} | {m['bills']:,} | {m['line_items']:,} | {m['stock_events']:,} |"
    for m in manifest["merchants"]
)
report = f"""# Munshi — standalone website verification

Fullscreen landing → Enter demo → standalone merchant workspace. All shop data and future outcomes are synthetic; no real Paytm connection, external order, loan offer or message is created.

## Delivered

| Feature | Status | Evidence / scope |
|---|---|---|
| Fullscreen landing and standalone workspace | VERIFIED | Desktop and 390px browser flows; no phone frame; screenshots and recorded journey |
| Seven business types and 12 months of POS data | VERIFIED | 365 days, {manifest["total_bills"]:,} bills, {manifest["total_line_items"]:,} item lines; SQLite plus CSV.gz extracts |
| Day/week/month revenue and inventory | VERIFIED | Trailing 1/7/30 days; line/item/chart reconciliation; stock-cover and no-sale checks |
| Grounded overview and customer profiles | VERIFIED | Sales leaders, revenue contribution, availability-adjusted trends, basket/loyalty evidence; no demographic or all-visitor inference |
| Canonical lookalikes | VERIFIED DEMO | Exact curated identity; same-type category rerank; known exposure; max 30 donors, k>=10 suppression, ESS; no production ANN |
| Replacement and recommendation twin | VERIFIED DEMO | Joint choices, stock caps, paired uncertainty, upfront cash and outside sensitivity; restaurants consume shared ingredients |
| Chat and numeric authorization | VERIFIED | Constrained local routing; input-bound templates and number guard; exact aliases / limited intents |
| Sarvam-only merchant agent | MOCK-VERIFIED | Six discoverable tools; optional catalogue tool messages; two-call planner budget; strict SKU/argument checks; engine-owned templates and traces; live model accuracy NOT RUN |
| Sarvam STT/TTS | {voice["status"]} | Final bounded test: {voice["live_calls_attempted"]} attempts; exact details in VOICE_TEST.md |
| Browser speech wiring | MOCK-VERIFIED | Auto STT → original-language transcript review → manual send → guarded localization → explicit answer-language TTS; actual microphone/code-mixed accuracy unverified |
| Supplier bill intake | VERIFIED SAMPLE | Labeled cached extraction; editable confirmation; atomic/idempotent local stock updates; live OCR unconnected |
| Cash/promo/restock/funding and memory | RETAINED & VERIFIED | Original independent fixtures in Decision lab; Tier A abstention; local test/approve/advance; lending illustration only |
| Docker/PostgreSQL/n8n/cognee/Telegram | PARTIAL | Configurations/adapters retained; local SQLite verified; external/runtime integrations not exercised |
| Production authentication and public deployment | NOT IMPLEMENTED | Local prototype; no hosted URL or real tenant protection claimed |

## Generated datasets

2025-10-03 through 2026-10-02, Asia/Kolkata timestamps, seed 731. Every focal dataset stores product/quantity/price/cost/bill/timestamp and stock arrivals. There are 40 donors per type (280 total) with {manifest["peer_week_facts"]:,} weekly product facts; raw donor bills are not stored.

| Shop | Type | Bills | Item lines | Stock arrivals |
|---|---|---:|---:|---:|
{rows}

Additional verticals cover frequent essentials (kirana), pack-sensitive identity (pharmacy), short-life goods (bakery), and low-frequency high-ticket items (electronics). Medical suitability and broader expiry/capacity decisions require additional policy/input data.

## Verification

- `make test`: **{test_count.group(1)} passing backend tests**, **{coverage.group(1)}% combined statement coverage** over the legacy engine, billing services and Sarvam speech/chat adapters. Ruff, limited mypy and TypeScript pass. Raw output: `demo/verification/make-test.txt`.
- Production `npm run build`: compiles `/` and `/demo`; type validation passes. `demo/verification/frontend-build.txt`.
- Production-server Playwright suite: four journeys, including both core demos, supplier confirmation, Tier A/approve/advance, 390px apparel, and configured speech UI with mocked media/provider responses. `demo/verification/playwright.txt`.
- Single backup demo recording: `demo/munshi-demo.webm`, regenerated by `make record`; screenshots under `demo/screenshots/`.
- Held-out synthetic transfer: {peers["cases"]} cold-start item cases, target merchant excluded from donors, candidate outcomes excluded from similarity, future weeks only scored. Weighted-peer RMSE **{peers["weighted_peer_rmse_units_per_100_bills"]:.3f}** versus type-item mean **{peers["type_item_mean_rmse_units_per_100_bills"]:.3f}** units/100 bills. P10–P90 model predictive coverage **{peers["model_predictive_p10_p90_coverage"] * 100:.1f}%**. This synthetic diagnostic does not establish real-world calibration or causal uplift.
- Sarvam integrated model tool-selection evaluation: **NOT RUN**. Ten English/Hindi/Marathi/adversarial cases and an opt-in bounded evaluator are included. Mock wire tests do not measure model accuracy; translation numeric preservation does not establish semantic fidelity. See `docs/SARVAM_AGENT.md`.
- Legacy evaluation: 55/55 hand-authored keyword cases, zero tested template numeric violations, planted promotion/pull-forward recovery within declared tolerances. No real LLM comparison benchmark is claimed.
- Docker/Compose/PostgreSQL, real POS/OCR, external automation delivery and production hosting were not exercised. Local Python/Next/SQLite are verified.

## Important model boundaries

The twin is conditional on a fixed completed-bill schedule, not identified all-shopper arrivals. New-item demand transfers under peer exchangeability; outside-option/IIA utility calibration is assumed. Only a narrow substitute family is modeled, with supplied stock, costs and restaurant ingredients. Existing Y stock is set aside; no salvage, disposal, replenishment, expiry or overhead is claimed by the replacement trial. The original FIFO/expiry/lead-time simulator remains separately available in Decision lab.

Recorded zero sales with known exposure motivate checking availability and a trial; absent exposure is not zero demand. Loyalty-linked return counts are bills, not total people. Profiles describe baskets, not demographics. A controlled assortment trial is needed to validate causal revenue change.

## Run

Unzip the project, install Python requirements and `npm ci` in `web`, then start `make local-api` and `make local-web`. Open http://localhost:3000 and enter the demo. `make seed` restores billing inventory. The default works without credentials; Sarvam text and voice require separately configured flags and a server-side key. No credential is packaged.

Detailed setup, plan, formulas, assumptions, integration status, timed demo script and pitch are included in the archive.
"""
(root / "docs/FINAL_REPORT.md").write_text(report)
shutil.copyfile(root / "docs/FINAL_REPORT.md", output / "Munshi-Verification.md")
source_video = root / "demo/munshi-demo.webm"
video_output = output / "Munshi-Demo.webm"
if source_video.exists() and (
    not video_output.exists()
    or not filecmp.cmp(source_video, video_output, shallow=False)
):
    shutil.copyfile(source_video, video_output)
excluded_dirs = {
    ".git",
    "node_modules",
    ".next",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
    "recordings",
    "test-results",
    "playwright-report",
}
excluded_names = {
    ".env",
    ".coverage",
    ".DS_Store",
    "munshi.db",
    "munshi.db-shm",
    "munshi.db-wal",
}
archive = output / "Munshi.zip"
count = 0
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for file in sorted(root.rglob("*")):
        relative = file.relative_to(root)
        if (
            not file.is_file()
            or any(p in excluded_dirs for p in relative.parts)
            or file.name in excluded_names
            or file.name.endswith((".tsbuildinfo", ".pyc", ".building"))
        ):
            continue
        z.write(file, Path("munshi") / relative)
        count += 1
print(
    json.dumps(
        {
            "files": count,
            "archive_bytes": archive.stat().st_size,
            "voice_status": voice["status"],
        }
    )
)
