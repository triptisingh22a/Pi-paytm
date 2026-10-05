.PHONY: up seed test demo record eval lint typecheck local-api local-web
up:
	docker compose up --build
seed:
	cd api && python -m simulate.generator
	cd api && python -m billing.generate
	cd api && python -m pricing.pilot
	python scripts/export_billing.py
	python eval/effect_recovery.py
# Seed is deterministic; preserve existing merchant sessions unless reset through UI.
test:
	cd api && python -m pytest --cov=engine --cov=billing --cov=ai.sarvam_voice --cov=ai.sarvam_chat --cov-report=term-missing --cov-fail-under=85 -q
	cd api && python -m ruff check .
	cd api && python -m mypy engine/receipts.py app/schemas.py twin/state.py
	cd web && npm run typecheck
demo: eval
	@echo 'Open http://localhost:3000 (run make up, or local-api and local-web in separate terminals).'
record:
	cd web && npm run record
	python scripts/collect_recording.py
eval:
	python eval/peer_transfer.py
	python eval/effect_recovery.py
	python eval/tool_selection.py
	python eval/pricing_eval.py
	python eval/wrapper_vs_munshi.py
lint:
	cd api && python -m ruff check .
typecheck:
	cd web && npm run typecheck
local-api:
	cd api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
local-web:
	cd web && npm run dev
