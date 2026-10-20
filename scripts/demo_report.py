import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.nutrition.engine import compute_meal  # noqa: E402
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

path, persona, meal = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "lunch"
raw = Path(path).read_bytes()
text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
data = json.loads(text)

items = [MealItem(fct_code=c["fct_code"], grams=c["grams"]) for c in data["candidates"] if c["fct_code"]]
totals = compute_meal(items)
profile = PERSONAS[persona]
report = build_report(totals, daily_targets(profile), meal)

print(f"{profile.name} | {meal}")
print(f"{'nutrient':<20}{'amount':>9}{'target':>9}{'%':>6}  status")
for ln in report.lines:
    flag = " (partial data)" if ln.partial_data else ""
    print(f"{ln.nutrient:<20}{ln.amount:>9}{ln.meal_target:>9}{ln.percent:>6.0f}  {ln.status}{flag}")
print("Gaps:", report.gaps)
print("Excesses:", report.excesses)
for n in report.notes:
    print("Note:", n)