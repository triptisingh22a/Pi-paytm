from engine.receipts import Receipt


def loan_nudge(shop, cash, action, assumed_cost=0.02, threshold=0.35):
    gap = cash.output.get("gap_size", 0)
    spend = action.output.get("spend", 0)
    profit = action.output.get("expected_incremental_profit", 0)
    amount = min(gap, max(0, spend - shop["cash"]))
    eligible = (
        shop["data_tier"] == "B"
        and cash.output.get("gap_probability", 0) > threshold
        and amount > 0
        and profit > amount * assumed_cost
    )
    return Receipt(
        inputs={"assumed_cost_fraction": assumed_cost, "risk_threshold": threshold},
        formula_text="B and risk>threshold and 0<amount≤gap and Δprofit>borrowing cost",
        assumptions=["Illustrative assumed borrowing cost; no offer or underwriting claim"],
        output={
            "show": eligible,
            "amount": round(amount, 2) if eligible else None,
            "expected_return": profit if eligible else None,
            "assumed_cost": round(amount * assumed_cost, 2) if eligible else None,
            "consent": "Illustration only. Offered by a lending partner; terms apply. Sharing needs your consent.",
        },
        data_tier=shop["data_tier"],
    )
