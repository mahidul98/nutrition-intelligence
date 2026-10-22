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


class SwapOption(BaseModel):
    fct_code: str
    name_en: str
    store: str
    eat_grams: float
    buy_grams: float
    cost_bdt: float
    protein_added_g: float
    energy_change_kcal: float
    covers_pct: float


class Swap(BaseModel):
    remove_code: str
    remove_name: str
    remove_grams: float
    remove_protein_g: float
    reason: str
    options: list[SwapOption]


class Trim(BaseModel):
    fct_code: str
    name_en: str
    from_grams: float
    to_grams: float
    energy_saved_kcal: float


class TrimPlan(BaseModel):
    trims: list[Trim]
    energy_before_pct: float
    energy_after_pct: float