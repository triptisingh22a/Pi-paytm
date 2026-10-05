"""What does the price history actually say? Evidence is judged before any price response is estimated.

Thousands of sales at one price are one price level. Many days inside one price spell are one assignment, not
many experiments. Observational price changes are never described as causal.
"""

from itertools import groupby

MIN_EXPERIMENT_BLOCKS = 8
MIN_OBSERVATIONAL_CHANGES = 4
MIN_DAYS = 60

LABELS = {
    "real_experiment": "Randomized price test",
    "synthetic_experiment": "Randomized price test (synthetic data)",
    "observational": "Observational scenario",
    "peer_prior": "Peer-prior scenario",
    "insufficient": "Insufficient evidence",
}


def spells(rows):
    """Consecutive runs of the same offered price."""
    return [(p, len(list(g))) for p, g in groupby(r["price"] for r in rows)]


def assess(series, proposed=None):
    rows = series.rows
    live = [r for r in rows if r["available"]]
    runs = spells(rows)
    levels = sorted({r["price"] for r in rows})
    changes = max(len(runs) - 1, 0)
    randomized = [r for r in rows if r["assignment"] == "randomized"]
    blocks = {r["block"] for r in randomized if r["block"] is not None}
    block_levels = {r["price"] for r in randomized}
    censored = sum(1 for r in live if r["censored"])
    promo = sum(1 for r in rows if r["promo"])
    lo, hi = (levels[0], levels[-1]) if levels else (None, None)
    support = None
    if proposed is not None and levels:
        if lo <= proposed <= hi:
            support = dict(kind="interpolation", outside_by_fraction=0.0)
        else:
            gap = (lo - proposed) / lo if proposed < lo else (proposed - hi) / hi
            support = dict(kind="extrapolation", outside_by_fraction=round(gap, 4))
    flags = []
    if series.cost_levels > 1:
        flags.append("COST_VARIES_BY_BATCH")
    if live and censored / len(live) > 0.2:
        flags.append("FREQUENT_STOCKOUTS")
    if promo:
        flags.append("PROMOTION_DAYS_PRESENT")
    if series.dataset == "pilot":
        flags.append("SYNTHETIC_DATA")

    if len(levels) < 2 or changes < 2:
        state = "insufficient"
        why = (
            "This item has only ever been sold at one price, so its price response cannot be estimated."
            if len(levels) < 2
            else "The price changed only once or twice, which is too few episodes to separate price from everything else."
        )
    elif len(blocks) >= MIN_EXPERIMENT_BLOCKS and len(block_levels) >= 3 and len(live) >= MIN_DAYS:
        state = "synthetic_experiment" if series.dataset == "pilot" else "real_experiment"
        why = (
            f"Price was assigned at random across {len(blocks)} blocks and {len(block_levels)} price levels, "
            "so price is not tied to demand."
        )
    elif changes >= MIN_OBSERVATIONAL_CHANGES and len(live) >= MIN_DAYS:
        state = "observational"
        why = (
            f"Price changed {changes} times, but the changes were not randomized. Busy periods, stock and promotions can "
            "move with price, so any estimate is a scenario, not a causal answer."
        )
    else:
        state = "insufficient"
        why = "There is not enough price variation or history to estimate a price response."
    return dict(
        state=state,
        label=LABELS[state],
        explanation=why,
        distinct_price_levels=len(levels),
        price_levels_paise=levels,
        price_range_paise=[lo, hi],
        price_change_episodes=changes,
        randomized_blocks=len(blocks),
        observation_days=len(rows),
        available_days=len(live),
        stockout_days=censored,
        stockout_share=round(censored / len(live), 4) if live else 0.0,
        promotion_days=promo,
        support=support,
        peer_contribution="none: peers never supply price sensitivity for this item",
        flags=flags,
        limitations=[
            "Stockout days are left out when fitting, because sales on those days understate demand.",
            "Observed completed bills are not all visitors; a lower price may also change store traffic, which is not modelled.",
            "Category spillovers (shoppers switching from similar items) are not included.",
        ],
    )
