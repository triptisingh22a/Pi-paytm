import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from engine.demand import forecast
from engine.receipts import Receipt, insufficient


def allocate(shop, budget, horizon=7, seed=42):
    if budget < 0 or not np.isfinite(budget):
        raise ValueError("Budget must be finite and nonnegative")
    if shop["data_tier"] != "B" or not shop["skus"] or any(s.get("cost") is None for s in shop["skus"]):
        return insufficient(shop["data_tier"], "SKU_COSTS_REQUIRED")
    rng = np.random.default_rng(seed)
    choices, costs, values = [], [], []
    for i, sku in enumerate(shop["skus"]):
        if sku["cost"] <= 0:
            return insufficient("B", "POSITIVE_COST_REQUIRED")
        mu = np.array(forecast(sku, horizon).output["mean_daily"])
        lead = sku["lead_time"]
        window = max(0, min(horizon - lead, sku["shelf_life"]))
        demand = rng.poisson(float(mu[lead : lead + window].sum()), 2048)
        at_arrival = max(0, sku["stock"] - int(mu[:lead].sum()))
        cap = min(120, int(np.quantile(demand, 0.99)) + 1)
        for quantity in range(cap + 1):
            extra_sales = np.minimum(demand, at_arrival + quantity) - np.minimum(demand, at_arrival)
            salvage = (quantity - extra_sales) * sku["cost"] if sku["shelf_life"] > horizon - lead else 0
            profit = float(np.mean(sku["price"] * extra_sales - sku["cost"] * quantity + salvage))
            choices.append((i, quantity))
            costs.append(sku["cost"] * quantity)
            values.append(profit)
    costs, values = np.array(costs), np.array(values)
    groups = np.array([[float(c[0] == i) for c in choices] for i in range(len(shop["skus"]))])

    def solve(b):
        matrix = np.vstack([groups, costs])
        lower = np.r_[np.ones(len(groups)), -np.inf]
        upper = np.r_[np.ones(len(groups)), b]
        result = milp(
            -values,
            integrality=np.ones(len(choices)),
            bounds=Bounds(0, 1),
            constraints=LinearConstraint(matrix, lower, upper),
            options={"time_limit": 5},
        )
        if not result.success:
            raise RuntimeError("Allocation solver failed; no recommendation issued")
        selected = np.where(result.x > 0.5)[0]
        return selected, float(values[selected].sum())

    selected, value = solve(budget)
    _, next_value = solve(budget + 1000)
    orders = [
        {
            "sku_id": shop["skus"][choices[j][0]]["id"],
            "name": shop["skus"][choices[j][0]]["name"],
            "quantity": choices[j][1],
            "spend": round(float(costs[j]), 2),
            "incremental_profit": round(float(values[j]), 2),
            "flag": "HOT_SELLER"
            if shop["skus"][choices[j][0]]["stock"] < shop["skus"][choices[j][0]]["mean"] * 2
            else "CHECK_STOCK",
        }
        for j in selected
        if choices[j][1] > 0
    ]
    return Receipt(
        inputs={"budget": budget, "horizon_days": horizon},
        assumptions=[
            "Finite candidate caps at 120 units; 2048 demand scenarios",
            "Existing stock remaining at arrival approximated by mean consumption",
            "Unexpired inventory valued at cost; expiry salvage zero",
        ],
        formula_text="max Σ_i V_i(q_i), Σ_i c_i q_i≤B; one integer choice per SKU",
        steps=[{"solver": "scipy.optimize.milp", "candidate_count": len(choices)}],
        output={
            "orders": orders,
            "spend": round(float(costs[selected].sum()), 2),
            "expected_incremental_profit": round(value, 2),
            "next_1000_profit": round(next_value - value, 2),
        },
    )
