import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.nutrition.engine import compute_meal
from backend.app.nutrition.foods import get_food, load_foods
from backend.app.optimizer import pivot
from backend.app.personalization.models import UserProfile
from backend.app.personalization.targets import daily_targets
from backend.app.schemas import MealItem

df = load_foods()
dups = df.index[df.index.duplicated()].tolist()
print("rows:", len(df), "| duplicated codes:", dups[:10])
print("group codes seen:", sorted(df["food_group_code"].dropna().astype(str).unique()))

for code in ("01_0024", "09_0068", "13_0004"):
    f = get_food(code)
    print(code, "->", type(f).__name__, "| group:", repr(f["food_group_code"]))

profile = UserProfile(age=38, sex="female", weight_kg=62, height_cm=158,
                      activity="sedentary", goal="lose", diet="vegetarian")
targets = daily_targets(profile)
totals = compute_meal([MealItem(fct_code="01_0024", grams=300)])
print("lunch energy target:", targets.targets["energy_kcal"].value * 0.35)
print("meal energy:", totals.totals["energy_kcal"])
print("TRIM_GROUPS:", pivot.TRIM_GROUPS, "| TRIM_TRIGGER:", pivot.TRIM_TRIGGER)
print("trim result:", pivot.plan_trims(totals, targets, profile, "lunch", set()))