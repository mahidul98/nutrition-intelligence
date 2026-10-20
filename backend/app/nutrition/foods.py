import difflib
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

FOODS_CSV = Path(__file__).resolve().parents[3] / "data" / "processed" / "foods.csv"
SUPPLEMENT_CSV = FOODS_CSV.parent / "supplement_foods.csv"


@lru_cache(maxsize=1)
def load_foods() -> pd.DataFrame:
    dtypes = {"code": str, "food_group_code": str}
    df = pd.read_csv(FOODS_CSV, encoding="utf-8-sig", dtype=dtypes)
    if SUPPLEMENT_CSV.exists():
        extra = pd.read_csv(SUPPLEMENT_CSV, encoding="utf-8-sig", dtype=dtypes)
        extra = extra.reindex(columns=df.columns)
        df = pd.concat([df, extra], ignore_index=True)
    return df.set_index("code", drop=False)


def get_food(code: str) -> pd.Series:
    df = load_foods()
    if code not in df.index:
        raise KeyError(f"Unknown FCT code: {code}")
    return df.loc[code]


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(s).lower()).split())


STOPWORDS = {"raw", "with", "without", "and", "of", "the", "in", "for"}


def _tokens(s: str) -> set[str]:
    return {t for t in _norm(s).split() if t not in STOPWORDS}


def search_foods(query: str, limit: int = 5) -> list[dict]:
    """Rank FCT rows against free text: word overlap first, character similarity as a tie-breaker."""
    df = load_foods()
    q = _norm(query)
    q_tok = _tokens(query)
    if not q or not q_tok:
        return []

    scored = []
    for code, name_en, name_bn in zip(df["code"], df["name_en"], df["name_bn_roman"]):
        best = 0.0
        for cand in (name_en, name_bn):
            if not isinstance(cand, str):
                continue
            c = _norm(cand)
            c_tok = _tokens(cand)
            if not c_tok:
                continue

            common = len(q_tok & c_tok)
            coverage = common / len(q_tok)
            precision = common / len(c_tok)
            ratio = difflib.SequenceMatcher(None, q, c).ratio()

            score = 0.6 * coverage + 0.2 * precision + 0.2 * ratio
            if q in c:
                score = max(score, 0.6 + 0.4 * (len(q) / len(c)))

            best = max(best, score)

        scored.append((best, code, name_en))

    scored.sort(reverse=True)
    return [
        {"code": c, "name_en": n, "score": round(s, 3)}
        for s, c, n in scored[:limit]
        if s >= 0.3
    ]