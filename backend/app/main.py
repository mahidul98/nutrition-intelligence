from fastapi import FastAPI

app = FastAPI(title="Nutrition Intelligence API")


@app.get("/health")
def health():
    return {"status": "ok"}