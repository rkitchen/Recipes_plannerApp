import streamlit as st
import os
from datetime import datetime
from google import genai

from auth import check_password
from utils import get_target_week, shift_week
from db import get_user_profile, save_user_preferences, get_meal_plan_for_week, update_recipe_rating
from recipe import load_recipes
from components import render_recipe_card, plan_week_dialog

# Set page config FIRST
st.set_page_config(page_title="Magic Meal Planner", page_icon="🍽️", layout="wide")

# Verify Authentication
check_password()

# CSS
st.markdown('''
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
html, body, [class*="css"]  { font-family: 'Outfit', sans-serif; color: #1e293b; }
[data-testid="stSidebar"] { background: #f8fafc !important; border-right: 1px solid #e2e8f0; }
.stApp { background: #ffffff; }
h1, h2, h3 { background: linear-gradient(135deg, #f43f5e, #f97316); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800 !important; }
div[data-baseweb="file-uploader"] { background: #f8fafc !important; border: 1px dashed #cbd5e1 !important; border-radius: 16px !important; padding: 10px; transition: all 0.3s ease; }
div[data-baseweb="file-uploader"]:hover { border: 1px dashed #f43f5e !important; background: #fff1f2 !important; }
.stButton > button { background: linear-gradient(135deg, #f43f5e 0%, #f97316 100%); border: none; border-radius: 12px; color: #ffffff !important; padding: 0.75rem 1.5rem; font-size: 1.1rem; font-weight: 600; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 4px 15px rgba(244, 63, 94, 0.3); width: 100%; }
.stButton > button:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 8px 25px rgba(244, 63, 94, 0.4); }
.stButton > button:active { transform: translateY(1px); }
.carousel-btn button { padding: 0.25rem 0.5rem; font-size: 1rem; }
</style>
''', unsafe_allow_html=True)

# Session State Defaults
if "viewed_monday" not in st.session_state: st.session_state.viewed_monday = get_target_week()
for key, default in [("parsed_ingredients", ""), ("photos_analyzed", False), ("current_user", None), ("user_profile", {"liked": [], "disliked": [], "preferences": {}})]:
    if key not in st.session_state: st.session_state[key] = default

# API Setup
api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
client = None
if api_key and api_key != "YOUR_API_KEY_HERE":
    try: client = genai.Client(api_key=api_key)
    except Exception: pass

# Sidebar Identity
st.sidebar.title("⚙️ Settings")
try:
    id_to_name = dict(st.secrets["users"])
    name_to_id = {v: k for k, v in id_to_name.items()}
except Exception:
    name_to_id = {"Default": "user_default"}

selected_name = st.sidebar.selectbox("👤 User", list(name_to_id.keys()))
new_user_id   = name_to_id[selected_name]

if st.session_state.current_user != new_user_id:
    st.session_state.current_user = new_user_id
    st.session_state.user_profile = get_user_profile(new_user_id)
    st.session_state.viewed_monday = get_target_week()
    st.rerun()

if not st.session_state.user_profile.get("liked") and not st.session_state.user_profile.get("disliked"):
    st.session_state.user_profile = get_user_profile(st.session_state.current_user)

prefs = st.session_state.user_profile.get("preferences", {})
meal_type = prefs.get("meal_type", "Main Only")
calories_goal = prefs.get("calories_goal", 2000)
nutrition_info = prefs.get("nutrition_info", "")
pantry_staples_str = prefs.get("pantry_staples", "olive oil, salt, black pepper, all-purpose flour, butter, garlic, onions, soy sauce, sugar, dried oregano, dried basil, cumin, water, vinegar, rice")
pantry_staples = [s.strip() for s in pantry_staples_str.split(",") if s.strip()]

st.sidebar.markdown("---")
st.sidebar.caption(f"**Meal structure:** {meal_type}")
st.sidebar.caption(f"**Calories/day:** {calories_goal} kcal")
if nutrition_info: st.sidebar.caption(f"**Constraints:** {nutrition_info}")
if not api_key or api_key == "YOUR_API_KEY_HERE": st.sidebar.error("⚠️ API Key not found in `.streamlit/secrets.toml`!")

# MAIN UI
st.title("✨ Intelligent Agentic Meal Planner")
if not client:
    st.warning("🔒 Please configure your Gemini API key in `.streamlit/secrets.toml`.")
    st.stop()

tab_recipes, tab_profile = st.tabs(["🍽️ Recipes", "👤 Profile"])

with tab_recipes:
    viewed_monday = st.session_state.viewed_monday
    vm_dt = datetime.strptime(viewed_monday, "%Y-%m-%d")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.markdown("<div class='carousel-btn'>", unsafe_allow_html=True)
        if st.button("◀ Previous Week", use_container_width=True):
            st.session_state.viewed_monday = shift_week(viewed_monday, -1)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<h3 style='text-align:center;'>Week of {vm_dt.strftime('%d %B %Y')}</h3>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='carousel-btn'>", unsafe_allow_html=True)
        if st.button("Next Week ▶", use_container_width=True):
            st.session_state.viewed_monday = shift_week(viewed_monday, 1)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
    st.markdown("---")

    all_recipes = load_recipes()
    recipe_dict = {r["uid"]: r for r in all_recipes}
    doc_id, plan_data, inventory_snapshot = get_meal_plan_for_week(st.session_state.current_user, viewed_monday)
    
    if plan_data:
        for idx, day_plan in enumerate(plan_data):
            day = day_plan.get("day", "Unknown Day")
            uid = day_plan.get("recipe_uid", "")
            reason = day_plan.get("reasoning", "")
            recipe = recipe_dict.get(uid)
            
            st.markdown(f"#### **{day}**")
            if recipe:
                recipe["_day"] = day
                render_recipe_card(
                    recipe=recipe, reason=reason, idx=idx,
                    plan_doc_id=doc_id, full_plan_data=plan_data,
                    inventory_snapshot=inventory_snapshot,
                    all_recipes=all_recipes, base_date_str=viewed_monday,
                    client=client
                )
            else:
                with st.container(border=True): st.error(f"Recipe UID `{uid}` not found in library.")
    else:
        st.info("No menu planned for this week.")
        if st.button("🪄 Plan This Week", type="primary"):
            plan_week_dialog(viewed_monday, all_recipes, client, pantry_staples, meal_type, calories_goal, nutrition_info)

with tab_profile:
    st.markdown("### 👤 Your Profile")
    st.markdown("#### 🎛️ Dietary Preferences")
    st.caption("These are saved to your profile and used to drive new plan generation.")

    p_col1, p_col2 = st.columns(2)
    with p_col1:
        pref_meal_type = st.radio("Meal Structure", ["Main Only", "Main + Starter/Dessert"], index=0 if meal_type == "Main Only" else 1)
        pref_calories = st.slider("Calories/day target", 1500, 3500, calories_goal, 100)
    with p_col2:
        pref_nutrition = st.text_area("Other Nutritional Constraints", value=nutrition_info)
        pref_staples = st.text_area("Pantry Staples", value=pantry_staples_str, height=120)

    if st.button("💾 Save Preferences"):
        new_prefs = {"meal_type": pref_meal_type, "calories_goal": pref_calories, "nutrition_info": pref_nutrition, "pantry_staples": pref_staples}
        save_user_preferences(st.session_state.current_user, new_prefs)
        st.session_state.user_profile["preferences"] = new_prefs
        st.success("✅ Preferences saved!")
        st.rerun()

    st.markdown("---")
    st.markdown("#### ⭐ Recipe Ratings")
    profile = st.session_state.user_profile
    liked_uids    = profile.get("liked", [])
    disliked_uids = profile.get("disliked", [])

    all_recipes = load_recipes()
    recipe_dict = {r["uid"]: r for r in all_recipes}
    def uid_to_name(uid): return recipe_dict.get(uid, {}).get("name", uid)
    
    liked_sorted    = sorted(liked_uids, key=uid_to_name)
    disliked_sorted = sorted(disliked_uids, key=uid_to_name)

    r_col_liked, r_col_disliked = st.columns(2)
    with r_col_liked:
        st.markdown("**👍 Liked Recipes**")
        if not liked_sorted: st.caption("None yet")
        for luid in liked_sorted:
            lc1, lc2 = st.columns([5, 1])
            with lc1: st.write(uid_to_name(luid))
            with lc2:
                if st.button("✕", key=f"rml_{luid}"):
                    update_recipe_rating(st.session_state.current_user, luid, "remove_like")
                    st.rerun()

    with r_col_disliked:
        st.markdown("**👎 Disliked Recipes**")
        if not disliked_sorted: st.caption("None yet")
        for duid in disliked_sorted:
            dc1, dc2 = st.columns([5, 1])
            with dc1: st.write(uid_to_name(duid))
            with dc2:
                if st.button("✕", key=f"rmd_{duid}"):
                    update_recipe_rating(st.session_state.current_user, duid, "remove_dislike")
                    st.rerun()
