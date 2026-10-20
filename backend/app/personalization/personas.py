from .models import UserProfile

PERSONAS = {
    "student": UserProfile(
        name="Student", age=21, sex="male", weight_kg=68, height_cm=172,
        activity="light", goal="maintain",
    ),
    "office_worker": UserProfile(
        name="Office worker", age=38, sex="female", weight_kg=62, height_cm=158,
        activity="sedentary", goal="lose", diet="vegetarian", budget_bdt_per_day=250,
    ),
}