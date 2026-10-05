from typing import Literal
from pydantic import BaseModel, Field


class Question(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    tier: Literal["A", "B"] = "B"
    language: Literal["en", "hi", "mr"] = "en"
    budget: float = Field(default=3000, ge=0, le=100000)
    discount: float = Field(default=0.1, ge=0, lt=1)


class ActionRequest(BaseModel):
    action: dict
    tier: Literal["A", "B"] = "B"
