import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.nutrition.engine import compute_meal  # noqa: E402
from backend.app.optimizer.optimizer import plan_addons  # noqa: E402
from backend.app.personalization.models import UserProfile  # noqa: E402
from backend.app.personalization.report import build_report  # noqa: E402
from backend.app.personalization.targets import daily_targets  # noqa: E402
from backend.app.schemas import MealItem  # noqa: E402

PERSONAS = {
    "a": UserProfile(name="Student", age=21, sex="male", weight_kg=68, height_cm=172,
                     activity="light", goal="maintain"),
    "b": UserProfile(name="Office worker", age=38, sex="female", weight_kg=62, height_cm=158,
                     activity="sedentary", goal="lose", diet="vegetarian", budget_bdt_per_day=250),
}

path, persona = sys.argv[1], sys.argv[2]
meal = sys.argv[3] if len(sys.argv) > 3 else "lunch"

raw = Path(path).read_bytes()
text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
data = json.loads(text)

items = [MealItem(fct_code=c["fct_code"], grams=c["grams"]) for c in data["candidates"] if c["fct_code"]]
totals = compute_meal(items)
profile = PERSONAS[persona]
targets = daily_targets(profile)
report = build_report(totals, targets, meal)
result = plan_addons(totals, targets, report, profile, meal)

print(f"{profile.name} | {meal} | status: {result.status}")
if result.catalog_is_sample:
    print("*** PRICES ARE DEVELOPMENT SAMPLES, NOT REAL ***")
print("Gaps in this meal:", report.gaps)
print()
print(f"{'food':<34}{'eat g':>7}{'buy g':>7}{'BDT':>8}  helps")
for it in result.items:
    print(f"{it.name_en[:33]:<34}{it.eat_grams:>7.0f}{it.buy_grams:>7.0f}{it.cost_bdt:>8.1f}  {', '.join(it.helps)}")
print(f"Total cost: {result.total_cost_bdt} BDT")
print()
print(f"{'nutrient':<20}{'before':>9}{'after':>9}")
for g in report.gaps:
    if g in result.after:
        print(f"{g:<20}{result.before[g]:>9}{result.after[g]:>9}")
print("Still low after add-ons:", result.remaining_gaps)
for n in result.notes:
    print("Note:", n)