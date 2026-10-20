from ..schemas import MealTotals
from .models import DailyTargets, MealReport, ReportLine

MEAL_SHARE = {"breakfast": 0.25, "lunch": 0.35, "dinner": 0.30, "snack": 0.10}

UNCOUNTED = (
    "Cooking oil, salt, spices, broth and sauces are counted only if detected, "
    "so fat and sodium may be understated."
)


def _status(kind: str, pct: float) -> str:
    if kind == "goal":
        return "low" if pct < 80 else "high" if pct > 120 else "ok"
    if kind == "min":
        return "low" if pct < 70 else "ok"
    return "high" if pct > 100 else "ok"  # max


def build_report(totals: MealTotals, targets: DailyTargets, meal: str = "lunch") -> MealReport:
    share = MEAL_SHARE[meal]
    lines: list[ReportLine] = []
    gaps: list[tuple[float, str]] = []
    excesses: list[str] = []
    notes = [UNCOUNTED]

    for key, t in targets.targets.items():
        amount = totals.totals.get(key)
        if amount is None:
            continue
        meal_target = t.value * share
        pct = amount / meal_target * 100 if meal_target else 0.0
        status = _status(t.kind, pct)
        partial = key in totals.unknown_by_nutrient

        if partial and status == "low":
            notes.append(f"{key}: {len(totals.unknown_by_nutrient[key])} item(s) have no data, so a gap cannot be confirmed.")
        elif status == "low":
            gaps.append((pct, key))
        elif status == "high":
            excesses.append(key)

        lines.append(
            ReportLine(
                nutrient=key,
                amount=round(amount, 1),
                meal_target=round(meal_target, 1),
                kind=t.kind,
                percent=round(pct, 0),
                status=status,
                partial_data=partial,
            )
        )

    if targets.kcal_floor_applied:
        notes.append("Your calorie target was raised to a safe minimum. Please do not go lower without professional advice.")

    return MealReport(
        meal=meal,
        lines=lines,
        gaps=[k for _, k in sorted(gaps)],
        excesses=excesses,
        notes=notes,
    )