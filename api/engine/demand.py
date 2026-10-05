import numpy as np
from scipy.stats import poisson
from engine.receipts import Receipt


def design(rows):
    return np.array(
        [[1, *[int(r["weekday"] == d) for d in range(1, 7)], r["festival"], r["payday"]] for r in rows],
        dtype=float,
    )


def fit(rows):
    x = design(rows)
    y = np.log(np.array([r["sales"] for r in rows]) + 0.5)
    penalty = np.eye(9)
    penalty[0, 0] = 0
    return np.linalg.solve(x.T @ x + penalty, x.T @ y)


def forecast(sku, horizon=7, weekday=4, peer_prior=20):
    rows = sku.get("history", [])
    valid = [r for r in rows if not r["stockout"]]
    flags = ["SIMULATED_DATA", "PARAMETER_UNCERTAINTY_OMITTED"]
    loss = None
    if len(valid) < 35:
        mu = np.full(horizon, peer_prior, dtype=float)
        flags += ["COLD_START_PEER_PRIOR"]
    else:
        split = rows[-28]["date"]
        train = [r for r in valid if r["date"] < split]
        test = [r for r in valid if r["date"] >= split]
        coef = fit(train)
        if test:
            pred = np.maximum(0.1, np.exp(design(test) @ coef) - 0.5)
            truth = np.array([r["sales"] for r in test])
            losses = []
            for tau in [0.1, 0.5, 0.9]:
                err = truth - poisson.ppf(tau, pred)
                losses.extend((err * (tau - (err < 0))).tolist())
            loss = float(np.mean(losses))
        else:
            flags.append("NO_UNCENSORED_HOLDOUT")
        coef = fit(valid)
        future = [{"weekday": (weekday + i) % 7, "festival": 0, "payday": 0} for i in range(horizon)]
        mu = np.maximum(0.1, np.exp(design(future) @ coef) - 0.5)
    qs = [poisson.ppf(q, mu).astype(int).tolist() for q in [0.1, 0.5, 0.9]]
    return Receipt(
        inputs={"sku": sku["id"], "history_days": len(rows), "horizon_days": horizon},
        assumptions=[
            "Future event indicators must be supplied for festival forecasts",
            "Stock-out days excluded; Poisson daily demand",
        ],
        formula_text="log(Y+0.5)=Xβ; μ=exp(Xβ)-0.5; Poisson predictive quantiles",
        steps=[{"uncensored_rows": len(valid), "holdout_pinball_loss": loss}],
        output={"mean_daily": mu.tolist(), "backtest_pinball_loss": loss},
        p10=qs[0],
        p50=qs[1],
        p90=qs[2],
        data_quality_flags=flags,
    )
