from google import genai
from google.genai import types

from ..config import GEMINI_API_KEY, GEMINI_MODEL
from ..nutrition.foods import load_foods
from .models import VisionResult

_client = None

PROMPT = """You identify foods in a photo for a Bangladeshi nutrition app.
Rules:
- List every distinct food or ingredient clearly visible. Never invent items you cannot see.
- For each item choose the best matching code from the FOOD LIST below. If no entry fits, use an empty string for fct_code and describe the item in name_en.
- Prefer the entry whose state (raw or cooked) matches what is shown.
- estimated_grams is your best estimate of the visible edible portion. Be conservative.
- confidence is your honest certainty from 0 to 1. Use low values when unsure.
- If the image is a printed menu, set scene_type to "menu", list nothing in items.
- If the image is too dark, blurry, or shows no food, set scene_type to "unusable" or "other", explain in quality_issue, and return no items.

FOOD LIST (code | name):
{vocab}
"""


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _vocabulary() -> str:
    df = load_foods()
    return "\n".join(f"{c} | {n}" for c, n in zip(df["code"], df["name_en"]))


def detect_foods(image_bytes: bytes, mime_type: str = "image/jpeg") -> VisionResult:
    resp = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            PROMPT.format(vocab=_vocabulary()),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VisionResult,
            temperature=0.1,
        ),
    )
    if getattr(resp, "parsed", None) is not None:
        return resp.parsed
    return VisionResult.model_validate_json(resp.text)