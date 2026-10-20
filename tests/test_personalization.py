import pytest
from pydantic import ValidationError

from backend.app.personalization.models import UserProfile
from backend.app.personalization.report import build_report
from backend.app.personalization.targets import bmr, daily_targets
from backend.app.schemas import MealTotals


def _p(**kw):
    base = dict(age=30, sex="male", weight_kg=70, height_cm=175, activity="light", goal="maintain")
    base.update(kw)
    return UserProfile(**base)


def _totals(**kw):
    t = {k: 0.0 for k in ["energy_kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "sodium_mg",
                          "calcium_mg", "iron_mg", "vitamin_a_rae_mcg", "vitamin_c_mg", "folate_mcg"]}
    t.update(kw.pop("totals", {}))
    return MealTotals(lines=[], totals=t, unknown_by_nutrient=kw.pop("unknown", {}))


def test_bmr_known_value():
    assert bmr(_p()) == pytest.approx(1648.75)


def test_minor_rejected():
    with pytest.raises(ValidationError):
        _p(age=17)


def test_calorie_floor_applied():
    t = daily_targets(_p(age=18, sex="female", weight_kg=40, height_cm=150, activity="sedentary", goal="lose"))
    assert t.kcal_floor_applied and t.targets["energy_kcal"].value == 1200


def test_macros_roughly_add_up():
    t = daily_targets(_p()).targets
    kcal = t["protein_g"].value * 4 + t["fat_g"].value * 9 + t["carb_g"].value * 4
    assert kcal == pytest.approx(t["energy_kcal"].value, rel=0.03)


def test_empty_meal_has_gaps_but_no_excess():
    r = build_report(_totals(), daily_targets(_p()), "lunch")
    assert "protein_g" in r.gaps and r.excesses == []


def test_high_sodium_flagged():
    r = build_report(_totals(totals={"sodium_mg": 1500}), daily_targets(_p()), "lunch")
    assert "sodium_mg" in r.excesses


def test_missing_data_is_not_called_a_gap():
    r = build_report(_totals(unknown={"folate_mcg": ["01_0001"]}), daily_targets(_p()), "lunch")
    assert "folate_mcg" not in r.gaps
    assert any("folate_mcg" in n for n in r.notes)


def test_uncounted_note_always_present():
    r = build_report(_totals(), daily_targets(_p()), "dinner")
    assert any("understated" in n for n in r.notes)