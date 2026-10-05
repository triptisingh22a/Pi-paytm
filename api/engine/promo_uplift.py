import numpy as np
from engine.receipts import Receipt, insufficient


def promo(sku, discount=0.1, tier="B", seed=42):
    if tier != "B" or sku is None or sku.get("cost") is None:
        return insufficient(tier, "ITEM_COSTS_AND_EXPERIMENT_HISTORY_REQUIRED")
    if not 0 <= discount < 1:
        raise ValueError("Discount must be in [0,1)")
    episodes = [e for e in sku.get("promo_episodes", []) if abs(e["discount"] - discount) < 1e-8]
    if len(episodes) < 8:
        return insufficient(tier, "NO_MATCHING_DISCOUNT_EXPERIMENT")
    rng = np.random.default_rng(seed)
    a = np.array([[e["control"], e["treated"], e["post_control"], e["post"]] for e in episodes])
    sample = a[rng.integers(0, len(a), (2048, len(a)))].mean(axis=1)
    uplift = sample[:, 1] / np.maximum(sample[:, 0], 1) - 1
    pull = np.maximum(0, 1 - sample[:, 3] / np.maximum(sample[:, 2], 1))
    q = float(a[:, 0].mean())
    p, c = sku["price"], sku["cost"]
    net = q * ((1 + uplift) * ((1 - discount) * p - c) - (p - c)) - q * pull * (p - c)
    lo, mid, hi = np.quantile(net, [0.1, 0.5, 0.9]).round(2)
    verdict = "DO" if lo > 0 else "DON'T" if hi < 0 else "INSUFFICIENT_DATA"
    return Receipt(
        inputs={
            "sku": sku["name"],
            "price": p,
            "cost": c,
            "discount": discount,
            "baseline_units": q,
            "episodes": len(a),
        },
        assumptions=[
            "Randomized synthetic matched control episodes; bootstrap whole episodes",
            "Post-period loss treated as pull-forward; not a live causal claim",
        ],
        formula_text="Δπ=Q[(1+u)((1−d)p−c)−(p−c)]−Q f(p−c)",
        steps=[
            {
                "estimated_uplift": round(float(np.median(uplift)), 4),
                "estimated_pull_forward": round(float(np.median(pull)), 4),
            }
        ],
        output={
            "verdict": verdict,
            "incremental_profit": float(mid),
            "probability_loss": float(np.mean(net < 0)),
            "reason": "Discount cost on existing sales and future displaced sales included",
        },
        p10=float(lo),
        p50=float(mid),
        p90=float(hi),
    )
