import pandas as pd

from ..schemas import MealItem, MealTotals, NutrientLine
from .foods import get_food

TRACKED = [
    "energy_kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "sodium_mg",
    "calcium_mg", "iron_mg", "vitamin_a_rae_mcg", "vitamin_c_mg", "folate_mcg",
]


def compute_meal(items: list[MealItem]) -> MealTotals:
    lines: list[NutrientLine] = []
    totals = {k: 0.0 for k in TRACKED}
    unknown: dict[str, list[str]] = {k: [] for k in TRACKED}

    for it in items:
        food = get_food(it.fct_code)
        coeff = food["edible_coeff"]
        edible = it.grams
        if it.as_purchased and not pd.isna(coeff):
            edible = it.grams * float(coeff)
        factor = edible / 100.0  # table values are per 100 g edible portion

        vals: dict[str, float | None] = {}
        for k in TRACKED:
            v = food[k]
            if pd.isna(v):
                vals[k] = None
                unknown[k].append(it.fct_code)
            else:
                vals[k] = round(float(v) * factor, 3)
                totals[k] += float(v) * factor

        lines.append(
            NutrientLine(
                fct_code=it.fct_code,
                name_en=str(food["name_en"]),
                grams_input=it.grams,
                edible_grams=round(edible, 2),
                nutrients=vals,
            )
        )

    return MealTotals(
        lines=lines,
        totals={k: round(v, 2) for k, v in totals.items()},
        unknown_by_nutrient={k: v for k, v in unknown.items() if v},
    )