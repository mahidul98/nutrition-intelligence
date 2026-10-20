import io

from PIL import Image

from backend.app.perception import pipeline
from backend.app.perception.image import prepare_image
from backend.app.perception.models import DetectedItem, VisionResult


def _png(w=64, h=64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def _item(**kw):
    base = dict(
        fct_code="",
        name_en="",
        name_bn_roman="",
        dish="",
        estimated_grams=100.0,
        confidence=0.9,
        state="raw",
    )
    base.update(kw)
    return DetectedItem(**base)


def _patch(monkeypatch, result):
    monkeypatch.setattr(
        pipeline, "detect_foods", lambda b, mime_type="image/jpeg": result
    )


def test_valid_code_accepted(monkeypatch):
    _patch(
        monkeypatch,
        VisionResult(
            scene_type="ingredients",
            quality_issue="",
            items=[
                _item(fct_code="01_0001", name_en="barley", estimated_grams=150)
            ],
        ),
    )
    r = pipeline.analyze_image(_png())
    c = r.candidates[0]
    assert r.status == "ok" and c.fct_code == "01_0001"
    assert c.match_method == "model_code" and not c.needs_confirmation


def test_hallucinated_code_falls_back_to_fuzzy(monkeypatch):
    _patch(
        monkeypatch,
        VisionResult(
            scene_type="cooked_meal",
            quality_issue="",
            items=[_item(fct_code="99_9999", name_en="khichuri")],
        ),
    )
    c = pipeline.analyze_image(_png()).candidates[0]
    assert c.fct_code != "99_9999" and "khichuri" in c.matched_name.lower()
    assert c.needs_confirmation


def test_no_match_is_flagged(monkeypatch):
    _patch(
        monkeypatch,
        VisionResult(
            scene_type="ingredients",
            quality_issue="",
            items=[_item(name_en="xyzzyq")],
        ),
    )
    c = pipeline.analyze_image(_png()).candidates[0]
    assert c.fct_code is None and c.needs_confirmation


def test_low_confidence_needs_confirmation(monkeypatch):
    _patch(
        monkeypatch,
        VisionResult(
            scene_type="ingredients",
            quality_issue="",
            items=[_item(fct_code="01_0001", confidence=0.3)],
        ),
    )
    assert pipeline.analyze_image(_png()).candidates[0].needs_confirmation


def test_menu_unsupported(monkeypatch):
    _patch(
        monkeypatch,
        VisionResult(scene_type="menu", quality_issue="", items=[]),
    )
    assert pipeline.analyze_image(_png()).status == "unsupported"


def test_unusable_needs_retake(monkeypatch):
    _patch(
        monkeypatch,
        VisionResult(
            scene_type="unusable", quality_issue="too dark", items=[]
        ),
    )
    r = pipeline.analyze_image(_png())
    assert r.status == "needs_retake" and "dark" in r.message


def test_api_failure_returns_error(monkeypatch):
    def boom(b, mime_type="image/jpeg"):
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline, "detect_foods", boom)
    assert pipeline.analyze_image(_png()).status == "error"


def test_garbage_bytes_return_error():
    assert pipeline.analyze_image(b"not an image").status == "error"


def test_prepare_image_downsizes_to_jpeg():
    out = Image.open(io.BytesIO(prepare_image(_png(3000, 2000))))
    assert out.format == "JPEG" and max(out.size) == 1280


def test_dish_components_are_grouped(monkeypatch):
    _patch(
        monkeypatch,
        VisionResult(
            scene_type="cooked_meal",
            quality_issue="",
            items=[
                _item(
                    fct_code="01_0001",
                    name_en="rice",
                    dish="fried rice",
                    estimated_grams=150,
                ),
                _item(
                    fct_code="11_0001",
                    name_en="egg",
                    dish="fried rice",
                    estimated_grams=30,
                ),
            ],
        ),
    )
    r = pipeline.analyze_image(_png())
    assert [c.dish for c in r.candidates] == ["fried rice", "fried rice"]


def test_irrelevant_alternatives_are_hidden(monkeypatch):
    _patch(
        monkeypatch,
        VisionResult(
            scene_type="ingredients",
            quality_issue="",
            items=[_item(name_en="fried rice")],
        ),
    )
    alts = pipeline.analyze_image(_png()).candidates[0].alternatives
    assert all("fig" not in a["name_en"].lower() for a in alts)

def test_dish_components_always_need_confirmation(monkeypatch):
    _patch(monkeypatch, VisionResult(scene_type="cooked_meal", quality_issue="", items=[
        _item(fct_code="01_0001", name_en="rice", dish="fried rice", confidence=0.95),
    ]))
    assert pipeline.analyze_image(_png()).candidates[0].needs_confirmation
def test_cooking_fat_dropped_when_dish_entry_already_includes_it(monkeypatch):
    _patch(monkeypatch, VisionResult(scene_type="cooked_meal", quality_issue="", items=[
        _item(fct_code="01_0036", name_en="Plain pulao", dish="Plain pulao", estimated_grams=250),
        _item(fct_code="13_0004", name_en="Ghee", dish="Plain pulao", estimated_grams=10),
    ]))
    r = pipeline.analyze_image(_png())
    assert [c.fct_code for c in r.candidates] == ["01_0036"]


def test_cooking_fat_kept_when_dish_is_built_from_raw_ingredients(monkeypatch):
    _patch(monkeypatch, VisionResult(scene_type="cooked_meal", quality_issue="", items=[
        _item(fct_code="01_0024", name_en="rice", dish="fried rice", estimated_grams=150),
        _item(fct_code="13_0012", name_en="soya oil", dish="fried rice", estimated_grams=10),
    ]))
    r = pipeline.analyze_image(_png())
    assert [c.fct_code for c in r.candidates] == ["01_0024", "13_0012"]