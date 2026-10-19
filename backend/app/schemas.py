from pydantic import BaseModel, Field


class MealItem(BaseModel):
    fct_code: str
    grams: float = Field(gt=0, le=5000)
    as_purchased: bool = False  # True: grams include inedible parts (peel, bones)


class NutrientLine(BaseModel):
    fct_code: str
    name_en: str
    grams_input: float
    edible_grams: float
    nutrients: dict[str, float | None]  # None = no data in the table


class MealTotals(BaseModel):
    lines: list[NutrientLine]
    totals: dict[str, float]  # sums of known values only
    unknown_by_nutrient: dict[str, list[str]]  # nutrient -> codes with no data