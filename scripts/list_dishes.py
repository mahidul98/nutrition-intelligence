import pandas as pd

d = pd.read_csv("data/processed/foods.csv", encoding="utf-8-sig")
m = d["is_recipe_calc"] | d["name_en"].str.contains(
    "boiled|cooked|fried|fry|curry|bhuna|khichuri|pulao|biryani|roast|grill",
    case=False, regex=True,
)
print(d[m][["code", "name_en"]].to_string(index=False))