import pandas as pd
import requests
import streamlit as st

API = "http://127.0.0.1:8000"

LABEL = {
    "energy_kcal": "Energy (kcal)", "protein_g": "Protein (g)", "fat_g": "Fat (g)",
    "carb_g": "Carbohydrate (g)", "fiber_g": "Fibre (g)", "sodium_mg": "Sodium (mg)",
    "calcium_mg": "Calcium (mg)", "iron_mg": "Iron (mg)",
    "vitamin_a_rae_mcg": "Vitamin A (mcg RAE)", "vitamin_c_mg": "Vitamin C (mg)",
    "folate_mcg": "Folate (mcg)",
}
STATUS = {"low": "LOW", "ok": "OK", "high": "HIGH"}
COLS = ["use", "food", "fct_code", "grams", "dish", "confidence", "check"]


def api_get(path, **params):
    r = requests.get(API + path, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def run_report(payload):
    try:
        with st.spinner("Calculating..."):
            r = requests.post(API + "/report", json=payload, timeout=60)
            r.raise_for_status()
            return r.json()
    except requests.HTTPError as e:
        st.error(f"The backend rejected the request: {e.response.text[:300]}")
    except requests.RequestException:
        st.error("Cannot reach the backend. Is it running on port 8000?")
    return None


def candidates_to_df(cands):
    rows = []
    for c in cands:
        rows.append({
            "use": bool(c["fct_code"]),
            "food": c["matched_name"] or (c["detected_name"] + " (not in table)"),
            "fct_code": c["fct_code"] or "",
            "grams": float(c["grams"]),
            "dish": c["dish"],
            "confidence": float(c["confidence"]),
            "check": "please confirm" if c["needs_confirmation"] else "",
        })
    return pd.DataFrame(rows, columns=COLS)


st.set_page_config(page_title="Nutrition Intelligence", layout="wide")
st.title("Nutrition Intelligence")
st.caption("Photo to nutrition report to a local shopping list. "
           "Educational tool, not medical advice. Adults 18+ only.")

try:
    personas = api_get("/personas")
except requests.RequestException:
    st.error("Cannot reach the backend. Start it in a second terminal with: "
             "uvicorn backend.app.main:app --port 8000")
    st.stop()

# ---------------- sidebar: person ----------------
st.sidebar.header("Person")
pkey = st.sidebar.selectbox("Profile", list(personas), format_func=lambda k: personas[k]["name"])
base = personas[pkey]
with st.sidebar.expander("Customize"):
    age = st.number_input("Age (18+)", 18, 80, int(base["age"]), key=f"age_{pkey}")
    sexes = ["male", "female"]
    sex = st.selectbox("Sex (used by the energy formula)", sexes,
                       index=sexes.index(base["sex"]), key=f"sex_{pkey}")
    weight = st.number_input("Weight (kg)", 35.0, 200.0, float(base["weight_kg"]), key=f"w_{pkey}")
    height = st.number_input("Height (cm)", 130.0, 220.0, float(base["height_cm"]), key=f"h_{pkey}")
    activities = ["sedentary", "light", "moderate", "active"]
    activity = st.selectbox("Activity", activities, index=activities.index(base["activity"]),
                            key=f"act_{pkey}")
    goals = ["maintain", "lose", "gain"]
    goal = st.selectbox("Goal", goals, index=goals.index(base["goal"]), key=f"goal_{pkey}")
    diets = ["omnivore", "vegetarian", "pescatarian"]
    diet = st.selectbox("Diet", diets, index=diets.index(base["diet"]), key=f"diet_{pkey}")
    avoid_txt = st.text_input("Foods to avoid (comma separated)",
                              ", ".join(base.get("avoid", [])), key=f"avoid_{pkey}")
    budget = st.number_input("Daily food budget (BDT, 0 = none)", 0.0, 5000.0,
                             float(base.get("budget_bdt_per_day") or 0.0), step=10.0,
                             key=f"bud_{pkey}")
meal = st.sidebar.selectbox("Meal", ["breakfast", "lunch", "dinner", "snack"], index=1)

profile = {
    "name": base["name"], "age": int(age), "sex": sex, "weight_kg": float(weight),
    "height_cm": float(height), "activity": activity, "goal": goal, "diet": diet,
    "avoid": [w.strip() for w in avoid_txt.split(",") if w.strip()],
    "budget_bdt_per_day": float(budget) if budget > 0 else None,
}

# ---------------- step 1: photo ----------------
st.header("1. Photo")
col_a, col_b = st.columns(2)
cam = col_a.camera_input("Take a photo")
up = col_b.file_uploader("...or upload one", type=["jpg", "jpeg", "png"])
img = cam if cam is not None else up
if img is not None:
    st.image(img, width=320)

if img is not None and st.button("Analyze photo"):
    data = None
    try:
        with st.spinner("Identifying foods..."):
            files = {"file": (getattr(img, "name", "photo.jpg"), img.getvalue(),
                              getattr(img, "type", None) or "image/jpeg")}
            r = requests.post(API + "/analyze", files=files, timeout=120)
            r.raise_for_status()
            data = r.json()
    except requests.RequestException as e:
        st.error(f"Photo analysis failed: {e}")
    if data:
        if data["status"] == "ok":
            st.session_state["items"] = candidates_to_df(data["candidates"])
            st.session_state.pop("editor", None)
            st.session_state.pop("result", None)
            if data["message"]:
                st.info(data["message"])
        else:
            st.warning(data["message"] or "Could not analyze this photo.")

# ---------------- step 2: confirm ----------------
st.header("2. Confirm what was found")
items = st.session_state.get("items")
if items is not None and not items.empty:
    st.caption("Untick anything that is wrong and correct the grams. "
               "Weights from a photo are estimates.")
    edited = st.data_editor(
        items, key="editor", hide_index=True,
        disabled=["food", "fct_code", "dish", "confidence", "check"],
        column_config={
            "use": st.column_config.CheckboxColumn("Use"),
            "grams": st.column_config.NumberColumn("Grams (edible)", min_value=1.0,
                                                   max_value=5000.0, step=5.0),
        },
    )
else:
    edited = pd.DataFrame(columns=COLS)
    st.caption("No foods yet. Analyze a photo, or add foods manually below.")

with st.expander("Add a food manually"):
    q = st.text_input("Search the food table (English, or Bangla written in English letters)")
    if q:
        try:
            hits = api_get("/foods/search", q=q, limit=8)
        except requests.RequestException:
            hits = []
        options = {f"{h['name_en']} ({h['code']})": h for h in hits}
        if options:
            choice = st.selectbox("Match", list(options))
            grams_new = st.number_input("Grams (edible)", 5.0, 1500.0, 100.0, step=5.0)
            if st.button("Add to meal"):
                h = options[choice]
                new = pd.DataFrame([{
                    "use": True, "food": h["name_en"], "fct_code": h["code"],
                    "grams": float(grams_new), "dish": "", "confidence": 1.0, "check": "added by you",
                }], columns=COLS)
                st.session_state["items"] = pd.concat([edited, new], ignore_index=True)
                st.session_state.pop("editor", None)
                st.rerun()
        else:
            st.caption("No match found. Try another word.")

use_rows = edited[(edited["use"] == True) & (edited["fct_code"].fillna("").astype(str) != "")]  # noqa: E712
unmatched = edited[edited["fct_code"].fillna("").astype(str) == ""]
if len(unmatched):
    st.warning(f"{len(unmatched)} item(s) are not in the food table and will be skipped. "
               "Use 'Add a food manually' for a close match.")

# ---------------- step 3: report ----------------
st.header("3. Report")
if st.button("Calculate report", type="primary"):
    if use_rows.empty:
        st.warning("Tick at least one food first.")
    else:
        payload = {
            "items": [{"fct_code": str(r.fct_code), "grams": float(r.grams)}
                      for r in use_rows.itertuples()],
            "profile": profile, "meal": meal, "out_of_stock": [],
        }
        st.session_state["payload"] = payload
        st.session_state["oos"] = []
        st.session_state["result"] = run_report(payload)

res = st.session_state.get("result")
if res:
    rep, pv = res["report"], res["pivot"]
    lines = rep["lines"]

    for c in res["diet_conflicts"]:
        st.warning(f"Diet conflict: {c['name_en']} {c['reason']}.")

    energy = next((ln for ln in lines if ln["nutrient"] == "energy_kcal"), None)
    protein = next((ln for ln in lines if ln["nutrient"] == "protein_g"), None)
    m1, m2, m3 = st.columns(3)
    if energy:
        m1.metric("Energy", f"{energy['amount']} kcal", f"{int(energy['percent'])}% of meal target",
                  delta_color="off")
    if protein:
        m2.metric("Protein", f"{protein['amount']} g", f"{int(protein['percent'])}% of meal target",
                  delta_color="off")
    m3.metric("Gaps found", len(rep["gaps"]))

    table = pd.DataFrame([{
        "Nutrient": LABEL.get(ln["nutrient"], ln["nutrient"]),
        "This meal": ln["amount"],
        "Meal target": ln["meal_target"],
        "% of target": int(ln["percent"]),
        "Status": STATUS[ln["status"]] + (" *" if ln["partial_data"] else ""),
    } for ln in lines])
    st.dataframe(table, hide_index=True)
    st.caption("* some foods have no data for this nutrient, so the total may be understated.")

    # ---- shopping list ----
    st.subheader("Shopping list to close the gaps")
    if pv["catalog_is_sample"]:
        st.error("These prices are development samples, not real prices.")

    if pv["status"] == "ok":
        shop = pd.DataFrame([{
            "Food": it["name_en"], "Eat (g)": it["eat_grams"], "Buy (g)": it["buy_grams"],
            "Cost (BDT)": it["cost_bdt"],
            "Helps with": ", ".join(LABEL.get(h, h) for h in it["helps"]),
            "Store": it["store"],
        } for it in pv["items"]])
        st.dataframe(shop, hide_index=True)
        st.metric("Estimated cost of add-ons", f"{pv['total_cost_bdt']} BDT")

        target_by = {ln["nutrient"]: ln["meal_target"] for ln in lines}
        focus = [n for n in rep["gaps"] if n in pv["after"] and target_by.get(n)]
        if focus:
            chart = pd.DataFrame({
                "Before (%)": [100 * pv["before"][n] / target_by[n] for n in focus],
                "After (%)": [100 * pv["after"][n] / target_by[n] for n in focus],
            }, index=[LABEL.get(n, n) for n in focus])
            st.bar_chart(chart)
        if pv["remaining_gaps"]:
            st.info("Still low after these add-ons: "
                    + ", ".join(LABEL.get(n, n) for n in pv["remaining_gaps"]))

        # ---- out-of-stock demo ----
        opts = {f"{it['name_en']} ({it['fct_code']})": it["fct_code"] for it in pv["items"]}
        pick = st.multiselect("Demo: mark these as out of stock", list(opts))
        c1, c2 = st.columns(2)
        if c1.button("Re-plan without them") and pick:
            payload = dict(st.session_state["payload"])
            payload["out_of_stock"] = sorted(set(st.session_state.get("oos", []))
                                             | {opts[p] for p in pick})
            st.session_state["oos"] = payload["out_of_stock"]
            st.session_state["result"] = run_report(payload)
            st.rerun()
        if st.session_state.get("oos") and c2.button("Reset stock"):
            payload = dict(st.session_state["payload"])
            payload["out_of_stock"] = []
            st.session_state["oos"] = []
            st.session_state["result"] = run_report(payload)
            st.rerun()
        if st.session_state.get("oos"):
            st.caption("Currently out of stock: " + ", ".join(st.session_state["oos"]))
    elif pv["status"] == "nothing_needed":
        st.success("No gaps to fill among the nutrients we track.")
    else:
        st.info(" ".join(pv["notes"]) or "No shopping suggestion could be made.")

    for n in rep["notes"] + pv["notes"]:
        st.caption(n)

st.divider()
st.caption("Nutrient values: Food Composition Table for Bangladesh (2013). "
           "Photo analysis uses a vision model and may make mistakes. "
           "This tool gives general educational information, not medical advice.")