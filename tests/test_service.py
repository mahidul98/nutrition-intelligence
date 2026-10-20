import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

PROFILE_A = {"name": "Student", "age": 21, "sex": "male", "weight_kg": 68, "height_cm": 172,
             "activity": "light", "goal": "maintain", "diet": "omnivore", "avoid": []}
PROFILE_B = {"name": "Office worker", "age": 38, "sex": "female", "weight_kg": 62, "height_cm": 158,
             "activity": "sedentary", "goal": "lose", "diet": "vegetarian", "avoid": [],
             "budget_bdt_per_day": 250}


def _body(profile=PROFILE_A, items=None, **kw):
    if items is None:
        items = [{"fct_code": "01_0024", "grams": 150}]
    body = {"items": items, "profile": profile, "meal": "lunch", "out_of_stock": []}
    body.update(kw)
    return body


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_personas_listed():
    data = client.get("/personas").json()
    assert "student" in data and "office_worker" in data


def test_report_returns_all_sections():
    r = client.post("/report", json=_body())
    assert r.status_code == 200
    data = r.json()
    for key in ("totals", "targets", "report", "diet_conflicts", "pivot"):
        assert key in data
    assert data["report"]["gaps"]


def test_vegetarian_conflict_flagged():
    r = client.post("/report", json=_body(PROFILE_B, [{"fct_code": "09_0068", "grams": 80}]))
    assert r.status_code == 200
    assert any(c["fct_code"] == "09_0068" for c in r.json()["diet_conflicts"])


def test_unknown_code_rejected():
    r = client.post("/report", json=_body(items=[{"fct_code": "99_9999", "grams": 100}]))
    assert r.status_code == 422


def test_minor_rejected():
    assert client.post("/report", json=_body(dict(PROFILE_A, age=17))).status_code == 422


def test_empty_items_rejected():
    assert client.post("/report", json=_body(items=[])).status_code == 422


def test_out_of_stock_items_are_not_suggested():
    first = client.post("/report", json=_body()).json()["pivot"]["items"]
    if not first:
        pytest.skip("no add-ons to exclude")
    codes = [it["fct_code"] for it in first]
    second = client.post("/report", json=_body(out_of_stock=codes)).json()["pivot"]["items"]
    assert all(it["fct_code"] not in codes for it in second)