from fastapi import FastAPI, File, HTTPException, UploadFile

from .api_models import ReportRequest, ReportResponse
from .nutrition.foods import search_foods
from .perception.pipeline import analyze_image
from .personalization.personas import PERSONAS
from .service import run_report

app = FastAPI(title="Nutrition Intelligence API")

MAX_BYTES = 8_000_000


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/foods/search")
def foods_search(q: str, limit: int = 5):
    return search_foods(q, limit)


@app.get("/personas")
def personas():
    return {key: p.model_dump() for key, p in PERSONAS.items()}


@app.post("/analyze")
def analyze(file: UploadFile = File(...)):
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8 MB)")
    return analyze_image(raw)


@app.post("/report", response_model=ReportResponse)
def report(req: ReportRequest):
    try:
        return run_report(req)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown food code: {exc}")