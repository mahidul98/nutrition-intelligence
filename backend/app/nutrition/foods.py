import difflib
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

FOODS_CSV = Path(__file__).resolve().parents[3] / "data" / "processed" / "foods.csv"


@lru_cache(maxsize=1)
def load_foods() -> pd.DataFrame:
    df = pd.read_csv(
        FOODS_CSV, encoding="utf-8-sig", dtype={"code": str, "food_group_code": str}
    )
    return df.set_index("code", drop=False)


def get_food(code: str) -> pd.Series:
    df = load_foods()
    if code not in df.index:
        raise KeyError(f"Unknown FCT code: {code}")
    return df.loc[code]


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(s).lower()).split())


def search_foods(query: str, limit: int = 5) -> list[dict]:
    """Fuzzy match a free-text food name to FCT rows (English + romanized Bengali)."""
    df = load_foods()
    q = _norm(query)
    if not q:
        return []
    scored = []
    for code, name_en, name_bn in zip(df["code"], df["name_en"], df["name_bn_roman"]):
        best = 0.0
        for cand in (name_en, name_bn):
            if not isinstance(cand, str):
                continue
            c = _norm(cand)
            r = difflib.SequenceMatcher(None, q, c).ratio()
            if q in c:
                r = max(r, 0.6 + 0.4 * len(q) / len(c))
            best = max(best, r)
        scored.append((best, code, name_en))
    scored.sort(reverse=True)
    return [
        {"code": c, "name_en": n, "score": round(s, 3)}
        for s, c, n in scored[:limit]
        if s > 0.3
    ]