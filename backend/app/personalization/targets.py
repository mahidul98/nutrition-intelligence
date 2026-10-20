from .models import DailyTargets, Target, UserProfile

ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
GOAL_ADJUST = {"maintain": 0.0, "lose": -0.15, "gain": 0.10}
CAL_FLOOR = {"female": 1200.0, "male": 1500.0}  # safety floor for this educational tool
PROTEIN_PER_KG = {"maintain": 1.0, "lose": 1.2, "gain": 1.4}


def bmr(p: UserProfile) -> float:
    """Mifflin-St Jeor equation."""
    return 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age + (5 if p.sex == "male" else -161)


def daily_targets(p: UserProfile) -> DailyTargets:
    kcal = bmr(p) * ACTIVITY[p.activity] * (1 + GOAL_ADJUST[p.goal])
    floor = CAL_FLOOR[p.sex]
    applied = kcal < floor
    kcal = max(kcal, floor)

    protein = PROTEIN_PER_KG[p.goal] * p.weight_kg
    protein = min(max(protein, 0.8 * p.weight_kg), 0.30 * kcal / 4)
    fat = 0.28 * kcal / 9
    carb = max((kcal - protein * 4 - fat * 9) / 4, 0.0)

    # Adult reference intakes (US NIH RDA values). Replace with Bangladesh / FAO-WHO
    # values if you adopt them, and say so in your documentation.
    iron = 8.0 if p.sex == "male" or p.age > 50 else 18.0
    calcium = 1200.0 if (p.sex == "female" and p.age > 50) or p.age > 70 else 1000.0
    vit_a = 900.0 if p.sex == "male" else 700.0
    vit_c = 90.0 if p.sex == "male" else 75.0

    targets = {
        "energy_kcal": Target(value=round(kcal), kind="goal"),
        "protein_g": Target(value=round(protein, 1), kind="min"),
        "fat_g": Target(value=round(fat, 1), kind="goal"),
        "carb_g": Target(value=round(carb, 1), kind="goal"),
        "fiber_g": Target(value=round(14 * kcal / 1000, 1), kind="min"),
        "sodium_mg": Target(value=2000.0, kind="max"),
        "calcium_mg": Target(value=calcium, kind="min"),
        "iron_mg": Target(value=iron, kind="min"),
        "vitamin_a_rae_mcg": Target(value=vit_a, kind="min"),
        "vitamin_c_mg": Target(value=vit_c, kind="min"),
        "folate_mcg": Target(value=400.0, kind="min"),
    }
    return DailyTargets(kcal_floor_applied=applied, targets=targets)