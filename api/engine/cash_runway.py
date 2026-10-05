import numpy as np
from engine.receipts import Receipt


def runway(shop, horizon=14, n_paths=2048, risk=0.1, seed=42):
    if not 0 < risk < 1 or n_paths < 2000 or not 1 <= horizon <= 14:
        raise ValueError("Use risk in (0,1), at least 2000 paths and a 1–14 day horizon")
    rng = np.random.default_rng(seed)
    history = np.asarray(shop["payments"][-56:], dtype=float)
    # Amount forecast uses observed settlement-channel coverage only.
    means = np.array(
        [history[np.arange(len(history)) % 7 == (len(history) + i) % 7].mean() for i in range(horizon)]
    )
    cv = max(0.1, float(history.std() / max(history.mean(), 1)))
    sales = rng.lognormal(np.log(np.maximum(means, 0.01)) - 0.5 * cv**2, cv, (n_paths, horizon))
    lag = rng.integers(1, 3, n_paths)
    inflows = np.zeros_like(sales)
    for delay in [1, 2]:
        mask = lag == delay
        inflows[mask, delay:] = sales[mask, :-delay]
    for i, amount in enumerate(shop["pending"][:horizon]):
        inflows[:, i] += amount
    path = shop["cash"] + np.cumsum(inflows - np.array(shop["dues"][:horizon]), axis=1)
    minimum = np.minimum(shop["cash"], path.min(axis=1))
    prob = float(np.mean(minimum < 0))
    marginal = np.mean(path < 0, axis=0)
    first = np.where(marginal >= 0.35)[0]
    quant = np.quantile(path, [0.1, 0.5, 0.9], axis=0).round(2).tolist()
    return Receipt(
        inputs={
            "opening_cash": shop["cash"],
            "pending": shop["pending"],
            "dues": shop["dues"],
            "risk_level": risk,
            "n_paths": n_paths,
            "horizon_days": horizon,
        },
        assumptions=[
            "Only recorded cash and liabilities included; observed payment channel only",
            "Lognormal daily receipts; T+1/T+2 lag; parameter uncertainty omitted",
        ],
        formula_text="C_t=C_0+Σ settlements−Σ dues; safe=max(0,Q_r(min C_t))",
        output={
            "gap_probability": prob,
            "earliest_likely_gap_day": int(first[0] + 1) if len(first) else None,
            "safe_to_commit": round(max(0, float(np.quantile(minimum, risk))), 2),
            "gap_size": round(max(0, -float(np.quantile(minimum, 0.1))), 2),
        },
        p10=quant[0],
        p50=quant[1],
        p90=quant[2],
        data_tier=shop["data_tier"],
        data_quality_flags=["SIMULATED_DATA", "MERCHANT_SUPPLIED_CASH_AND_DUES", "PARTIAL_CHANNEL_COVERAGE"],
    )
