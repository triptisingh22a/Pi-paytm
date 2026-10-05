"""Read-only repricing endpoints. Merchant identity comes from the path; the SKU must belong to that merchant."""

from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from billing.store import connection, merchant
from pricing import data, service

router = APIRouter(prefix="/v2/pricing", tags=["Repricing"])


class Arrival(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: int = Field(ge=1, le=30, description="Day of the horizon the delivery arrives (1 = tomorrow)")
    qty: int = Field(gt=0, le=100000)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product: str = Field(min_length=1, max_length=60)
    dataset: Literal["live", "pilot"] = "live"
    horizon: int = Field(default=7, ge=1, le=30)
    extra_cost: float = Field(default=0, ge=0, le=100000, description="Other variable cost per unit, rupees")
    receipts: list[Arrival] = Field(default_factory=list, max_length=10)
    use_policy: bool = True
    baseline_units: float | None = Field(default=None, ge=0, le=1_000_000, description="Units you expect at today's price")
    assumed_eta: float | None = Field(default=None, ge=0.1, le=8, description="Your own price sensitivity; labelled an assumption")


class Reprice(Scenario):
    proposed_price: float = Field(gt=0, le=1_000_000, description="Rupees")


class Recommend(Scenario):
    candidates: list[float] | None = Field(default=None, max_length=15)
    low: float | None = Field(default=None, gt=0)
    high: float | None = Field(default=None, gt=0)
    step: float | None = Field(default=None, gt=0)
    max_price: float | None = Field(default=None, gt=0)
    min_margin_fraction: float | None = Field(default=None, ge=0, lt=1)


class Save(Reprice):
    kind: Literal["scenario", "experiment_plan"] = "scenario"


def _guard(mid):
    try:
        with connection() as db:
            merchant(mid, db)
    except ValueError:
        raise HTTPException(404, "Unknown merchant") from None


def _common(s):
    return dict(horizon=s.horizon, dataset=s.dataset, extra_cost=s.extra_cost, receipts=[r.model_dump() for r in s.receipts],
                use_policy=s.use_policy, assumed_eta=s.assumed_eta)


def _run(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.get("/{mid}/products")
def products(mid: str, dataset: Literal["live", "pilot"] = "live"):
    _guard(mid)
    rows = _run(data.list_products, mid, dataset)
    out = []
    for p in rows:
        s = data.load(mid, p["id"], dataset)
        from pricing.evidence import assess

        e = assess(s)
        out.append(p | dict(on_hand=s.on_hand, evidence_state=e["state"], evidence_label=e["label"],
                            price_levels=e["distinct_price_levels"]))
    return {"dataset": dataset, "products": out}


@router.post("/{mid}/reprice")
def reprice(mid: str, body: Reprice):
    _guard(mid)
    return _run(service.reprice, mid, body.product, body.proposed_price, baseline_units=body.baseline_units, **_common(body))


@router.post("/{mid}/recommend")
def recommend(mid: str, body: Recommend):
    _guard(mid)
    return _run(
        service.recommend_price, mid, body.product, candidates=body.candidates, low=body.low, high=body.high, step=body.step,
        max_price=body.max_price, min_margin_fraction=body.min_margin_fraction, **_common(body),
    )


@router.post("/{mid}/scenarios")
def save_scenario(mid: str, body: Save):
    """Saves the scenario (or its experiment plan) locally. Nothing is sent to a POS."""
    _guard(mid)
    result = _run(service.reprice, mid, body.product, body.proposed_price, baseline_units=body.baseline_units, **_common(body))
    payload = result if body.kind == "scenario" else result["experiment_plan"]
    if payload is None:
        raise HTTPException(422, "This scenario has no experiment plan: the evidence already supports a decision")
    sid = _run(service.save, mid, body.dataset, body.product, body.kind, payload)
    return {"saved": True, "id": sid, "kind": body.kind, "external_price_change": False}


@router.get("/{mid}/scenarios")
def scenarios(mid: str, dataset: Literal["live", "pilot"] = "live"):
    _guard(mid)
    return {"scenarios": data.list_scenarios(mid, dataset)}
