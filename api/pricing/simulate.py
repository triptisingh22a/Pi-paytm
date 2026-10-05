"""Paired, stock-constrained simulation of a price over a horizon.

Per path: draw demand-model parameters (parameter uncertainty), draw daily demand (random future variation),
walk stock forward with timed replenishment, and record fulfilled units, revenue, cost and contribution.
Every candidate price shares the same parameter draws and the same uniforms, so differences are paired.
E[min(D, stock)] is computed over the simulated paths; it is not min(E[D], stock).
"""

import math
import numpy as np
from scipy.stats import nbinom
from pricing.model import mean_demand, draw_parameters

SEED = 92341
PARAM_DRAWS = 400
NOISE_DRAWS = 8
ASSUMED_ALPHA = 0.15


def assumption_model(daily_mean, eta, ref_price, alpha=ASSUMED_ALPHA):
    """A fixed-parameter stand-in used only for clearly labelled assumption-based scenarios."""
    k = 10
    theta = np.zeros(k)
    theta[0] = math.log(max(daily_mean, 1e-6))
    theta[1] = -eta
    theta[-1] = math.log(alpha)
    return dict(theta=theta, cov=np.zeros((k, k)), ref_price=ref_price, alpha=alpha, eta=eta)


def run(fitted, days, prices, cost, extra_cost, opening_stock, receipts=None, policy=None, seed=SEED,
        param_draws=PARAM_DRAWS, noise_draws=NOISE_DRAWS):
    """Simulate each price in `prices` (paise) and return per-price paired summaries.

    receipts: [(day_index, qty)] explicit arrivals. policy: {"weekday": 0, "level": 190} order-up-to rule applied
    identically under every price. cost and extra_cost are paise per unit.
    """
    rng = np.random.default_rng(seed)
    thetas = draw_parameters(fitted, param_draws, rng)
    alpha = np.exp(thetas[:, -1])[:, None, None]
    uniforms = rng.random((param_draws, noise_draws, len(days)))
    arrivals = np.zeros(len(days))
    for day_index, qty in receipts or []:
        if 0 <= day_index < len(days):
            arrivals[day_index] += qty
    out = {}
    for price in prices:
        mu = mean_demand(thetas, days, price, fitted["ref_price"])[:, None, :]
        r = 1.0 / alpha
        demand = nbinom.ppf(uniforms, r, r / (r + mu))
        stock = np.full((param_draws, noise_draws), float(opening_stock))
        sold = np.zeros_like(stock)
        stockout = np.zeros_like(stock)
        for t, d in enumerate(days):
            stock = stock + arrivals[t]
            if policy and d.weekday() == policy["weekday"]:
                stock = np.maximum(stock, policy["level"])
            fulfilled = np.minimum(demand[:, :, t], stock)
            stockout += demand[:, :, t] > stock
            stock = stock - fulfilled
            sold += fulfilled
        unit_margin = price - cost - extra_cost
        out[price] = dict(
            demand=demand.sum(axis=2), units=sold, remaining=stock, stockout_days=stockout,
            revenue=sold * price, contribution=sold * unit_margin,
        )
    return out


def _q(a, lo=10, hi=90):
    return [float(np.percentile(a, lo)), float(np.percentile(a, hi))]


def summarise(sim, current_price, price):
    """Summary of `price` against the baseline `current_price`, using the same paths."""
    s, b = sim[price], sim[current_price]
    delta = s["contribution"] - b["contribution"]
    per_param = delta.mean(axis=1)  # one number per parameter draw: uncertainty about the mean
    return dict(
        price_paise=price,
        expected_units=float(s["units"].mean()),
        units_outcome_interval=_q(s["units"]),
        units_mean_interval=_q(s["units"].mean(axis=1)),
        expected_demand=float(s["demand"].mean()),
        expected_units_lost_to_stock=float((s["demand"] - s["units"]).mean()),
        expected_revenue_paise=float(s["revenue"].mean()),
        expected_contribution_paise=float(s["contribution"].mean()),
        contribution_outcome_interval=_q(s["contribution"]),
        expected_remaining_stock=float(s["remaining"].mean()),
        stockout_probability=float((s["stockout_days"] > 0).mean()),
        expected_stockout_days=float(s["stockout_days"].mean()),
        delta_contribution_paise=float(delta.mean()),
        delta_outcome_interval=_q(delta),
        delta_mean_interval=_q(per_param),
        probability_lower=float((delta < 0).mean()),
        probability_higher=float((delta > 0).mean()),
        baseline_units=float(b["units"].mean()),
        baseline_contribution_paise=float(b["contribution"].mean()),
        delta_revenue_paise=float((s["revenue"] - b["revenue"]).mean()),
        paths=int(delta.size),
    )
