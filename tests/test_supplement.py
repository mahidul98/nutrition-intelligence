import io

import pytest
from PIL import Image

from backend.app.nutrition.engine import compute_meal
from backend.app.nutrition.foods import get_food, load_foods, search_foods
from backend.app.perception import pipeline
from backend.app.perception.models import DetectedItem, VisionResult
from backend.app.schemas import MealItem


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buf, format="PNG")
    return buf.getvalue()


def _item(**kw):
    base = dict(fct_code="", name_en="", name_bn_roman="", dish="", estimated_grams=100.0,
                confidence=0.9, state="raw")
    base.update(kw)
    return DetectedItem(**base)


def test_supplement_rows_loaded_with_sources():
    df = load_foods()
    for code in ("05_9001", "10_9001"):
        row = df.loc[code]
        assert "USDA" in str(row["source"])
        assert bool(row["is_recipe_calc"]) is True


def test_fries_values_match_usda_record():
    r = compute_meal([MealItem(fct_code="05_9001", grams=100)])
    assert r.totals["energy_kcal"] == pytest.approx(280.0, abs=0.01)
    assert r.totals["fat_g"] == pytest.approx(12.5, abs=0.01)


def test_missing_supplement_nutrients_are_unknown_not_zero():
    r = compute_meal([MealItem(fct_code="10_9001", grams=100)])
    assert "10_9001" in r.unknown_by_nutrient["folate_mcg"]
    assert "10_9001" in r.unknown_by_nutrient["vitamin_c_mg"]


def test_fried_chicken_counts_as_meat():
    assert str(get_food("10_9001")["food_group_code"]) == "10"


def test_search_finds_fries():
    assert any(h["code"] == "05_9001" for h in search_foods("french fries"))


def test_no_extra_oil_added_on_top_of_supplement_dish(monkeypatch):
    result = VisionResult(scene_type="cooked_meal", quality_issue="", items=[
        _item(fct_code="05_9001", name_en="french fries", dish="fries", estimated_grams=90),
        _item(fct_code="13_0012", name_en="soya oil", dish="fries", estimated_grams=15),
    ])
    monkeypatch.setattr(pipeline, "detect_foods", lambda b, mime_type="image/jpeg": result)
    assert [c.fct_code for c in pipeline.analyze_image(_png()).candidates] == ["05_9001"]