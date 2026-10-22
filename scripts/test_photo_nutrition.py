
import sys
from pathlib import Path

# Allow imports from the project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.nutrition.engine import compute_meal
from backend.app.perception.pipeline import analyze_image
from backend.app.schemas import MealItem


def main():
    image_path = Path(
        sys.argv[1] if len(sys.argv) > 1
        else ROOT / "data" / "samples" / "khichuri.jpg"
    )

    print(f"\nAnalyzing: {image_path.name}")

    # 1. Detect foods in the photo
    result = analyze_image(image_path.read_bytes())

    if result.status != "ok":
        print(f"\nAnalysis failed: {result.message}")
        return

    # 2. Show detected foods
    print("\nDetected foods:")
    for candidate in result.candidates:
        print(
            f"- {candidate.detected_name}: "
            f"{candidate.grams} g "
            f"(confidence: {candidate.confidence:.0%})"
        )

    # 3. Use only matched foods for the nutrition calculation
    matched = [
        MealItem(fct_code=c.fct_code, grams=c.grams)
        for c in result.candidates
        if c.fct_code and not c.needs_confirmation
    ]

    if not matched:
        print("\nNo confirmed food matches available.")
        print("Please review the detected foods manually.")
        return

    # 4. Calculate nutrients using the existing engine
    totals = compute_meal(matched)

    print("\n=== NUTRITION REPORT ===")
    for nutrient, value in totals.totals.items():
        print(f"{nutrient}: {value}")

    if totals.unknown_by_nutrient:
        print("\nNutrients with missing data:")
        for nutrient, codes in totals.unknown_by_nutrient.items():
            print(f"- {nutrient}: {', '.join(codes)}")


if __name__ == "__main__":
    main()
