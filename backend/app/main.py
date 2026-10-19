from fastapi import FastAPI, File, HTTPException, UploadFile

from .nutrition.foods import search_foods
from .perception.pipeline import analyze_image

app = FastAPI(title="Nutrition Intelligence API")

MAX_BYTES = 8_000_000


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/foods/search")
def foods_search(q: str, limit: int = 5):
    return search_foods(q, limit)


@app.post("/analyze")
def analyze(file: UploadFile = File(...)):
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8 MB)")
    return analyze_image(raw)