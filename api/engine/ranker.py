from engine.receipts import Receipt
from twin.simulator import simulate


def rank(shop, allocation):
    actions = []
    if shop["data_tier"] == "B":
        for order in allocation.output.get("orders", []):
            action = {"type": "restock", "orders": [order]}
            receipt = simulate(shop, action, n_paths=256)
            spend = order["spend"]
            actions.append(
                {
                    "label": "Restock " + order["name"],
                    "action": action,
                    "spend": spend,
                    "profit": receipt.output["expected_incremental_profit"],
                    "roi": receipt.output["expected_incremental_profit"] / spend if spend else None,
                    "probability_loss": receipt.output["probability_loss"],
                    "receipt": receipt.model_dump(),
                }
            )
    actions.sort(key=lambda a: a["roi"] if a["roi"] is not None else float("-inf"), reverse=True)
    actions = [a for a in actions if a["profit"] > 0][:4]
    actions.append(
        {
            "label": "Keep a cash buffer",
            "action": {"type": "hold"},
            "spend": 0,
            "profit": 0,
            "roi": None,
            "probability_loss": 0,
            "receipt": None,
        }
    )
    return Receipt(
        inputs={"horizon_days": 7},
        formula_text="Rank paired Δprofit/cash committed over same horizon",
        assumptions=["Holding cash is a risk safeguard, with undefined ROI"],
        output={"actions": actions},
        data_tier=shop["data_tier"],
    )
