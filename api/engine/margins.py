from engine.receipts import Receipt, insufficient


def margin(cost, price, tier="B"):
    if tier != "B" or cost is None or price is None or price <= 0 or cost < 0:
        return insufficient(tier, "MISSING_VALID_COST_PRICE")
    value = (price - cost) / price
    return Receipt(
        inputs={"cost": cost, "price": price},
        formula_text="margin=(price-cost)/price",
        output={"margin": value, "contribution_per_unit": price - cost},
        data_tier=tier,
    )
