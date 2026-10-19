import pytest

from backend.app.nutrition.engine import compute_meal
from backend.app.nutrition.foods import get_food, load_foods, search_foods
from backend.app.schemas import MealItem


def test_100g_matches_table():
    r = compute_meal([MealItem(fct_code="01_0001", grams=100)])
    assert r.totals["energy_kcal"] == pytest.approx(324.0, abs=0.01)
    assert r.totals["protein_g"] == pytest.approx(
        float(get_food("01_0001")["protein_g"]), abs=0.01
    )


def test_scales_linearly():
    a = compute_meal([MealItem(fct_code="01_0001", grams=100)])
    b = compute_meal([MealItem(fct_code="01_0001", grams=250)])
    assert b.totals["carb_g"] == pytest.approx(a.totals["carb_g"] * 2.5, rel=0.01)


def test_two_items_add_up():
    r = compute_meal(
        [MealItem(fct_code="01_0001", grams=100), MealItem(fct_code="01_0002", grams=100)]
    )
    assert r.totals["energy_kcal"] == pytest.approx(324.0 + 270.0, abs=0.01)


def test_missing_is_not_zero():
    df = load_foods()
    code = df[df["folate_mcg"].isna()].iloc[0]["code"]
    r = compute_meal([MealItem(fct_code=code, grams=100)])
    assert code in r.unknown_by_nutrient["folate_mcg"]
    assert r.lines[0].nutrients["folate_mcg"] is None


def test_as_purchased_applies_edible_coefficient():
    df = load_foods()
    code = df[(df["edible_coeff"] < 1) & (df["energy_kcal"] > 0)].iloc[0]["code"]
    full = compute_meal([MealItem(fct_code=code, grams=100)])
    bought = compute_meal([MealItem(fct_code=code, grams=100, as_purchased=True)])
    assert bought.totals["energy_kcal"] < full.totals["energy_kcal"]


def test_search_finds_khichuri():
    assert any("khichuri" in h["name_en"].lower() for h in search_foods("khichuri"))


def test_unknown_code_raises():
    with pytest.raises(KeyError):
        compute_meal([MealItem(fct_code="99_9999", grams=100)])


def test_invalid_grams_rejected():
    with pytest.raises(Exception):
        MealItem(fct_code="01_0001", grams=-5)