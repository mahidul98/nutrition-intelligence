import math

from ..nutrition.foods import get_food
from ..personalization.models import DailyTargets, UserProfile
from ..personalization.report import MEAL_SHARE
from ..schemas import MealTotals
from .models import Swap, SwapOption, Trim, TrimPlan
from .optimizer import MAX_GRAMS, _filter_catalog

# ---- swaps ----
SWAP_GROUPS = {"02", "06", "09", "10", "11", "12"}   # pulses, nuts, fish, meat, eggs, milk
MIN_PROTEIN_DENSITY = 5.0      # g protein per 100 g for a food to count as a protein source
MIN_PROTEIN_TO_REPLACE = 3.0   # ignore conflicting items that give almost no protein
MIN_COVERAGE = 0.6             # an option must replace at least 60% of the removed protein
MAX_OPTIONS = 3

# ---- trims ----
TRIM_TRIGGER = 1.2             # only trim when the meal is above 120% of its energy target
TRIM_TARGET = 1.1              # aim for about 110%
MAX_TRIM_FRACTION = 0.4        # never cut more than 40% of one food
MIN_TRIM_G = 15.0
MIN_TRIM_KCAL = 40.0
TRIM_GROUPS = {"01", "05", "13"}   # cereals, starchy roots, fats and oils


def _options_for(protein_g: float, energy_kcal: float, pool) -> list[SwapOption]:
    coeff = pool["edible_coeff"].fillna(1.0).clip(0.1, 1.0)
    prot_per_g = pool["protein_g"] / 100.0
    kcal_per_g = pool["energy_kcal"].fillna(0.0) / 100.0
    order = (pool["cost_per_edible_g"] / prot_per_g).sort_values().index.tolist()

    options: list[SwapOption] = []
    used_groups: set[str] = set()
    for pass_no in (1, 2):   # pass 1: one option per food group; pass 2: fill remaining slots
        for i in order:
            if len(options) >= MAX_OPTIONS:
                break
            code = str(pool.loc[i, "fct_code"])
            group = str(pool.loc[i, "food_group_code"])
            if code in {o.fct_code for o in options}:
                continue
            if pass_no == 1 and group in used_groups:
                continue
            grams = min(protein_g / prot_per_g[i], float(MAX_GRAMS[group]))
            grams = round(grams / 5.0) * 5.0
            if grams < 10.0:
                continue
            added = grams * prot_per_g[i]
            if added < MIN_COVERAGE * protein_g:
                continue
            buy = grams / coeff[i]
            cost = buy / float(pool.loc[i, "unit_grams"]) * float(pool.loc[i, "price_bdt"])
            options.append(SwapOption(
                fct_code=code,
                name_en=str(pool.loc[i, "name_en"]),
                store=str(pool.loc[i, "store"]),
                eat_grams=grams,
                buy_grams=float(round(buy / 10.0) * 10.0),
                cost_bdt=round(cost, 1),
                protein_added_g=round(added, 1),
                energy_change_kcal=round(grams * kcal_per_g[i] - energy_kcal),
                covers_pct=round(100.0 * added / protein_g),
            ))
            used_groups.add(group)
    options.sort(key=lambda o: o.cost_bdt)
    return options


def plan_swaps(totals: MealTotals, conflicts: dict[str, str], profile: UserProfile,
               catalog, exclude_codes: set[str] | None = None) -> list[Swap]:
    """For each food that conflicts with the user's diet, offer priced protein alternatives."""
    if not conflicts:
        return []

    agg: dict[str, dict] = {}
    for ln in totals.lines:
        a = agg.setdefault(ln.fct_code, {"name": ln.name_en, "grams": 0.0, "protein": 0.0, "energy": 0.0})
        a["grams"] += ln.edible_grams
        a["protein"] += ln.nutrients.get("protein_g") or 0.0
        a["energy"] += ln.nutrients.get("energy_kcal") or 0.0

    pool = _filter_catalog(catalog, profile, exclude_codes)
    if not pool.empty:
        pool = pool[pool["food_group_code"].isin(SWAP_GROUPS)]
        pool = pool[pool["protein_g"].fillna(0.0) >= MIN_PROTEIN_DENSITY].reset_index(drop=True)

    swaps: list[Swap] = []
    for code, reason in conflicts.items():
        a = agg.get(code)
        if not a:
            continue
        options: list[SwapOption] = []
        if not pool.empty and a["protein"] >= MIN_PROTEIN_TO_REPLACE:
            options = _options_for(a["protein"], a["energy"], pool)
        swaps.append(Swap(
            remove_code=code, remove_name=a["name"], remove_grams=round(a["grams"], 1),
            remove_protein_g=round(a["protein"], 1), reason=reason, options=options,
        ))
    return swaps


def plan_trims(totals: MealTotals, targets: DailyTargets, profile: UserProfile,
               meal: str, protected_codes: set[str]) -> TrimPlan | None:
    """If the meal is well above its energy target, suggest smaller portions of staples and oil."""
    if profile.goal == "gain":
        return None
    meal_target = targets.targets["energy_kcal"].value * MEAL_SHARE[meal]
    kcal = totals.totals.get("energy_kcal", 0.0)
    if meal_target <= 0 or kcal <= TRIM_TRIGGER * meal_target:
        return None
    need = kcal - TRIM_TARGET * meal_target

    cands = []
    for ln in totals.lines:
        e = ln.nutrients.get("energy_kcal")
        if e is None or ln.edible_grams <= 0 or ln.fct_code in protected_codes:
            continue
        if str(get_food(ln.fct_code)["food_group_code"]) in TRIM_GROUPS:
            cands.append((e, ln))
    cands.sort(key=lambda t: -t[0])

    trims: list[Trim] = []
    saved = 0.0
    for e, ln in cands:
        if saved >= need or len(trims) >= 2:
            break
        per_g = e / ln.edible_grams
        cut = min(MAX_TRIM_FRACTION * ln.edible_grams, (need - saved) / per_g)
        cut = math.floor(cut / 5.0) * 5.0
        if cut < MIN_TRIM_G or cut * per_g < MIN_TRIM_KCAL:
            continue
        trims.append(Trim(
            fct_code=ln.fct_code, name_en=ln.name_en, from_grams=ln.edible_grams,
            to_grams=round(ln.edible_grams - cut, 1), energy_saved_kcal=round(cut * per_g),
        ))
        saved += cut * per_g

    if not trims:
        return None
    return TrimPlan(
        trims=trims,
        energy_before_pct=round(100.0 * kcal / meal_target),
        energy_after_pct=round(100.0 * (kcal - saved) / meal_target),
    )