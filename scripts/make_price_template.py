from pathlib import Path

import pandas as pd

OUT = Path("data/prices/price_template.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)

d = pd.read_csv("data/processed/foods.csv", encoding="utf-8-sig")
d = d[~d["is_recipe_calc"]].sort_values(["food_group_code", "name_en"])

out = pd.DataFrame({
    "fct_code": d["code"],
    "name_en": d["name_en"],
    "name_bn_roman": d["name_bn_roman"],
    "food_group": d["food_group"],
    "price_bdt": "",        # price you paid / saw
    "unit_grams": "",       # grams that price buys: 1000 for 1 kg, 660 for a dozen eggs
    "store": "",            # e.g. kacha bazar, supermarket name
    "price_date": "",       # YYYY-MM-DD
    "in_stock": "yes",
    "note": "",             # offers, real variety name, estimated weight
})
out.to_csv(OUT, index=False, encoding="utf-8-sig")
print("Rows:", len(out), "->", OUT)