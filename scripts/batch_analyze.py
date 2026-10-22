import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.perception.pipeline import analyze_image

SRC = Path("data/samples")
OUT = Path("data/processed/batch_results.csv")
EXT = {".jpg", ".jpeg", ".png"}

photos = sorted(p for p in SRC.rglob("*") if p.suffix.lower() in EXT)
if not photos:
    sys.exit("No photos found in data/samples")

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["photo", "status", "seconds", "n_items", "n_need_confirm", "detected", "message"])
    for i, p in enumerate(photos, 1):
        t0 = time.time()
        res = analyze_image(p.read_bytes())
        secs = round(time.time() - t0, 1)
        detected = "; ".join(
            f"{c.matched_name or c.detected_name + ' (not in table)'} {c.grams:g} g"
            + (" [confirm]" if c.needs_confirmation else "")
            for c in res.candidates
        )
        w.writerow([p.name, res.status, secs, len(res.candidates),
                    sum(c.needs_confirmation for c in res.candidates), detected, res.message])
        print(f"[{i}/{len(photos)}] {p.name}: {res.status} in {secs}s, {len(res.candidates)} items")
        time.sleep(2)
print("Saved", OUT)