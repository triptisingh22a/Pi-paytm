"""Constrained question router. Models choose tools; the application supplies every result."""

import copy
import os
import re
import httpx
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from ai.number_guard import check
from billing.catalogue import catalogue
from billing.services import overview, peers, replacement, recommend
from billing.insights import run_insight


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["overview", "inventory", "insight", "peers", "replace", "recommend", "reprice", "recommend_price"]
    period: Literal["day", "week", "month"] = "day"
    product: str | None = None
    price: float | None = Field(default=None, gt=0, le=1_000_000)
    candidates: list[float] | None = Field(default=None, max_length=15)
    insight: Literal["most_sold", "revenue_leader", "rising", "falling", "dead_shelf", "restock", "regulars"] | None = None
    remove: str | None = None
    replace: str | None = None
    quantity: int = Field(default=50, ge=1, le=500)
    budget: float = Field(default=10000, ge=0, le=1000000)
    horizon: int = Field(default=7, ge=1, le=30)


DECLARATION = {
    "name": "merchant_decision",
    "description": "Read grounded overview, inventory, aggregate lookalikes, or run a conditional assortment trial. Never place an order.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "tool": {"type": "STRING", "enum": ["overview", "inventory", "peers", "replace", "recommend"]},
            "period": {"type": "STRING", "enum": ["day", "week", "month"]},
            "remove": {"type": "STRING", "description": "Exact canonical SKU from supplied catalogue"},
            "replace": {"type": "STRING", "description": "Exact canonical SKU from supplied catalogue"},
            "quantity": {"type": "INTEGER"},
            "budget": {"type": "NUMBER"},
            "horizon": {"type": "INTEGER"},
        },
        "required": ["tool"],
    },
}


INSIGHT_WORDS = [
    ("regulars", ("regular", "loyal", "repeat", "visit", "habit", "rhythm", "come back", "comes back", "due back")),
    ("restock", ("replenish", "reorder", "re-order", "running low", "low on", "top-up", "top up", "how much to order")),
    ("falling", ("losing traction", "falling", "declin", "slowing", "selling worst", "worst sell", "weakest")),
    ("rising", ("rising", "trending", "growing", "gaining")),
    ("dead_shelf", ("check this shelf", "which shelf", "no recorded sales", "not selling", "dead stock")),
    ("revenue_leader", ("revenue leader", "most revenue", "brings in the most", "top revenue", "highest revenue")),
    ("most_sold", ("most sold", "best seller", "bestseller", "best selling", "top seller", "selling the most", "top selling")),
]


def local_insight(lower):
    for name, words in INSIGHT_WORDS:
        if any(w in lower for w in words):
            return name
    return None


PRICE_INTENT = re.compile(
    r"\b(price|pricing|reprice|re-price|sell(?:ing)? (?:it )?(?:at|for)|break[- ]?even|justify|additional units)\b|₹\s*\d"
)
AMOUNT = re.compile(r"(?:₹|\brs\.?|\binr)\s*(\d+(?:\.\d{1,2})?)|\b(?:at|to|for)\s+(\d+(?:\.\d{1,2})?)\b(?!\s*(?:kg|g|l|ml|days?|units?|%))")


def price_route(lower, products, period):
    """Repricing questions. Needs one existing product; amounts come only from the user's own words."""
    if any(w in lower for w in ("replace", "replacement", "swap", "lookalike")) or not PRICE_INTENT.search(lower):
        return None
    named = [(lower.find(a.lower()), p) for p in products for a in [p["id"], *p["aliases"]] if a.lower() in lower]
    named = [p for _, p in sorted(named, key=lambda x: x[0]) if not p["candidate"]]
    if not named:
        return None
    amounts = [float(a or b) for a, b in AMOUNT.findall(lower)]
    horizon = next((int(h) for h in re.findall(r"(\d{1,2})\s*(?:-|\s)?days?", lower) if 1 <= int(h) <= 30), None)
    horizon = {"day": 7, "week": 7, "month": 30}[period] if horizon is None and "month" in lower else horizon or 7
    wants_best = any(w in lower for w in ("best price", "optimal", "which price", "recommend", "supported price", "compare"))
    if len(amounts) >= 3 or (wants_best and amounts) or (len(amounts) >= 2 and "compare" in lower):
        return ToolCall(tool="recommend_price", period=period, product=named[0]["id"], candidates=sorted(set(amounts)), horizon=horizon)
    if not amounts:
        return ToolCall(tool="recommend_price", period=period, product=named[0]["id"], horizon=horizon) if wants_best else None
    return ToolCall(tool="reprice", period=period, product=named[0]["id"], price=amounts[-1], horizon=horizon)


def local_route(text, mid, period, dataset="live"):
    lower = text.lower()
    from pricing.data import sku_catalogue

    priced = price_route(lower, sku_catalogue(mid, dataset), period)
    if priced:
        return priced
    if re.search(r"\b(month|monthly|mahine)\b", lower):
        period = "month"
    elif re.search(r"\b(week|weekly|hafte)\b", lower):
        period = "week"
    elif re.search(r"\b(today|day|aaj)\b", lower):
        period = "day"
    matches = []
    for p in catalogue(mid):
        positions = [lower.find(a.lower()) for a in [p["id"], *p["aliases"]] if a.lower() in lower]
        if positions:
            matches.append((min(positions), p))
    matches.sort(key=lambda x: x[0])
    identified = [p for _, p in matches]
    if any(w in lower for w in ("replace", "replacement", "swap", "what if", "badal")):
        if not identified:
            return None
        existing = [p for p in identified if not p["candidate"]]
        candidate = [p for p in identified if p["candidate"]]
        if not existing:
            return None
        return ToolCall(
            tool="replace" if candidate else "recommend",
            period=period,
            remove=existing[0]["id"],
            replace=candidate[0]["id"] if candidate else None,
        )
    if any(w in lower for w in ("lookalike", "similar shops", "peer")):
        return ToolCall(
            tool="peers",
            period=period,
            replace=identified[0]["id"]
            if identified
            else next(p["id"] for p in catalogue(mid) if p["candidate"]),
        )
    insight = local_insight(lower)
    if insight:
        return ToolCall(tool="insight", period=period, insight=insight)
    if any(w in lower for w in ("stock", "inventory", "restock", "unpopular", "dead", "bacha", "kitna")):
        return ToolCall(tool="inventory", period=period)
    if any(
        w in lower
        for w in (
            "overview",
            "sales",
            "revenue",
            "sold",
            "customer",
            "rising",
            "traction",
            "aaj",
            "today",
            "week",
            "month",
            "day",
            "summary",
        )
    ):
        return ToolCall(tool="overview", period=period)
    return None


def gemini_route(text, mid, period):
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or os.getenv("GEMINI_ENABLED", "false").lower() != "true":
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", model):
        return None
    prompt = {
        "question": text,
        "selected_period": period,
        "canonical_products": [
            {"id": p["id"], "name": p["name"], "candidate": p["candidate"]} for p in catalogue(mid)
        ],
        "instruction": "Choose one read-only tool. Use canonical IDs. No explanation, arithmetic, forecasts or orders. Unsupported questions must not call a tool.",
    }
    try:
        with httpx.Client(timeout=20, trust_env=False) as client:
            res = client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                json={
                    "contents": [{"role": "user", "parts": [{"text": str(prompt)}]}],
                    "tools": [{"functionDeclarations": [DECLARATION]}],
                    "generationConfig": {"temperature": 0},
                },
            )
        res.raise_for_status()
        calls = [
            p["functionCall"]
            for c in res.json().get("candidates", [])
            for p in c.get("content", {}).get("parts", [])
            if "functionCall" in p
        ]
        if len(calls) != 1 or calls[0].get("name") != "merchant_decision":
            return None
        return ToolCall.model_validate(calls[0]["args"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def ask(mid, text, period="day", language="en-IN", dataset="live"):
    from ai import sarvam_chat

    trace = []
    requested_language = language
    live = sarvam_chat.enabled()
    if language == "unknown":
        language = sarvam_chat.detect_language(text) if live else None
        language = language or "en-IN"
    if live:
        call, trace = sarvam_chat.route(text, mid, period, language, dataset)
        provider = "Sarvam validated tool route"
    else:
        call = local_route(text, mid, period, dataset)
        provider = "Local constrained tool route (Sarvam unavailable)"
    response = execute_call(mid, call, provider, dataset)
    if trace and response["tool"] != "clarify":
        trace[-1]["status"] = "executed"
    response["tool_trace"] = trace
    response["canonical_answer"] = response["answer"]
    response["language_code"] = "en-IN"
    response["requested_language"] = requested_language
    response["translation_status"] = "canonical English template"
    if live:
        reply, state = sarvam_chat.compose(text, response["answer"], language, response["receipt"])
        if reply:
            response.update(answer=reply, language_code=language, translation_status=state, composed_by_model=True)
        else:
            # Fall back to the engine's own wording, translated when the merchant wrote in another language.
            reply, code, why = sarvam_chat.localize(response["answer"], mid, language, response["receipt"])
            response.update(answer=reply, language_code=code, translation_status=f"{state}. {why}", composed_by_model=False)
    return response


def execute_call(mid, call, provider, dataset="live"):
    if not call:
        return {
            "tool": "clarify",
            "provider": provider,
            "answer": "Please name the product to replace, or ask about sales, stock, customers or lookalike shops. I can only answer from the recorded POS data and the supported twin tools.",
            "result": None,
            "receipt": None,
            "grounded": True,
        }
    args = call.model_dump()
    if call.tool in ("reprice", "recommend_price"):
        from pricing import service as pricing

        if not call.product:
            raise ValueError("Repricing needs the product")
        if call.tool == "reprice":
            if call.price is None:
                raise ValueError("Repricing needs a proposed price")
            result = pricing.reprice(mid, call.product, call.price, call.horizon, dataset)
        else:
            result = pricing.recommend_price(mid, call.product, call.horizon, dataset, candidates=call.candidates)
        answer = f"{result['headline']} Evidence: {result['evidence']['label']}. Verdict: {result['decision']['label']}."
        proof = result["receipt"]
    elif call.tool == "insight":
        if not call.insight:
            raise ValueError("Insight tool needs an insight name")
        result = run_insight(mid, call.insight, call.period)
        answer = f"{result['title']}: {result['headline']}. {result['detail']}"
        proof = result["receipt"]
    elif call.tool in ("overview", "inventory"):
        result = overview(mid, call.period)
        if call.tool == "inventory":
            restock = run_insight(mid, "restock", call.period, data=result)
            answer = f"{len(result['nudges'])} inventory checks for {result['start']} to {result['end']}. "
            if restock["facts"].get("items"):
                answer += "Replenish soon: " + restock["detail"] + " "
            others = [p for p in result["nudges"] if p["reason"] != "restock soon"][:3]
            if others:
                answer += (
                    "Also review: "
                    + "; ".join(f"{p['name']}: {p['reason']} ({p['on_hand']} on hand)" for p in others)
                    + ". "
                )
            answer += "Check availability before calling a product dead."
            result["receipt"]["output"]["restock"] = restock["facts"]
        else:
            answer = f"From {result['start']} to {result['end']}, recorded revenue was ₹{result['revenue']:,.0f} across {result['bills']} bills. "
            if result["top_units"]:
                p = result["top_units"][0]
                answer += f"{p['name']} led units ({p['units']}); "
            if result["top_revenue"]:
                p = result["top_revenue"][0]
                answer += f"{p['name']} contributed the most revenue (₹{p['revenue']:,.0f}). "
            if result["rising"]:
                p = result["rising"][0]
                answer += f"{p['name']} is rising ({p['rate_change_pct']:+.1f}% in the latest weekly availability-adjusted rate). "
            if result["falling"]:
                p = result["falling"][0]
                answer += f"{p['name']} is losing traction ({p['rate_change_pct']:+.1f}%). "
            if result["dead"]:
                answer += (
                    "No recorded sales while available: "
                    + ", ".join(p["name"] for p in result["dead"])
                    + ". "
                )
            if result["customer_profiles"]:
                answer += (
                    "Largest purchased-basket profiles: "
                    + ", ".join(
                        f"{p['profile']} ({p['bills']} bills)" for p in result["customer_profiles"][:2]
                    )
                    + ". "
                )
            answer += "Basket profiles describe purchases, not demographics. Ask about regular customers for buying rhythms."
        proof = result["receipt"]
    elif call.tool == "peers":
        result = peers(mid, call.replace or call.remove or "")
        if result["verdict"] != "SUPPORTED":
            answer = result["reason"]
        else:
            answer = f"{result['name']} has {result['peer_count']} eligible anonymized donors in the selected cohort (effective peers: {result['effective_peers']}). Their weighted recorded rate is {result['peer_rate_per_100_bills']:.3f} units per 100 available bill opportunities. This transfers demand evidence, not costs or customer demographics."
        proof = result.get("receipt")
    elif call.tool == "replace":
        if not call.remove or not call.replace:
            raise ValueError("Replacement needs both canonical products")
        result = replacement(mid, call.remove, call.replace, call.quantity, call.horizon, call.budget)
        answer = scenario_answer(result)
        proof = result.get("receipt")
    else:
        if not call.remove:
            raise ValueError("Recommendation needs the product to remove")
        result = recommend(mid, call.remove, call.quantity, call.budget, call.horizon)
        if result["candidates"]:
            answer = "Highest conservative revenue trial: " + scenario_answer(result["candidates"][0])
            proof = result["candidates"][0]["receipt"]
        else:
            answer = result["reason"]
            proof = None
    if proof:
        proof = copy.deepcopy(proof)
        # Explicit display bindings preserve rounding/percentage units under the numeric guard.
        bindings = {"rate_denominator_bills": 100}
        if call.tool == "inventory":
            bindings["nudge_count"] = len(result["nudges"])
        if call.tool == "overview":
            bindings["weekly_rate_changes_as_fractions"] = [
                p["rate_change_pct"] / 100 for p in result["rising"] + result["falling"]
            ]
        if call.tool in ("replace", "recommend"):
            scenario = result if call.tool == "replace" else result["candidates"][0]
            bindings["rounded_rupee_display"] = {
                name: round(scenario[name]) for name in ("incremental_revenue", "p10", "p90", "purchase_cost")
            }
        proof["output"]["display_bindings"] = bindings
        if not check(answer, proof):
            answer = (
                "The calculation is ready. Open its receipt to inspect the exact outputs and assumptions."
            )
    return dict(
        tool=call.tool,
        provider=provider,
        answer=answer,
        result=result,
        receipt=proof,
        arguments=args,
        grounded=True,
        guard_passed=check(answer, proof or {}),
    )


def scenario_answer(result):
    if result["verdict"] != "SCENARIO":
        return result["reason"]
    return (
        f"Replacing {result['remove']} with {result['replace']} gives a modeled {result['horizon']}-day incremental revenue of ₹{result['incremental_revenue']:,.0f} "
        f"(P10 ₹{result['p10']:,.0f}; P90 ₹{result['p90']:,.0f}). Upfront purchase cash is ₹{result['purchase_cost']:,.0f}. "
        f"The model uses {result['peer_count']} anonymized donors and includes stock caps and substitution. This is an assumption-based trial estimate, not guaranteed or causal uplift."
    )
