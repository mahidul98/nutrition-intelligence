from .api_models import DietConflict, ReportRequest, ReportResponse
from .nutrition.engine import compute_meal
from .nutrition.foods import get_food
from .optimizer.optimizer import plan_addons
from .personalization.models import UserProfile
from .personalization.report import build_report
from .personalization.targets import daily_targets
from .schemas import MealItem


def diet_conflicts(items: list[MealItem], profile: UserProfile) -> list[DietConflict]:
    """Flag items that clash with the user's diet. Vegetarian here means no fish or meat (eggs allowed)."""
    out: list[DietConflict] = []
    for it in items:
        food = get_food(it.fct_code)
        name = str(food["name_en"])
        group = str(food["food_group_code"])
        if profile.diet == "vegetarian" and group in {"09", "10"}:
            out.append(DietConflict(fct_code=it.fct_code, name_en=name,
                                    reason="contains fish or meat (vegetarian diet)"))
        elif profile.diet == "pescatarian" and group == "10":
            out.append(DietConflict(fct_code=it.fct_code, name_en=name,
                                    reason="contains meat (pescatarian diet)"))
        for word in profile.avoid:
            w = word.strip().lower()
            if w and w in name.lower():
                out.append(DietConflict(fct_code=it.fct_code, name_en=name,
                                        reason=f"matches your avoid list: {word}"))
    return out


def run_report(req: ReportRequest) -> ReportResponse:
    totals = compute_meal(req.items)
    targets = daily_targets(req.profile)
    report = build_report(totals, targets, req.meal)
    pivot = plan_addons(totals, targets, report, req.profile, req.meal,
                        exclude_codes=set(req.out_of_stock))
    return ReportResponse(
        totals=totals, targets=targets, report=report,
        diet_conflicts=diet_conflicts(req.items, req.profile), pivot=pivot,
    )