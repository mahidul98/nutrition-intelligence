from google import genai
from google.genai import types

from ..config import GEMINI_API_KEY, GEMINI_MODEL
from ..nutrition.foods import load_foods
from .models import VisionResult

_client = None

PROMPT = """You identify foods in a photo for a Bangladeshi nutrition app. A nutrient table (the FOOD LIST below) is the ONLY source of numbers, so you must describe what you see in terms of that list.
Rules:
1. List every food clearly visible. Never invent items you cannot see.
2. A single ingredient (rice, an egg, a fish): set dish to an empty string and choose the best matching code.
3. A prepared dish (fried rice, chicken curry, soup): break it into its main ingredients. Create one item per ingredient, set dish to the dish name, choose the closest code for each ingredient, and give each ingredient its own estimated_grams so the parts add up to the visible portion.
4. If a dish looks oily or fried, add the cooking fat (for example an oil or ghee, if it is in the list) as a separate item with a modest estimate (5 to 15 g per portion).
5. Prefer a cooked or prepared list entry when one exists; otherwise use the raw entry and set state to the real condition shown.
6. Use an empty fct_code only when nothing in the list is a reasonable stand-in (for example a packaged sausage); then describe it in name_en.
7. Ignore sauces in small cups, garnish, plates, cutlery and drinks unless they are a meaningful portion of food.
8. confidence is your honest certainty from 0 to 1. Use lower values for mixed dishes and for estimated weights.
9. If the image is a printed menu, set scene_type to "menu" and return no items.
10. If the image is too dark, blurry, or shows no food, set scene_type to "unusable" or "other", explain in quality_issue, and return no items.
11. Never omit a main component of the meal (noodles, rice, bread, meat, fish). If no list entry is a reasonable stand-in, still return the item with an empty fct_code, its real name in name_en, and an estimated_grams, so the user can confirm it. If the closest list entry is a clearly different food, prefer the empty code to a wrong match.

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