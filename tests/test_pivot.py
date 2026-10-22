from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.nutrition.engine import TRACKED, compute_meal
from backend.app.optimizer.catalog import load_catalog
from backend.app.optimizer.pivot import plan_swaps, plan_trims
from backend.app.personalization.models import UserProfile
from backend.app.personalization.report import build_report
from backend.app.personalization.targets import daily_targets
from backend.app.schemas import MealItem, MealTotals

ROWS = """fct_code,name_en,price_bdt,unit_grams,store,price_date,in_stock,note
02_0008,lentil,130,1000,A,2026-10-21,yes,
02_0005,green gram,160,1000,A,2026-10-21,yes,
11_0001,egg,140,660,A,2026-10-21,yes,
09_0068,tilapia,10,1000,A,2026-10-21,yes,
04_0028,sweet potato leaves,30,1000,A,2026-10-21,yes,
"""

client = TestClient(app)
FISH_REASON = {"09_0068": "contains fish or meat (vegetarian diet)"}


def _catalog(tmp_path):
    p = tmp_path / "test_prices.csv"
    p.write_text(ROWS, encoding="utf-8")
    return load_catalog(p)[0]


def _profile(**kw):
    base = dict(age=38, sex="female", weight_kg=62, height_cm=158,
                activity="sedentary", goal="lose", diet="vegetarian")
    base.update(kw)
    return UserProfile(**base)


def _rice_and_fish():
    return compute_meal([MealItem(fct_code="01_0024", grams=150),
                         MealItem(fct_code="09_0068", grams=80)])


def test_vegetarian_swap_offers_non_fish_protein(tmp_path):
    swaps = plan_swaps(_rice_and_fish(), FISH_REASON, _profile(), _catalog(tmp_path))
    assert len(swaps) == 1 and swaps[0].remove_code == "09_0068"
    assert swaps[0].options
    for o in swaps[0].options:
        assert not o.fct_code.startswith(("09_", "10_"))
        assert o.cost_bdt > 0 and o.covers_pct >= 60


def test_swap_skips_out_of_stock(tmp_path):
    swaps = plan_swaps(_rice_and_fish(), FISH_REASON, _profile(), _catalog(tmp_path),
                       exclude_codes={"02_0008"})
    assert all(o.fct_code != "02_0008" for o in swaps[0].options)


def test_no_swaps_without_conflicts(tmp_path):
    assert plan_swaps(_rice_and_fish(), {}, _profile(), _catalog(tmp_path)) == []


def test_trim_reduces_the_staple_for_an_oversized_meal():
    profile = _profile()
    totals = compute_meal([MealItem(fct_code="01_0024", grams=300)])
    plan = plan_trims(totals, daily_targets(profile), profile, "lunch", set())
    assert plan and plan.trims
    t = plan.trims[0]
    assert t.fct_code == "01_0024"
    assert t.to_grams < t.from_grams and t.to_grams >= 0.6 * t.from_grams - 0.01
    assert plan.energy_after_pct < plan.energy_before_pct


def test_no_trim_when_meal_is_within_range():
    profile = _profile()
    totals = compute_meal([MealItem(fct_code="01_0024", grams=100)])
    assert plan_trims(totals, daily_targets(profile), profile, "lunch", set()) is None


def test_no_trim_for_weight_gain_goal():
    profile = _profile(goal="gain")
    totals = compute_meal([MealItem(fct_code="01_0024", grams=400)])
    assert plan_trims(totals, daily_targets(profile), profile, "lunch", set()) is None


def test_trim_never_cuts_protein_foods():
    profile = _profile()
    totals = compute_meal([MealItem(fct_code="09_0068", grams=600)])
    assert plan_trims(totals, daily_targets(profile), profile, "lunch", set()) is None


def test_missing_data_goes_to_possible_gaps_not_gaps():
    totals = MealTotals(lines=[], totals={n: 0.0 for n in TRACKED},
                        unknown_by_nutrient={"folate_mcg": ["x"]})
    r = build_report(totals, daily_targets(_profile()), "lunch")
    assert "folate_mcg" in r.possible_gaps and "folate_mcg" not in r.gaps


PROFILE_B = {"name": "Office worker", "age": 38, "sex": "female", "weight_kg": 62, "height_cm": 158,
             "activity": "sedentary", "goal": "lose", "diet": "vegetarian", "avoid": [],
             "budget_bdt_per_day": 250}


def _body(items):
    return {"items": items, "profile": PROFILE_B, "meal": "lunch", "out_of_stock": []}


def test_api_returns_swaps_for_vegetarian_with_fish():
    r = client.post("/report", json=_body([{"fct_code": "01_0024", "grams": 150},
                                           {"fct_code": "09_0068", "grams": 80}]))
    data = r.json()
    assert r.status_code == 200
    assert data["swaps"] and data["swaps"][0]["remove_code"] == "09_0068"
    assert all(not o["fct_code"].startswith(("09_", "10_")) for o in data["swaps"][0]["options"])


def test_api_returns_trim_for_oversized_meal():
    r = client.post("/report", json=_body([{"fct_code": "01_0024", "grams": 300}]))
    data = r.json()
    assert r.status_code == 200
    assert data["trim"] and data["trim"]["trims"][0]["fct_code"] == "01_0024"