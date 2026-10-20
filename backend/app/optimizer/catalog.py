from pathlib import Path

import pandas as pd

from ..nutrition.foods import load_foods

ROOT = Path(__file__).resolve().parents[3]
REAL = ROOT / "data" / "prices" / "prices.csv"
SAMPLE = ROOT / "data" / "prices" / "sample_prices.csv"
REQUIRED = ["fct_code", "price_bdt", "unit_grams", "store", "price_date", "in_stock"]


def load_catalog(path: Path | None = None) -> tuple[pd.DataFrame, bool]:
    """Load prices, join nutrients, keep the cheapest in-stock offer per food.
    Returns (catalog, is_sample). Uses the real prices.csv if it exists, else the dev sample."""
    if path is None:
        path = REAL if REAL.exists() else SAMPLE
    is_sample = Path(path).name.startswith("sample")

    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"fct_code": str})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")

    df = df[REQUIRED].copy()
    df["price_bdt"] = pd.to_numeric(df["price_bdt"], errors="coerce")
    df["unit_grams"] = pd.to_numeric(df["unit_grams"], errors="coerce")
    df["store"] = df["store"].fillna("")
    df = df[(df["price_bdt"] > 0) & (df["unit_grams"] > 0)]
    df = df[df["in_stock"].astype(str).str.strip().str.lower().isin(["yes", "y", "true", "1"])]

    foods = load_foods().reset_index(drop=True)
    df = df.merge(foods, left_on="fct_code", right_on="code", how="inner")
    if df.empty:
        return df, is_sample

    coeff = df["edible_coeff"].fillna(1.0).clip(0.1, 1.0)
    df["cost_per_edible_g"] = df["price_bdt"] / (df["unit_grams"] * coeff)
    df = df.loc[df.groupby("fct_code")["cost_per_edible_g"].idxmin()].reset_index(drop=True)
    return df, is_sample