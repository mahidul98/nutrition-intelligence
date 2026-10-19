from dataclasses import asdict, is_dataclass
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from backend.app.nutrition.engine import MealItem, compute_meal
from backend.app.nutrition.foods import load_foods, search_foods
from backend.app.perception.pipeline import analyze_image

app = FastAPI(title="Nutrition Intelligence API", version="0.1.0")


class MealAnalysisRequest(BaseModel):
    items: list[MealItem]


@app.get("/")
def root():
    return {
        "service": "Nutrition Intelligence API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/foods/search")
def search_food_database(
    q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=20)
):
    results = search_foods(q, limit=limit)
    return {"query": q, "count": len(results), "results": results}


@app.post("/api/nutrition/calculate")
def calculate_nutrition(payload: MealAnalysisRequest):
    try:
        totals = compute_meal(payload.items)
        if hasattr(totals, "model_dump"):
            return totals.model_dump()
        elif is_dataclass(totals):
            return asdict(totals)
        return totals
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {e}")


@app.post("/api/perception/analyze")
async def analyze_photo(file: UploadFile = File(...)):
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=400, detail="Uploaded file contains no data."
        )

    try:
        result = analyze_image(image_bytes)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        elif is_dataclass(result):
            return asdict(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Perception error: {e}")