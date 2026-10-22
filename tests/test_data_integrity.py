import pandas as pd

from backend.app.nutrition.foods import FOODS_CSV, load_foods


def test_group_codes_are_two_digit_in_memory():
    codes = load_foods()["food_group_code"].dropna().astype(str)
    assert codes.str.fullmatch(r"\d{2}").all()


def test_foods_csv_on_disk_keeps_leading_zeros():
    raw = pd.read_csv(FOODS_CSV, encoding="utf-8-sig", dtype=str)
    assert raw["food_group_code"].dropna().str.fullmatch(r"\d{2}").all(), (
        "foods.csv was probably re-saved in Excel; run: git restore data/processed/foods.csv"
    )