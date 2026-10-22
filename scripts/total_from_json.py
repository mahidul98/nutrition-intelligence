import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.nutrition.engine import compute_meal
from backend.app.schemas import MealItem

raw = Path(sys.argv[1]).read_bytes()
# PowerShell's ">" often writes UTF-16, so handle both encodings
text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
data = json.loads(text)

items = [
    MealItem(fct_code=c["fct_code"], grams=c["grams"])
    for c in data["candidates"]
    if c["fct_code"]
]
skipped = [c["detected_name"] for c in data["candidates"] if not c["fct_code"]]

result = compute_meal(items)
print("Items counted:", len(items))
print("Skipped (no code):", skipped)
print("Totals:")
for k, v in result.totals.items():
    print(f"  {k}: {v}")
print("Missing data:", {k: len(v) for k, v in result.unknown_by_nutrient.items()})