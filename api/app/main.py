import copy
import json
import logging
import time
import uuid
from functools import lru_cache
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.db import Base, engine, Session
from app.models import ShopSession
from app.schemas import Question, ActionRequest
from app.config import BORROWING_COST, GAP_THRESHOLD
from integrations.paytm_pos_sim import PaytmPOSAdapter
from integrations.paytm_tools_stub import execute
from engine.cash_runway import runway
from engine.allocator import allocate
from engine.promo_uplift import promo
from engine.ranker import rank
from engine.overview import overview
from engine.loan_nudge import loan_nudge
from engine.receipts import insufficient
from twin.lookalikes import peers
from twin.simulator import simulate
from ai.tools import route
from ai.llm_adapter import LLMAdapter
from ai.provider_adapter import SarvamExplanationAdapter
from memory.memory_adapter import MemoryAdapter

Base.metadata.create_all(engine)
adapter = PaytmPOSAdapter()
app = FastAPI(title="Pi — simulated merchant digital twin")


@app.on_event("startup")
def start_insight_refresh():
    from billing import insights

    insights.start_scheduler()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
logger = logging.getLogger("pi")


@app.middleware("http")
async def request_log(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    rid = str(uuid.uuid4())
    response.headers["X-Request-ID"] = rid
    logger.info(
        json.dumps(
            {
                "request_id": rid,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(ValueError)
async def bad_value(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": str(exc)})


def session_for(db, merchant):
    if merchant not in adapter.bundle["shops"]:
        raise HTTPException(404, "Unknown merchant persona")
    s = db.get(ShopSession, merchant)
    if s is None:
        s = ShopSession(merchant=merchant, day=0, earned=0, pending_action="null", memory="[]", state="null")
        db.add(s)
        db.flush()
    return s


def shop_for(db, merchant, tier):
    s = session_for(db, merchant)
    shop = adapter.merchant(merchant, "B")
    state = json.loads(s.state)
    if state:
        shop["cash"] = state["cash"]
        shop["customer_cohorts"] = state.get("customer_cohorts", shop["customer_cohorts"])
        shop["repeat_rate"] = shop["customer_cohorts"]["repeat"] / max(
            1, sum(shop["customer_cohorts"].values())
        )
        for sku in shop["skus"]:
            sku["stock"] = state["stock"].get(sku["id"], 0)
            sku["batches"] = state.get("batches", {}).get(sku["id"], [])
        shop["pending"] = [state["pending"].get(str(i), 0) for i in range(2)]
        # Dues are paid once; model obligations after initial synthetic fortnight are zero.
        shop["dues"] = (shop["dues"][s.day :] + [0] * 14)[:14]
    shop["data_tier"] = tier
    if tier == "A":
        shop["skus"] = []
    return shop, s


@lru_cache(maxsize=64)
def dashboard_cached(merchant, tier, day, state_string):
    shop = adapter.merchant(merchant, "B")
    state = json.loads(state_string)
    if state:
        shop["cash"] = state["cash"]
        shop["customer_cohorts"] = state.get("customer_cohorts", shop["customer_cohorts"])
        shop["repeat_rate"] = shop["customer_cohorts"]["repeat"] / max(
            1, sum(shop["customer_cohorts"].values())
        )
        for sku in shop["skus"]:
            sku["stock"] = state["stock"].get(sku["id"], 0)
            sku["batches"] = state.get("batches", {}).get(sku["id"], [])
        shop["pending"] = [state["pending"].get(str(i), 0) for i in range(2)]
        shop["dues"] = (shop["dues"][day:] + [0] * 14)[:14]
    shop["data_tier"] = tier
    if tier == "A":
        shop["skus"] = []
    cash = runway(shop)
    basket = allocate(shop, min(3000, cash.output["safe_to_commit"]))
    promo_receipt = promo(shop["skus"][0] if shop["skus"] else None, tier=tier)
    return {
        "merchant": merchant,
        "name": shop["name"],
        "tier": tier,
        "cash": shop["cash"],
        "simulated": True,
        "cash_receipt": cash.model_dump(),
        "allocation": basket.model_dump(),
        "promo": promo_receipt.model_dump(),
        "ranked": rank(shop, basket).model_dump(),
        "peers": peers(shop, adapter.bundle["peers"]).model_dump(),
        "overview": overview(shop).model_dump(),
        "loan": loan_nudge(shop, cash, allocate(shop, 3000), BORROWING_COST, GAP_THRESHOLD).model_dump(),
        "stock": [
            {k: v for k, v in sku.items() if k not in ("history", "promo_episodes")} for sku in shop["skus"]
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok", "simulated": True, "llm": "MOCKED", "mode": "local cached computation"}


@app.get("/dashboard/{merchant}")
def dashboard(merchant: str, tier: str = "B"):
    if tier not in ("A", "B"):
        raise HTTPException(422, "Tier must be A or B")
    with Session.begin() as db:
        s = session_for(db, merchant)
        result = copy.deepcopy(dashboard_cached(merchant, tier, s.day, s.state))
        result.update(
            {
                "earned": s.earned,
                "day": s.day,
                "memory": MemoryAdapter.recall(s),
                "pending_action": json.loads(s.pending_action),
            }
        )
        return result


@app.post("/ask/{merchant}")
def ask(merchant: str, q: Question):
    start = time.perf_counter()
    with Session.begin() as db:
        shop, s = shop_for(db, merchant, q.tier)
        tool = route(q.text)
        if tool == "promo":
            receipt = promo(shop["skus"][0] if shop["skus"] else None, q.discount, q.tier)
        elif tool == "cash":
            receipt = runway(shop)
        elif tool == "allocate":
            safe = runway(shop).output["safe_to_commit"]
            receipt = allocate(shop, min(q.budget, safe))
        elif tool == "overview":
            receipt = overview(shop)
        elif tool == "peers":
            receipt = peers(shop, adapter.bundle["peers"])
        elif tool == "loan":
            cash = runway(shop)
            basket = allocate(shop, q.budget)
            receipt = loan_nudge(shop, cash, basket, BORROWING_COST, GAP_THRESHOLD)
        else:
            receipt = insufficient(q.tier, "OUT_OF_SCOPE")
        memory = MemoryAdapter.recall(s)
        fallback = LLMAdapter().explain(tool, receipt, q.language)
        answer, provider = SarvamExplanationAdapter().explain(receipt, q.language, fallback, memory)
        return {
            "tool": tool,
            "answer": answer,
            "receipt": receipt.model_dump(),
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "guard_passed": True,
            "provider": provider,
            "memory_moment": memory[-1] if memory else None,
        }


@app.post("/simulate/{merchant}")
def whatif(merchant: str, request: ActionRequest):
    with Session.begin() as db:
        shop, _ = shop_for(db, merchant, request.tier)
        return simulate(shop, request.action, n_paths=512).model_dump()


@app.post("/approve/{merchant}")
def approve(merchant: str, request: ActionRequest):
    with Session.begin() as db:
        shop, s = shop_for(db, merchant, request.tier)
        if request.tier != "B":
            raise HTTPException(422, "Approval requires item-level tier B")
        if json.loads(s.pending_action):
            raise HTTPException(409, "A plan is already pending. Advance or skip it first.")
        simulate(shop, request.action, n_paths=1)
        s.pending_action = json.dumps(request.action)
        return {"approved": True, "stub": execute(request.action)}


@app.post("/skip/{merchant}")
def skip(merchant: str):
    with Session.begin() as db:
        s = session_for(db, merchant)
        s.pending_action = "null"
        return {"skipped": True}


@app.post("/advance/{merchant}")
def advance(merchant: str):
    with Session.begin() as db:
        shop, s = shop_for(db, merchant, "B")
        action = json.loads(s.pending_action) or {"type": "hold"}
        receipt = simulate(shop, action, n_paths=256, seed=42 + s.day)
        out = receipt.output
        s.day += 7
        s.earned += out["simulated_realized_delta"]
        s.pending_action = "null"
        s.state = json.dumps({"cash": out["simulated_realized_cash"], **out["terminal_sample"]})
        memory = {
            "day": s.day,
            "action": action["type"],
            "simulated_incremental_profit": out["simulated_realized_delta"],
            "note": "Simulated outcome, not observed merchant profit",
        }
        MemoryAdapter.remember(s, memory)
        return {"receipt": receipt.model_dump(), "earned": s.earned, "day": s.day, "memory": memory}


@app.post("/reset/{merchant}")
def reset(merchant: str):
    with Session.begin() as db:
        s = session_for(db, merchant)
        s.day, s.earned, s.pending_action, s.memory, s.state = 0, 0, "null", "[]", "null"
    return {"reset": True}


@app.get("/briefing/{merchant}")
def briefing(merchant: str):
    return ask(merchant, Question(text="aaj kaisa raha"))


@app.get("/integration-status")
def integrations():
    return {
        "Paytm POS": "MOCKED",
        "LLM": "MOCKED",
        "Sarvam": "VERIFIED schema / live untested",
        "cognee": "UNVERIFIED",
        "Telegram": "VERIFIED schema / live untested",
        "n8n": "PARTIAL workflow exports",
        "WhatsApp": "MOCKED",
        "Browser speech": "Permission-dependent",
        "SQLite memory": "WORKING",
    }


@app.get("/restock-alert/{merchant}")
def restock_alert(merchant: str):
    from engine.demand import forecast

    with Session.begin() as db:
        shop, _ = shop_for(db, merchant, "B")
        alerts = []
        for sku in shop["skus"]:
            f = forecast(sku)
            mean = sum(f.output["mean_daily"]) / 7
            cover = sku["stock"] / mean
            if cover < sku["lead_time"]:
                alerts.append(
                    {
                        "sku_id": sku["id"],
                        "name": sku["name"],
                        "cover_days": round(cover, 2),
                        "lead_time_days": sku["lead_time"],
                    }
                )
        return {"alerts": alerts, "simulated": True}


@app.post("/channels/telegram/proposal/{merchant}")
def telegram_proposal(merchant: str, only_when_low_cover: bool = False):
    from app.models import Proposal
    from integrations.telegram import TelegramAdapter

    if only_when_low_cover and not restock_alert(merchant)["alerts"]:
        return {"created": False, "reason": "No cover below lead time"}
    with Session.begin() as db:
        shop, _ = shop_for(db, merchant, "B")
        cash = runway(shop)
        allocation = allocate(shop, min(3000, cash.output["safe_to_commit"]))
        actions = rank(shop, allocation).output["actions"]
        candidates = [a for a in actions if a["spend"] > 0 and a["profit"] > 0]
        if not candidates:
            return {"created": False, "reason": "No profitable cash-safe action"}
        action = candidates[0]
        pid = uuid.uuid4().hex[:24]
        db.add(
            Proposal(
                id=pid,
                merchant=merchant,
                action=json.dumps(action["action"]),
                expires=time.time() + 86400,
                consumed=0,
            )
        )
        # No delivery can occur in cached mode. Numbers originate in the engine.
        text = f"SIMULATED DATA: {action['label']}. Commit INR {action['spend']:.2f}; estimated extra profit INR {action['profit']:.2f}. Approval runs the twin only."
        delivery = TelegramAdapter().proposal(text, pid)
        return {"created": True, "proposal_id": pid, "delivery": delivery}


@app.post("/channels/telegram/webhook")
async def telegram_webhook(request: Request):
    # Annotation added below for FastAPI to treat this as a Request, never a query parameter.
    import hmac
    import os
    from sqlalchemy import update
    from app.models import Proposal
    from integrations.telegram import TelegramAdapter

    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    provided = request.headers.get("x-telegram-bot-api-secret-token", "")
    allowed = os.getenv("TELEGRAM_CHAT_ID", "")
    if not secret or not allowed or not hmac.compare_digest(secret, provided):
        raise HTTPException(403, "Webhook authentication failed")
    payload = await request.json()
    cb = payload.get("callback_query", {})
    if str(cb.get("message", {}).get("chat", {}).get("id", "")) != allowed:
        raise HTTPException(403, "Unrecognized chat")
    command, _, pid = cb.get("data", "").partition(":")
    if command not in ("approve", "skip"):
        raise HTTPException(422, "Invalid callback action")
    with Session.begin() as db:
        proposal = db.get(Proposal, pid)
        if not proposal or proposal.expires < time.time():
            raise HTTPException(410, "Proposal missing or expired")
        result = db.execute(
            update(Proposal).where(Proposal.id == pid, Proposal.consumed == 0).values(consumed=1)
        )
        if result.rowcount == 0:
            return {"handled": True, "duplicate": True}
        s = session_for(db, proposal.merchant)
        if command == "approve":
            if json.loads(s.pending_action):
                raise HTTPException(409, "A plan is already pending")
            shop, _ = shop_for(db, proposal.merchant, "B")
            action = json.loads(proposal.action)
            simulate(shop, action, n_paths=1)
            s.pending_action = proposal.action
        TelegramAdapter().acknowledge(
            cb.get("id", ""), "Simulation plan " + ("approved" if command == "approve" else "skipped")
        )
        return {"handled": True, "duplicate": False, "action": command, "external_order_placed": False}


@app.post("/channels/telegram/briefing/{merchant}")
def telegram_briefing(merchant: str):
    from integrations.telegram import TelegramAdapter

    result = briefing(merchant)
    return {"briefing": result, "delivery": TelegramAdapter().message("SIMULATED DATA. " + result["answer"])}

# Revised standalone product; original deterministic decision tools remain backward compatible.
from billing.routes import router as billing_router  # noqa: E402
from pricing.routes import router as pricing_router  # noqa: E402
app.include_router(billing_router)
app.include_router(pricing_router)
