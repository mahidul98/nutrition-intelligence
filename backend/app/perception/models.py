from typing import Literal

from pydantic import BaseModel, Field


# ---- what the vision model returns ----
class DetectedItem(BaseModel):
    fct_code: str = Field(description="Code from the provided FOOD LIST, or empty string if none fits")
    name_en: str = Field(description="Plain English name of the food as seen")
    name_bn_roman: str = Field(description="Common Bangla name in Latin letters, or empty string")
    estimated_grams: float = Field(description="Estimated edible weight in grams of the visible portion")
    confidence: float = Field(description="Honest certainty from 0.0 to 1.0")
    state: Literal["raw", "cooked", "packaged", "unknown"]


class VisionResult(BaseModel):
    scene_type: Literal["ingredients", "cooked_meal", "menu", "other", "unusable"]
    quality_issue: str = Field(description="Empty if fine, else e.g. too dark, blurry, no food visible")
    items: list[DetectedItem]


# ---- what the API returns to the UI ----
class Candidate(BaseModel):
    fct_code: str | None
    matched_name: str | None
    detected_name: str
    grams: float
    confidence: float
    match_method: Literal["model_code", "fuzzy", "none"]
    needs_confirmation: bool
    alternatives: list[dict[str, str]] = []


class AnalysisResult(BaseModel):
    status: Literal["ok", "needs_retake", "unsupported", "error"]
    message: str = ""
    candidates: list[Candidate] = []