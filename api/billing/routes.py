from datetime import datetime
import hashlib
import json
from typing import Literal
from fastapi import APIRouter, UploadFile, File, Form, Response, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from billing.store import connection, merchant
from billing.services import overview, peers, replacement, recommend, receipt
from billing.agent import ask
from billing import insights
from billing.habits import customer_habits
from billing.payments_only import payments_only
from ai.sarvam_voice import status, transcribe, synthesize, LANGUAGES, STT_LANGUAGES
from ai import sarvam_chat

router = APIRouter(prefix="/v2", tags=["Billing-first standalone demo"])


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    period: Literal["day", "week", "month"] = "day"
    language: str = "en-IN"
    dataset: Literal["live", "pilot"] = "live"


class Trial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remove: str
    replace: str | None = None
    quantity: int = Field(default=50, ge=1, le=500)
    horizon: int = Field(default=7, ge=1, le=30)
    budget: float = Field(default=10000, ge=0, le=1000000)
    outside: float = Field(default=1, ge=0.25, le=4)


class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=2500)
    language: str = "en-IN"


class ImportLine(BaseModel):
    product: str
    quantity: int = Field(ge=1, le=500)
    unit_cost: float = Field(ge=0, le=100000)


class ImportBill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    lines: list[ImportLine] = Field(min_length=1, max_length=40)
    confirmed: bool = False


@router.get("/merchants")
def merchants():
    with connection() as db:
        rows = [dict(r) for r in db.execute("SELECT id,name,kind FROM merchants")]
    return {
        "merchants": rows,
        "primary": ["hypermarket", "restaurant", "apparel"],
        "as_of": "2026-10-02",
        "start": "2025-10-03",
        "days": 365,
        "simulated": True,
        "voice": status(),
        "agent": {
            "provider": "Sarvam",
            "enabled": sarvam_chat.enabled(),
            "tools": sarvam_chat.tool_definitions(),
            "max_planner_calls": 2,
        },
        "insight_refresh_seconds": insights.refresh_seconds(),
    }


@router.get("/dashboard/{mid}")
def dashboard(mid: str, period: Literal["day", "week", "month"] = "day"):
    return overview(mid, period)


@router.get("/insights/{mid}")
def insight_list(mid: str, period: Literal["day", "week", "month"] = "day"):
    with connection() as db:
        merchant(mid, db)
    return insights.get_insights(mid, period)


@router.post("/insights/{mid}/refresh")
def insight_refresh(mid: str, period: Literal["day", "week", "month"] = "day"):
    with connection() as db:
        merchant(mid, db)
    return insights.get_insights(mid, period, refresh=True)


@router.get("/habits/{mid}")
def habits(mid: str):
    return customer_habits(mid)


@router.get("/payments-only/{mid}")
def payments_only_view(mid: str):
    return payments_only(mid)


@router.get("/peers/{mid}")
def peer_tool(mid: str, product: str):
    return peers(mid, product)


@router.post("/ask/{mid}")
def question(mid: str, q: Question):
    with connection() as db:
        merchant(mid, db)
    if q.language not in STT_LANGUAGES:
        raise HTTPException(422, "Unsupported language")
    try:
        if q.dataset == "pilot" and mid != "hypermarket":
            raise HTTPException(422, "The price-test pilot belongs to Asha Hypermarket")
        return ask(mid, q.text, q.period, q.language, q.dataset)
    except ValueError:
        raise HTTPException(
            422, "Tool inputs cannot be executed; review products, quantity and budget"
        ) from None


@router.post("/twin/{mid}")
def twin(mid: str, t: Trial):
    if t.replace:
        return replacement(mid, t.remove, t.replace, t.quantity, t.horizon, t.budget, outside=t.outside)
    return recommend(mid, t.remove, t.quantity, t.budget, t.horizon)


@router.get("/invoices/{mid}/sample")
def sample(mid: str):
    d = overview(mid)
    p = d["inventory"][0]  # Stable cached fixture; invoice identity always has the same contents.
    return {
        "invoice_id": f"DEMO-{mid}-001",
        "lines": [{"product": p["id"], "quantity": 40, "unit_cost": p["cost"]}],
        "status": "CACHED_SAMPLE_EXTRACTION",
        "confirmation_required": True,
        "note": "Sample supplier-bill extraction. Live OCR is not connected; review every field before importing.",
        "source_text": f"Supplier invoice • {p['name']} • 40 units • ₹{p['cost']} per unit",
    }


@router.post("/invoices/{mid}/confirm")
def confirm(mid: str, b: ImportBill):
    if not b.confirmed:
        raise HTTPException(422, "Explicit confirmation is required")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        shop = merchant(mid, db)
        products = {p["id"]: p for p in shop["products"]}
        if any(line.product not in products for line in b.lines):
            raise HTTPException(422, "Review unmatched canonical SKU")
        # One transaction, unique invoice identity, whole-payload collision guard.
        db.execute(
            "CREATE TABLE IF NOT EXISTS bill_imports (merchant TEXT,invoice TEXT,payload TEXT,PRIMARY KEY(merchant,invoice))"
        )
        payload = json.dumps(b.model_dump(exclude={"confirmed"}), sort_keys=True)
        old = db.execute(
            "SELECT payload FROM bill_imports WHERE merchant=? AND invoice=?", (mid, b.invoice_id)
        ).fetchone()
        if old:
            if old[0] != payload:
                raise HTTPException(409, "Invoice identity already exists with different contents")
            return {"imported": False, "duplicate": True, "external_order_placed": False}
        db.execute("INSERT INTO bill_imports VALUES(?,?,?)", (mid, b.invoice_id, payload))
        for i, line in enumerate(b.lines):
            identity = hashlib.sha256(f"{mid}/{b.invoice_id}/{i}".encode()).hexdigest()
            db.execute(
                "INSERT INTO stock_events VALUES(?,?,?,?,?,?,?)",
                (
                    identity,
                    mid,
                    line.product,
                    datetime.now().isoformat(),
                    line.quantity,
                    line.unit_cost,
                    "confirmed demo import",
                ),
            )
        db.commit()
        insights.invalidate(mid)
        return {
            "imported": True,
            "duplicate": False,
            "external_order_placed": False,
            "receipt": receipt(
                b.model_dump(),
                "New stock = recorded stock + confirmed bill quantities",
                {"added_units": sum(line.quantity for line in b.lines)},
                [
                    "Local synthetic inventory only. Extracted costs are saved as receipt evidence; catalogue scenario prices/costs remain explicitly supplied. Restaurant imports represent prepared dish portions; ingredient replenishment requires separate BOM input."
                ],
            ),
        }


@router.post("/voice/stt")
async def stt(file: UploadFile = File(...), language: str = Form("unknown")):
    if not status()["enabled"]:
        raise HTTPException(503, "Sarvam voice is not configured. Use text chat.")
    data = await file.read(4_000_001)
    return transcribe(
        data,
        "recording." + ("webm" if "webm" in (file.content_type or "") else "wav"),
        file.content_type or "audio/webm",
        language,
    )


@router.post("/voice/tts")
def tts(s: Speech):
    if not status()["enabled"]:
        raise HTTPException(503, "Sarvam voice is not configured. Use text chat.")
    if s.language not in LANGUAGES:
        raise HTTPException(422, "Unsupported speech language")
    audio, request_id = synthesize(s.text, s.language)
    return Response(
        audio,
        media_type="audio/wav",
        headers={"X-Speech-Request-ID": request_id or "", "Cache-Control": "no-store"},
    )
