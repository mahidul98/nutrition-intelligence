"""
Build data/processed/foods.csv from the Bangladesh Food Composition Table (2013).
Run from the project root:  python scripts\\build_foods.py
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/FCDB_7_4_14.xlsx")
OUT = Path("data/processed/foods.csv")
SHEET = "UserDB_Main_table"

COLUMNS = [
    "code", "name_en", "name_bn_roman", "scientific_name", "source", "edible_coeff",
    "energy_raw", "water_g", "protein_g", "fat_g", "carb_g", "fiber_g", "ash_g",
    "calcium_mg", "iron_mg", "magnesium_mg", "phosphorus_mg", "potassium_mg",
    "sodium_mg", "zinc_mg", "copper_mg", "vitamin_a_rae_mcg", "retinol_mcg",
    "beta_carotene_eq_mcg", "alpha_carotene_mcg", "beta_carotene_mcg",
    "cryptoxanthin_mcg", "vitamin_d_mcg", "vitamin_e_mg", "thiamin_mg",
    "riboflavin_mg", "niacin_eq_total_mg", "niacin_preformed_mg",
    "niacin_eq_from_trp_mg", "vitamin_b6_mg", "folate_mcg", "vitamin_c_mg",
]
NUTRIENTS = COLUMNS[7:]                 # water_g ... vitamin_c_mg
NUMERIC = ["edible_coeff"] + NUTRIENTS

# Sanity check that the sheet layout is what we expect
EXPECTED_START = {6: "ENERC", 7: "WATER", 8: "PROT", 9: "FATCE", 10: "CHOAVLDF",
                  11: "FIBTG", 13: "CA", 14: "FE", 18: "NA", 36: "ASCL"}

CODE_RE = re.compile(r"^\d{2}_\d{4}$")
GROUP_RE = re.compile(r"^(\d{2})\s+(.+)$")
ENERGY_RE = re.compile(r"^\(\s*([\d.]+)\s*\)\s*([\d.]+)$")

unparsed = {}


def to_number(x, col):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    if isinstance(x, (int, float, np.number)):
        return float(x)
    s = str(x).strip().replace("[", "").replace("]", "").replace(",", "")
    if s == "":
        return np.nan
    if s.lower() in {"tr", "trace"}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        unparsed.setdefault(col, set()).add(str(x))
        return np.nan


def parse_energy(x):
    """'(324)1360' -> (324.0, 1360.0). Anything else -> (nan, nan)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return (np.nan, np.nan)
    s = str(x).strip().replace("[", "").replace("]", "")
    m = ENERGY_RE.match(s)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    return (np.nan, np.nan)


def main():
    if not RAW.exists():
        sys.exit(f"Missing {RAW}. Download it first.")
    xl = pd.ExcelFile(RAW)
    if SHEET not in xl.sheet_names:
        sys.exit(f"Sheet '{SHEET}' not found. Sheets: {xl.sheet_names}")

    df = xl.parse(SHEET, header=None, dtype=object)
    if df.shape[1] != len(COLUMNS):
        sys.exit(f"Expected {len(COLUMNS)} columns, found {df.shape[1]}.")
    header = df.iloc[0].tolist()
    for idx, token in EXPECTED_START.items():
        if not str(header[idx]).strip().startswith(token):
            sys.exit(f"Column {idx} is '{header[idx]}', expected '{token}...'. "
                     "Send me the header row.")

    df = df.iloc[2:].copy()
    df.columns = COLUMNS

    # Keep only real food rows; carry the food group forward from header rows
    group_code, group_name, rows = None, None, []
    for _, r in df.iterrows():
        first = str(r["code"]).strip() if pd.notna(r["code"]) else ""
        if CODE_RE.match(first):
            rec = r.to_dict()
            rec["code"] = first
            rec["food_group_code"] = group_code
            rec["food_group"] = group_name
            rows.append(rec)
        else:
            m = GROUP_RE.match(first)
            if m:
                group_code, group_name = m.group(1), m.group(2).strip()

    foods = pd.DataFrame(rows)

    for col in ["name_en", "name_bn_roman", "scientific_name", "source"]:
        foods[col] = foods[col].astype("string").str.strip()

    for col in NUMERIC:
        foods[col] = foods[col].map(lambda v, c=col: to_number(v, c))

    parsed = foods["energy_raw"].map(parse_energy)
    foods["energy_kcal"] = [p[0] for p in parsed]
    foods["energy_kj"] = [p[1] for p in parsed]

    est = 4 * foods["protein_g"] + 4 * foods["carb_g"] + 9 * foods["fat_g"]
    missing = foods["energy_kcal"].isna()
    foods["energy_source"] = np.where(
        missing & est.notna(), "estimated_atwater", np.where(missing, "missing", "table")
    )
    foods.loc[missing, "energy_kcal"] = est[missing].round(0)

    foods["is_recipe_calc"] = foods["source"].fillna("").str.contains("recipe", case=False)
    foods["has_macros"] = foods[["protein_g", "fat_g", "carb_g"]].notna().all(axis=1)

    ordered = ["code", "food_group_code", "food_group", "name_en", "name_bn_roman",
               "scientific_name", "source", "is_recipe_calc", "edible_coeff",
               "energy_kcal", "energy_kj", "energy_source", "has_macros"] + NUTRIENTS
    foods = foods[ordered]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    foods.to_csv(OUT, index=False, encoding="utf-8-sig")

    # ---- report ----
    print(f"Foods written: {len(foods)} -> {OUT}")
    print(f"Duplicate codes: {foods['code'].duplicated().sum()}")
    print("\nFoods per group:")
    print(foods.groupby(["food_group_code", "food_group"], dropna=False).size().to_string())
    print(f"\nWith protein+fat+carb: {int(foods['has_macros'].sum())}")
    print(f"Recipe-calculated rows: {int(foods['is_recipe_calc'].sum())}")
    print("Energy source:", foods["energy_source"].value_counts().to_dict())

    key = ["energy_kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "sodium_mg",
           "calcium_mg", "iron_mg", "vitamin_a_rae_mcg", "vitamin_c_mg", "folate_mcg"]
    print("\n% missing:")
    print((foods[key].isna().mean() * 100).round(1).to_string())

    prox = foods[["water_g", "protein_g", "fat_g", "carb_g", "fiber_g", "ash_g"]].sum(axis=1, min_count=6)
    bad = foods[(prox < 90) | (prox > 110)]
    print(f"\nRows whose proximates do not sum to 90-110 g: {len(bad)}")
    if len(bad):
        print(bad[["code", "name_en"]].head(10).to_string(index=False))

    if unparsed:
        print("\nValues I could not parse (column: examples):")
        for c, vals in unparsed.items():
            print(f"  {c}: {sorted(vals)[:8]}")

    print("\nSample:")
    print(foods[["code", "name_en", "energy_kcal", "protein_g", "fat_g", "carb_g"]]
          .head(10).to_string(index=False))


if __name__ == "__main__":
    main()