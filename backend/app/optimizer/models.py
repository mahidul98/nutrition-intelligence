from typing import Literal

from pydantic import BaseModel


class ShoppingItem(BaseModel):
    fct_code: str
    name_en: str
    store: str
    eat_grams: float
    buy_grams: float
    cost_bdt: float
    helps: list[str]


class PivotResult(BaseModel):
    status: Literal["ok", "nothing_needed", "no_catalog", "no_solution"]
    items: list[ShoppingItem] = []
    total_cost_bdt: float = 0.0
    before: dict[str, float] = {}
    after: dict[str, float] = {}
    remaining_gaps: list[str] = []
    catalog_is_sample: bool = False
    notes: list[str] = []