"""Break-even arithmetic for a regular-price change. Exact, integer paise, no demand assumptions.

Gross contribution = units x (price - landed unit cost - other variable cost per unit). It is not net profit.
The new price applies to every unit sold under the new policy, including units that would have sold anyway.
"""

from fractions import Fraction


def margin(price, cost, extra=0):
    return price - cost - extra


def breakeven(current_price, new_price, unit_cost, baseline_units, extra_cost=0):
    """All money in integer paise. `baseline_units` is the expected sales at the current price over the horizon.

    Returns the units needed at `new_price` to strictly beat the baseline contribution, or the reason none exists.
    """
    if baseline_units < 0:
        raise ValueError("baseline units cannot be negative")
    m0 = margin(current_price, unit_cost, extra_cost)
    m1 = margin(new_price, unit_cost, extra_cost)
    base = Fraction(str(baseline_units)) * m0  # str() keeps 130.4 as 130.4, not its binary expansion
    out = dict(
        current_margin_paise=m0,
        new_margin_paise=m1,
        baseline_units=baseline_units,
        baseline_contribution_paise=float(base),
        baseline_revenue_paise=float(Fraction(baseline_units) * current_price),
        price_change_fraction=(new_price - current_price) / current_price if current_price else None,
    )
    if m1 <= 0:
        return out | dict(
            status="no_breakeven",
            reason=(
                "At this price each unit earns nothing or loses money after cost, so no sales volume can beat the "
                "baseline contribution."
                if base > 0
                else "At this price each unit earns nothing or loses money after cost."
            ),
            required_units_exact=None,
            required_units=None,
            required_uplift_exact=None,
            required_uplift=None,
            unit_change_needed=None,
        )
    if base <= 0:
        # Baseline already earns nothing, so any sale at a positive margin beats it.
        return out | dict(
            status="baseline_not_positive",
            reason="The current price earns nothing or loses money per unit, so any sale at the new margin is an improvement.",
            required_units_exact=0.0,
            required_units=1,
            required_uplift_exact=None,
            required_uplift=None,
            unit_change_needed=None,
        )
    exact = base / m1  # units at which contribution exactly ties
    needed = exact.numerator // exact.denominator + 1  # smallest integer strictly above the tie
    uplift_exact = float(exact / baseline_units - 1) if baseline_units else None
    uplift = (needed / baseline_units - 1) if baseline_units else None
    return out | dict(
        status="ok",
        reason=None,
        required_units_exact=float(exact),
        required_units=int(needed),
        required_uplift_exact=uplift_exact,
        required_uplift=uplift,
        unit_change_needed=int(needed) - baseline_units,
        revenue_at_required_units_paise=int(needed) * new_price,
        contribution_at_required_units_paise=int(needed) * m1,
    )
