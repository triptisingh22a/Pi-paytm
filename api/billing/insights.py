"""Pi insights. Every insight is a deterministic tool grounded in POS data.

The same tools feed the overview cards and the chat agent. Results are cached per shop and period,
refreshed on a schedule in the background and on demand.
"""

import math
import os
import threading
import time
from datetime import datetime, timezone
from billing.habits import WINDOW, customer_habits
from billing.services import overview, receipt

TARGET_COVER_DAYS = 14
WHEN = {"day": ("today", 1), "week": ("in the last 7 days", 7), "month": ("in the last 30 days", 30)}
IDS = ["most_sold", "revenue_leader", "rising", "falling", "dead_shelf", "restock", "regulars"]
TITLES = {
    "most_sold": "Most sold",
    "revenue_leader": "Revenue leader",
    "rising": "Rising star",
    "falling": "Losing traction",
    "dead_shelf": "Check this shelf",
    "restock": "Replenish soon",
    "regulars": "Regular customers",
}
DESCRIPTIONS = {
    "most_sold": "Product with the most units sold in the period.",
    "revenue_leader": "Product that brought in the most revenue and its share of the total.",
    "rising": "Product whose availability-adjusted sales rate rose most versus the prior week.",
    "falling": "Product whose availability-adjusted sales rate fell most versus the prior week.",
    "dead_shelf": "Stocked products with no recorded sales while available.",
    "restock": "Products with under 7 days of stock cover and a suggested top-up quantity.",
    "regulars": "Customers who buy the same product on a steady rhythm (daily, weekly, every N days) and who is due back.",
}
QUESTIONS = {
    "most_sold": "What is my most sold item?",
    "revenue_leader": "Which item brings in the most revenue?",
    "rising": "Which product is rising?",
    "falling": "Which product is losing traction?",
    "dead_shelf": "Which shelf should I check?",
    "restock": "What do I need to replenish soon?",
    "regulars": "Who are my regular customers?",
}


def _result(id, tone, headline, detail, facts, assumptions, window, merchant):
    return dict(
        id=id,
        title=TITLES[id],
        tone=tone,
        headline=headline,
        detail=detail,
        question=QUESTIONS[id],
        facts=facts,
        receipt=receipt(
            {"tool": "insight", "insight": id, "merchant": merchant, "window": window},
            DESCRIPTIONS[id],
            facts,
            assumptions,
        ),
    )


def _money(n):
    return f"₹{n:,.0f}"


def run_insight(mid, id, period="day", data=None, habits=None):
    if id not in IDS:
        raise ValueError("Unknown insight")
    o = data or overview(mid, period)
    result = _run(mid, id, period, o, habits)
    # Product names carry pack sizes ("Milk 1 L"); listing them lets the numeric guard recognise those digits.
    result["receipt"]["output"]["product_names"] = [p["name"] for p in o["inventory"]]
    return result


def _run(mid, id, period, o, habits):
    when, days = WHEN[period]
    window = [o["start"], o["end"]]
    inv = {p["name"]: p for p in o["inventory"]}
    if id == "most_sold":
        p = o["top_units"][0] if o["top_units"] else None
        if not p:
            return _result(id, "info", "No sales recorded", f"No completed bills {when}.", {"days": days}, [], window, mid)
        rest = ", ".join(f"{x['name']} ({x['units']})" for x in o["top_units"][1:])
        facts = {"units": p["units"], "days": days, "runners_up": [x["units"] for x in o["top_units"][1:]]}
        return _result(
            id, "info", p["name"], f"{p['units']} units sold {when}." + (f" Next: {rest}." if rest else ""),
            facts, ["Units are summed from recorded bill lines."], window, mid,
        )
    if id == "revenue_leader":
        p = o["top_revenue"][0] if o["top_revenue"] else None
        if not p:
            return _result(id, "info", "No revenue recorded", f"No completed bills {when}.", {"days": days}, [], window, mid)
        full = inv[p["name"]]
        facts = {"revenue": p["revenue"], "share_fraction": round(full["revenue_share"] / 100, 4), "days": days}
        return _result(
            id, "info", p["name"],
            f"{_money(p['revenue'])} · {full['revenue_share']}% of revenue {when}.",
            facts, ["Revenue = quantity x realized unit price."], window, mid,
        )
    if id in ("rising", "falling"):
        pool = o["rising"] if id == "rising" else o["falling"]
        if not pool:
            return _result(
                id, "info", "No clear change",
                "No product moved more than 15% against the prior week once availability is accounted for.",
                {"threshold_fraction": 0.15}, ["Compares the latest 7 days with the 7 days before, per available bill."],
                window, mid,
            )
        p = pool[0]
        pct = p["rate_change_pct"]
        facts = {"change_fraction": round(abs(pct) / 100, 4), "threshold_fraction": 0.15}
        return _result(
            id, "up" if id == "rising" else "down", p["name"],
            f"Sells {abs(pct)}% {'faster' if pct > 0 else 'slower'} than the week before, adjusted for days it was on the shelf.",
            facts, ["Compares the latest 7 days with the 7 days before, per available bill."], window, mid,
        )
    if id == "dead_shelf":
        dead = o["dead"]
        if not dead:
            return _result(id, "info", "All shelves are moving", f"Every available product sold something {when}.",
                           {"days": days, "products": 0}, [], window, mid)
        facts = {"products": len(dead), "on_hand": [p["on_hand"] for p in dead], "days": days}
        return _result(
            id, "warn", ", ".join(p["name"] for p in dead),
            "No recorded sales while available: " + ", ".join(f"{p['name']} ({p['on_hand']} on hand)" for p in dead)
            + f" {when}. Check placement before calling it dead stock.",
            facts, ["Zero recorded sales is not proof of zero demand. Check availability and display first."], window, mid,
        )
    if id == "restock":
        rows = []
        for p in o["inventory"]:
            if p["health"] == "restock soon" and p["days_cover"]:
                rate = p["on_hand"] / p["days_cover"]
                rows.append(
                    dict(
                        name=p["name"], on_hand=p["on_hand"], days_cover=p["days_cover"],
                        topup=max(1, math.ceil(rate * TARGET_COVER_DAYS - p["on_hand"])),
                    )
                )
        rows.sort(key=lambda r: r["days_cover"])
        if not rows:
            return _result(id, "info", "Nothing to replenish yet", "Every stocked product has 7 or more days of cover.",
                           {"threshold_days": 7}, [], window, mid)
        facts = {"products": len(rows), "target_days": TARGET_COVER_DAYS, "items": rows}
        return _result(
            id, "warn", f"{len(rows)} product{'s' if len(rows) != 1 else ''} running low",
            "; ".join(
                f"{r['name']}: {r['on_hand']} on hand, {r['days_cover']} days of cover, about {r['topup']} more to reach {TARGET_COVER_DAYS} days"
                for r in rows
            ) + ".",
            facts,
            [
                "Cover = units on hand / average daily units sold over the latest 7 days.",
                f"Top-up = daily rate x {TARGET_COVER_DAYS} days - on hand. The {TARGET_COVER_DAYS}-day target is a demo assumption; lead time and supplier minimums are not modelled.",
            ],
            window, mid,
        )
    h = habits or customer_habits(mid)
    s = h["summary"]
    lead = h["groups"][0] if h["groups"] else None
    if not lead:
        return _result(id, "info", "No steady rhythms yet", f"No customer buys the same product on a steady rhythm in the last {WINDOW} days.",
                       {"days": WINDOW}, [], h["window"], mid)
    facts = {"regular_customers": s["regular_customers"], "habits": s["habits"], "due_back": s["due_back"],
             "days": WINDOW, "lead_customers": lead["customers"]}
    return _result(
        id, "info", f"{s['regular_customers']} customer{'s' if s['regular_customers'] != 1 else ''} with a steady rhythm",
        f"{lead['customers']} customer{'s' if lead['customers'] != 1 else ''} buy {lead['product_name']}: {lead['cadence'][0].lower() + lead['cadence'][1:]}. "
        f"{s['habits']} buying rhythms in the last {WINDOW} days; {s['due_back']} due back.",
        facts, h["receipt"]["assumptions"], h["window"], mid,
    )


# ---- cache, scheduled and manual refresh -------------------------------------------------------

_cache = {}
_lock = threading.Lock()


def _build(mid, period, trigger):
    data = overview(mid, period)
    habits = customer_habits(mid)
    items = [run_insight(mid, i, period, data, habits) for i in IDS]
    entry = dict(
        merchant=mid,
        period=period,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        trigger=trigger,
        refresh_seconds=refresh_seconds(),
        insights=items,
    )
    with _lock:
        _cache[(mid, period)] = entry
    return entry


def refresh_seconds():
    return int(os.getenv("INSIGHT_REFRESH_SECONDS", "900"))


def get_insights(mid, period="day", refresh=False):
    with _lock:
        entry = _cache.get((mid, period))
    if entry is None:
        return _build(mid, period, "first load")
    if refresh:
        return _build(mid, period, "manual refresh")
    return entry


def invalidate(mid):
    with _lock:
        for key in [k for k in _cache if k[0] == mid]:
            del _cache[key]


def _loop():
    while True:
        time.sleep(refresh_seconds())
        with _lock:
            keys = list(_cache)
        for mid, period in keys:
            try:
                _build(mid, period, "scheduled refresh")
            except Exception:  # a failed refresh keeps the last good result
                pass


def start_scheduler():
    threading.Thread(target=_loop, name="insight-refresh", daemon=True).start()
