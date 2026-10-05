"""Candidate-price grid, decision labels and the experiment plan.

All thresholds are product choices, listed in `POLICY` and echoed in every receipt. They are not statistical
guarantees. Evidence limits the label: only a randomized price test inside its observed price range can say
"likely improves contribution"; weaker evidence stops at "trial recommended" (or "likely reduces" with a high bar).
"""

import math
from statistics import NormalDist

POLICY = dict(
    confident_probability=0.80,  # P(contribution higher) needed for "likely improves"
    downside_probability=0.80,  # P(contribution lower) needed for "likely reduces"
    observational_downside_probability=0.90,
    max_p10_loss_fraction=0.05,  # P10 loss must stay inside 5% of baseline contribution to call it "likely improves"
    min_margin_fraction=0.05,  # candidate must keep at least 5% margin on price
    default_span_fraction=0.15,  # default grid is +/-15% around the current price
    max_candidates=15,
    min_useful_improvement_fraction=0.05,  # experiment should detect a 5% contribution change
    power=0.80,
    alpha=0.05,
)
LABELS = {
    "likely_improves": "Likely improves contribution",
    "likely_reduces": "Likely reduces contribution",
    "trial_recommended": "Trial recommended",
    "insufficient_evidence": "Insufficient evidence",
}


def candidate_grid(current, cost, extra, step=None, low=None, high=None, explicit=None, max_price=None,
                   min_margin_fraction=None):
    """Prices (paise) to compare. Always includes the current price. Returns (prices, dropped_reasons)."""
    frac = POLICY["min_margin_fraction"] if min_margin_fraction is None else min_margin_fraction
    dropped = []
    if explicit:
        raw = sorted({int(p) for p in explicit} | {current})
    else:
        step = step or max(100, round(current * 0.02 / 100) * 100)  # whole rupees, about 2% of price
        lo = low if low is not None else int(current * (1 - POLICY["default_span_fraction"]))
        hi = high if high is not None else int(current * (1 + POLICY["default_span_fraction"]))
        lo, hi = max(lo, step), max(hi, lo)
        first = (lo + step - 1) // step * step
        raw = sorted({*range(first, hi + 1, step), current})
    keep = []
    for p in raw:
        if p == current:
            keep.append(p)
        elif max_price is not None and p > max_price:
            dropped.append((p, "above your maximum price"))
        elif p - cost - extra < frac * p:
            dropped.append((p, f"keeps under {int(frac * 100)}% margin"))
        else:
            keep.append(p)
    if len(keep) > POLICY["max_candidates"]:  # thin evenly but keep the current price
        idx = sorted({round(i * (len(keep) - 1) / (POLICY["max_candidates"] - 1)) for i in range(POLICY["max_candidates"])})
        keep = sorted({keep[i] for i in idx} | {current})
    return keep, dropped


def decide(evidence, summary):
    """Label one candidate. `summary` comes from simulate.summarise; None when no forecast is allowed."""
    if summary is None or evidence["state"] == "insufficient":
        return "insufficient_evidence"
    base = max(abs(summary["baseline_contribution_paise"]), 1.0)
    extrapolating = (evidence["support"] or {}).get("kind") == "extrapolation"
    p_up, p_down = summary["probability_higher"], summary["probability_lower"]
    experiment = evidence["state"] in ("real_experiment", "synthetic_experiment")
    if experiment and not extrapolating:
        if p_up >= POLICY["confident_probability"] and summary["delta_outcome_interval"][0] >= -POLICY["max_p10_loss_fraction"] * base:
            return "likely_improves"
        if p_down >= POLICY["downside_probability"]:
            return "likely_reduces"
        return "trial_recommended"
    if p_down >= POLICY["observational_downside_probability"] and not extrapolating:
        return "likely_reduces"
    return "trial_recommended"


def experiment_plan(series, candidates, summaries, horizon, baseline_daily_contribution, daily_contribution_sd, cost,
                    extra):
    """A structured, local-only plan for learning the price response. Nothing here is executed."""
    z = NormalDist()
    delta = POLICY["min_useful_improvement_fraction"] * max(abs(baseline_daily_contribution), 1.0)
    sd = max(daily_contribution_sd, 1.0)
    n = 2 * ((z.inv_cdf(1 - POLICY["alpha"] / 2) + z.inv_cdf(POLICY["power"])) * sd / delta) ** 2
    days_per_arm = max(14, math.ceil(n))
    weeks = math.ceil(days_per_arm / 7)
    top = summaries[-3:] if summaries else []
    arms = sorted({series.price, *candidates})[:4]
    peak_units = max([s["units_outcome_interval"][1] for s in top], default=0)
    return dict(
        status="plan_only_not_executed",
        candidate_prices_paise=arms,
        randomization_unit="whole weeks (7-day blocks) at this shop; use comparable shops instead if you have several",
        assignment="Shuffle the order of prices inside each cycle so every price appears once per cycle and each weekday is balanced.",
        weeks_per_price=weeks,
        days_per_price=weeks * 7,
        total_weeks=weeks * len(arms),
        sample_size_reasoning=(
            f"Daily contribution varies by about {round(sd / 100):,} rupees. To detect a {int(POLICY['min_useful_improvement_fraction'] * 100)}% "
            f"change with {int(POLICY['power'] * 100)}% power takes about {days_per_price(n)} days per price, rounded up to whole weeks."
        ),
        minimum_useful_improvement_paise_per_day=round(delta),
        inventory_requirement=f"Hold enough stock for the strongest price: plan for up to {int(round(peak_units))} units per week-equivalent horizon "
                              f"({horizon} days) so stockouts do not censor the test.",
        keep_constant=["promotions and displays (log them; do not run them on test weeks)", "shelf position", "supplier cost"],
        primary_metric="gross contribution per week (revenue minus landed cost), including any measurable category effect",
        logging=["date", "price offered", "units sold", "opening stock", "stockout flag", "promotion flag", "assignment block"],
        after_the_test="Keep logging for 2 weeks after the test ends to see whether lower prices pulled purchases forward from later.",
    )


def days_per_price(n):
    return max(14, math.ceil(n))
