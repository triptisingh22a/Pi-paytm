import copy
import numpy as np
from engine.demand import forecast
from engine.receipts import Receipt, insufficient
from twin.customers import evolve


def simulate(shop, action, horizon_days=7, n_paths=2048, seed=42):
    if shop["data_tier"] != "B":
        return insufficient("A", "ITEM_LEVEL_SIMULATION_REQUIRES_TIER_B")
    if not 1 <= horizon_days <= 14 or not 1 <= n_paths <= 10000:
        raise ValueError("Invalid simulation horizon or path count")
    if action.get("type") not in ("restock", "promo", "hold", "credit"):
        raise ValueError("Unsupported action")
    rng = np.random.default_rng(seed)
    mus = np.array([forecast(s, horizon_days).output["mean_daily"] for s in shop["skus"]])
    draws = rng.poisson(mus, (n_paths, len(shop["skus"]), horizon_days))
    delays = rng.integers(1, 3, n_paths)
    orders = action.get("orders", [])
    known = {s["id"]: s for s in shop["skus"]}
    for order in orders:
        if order["sku_id"] not in known or not isinstance(order["quantity"], int) or order["quantity"] < 0:
            raise ValueError("Invalid order")
    amount = sum(known[o["sku_id"]]["cost"] * o["quantity"] for o in orders)
    if action["type"] == "restock" and amount > shop["cash"] + 0.001:
        raise ValueError("Restock exceeds available cash; test affordable order or explicit credit")
    profits = np.zeros((2, n_paths))
    final_cash = np.zeros((2, n_paths))
    stockouts = np.zeros((2, n_paths))
    expiries = np.zeros((2, n_paths))
    final_stock = []
    for branch in range(2):
        sample_stock = {}
        for path in range(n_paths):
            cash = shop["cash"]
            pending = {i: v for i, v in enumerate(shop["pending"])}
            stock = {
                s["id"]: copy.deepcopy(s.get("batches", [[s["stock"], s["shelf_life"]]]))
                for s in shop["skus"]
            }
            profit = 0.0
            if branch and action["type"] == "restock":
                cash -= amount
            if branch and action["type"] == "credit":
                cash += action.get("amount", 0)
            for day in range(horizon_days):
                cash += pending.pop(day, 0) - shop["dues"][day]
                for j, sku in enumerate(shop["skus"]):
                    sid = sku["id"]
                    if branch and action["type"] == "restock" and day == sku["lead_time"]:
                        for o in orders:
                            if o["sku_id"] == sid:
                                stock[sid].append([o["quantity"], day + sku["shelf_life"]])
                    kept = []
                    for batch in stock[sid]:
                        if batch[1] <= day:
                            loss = batch[0] * sku["cost"]
                            profit -= loss
                            expiries[branch, path] += loss
                        else:
                            kept.append(batch)
                    stock[sid] = kept
                    demand = int(draws[path, j, day])
                    discount = 0.0
                    if branch and action["type"] == "promo" and sid == action.get("sku_id"):
                        # Estimated response is supplied by deterministic promo engine.
                        uplift = float(action.get("uplift", 0))
                        pull = float(action.get("pull_forward", 0))
                        demand = max(0, int(demand * (1 + uplift if day < horizon_days // 2 else 1 - pull)))
                        discount = float(action.get("discount", 0)) if day < horizon_days // 2 else 0
                    remaining = demand
                    for batch in stock[sid]:
                        sold = min(remaining, batch[0])
                        batch[0] -= sold
                        remaining -= sold
                    sold = demand - remaining
                    stockouts[branch, path] += int(remaining > 0)
                    revenue = sold * sku["price"] * (1 - discount)
                    profit += revenue - sold * sku["cost"]
                    due = day + int(delays[path])
                    pending[due] = pending.get(due, 0) + revenue
                # Expiry on the horizon boundary is charged, avoiding terminal day bias.
            for sku in shop["skus"]:
                for batch in stock[sku["id"]]:
                    if batch[1] <= horizon_days:
                        loss = batch[0] * sku["cost"]
                        profit -= loss
                        expiries[branch, path] += loss
            if branch and action["type"] == "credit":
                repay = action.get("amount", 0) * (1 + action.get("cost_fraction", 0.02))
                cash -= repay
                profit -= action.get("amount", 0) * action.get("cost_fraction", 0.02)
            profits[branch, path] = profit
            final_cash[branch, path] = cash
            if path == 0:
                sample_stock = {k: sum(b[0] for b in v if b[1] > horizon_days) for k, v in stock.items()}
                sample_pending = {str(k - horizon_days): v for k, v in pending.items() if k >= horizon_days}
                sample_batches = {
                    k: [[b[0], b[1] - horizon_days] for b in v if b[1] > horizon_days and b[0] > 0]
                    for k, v in stock.items()
                }
        final_stock.append({"stock": sample_stock, "pending": sample_pending, "batches": sample_batches})
    delta = profits[1] - profits[0]
    q = np.quantile(delta, [0.1, 0.5, 0.9]).round(2).tolist()
    return Receipt(
        inputs={
            "action": copy.deepcopy(action),
            "horizon_days": horizon_days,
            "n_paths": n_paths,
            "opening_cash": shop["cash"],
            "seed": seed,
        },
        assumptions=[
            "Common random numbers; FIFO expiry; settlement lag one or two days",
            "No automatic replenishment; simulated path is not observed outcome",
            "Purchase is asset acquisition; profit charges sold cost and expired stock",
        ],
        formula_text="Δπ=π(action)−π(do nothing), paired stochastic demand paths",
        output={
            "expected_incremental_profit": round(float(delta.mean()), 2),
            "probability_loss": round(float(np.mean(delta < 0)), 4),
            "baseline_profit": round(float(profits[0].mean()), 2),
            "action_profit": round(float(profits[1].mean()), 2),
            "baseline_cash": round(float(final_cash[0].mean()), 2),
            "action_cash": round(float(final_cash[1].mean()), 2),
            "baseline_stockouts": round(float(stockouts[0].mean()), 2),
            "action_stockouts": round(float(stockouts[1].mean()), 2),
            "expiry_loss": round(float(expiries[1].mean()), 2),
            "simulated_realized_delta": round(float(delta[0]), 2),
            "simulated_realized_cash": round(float(final_cash[1, 0]), 2),
            "terminal_sample": {
                **final_stock[1],
                "customer_cohorts": evolve(
                    shop.get("customer_cohorts", {"new": 25, "repeat": 70, "at_risk": 15, "inactive": 20}),
                    horizon_days,
                    seed,
                ),
            },
        },
        p10=q[0],
        p50=q[1],
        p90=q[2],
    )
