from typing import Any, Literal
from pydantic import BaseModel, Field


class Receipt(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    formula_text: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    output: dict[str, Any]
    p10: Any = None
    p50: Any = None
    p90: Any = None
    data_tier: Literal["A", "B"] = "B"
    data_quality_flags: list[str] = Field(default_factory=lambda: ["SIMULATED_DATA"])


def insufficient(tier: str, reason: str) -> Receipt:
    return Receipt(
        formula_text="No estimate: required inputs unavailable",
        output={"verdict": "INSUFFICIENT_DATA", "reason": reason},
        data_tier=tier,
        data_quality_flags=["SIMULATED_DATA", reason],
    )
