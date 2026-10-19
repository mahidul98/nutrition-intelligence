
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.app.perception.pipeline import analyze_image
from backend.app.nutrition.foods import load_foods, search_foods
from backend.app.nutrition.engine import compute_meal
from backend.app.schemas import MealItem

st.set_page_config(
    page_title="Nutrition Intelligence",
    page_icon="🥗",
    layout="wide",
)

st.title("🥗 Nutrition Intelligence")
st.caption("Understand your meal. Make informed food choices.")
st.info(
    "Prototype notice: food recognition, portion sizes, and nutrition values "
    "may be inaccurate. Review all detected foods before calculating."
)

with st.sidebar:
    st.header("About")
    st.write("Upload a meal photo to estimate its nutritional content.")
    st.write("Nutrition values come from the project's food-composition database.")
    st.caption("This tool provides estimates, not medical advice.")

uploaded = st.file_uploader(
    "Upload a meal photo",
    type=["jpg", "jpeg", "png", "webp"],
)

if uploaded:
    image_bytes = uploaded.getvalue()
    st.image(uploaded, caption="Your meal", use_container_width=True)

    if st.button("Analyze meal", type="primary"):
        with st.spinner("Analyzing your meal..."):
            result = analyze_image(image_bytes)

        st.session_state["analysis_result"] = result
        st.session_state["analysis_filename"] = uploaded.name

result = st.session_state.get("analysis_result")

if result is not None:
    st.divider()
    st.subheader("1. Review detected foods")

    if result.status != "ok":
        st.error(result.message or "Unable to analyze this image.")
    elif not result.candidates:
        st.warning("No foods were detected. Try another photo.")
    else:
        if result.message:
            st.warning(result.message)

        st.write(
            "Check every food and its estimated weight. "
            "You can change the food match or remove items before calculating."
        )

        foods_df = load_foods().copy()
        food_names = foods_df["name_en"].astype(str).tolist()
        food_codes = foods_df["code"].astype(str).tolist()
        name_to_code = dict(zip(food_names, food_codes))

        edited_items = []

        for i, candidate in enumerate(result.candidates):
            with st.container(border=True):
                st.markdown(f"**Item {i + 1}: {candidate.detected_name}**")
                st.caption(
                    f"AI confidence: {candidate.confidence:.0%} · "
                    f"Match method: {candidate.match_method}"
                )

                if candidate.needs_confirmation:
                    st.warning("Please confirm this food match and portion.")

                default_code = candidate.fct_code
                default_name = candidate.matched_name

                if default_code and default_name in name_to_code:
                    default_index = food_codes.index(default_code)
                else:
                    default_index = 0

                selected_name = st.selectbox(
                    "Food database match",
                    options=food_names,
                    index=default_index,
                    key=f"food_{i}",
                )

                grams = st.number_input(
                    "Estimated edible portion (grams)",
                    min_value=1.0,
                    max_value=5000.0,
                    value=float(candidate.grams),
                    step=5.0,
                    key=f"grams_{i}",
                )

                include = st.checkbox(
                    "Include this item",
                    value=True,
                    key=f"include_{i}",
                )

                if include:
                    edited_items.append(
                        MealItem(
                            fct_code=name_to_code[selected_name],
                            grams=grams,
                        )
                    )

        if st.button("Calculate nutrition", type="primary"):
            if not edited_items:
                st.warning("Include at least one food item.")
            else:
                try:
                    totals = compute_meal(edited_items)
                    st.session_state["meal_totals"] = totals
                except Exception as exc:
                    st.error(f"Could not calculate nutrition: {exc}")

if "meal_totals" in st.session_state:
    totals = st.session_state["meal_totals"]

    st.divider()
    st.subheader("2. Estimated nutrition")

    values = totals.totals
    columns = st.columns(4)

    summary_metrics = [
        ("Energy", "energy_kcal", "kcal"),
        ("Protein", "protein_g", "g"),
        ("Carbohydrates", "carb_g", "g"),
        ("Fat", "fat_g", "g"),
    ]

    for column, (label, key, unit) in zip(columns, summary_metrics):
        value = values.get(key)
        if value is not None:
            column.metric(label, f"{value:,.1f} {unit}")
        else:
            column.metric(label, "Unavailable")

    st.markdown("#### Nutrient breakdown")

    nutrient_labels = {
        "energy_kcal": "Energy (kcal)",
        "protein_g": "Protein (g)",
        "fat_g": "Fat (g)",
        "carb_g": "Carbohydrates (g)",
        "fiber_g": "Fiber (g)",
        "sodium_mg": "Sodium (mg)",
        "calcium_mg": "Calcium (mg)",
        "iron_mg": "Iron (mg)",
        "vitamin_a_rae_mcg": "Vitamin A (µg RAE)",
        "vitamin_c_mg": "Vitamin C (mg)",
        "folate_mcg": "Folate (µg)",
    }

    table_rows = []
    for key, label in nutrient_labels.items():
        value = values.get(key)
        table_rows.append(
            {
                "Nutrient": label,
                "Amount": f"{value:,.2f}" if value is not None else "Unavailable",
            }
        )

    st.dataframe(table_rows, hide_index=True, use_container_width=True)

    if totals.unknown_by_nutrient:
        st.warning(
            "Some nutrient values are missing from the database. "
            "Totals for those nutrients may be incomplete."
        )

    st.markdown("#### Foods used in the calculation")
    st.dataframe(
        [
            {
                "Food": line.name_en,
                "Portion (g)": line.grams_input,
                "Edible portion (g)": line.edible_grams,
            }
            for line in totals.lines
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Estimates depend on correct food identification, portion size, "
        "preparation method, and database coverage. They are not a diagnosis "
        "or a substitute for professional dietary advice."
    )
