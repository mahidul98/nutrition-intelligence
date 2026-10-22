import pandas as pd

from backend.app.nutrition.engine import TRACKED, compute_meal
from backend.app.optimizer.catalog import load_catalog
from backend.app.optimizer.optimizer import plan_addons
from backend.app.personalization.models import UserProfile
from backend.app.personalization.report import MEAL_SHARE, build_report
from backend.app.personalization.targets import daily_targets
from backend.app.schemas import MealItem, MealTotals

ROWS = """fct_code,name_en,price_bdt,unit_grams,store,price_date,in_stock,note
02_0008,lentil,130,1000,A,2026-10-20,yes,
03_0007,cabbage,40,1000,A,2026-10-20,yes,
04_0007,beet greens,40,1000,A,2026-10-20,yes,
04_0028,sweet potato leaves,30,1000,A,2026-10-20,yes,
05_0005,potato,50,1000,A,2026-10-20,yes,
09_0068,tilapia,10,1000,A,2026-10-20,yes,
11_0001,egg,140,660,A,2026-10-20,yes,
03_0008,carrot,60,0,A,2026-10-20,yes,
08_0017,jackfruit,60,1000,A,2026-10-20,no,
02_0008,lentil dear,300,1000,B,2026-10-20,yes,
"""


def _setup(tmp_path, **profile_kw):
    p = tmp_path / "test_prices.csv"
    p.write_text(ROWS, encoding="utf-8")
    catalog, _ = load_catalog(p)
    base = dict(age=21, sex="male", weight_kg=68, height_cm=172, activity="light", goal="maintain")
    base.update(profile_kw)
    profile = UserProfile(**base)
    totals = compute_meal([MealItem(fct_code="01_0024", grams=150)])  # a plain rice meal
    targets = daily_targets(profile)
    report = build_report(totals, targets, "lunch")
    return catalog, profile, totals, targets, report


def test_loader_filters_and_keeps_cheapest(tmp_path):
    p = tmp_path / "test_prices.csv"
    p.write_text(ROWS, encoding="utf-8")
    cat, is_sample = load_catalog(p)
    codes = set(cat["fct_code"])
    assert "03_0008" not in codes      # unit_grams = 0
    assert "08_0017" not in codes      # out of stock
    assert cat[cat["fct_code"] == "02_0008"].iloc[0]["store"] == "A"   # cheaper offer kept
    assert not is_sample


def test_plan_improves_gaps(tmp_path):
    catalog, profile, totals, targets, report = _setup(tmp_path)
    res = plan_addons(totals, targets, report, profile, "lunch", catalog=catalog)
    assert res.status == "ok" and res.items and res.total_cost_bdt > 0
    assert any(res.after[g] > res.before[g] for g in report.gaps if g in res.after)
    assert set(res.remaining_gaps) <= set(report.gaps)


def test_vegetarian_gets_no_fish(tmp_path):
    catalog, profile, totals, targets, report = _setup(tmp_path, diet="vegetarian")
    res = plan_addons(totals, targets, report, profile, "lunch", catalog=catalog)
    assert all(not it.fct_code.startswith(("09_", "10_")) for it in res.items)


def test_avoid_keyword_respected(tmp_path):
    catalog, profile, totals, targets, report = _setup(tmp_path, avoid=["egg"])
    res = plan_addons(totals, targets, report, profile, "lunch", catalog=catalog)
    assert all(it.fct_code != "11_0001" for it in res.items)


def test_budget_respected(tmp_path):
    catalog, profile, totals, targets, report = _setup(tmp_path, budget_bdt_per_day=60)
    res = plan_addons(totals, targets, report, profile, "lunch", catalog=catalog)
    assert res.total_cost_bdt <= 60 * MEAL_SHARE["lunch"] * 0.5 + 0.5


def test_energy_cap_respected(tmp_path):
    catalog, profile, totals, targets, report = _setup(tmp_path, goal="lose")
    res = plan_addons(totals, targets, report, profile, "lunch", catalog=catalog)
    cap = max(80.0,
              1.10 * targets.targets["energy_kcal"].value * MEAL_SHARE["lunch"]
              - totals.totals["energy_kcal"])
    assert res.after["energy_kcal"] - res.before["energy_kcal"] <= cap + 1


def test_nothing_needed_when_meal_is_full(tmp_path):
    catalog, profile, _, targets, _ = _setup(tmp_path)
    full = MealTotals(lines=[], totals={n: 10000.0 for n in TRACKED}, unknown_by_nutrient={})
    report = build_report(full, targets, "lunch")
    res = plan_addons(full, targets, report, profile, "lunch", catalog=catalog)
    assert res.status == "nothing_needed"


def test_empty_catalog_reported(tmp_path):
    _, profile, totals, targets, report = _setup(tmp_path)
    res = plan_addons(totals, targets, report, profile, "lunch", catalog=pd.DataFrame())
    assert res.status == "no_catalog"


def test_sample_flag_adds_warning(tmp_path):
    catalog, profile, totals, targets, report = _setup(tmp_path)
    res = plan_addons(totals, targets, report, profile, "lunch",
                      catalog=catalog, catalog_is_sample=True)
    assert any("DEVELOPMENT SAMPLE" in n for n in res.notes)