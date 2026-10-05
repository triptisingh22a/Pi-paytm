"""Money at the pricing boundary is integer paise; rupee floats never enter a calculation."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

PAISE = Decimal(100)
MAX_PRICE_PAISE = 100_000_000  # INR 10 lakh; a sanity bound, not a business rule


def to_paise(value, field="price"):
    """Rupees (int, float, str or Decimal) -> integer paise. Rejects non-finite, negative and sub-paise input."""
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number of rupees")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field} must be a number of rupees") from None
    if not d.is_finite() or d < 0:
        raise ValueError(f"{field} must be a non-negative amount in rupees")
    paise = d * PAISE
    if paise != paise.to_integral_value():
        raise ValueError(f"{field} cannot have fractions of a paisa")
    if paise > MAX_PRICE_PAISE:
        raise ValueError(f"{field} is outside the supported range")
    return int(paise)


def rupees(paise):
    """Integer paise -> Decimal rupees (exact)."""
    return (Decimal(paise) / PAISE).quantize(Decimal("0.01"))


def rupees_float(paise):
    return float(rupees(paise))


def round_paise(x):
    """Round a model-derived rupee-paise float to whole paise (half up)."""
    return int(Decimal(str(x)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
