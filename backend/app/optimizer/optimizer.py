import numpy as np
import pandas as pd
from scipy.optimize import linprog

from ..nutrition.engine import TRACKED, compute_meal
from ..personalization.models import DailyTargets, MealReport, UserProfile
from ..personalization.report import MEAL_SHARE
from ..schemas import MealItem, MealTotals
from .catalog import load_catalog
from .models import PivotResult, ShoppingItem

PROTECTIVE = ["protein_g", "fiber_g", "calcium_mg", "iron_mg",
              "vitamin_a_rae_mcg", "vitamin_c_mg", "folate_mcg"]
COVERAGE = 0.8             # try to bring each gap up to 80% of the per-meal target
GAP_LINE = 0.7             # same line the report uses to call a nutrient "low"
PENALTY = 60.0             # BDT-equivalent cost of leaving one whole need unmet
MIN_ENERGY_ALLOWANCE = 80.0
ADDON_BUDGET_SHARE = 0.5   # add-ons may use half of the meal's share of the daily budget

# Maximum EDIBLE grams of one food per meal, by food group (also decides which groups are used)
MAX_GRAMS = {"01": 150, "02": 80, "03": 200, "04": 150, "05": 200, "06": 30,
             "08": 200, "09": 150, "10": 150, "11": 100, "12": 250}


def _result(status, before, notes, is_sample, remaining=None):
    return PivotResult(status=status, before=before, after=before,
                       remaining_gaps=remaining or [], catalog_is_sample=is_sample, notes=notes)


def _filter_catalog(catalog, profile: UserProfile) -> pd.DataFrame:
    if catalog is None or catalog.empty:
        return pd.DataFrame()
    cat = catalog[catalog["food_group_code"].isin(MAX_GRAMS.keys())]
    if profile.diet == "vegetarian":
        cat = cat[~cat["food_group_code"].isin({"09", "10"})]
    elif profile.diet == "pescatarian":
        cat = cat[~cat["food_group_code"].isin({"10"})]
    for word in profile.avoid:
        w = word.strip().lower()
        if w:
            cat = cat[~cat["name_en"].str.lower().str.contains(w, regex=False)]
    return cat.reset_index(drop=True)


def plan_addons(totals: MealTotals, targets: DailyTargets, report: MealReport,
                profile: UserProfile, meal: str = "lunch",
                catalog=None, catalog_is_sample: bool = False) -> PivotResult:
    share = MEAL_SHARE[meal]
    before = {n: round(totals.totals.get(n, 0.0), 2) for n in TRACKED}
    notes: list[str] = []

    if catalog is None:
        catalog, catalog_is_sample = load_catalog()
    if catalog_is_sample:
        notes.append("DEVELOPMENT SAMPLE PRICES - not real. Do not show these in the demo.")

    needs = {}
    for g in report.gaps:
        if g in PROTECTIVE:
            need = COVERAGE * targets.targets[g].value * share - totals.totals.get(g, 0.0)
            if need > 1e-9:
                needs[g] = need
    gaps = list(needs)
    if not gaps:
        return _result("nothing_needed", before, notes, catalog_is_sample)

    cat = _filter_catalog(catalog, profile)
    if cat.empty:
        notes.append("No suitable in-stock foods with prices were found for this profile.")
        return _result("no_catalog", before, notes, catalog_is_sample, gaps)

    m, k = len(cat), len(gaps)
    coeff = cat["edible_coeff"].fillna(1.0).clip(0.1, 1.0).to_numpy()
    cost_g = cat["cost_per_edible_g"].to_numpy(dtype=float)
    supply = cat[gaps].fillna(0.0).to_numpy(dtype=float).T / 100.0   # k x m, per edible gram

    kcal_target = targets.targets["energy_kcal"].value * share
    kcal_have = totals.totals.get("energy_kcal", 0.0)
    if profile.goal == "gain":
        energy_cap = 1e9
    else:
        energy_cap = max(MIN_ENERGY_ALLOWANCE, 1.10 * kcal_target - kcal_have)
        if kcal_have > 1.2 * kcal_target:
            notes.append("This meal is already above your energy target, so add-ons are kept small. "
                         "A smaller portion of the main dish would also help.")
    na_cap = max(100.0, targets.targets["sodium_mg"].value * share - totals.totals.get("sodium_mg", 0.0))

    # Variables: grams of each food (m), then one shortfall slack per gap nutrient (k)
    c = np.concatenate([cost_g, [PENALTY / needs[g] for g in gaps]])
    rows, rhs = [], []
    for j, g in enumerate(gaps):
        row = np.zeros(m + k)
        row[:m] = -supply[j]
        row[m + j] = -1.0
        rows.append(row)
        rhs.append(-needs[g])

    row = np.zeros(m + k)
    row[:m] = cat["energy_kcal"].fillna(0.0).to_numpy(dtype=float) / 100.0
    rows.append(row)
    rhs.append(energy_cap)

    row = np.zeros(m + k)
    row[:m] = cat["sodium_mg"].fillna(0.0).to_numpy(dtype=float) / 100.0
    rows.append(row)
    rhs.append(na_cap)

    if profile.budget_bdt_per_day:
        row = np.zeros(m + k)
        row[:m] = cost_g
        rows.append(row)
        rhs.append(profile.budget_bdt_per_day * share * ADDON_BUDGET_SHARE)

    bounds = [(0.0, float(MAX_GRAMS[g])) for g in cat["food_group_code"]] + [(0.0, None)] * k
    res = linprog(c, A_ub=np.array(rows), b_ub=np.array(rhs), bounds=bounds, method="highs")
    if not res.success:
        notes.append("The optimizer could not find a solution within your limits.")
        return _result("no_solution", before, notes, catalog_is_sample, gaps)

    x = res.x[:m]
    picks = []
    for i in np.argsort(-x):
        grams = float(np.floor((x[i] + 1e-6) / 5.0) * 5.0)   # round DOWN to 5 g so limits still hold
        if grams >= 10.0:
            picks.append((int(i), grams))
    picks = picks[:6]
    if not picks:
        notes.append("No add-on could close the gaps within your limits.")
        return _result("no_solution", before, notes, catalog_is_sample, gaps)

    added = compute_meal([MealItem(fct_code=str(cat.loc[i, "fct_code"]), grams=g) for i, g in picks])
    after = {n: round(before[n] + added.totals[n], 2) for n in TRACKED}
    remaining = [g for g in gaps if after[g] < GAP_LINE * targets.targets[g].value * share]

    items = []
    for i, grams in picks:
        r = cat.loc[i]
        buy = grams / coeff[i]
        cost = buy / float(r["unit_grams"]) * float(r["price_bdt"])
        helps = []
        for g in gaps:
            v = float(r[g]) if pd.notna(r[g]) else 0.0
            if v / 100.0 * grams >= 0.15 * needs[g]:
                helps.append(g)
        items.append(ShoppingItem(
            fct_code=str(r["fct_code"]), name_en=str(r["name_en"]), store=str(r["store"]),
            eat_grams=grams, buy_grams=float(round(buy / 10.0) * 10.0),
            cost_bdt=round(cost, 1), helps=helps,
        ))

    notes.append(f"Add-ons add about {round(added.totals['energy_kcal'])} kcal.")
    notes.append("Eat grams are edible weight. Buy grams include peel, bones and stalks.")
    return PivotResult(
        status="ok", items=items,
        total_cost_bdt=round(sum(it.cost_bdt for it in items), 1),
        before=before, after=after, remaining_gaps=remaining,
        catalog_is_sample=catalog_is_sample, notes=notes,
    )