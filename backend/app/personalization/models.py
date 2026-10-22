from typing import Literal

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    name: str = "Demo user"
    age: int = Field(ge=18, le=80)
    sex: Literal["male", "female"]  # used only by the energy formula
    weight_kg: float = Field(ge=35, le=200)
    height_cm: float = Field(ge=130, le=220)
    activity: Literal["sedentary", "light", "moderate", "active"] = "light"
    goal: Literal["maintain", "lose", "gain"] = "maintain"
    diet: Literal["omnivore", "vegetarian", "pescatarian"] = "omnivore"
    avoid: list[str] = []
    budget_bdt_per_day: float | None = Field(default=None, gt=0)


class Target(BaseModel):
    value: float
    kind: Literal["goal", "min", "max"]  # aim near / at least / at most


class DailyTargets(BaseModel):
    kcal_floor_applied: bool
    targets: dict[str, Target]


class ReportLine(BaseModel):
    nutrient: str
    amount: float
    meal_target: float
    kind: Literal["goal", "min", "max"]
    percent: float
    status: Literal["low", "ok", "high"]
    partial_data: bool = False


class MealReport(BaseModel):
    meal: str
    lines: list[ReportLine]
    gaps: list[str]
    excesses: list[str]
    notes: list[str]
    possible_gaps: list[str] = []