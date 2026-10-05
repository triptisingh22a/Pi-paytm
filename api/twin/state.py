from pydantic import BaseModel, Field


class Batch(BaseModel):
    quantity: int
    expires_day: int


class TwinState(BaseModel):
    cash: float
    stock: dict[str, list[Batch]]
    pending_settlements: dict[int, float] = Field(default_factory=dict)
    customer_cohorts: dict[str, int] = Field(
        default_factory=lambda: {"new": 25, "repeat": 70, "at_risk": 15, "inactive": 20}
    )
    day: int = 0


def from_shop(shop):
    return TwinState(
        cash=shop["cash"],
        stock={s["id"]: [Batch(quantity=s["stock"], expires_day=s["shelf_life"])] for s in shop["skus"]},
        pending_settlements={i: amount for i, amount in enumerate(shop["pending"])},
    )
