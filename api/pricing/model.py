"""Regularised negative-binomial demand model with a censored likelihood for stockout days.

log E[D_t] = b0 + b_price * log(p_t / p_ref) + b_promo * promo_t + weekday_t
D_t ~ NegBin(mean E[D_t], overdispersion alpha)

So E[D(p)] = baseline * (p / p_ref)^(-eta) with eta = -b_price. A day on which stock ran out contributes
P(D >= units sold), not P(D = units sold). The price coefficient has a normal prior; when comparable items with
randomized price tests exist it is centred on their pooled estimate (partial pooling), otherwise it is nearly flat.
Parameter uncertainty is a Laplace approximation around the penalised optimum.
"""

import math
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import nbinom

NAMES = ["intercept", "log_price", "promo", "tue", "wed", "thu", "fri", "sat", "sun"]
RIDGE = 1.0  # penalty on promo and weekday effects (intercept and price are handled separately)
ALPHA_PRIOR = (math.log(0.15), 1.0)  # weak prior on log overdispersion
FLAT_PRIOR = (0.0, 5.0)  # used when no comparable items give a price prior


def features(days, prices, promo, ref_price):
    n = len(days)
    X = np.zeros((n, len(NAMES)))
    X[:, 0] = 1.0
    X[:, 1] = np.log(np.asarray(prices, float) / ref_price)
    X[:, 2] = np.asarray(promo, float)
    for i, d in enumerate(days):
        if d.weekday() > 0:
            X[i, 2 + d.weekday()] = 1.0
    return X


def _logpmf(y, mu, alpha):
    r = 1.0 / alpha
    return gammaln(y + r) - gammaln(r) - gammaln(y + 1) + r * np.log(r / (r + mu)) + y * np.log(mu / (r + mu))


def _loglik(theta, X, y, cens):
    mu = np.exp(np.clip(X @ theta[:-1], -20, 20))
    alpha = math.exp(np.clip(theta[-1], -6, 3))
    ll = np.where(cens, 0.0, _logpmf(y, mu, alpha))
    if cens.any():
        r = 1.0 / alpha
        sf = nbinom.sf(y[cens] - 1, r, r / (r + mu[cens]))  # P(D >= y)
        ll[cens] = np.log(np.maximum(sf, 1e-300))
    return ll.sum()


def _penalty_terms(prior):
    centre = np.zeros(len(NAMES) + 1)
    precision = np.full(len(NAMES) + 1, RIDGE)
    precision[0] = 0.0
    centre[1], precision[1] = prior[0], 1.0 / prior[1] ** 2
    centre[-1], precision[-1] = ALPHA_PRIOR[0], 1.0 / ALPHA_PRIOR[1] ** 2
    return centre, precision


def fit(series, prior=FLAT_PRIOR, last_day=None):
    """Fit on available days (optionally up to `last_day`). Returns None when there is too little to fit."""
    rows = [r for r in series.rows if r["available"] and (last_day is None or r["day"] <= last_day)]
    if len(rows) < 30 or len({r["price"] for r in rows}) < 2:
        return None
    X = features([r["day"] for r in rows], [r["price"] for r in rows], [r["promo"] for r in rows], series.price)
    y = np.array([r["units"] for r in rows], float)
    cens = np.array([r["censored"] for r in rows], bool)
    centre, precision = _penalty_terms(prior)

    def objective(theta):
        return -_loglik(theta, X, y, cens) + 0.5 * float(np.sum(precision * (theta - centre) ** 2))

    start = np.zeros(len(NAMES) + 1)
    start[0] = math.log(max(y.mean(), 0.5))
    start[-1] = math.log(0.15)
    res = minimize(objective, start, method="L-BFGS-B")
    theta = res.x
    # Numerical Hessian of the penalised objective gives the Laplace covariance.
    k = len(theta)
    H = np.zeros((k, k))
    h = 1e-3
    for i in range(k):
        for j in range(i, k):
            e_i, e_j = np.eye(k)[i] * h, np.eye(k)[j] * h
            H[i, j] = H[j, i] = (
                objective(theta + e_i + e_j) - objective(theta + e_i - e_j)
                - objective(theta - e_i + e_j) + objective(theta - e_i - e_j)
            ) / (4 * h * h)
    w, v = np.linalg.eigh((H + H.T) / 2)
    cov = (v * (1.0 / np.maximum(w, 1e-6))) @ v.T
    # Demand shocks last about a week (festivals, weather, local events), so days are not independent. Use a
    # week-clustered robust (sandwich) covariance rather than the model-based one when there are enough weeks.
    first = rows[0]["day"]
    week = np.array([(r["day"] - first).days // 7 for r in rows])
    clusters = np.unique(week)
    robust = False
    if len(clusters) >= 8:
        scores = []
        for c in clusters:
            m = week == c
            g = np.zeros(k)
            for i in range(k):
                e = np.eye(k)[i] * 1e-4
                g[i] = (_loglik(theta + e, X[m], y[m], cens[m]) - _loglik(theta - e, X[m], y[m], cens[m])) / 2e-4
            scores.append(g)
        S = np.array(scores)
        meat = S.T @ S * len(clusters) / (len(clusters) - 1)
        sandwich = cov @ meat @ cov
        cov = (sandwich + sandwich.T) / 2 + 1e-9 * np.eye(k)
        robust = True
    se_price = math.sqrt(max(cov[1, 1], 0))
    data_precision = max(H[1, 1] - precision[1], 1e-9)
    return dict(
        theta=theta, cov=cov, names=NAMES + ["log_alpha"], ref_price=series.price,
        eta=-float(theta[1]), eta_se=se_price, alpha=float(math.exp(theta[-1])),
        n_obs=len(rows), n_censored=int(cens.sum()), converged=bool(res.success), robust_weekly_clusters=robust,
        prior=dict(mean=prior[0], sd=prior[1], weight=float(precision[1] / (precision[1] + data_precision))),
    )


def draw_parameters(fitted, n, rng):
    chol = np.linalg.cholesky(fitted["cov"] + 1e-9 * np.eye(len(fitted["theta"])))
    return fitted["theta"] + rng.standard_normal((n, len(fitted["theta"]))) @ chol.T


def mean_demand(thetas, days, price, ref_price, promo=0):
    """Expected demand per draw per day at a given price; shape (draws, days)."""
    X = features(days, [price] * len(days), [promo] * len(days), ref_price)
    return np.exp(np.clip(thetas[:, :-1] @ X.T, -20, 20))
