"""Synthetic cohort transition, no customer identity stored or shared."""

import numpy as np


def evolve(cohorts, days, seed=42):
    rng = np.random.default_rng(seed)
    c = dict(cohorts)
    for _ in range(days):
        returning = int(rng.binomial(c["new"], 0.15))
        cooling = int(rng.binomial(c["repeat"], 0.015))
        churning = int(rng.binomial(c["at_risk"], 0.04))
        recovering = int(rng.binomial(c["at_risk"] - churning, 0.02))
        reactivating = int(rng.binomial(c["inactive"], 0.005))
        arrivals = int(rng.poisson(2))
        c["new"] += arrivals - returning
        c["repeat"] += returning + recovering + reactivating - cooling
        c["at_risk"] += cooling - churning - recovering
        c["inactive"] += churning - reactivating
    return c
