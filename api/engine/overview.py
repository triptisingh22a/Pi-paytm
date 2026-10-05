from engine.receipts import Receipt


def overview(shop, period="week"):
    days = {"day": 1, "week": 7, "month": 30, "festival": 7}[period]
    sales = sum(shop["payments"][-days:])
    previous = sum(shop["payments"][-2 * days : -days])
    items = [
        {"name": s["name"], "units": sum(r["sales"] for r in s["history"][-days:])} for s in shop["skus"]
    ]
    return Receipt(
        inputs={"period": period, "days": days},
        formula_text="Σ recorded channel sales; change vs preceding period",
        output={
            "sales": round(sales, 2),
            "change_fraction": sales / previous - 1 if previous else None,
            "top_items": sorted(items, key=lambda s: s["units"], reverse=True),
            "repeat_rate": shop["repeat_rate"] if shop["data_tier"] == "B" else None,
        },
        assumptions=[
            "Festival view uses trailing seven days; no festival-specific inference",
            "Sales are payment-channel totals, not full business turnover",
        ],
        data_tier=shop["data_tier"],
    )
