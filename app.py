import streamlit as st
import os
import zipfile
import gzip
import json
import re
import base64
from datetime import datetime, timedelta
from PIL import Image
try:
    from io import BytesIO
except ImportError:
    pass
from google import genai
from google.genai import types
from typing import Optional, List, Tuple

# Optional Firebase imports (only needed when FIREBASE_* secrets are set)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore as fb_firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# Set page config FIRST
st.set_page_config(page_title="Magic Meal Planner", page_icon="🍽️", layout="wide")


# ---------------------------------------------------------------------------
# Password Gate
# ---------------------------------------------------------------------------
def _check_password() -> bool:
    """Returns True only if the user has already authenticated this session."""
    if st.session_state.get("authenticated", False):
        return True

    try:
        app_password = st.secrets["APP_PASSWORD"]
    except (KeyError, Exception):
        return True

    st.markdown(
        "<h2 style='text-align:center; margin-top: 20vh;'>🍽️ Meal Planner</h2>"
        "<p style='text-align:center; color:#64748b;'>Enter the access password to continue.</p>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 1, 1])
    with col:
        entered = st.text_input("Password", type="password", label_visibility="collapsed",
                                placeholder="Enter password…")
        if st.button("Unlock →", use_container_width=True):
            if entered == app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()
    return False

_check_password()


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown('''
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

html, body, [class*="css"]  { font-family: 'Outfit', sans-serif; color: #1e293b; }

[data-testid="stSidebar"] { background: #f8fafc !important; border-right: 1px solid #e2e8f0; }
.stApp { background: #ffffff; }

h1, h2, h3 {
    background: linear-gradient(135deg, #f43f5e, #f97316);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-weight: 800 !important;
}

div[data-baseweb="file-uploader"] {
    background: #f8fafc !important; border: 1px dashed #cbd5e1 !important;
    border-radius: 16px !important; padding: 10px; transition: all 0.3s ease;
}
div[data-baseweb="file-uploader"]:hover {
    border: 1px dashed #f43f5e !important; background: #fff1f2 !important;
}

.stButton > button {
    background: linear-gradient(135deg, #f43f5e 0%, #f97316 100%);
    border: none; border-radius: 12px; color: #ffffff !important;
    padding: 0.75rem 1.5rem; font-size: 1.1rem; font-weight: 600;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 15px rgba(244, 63, 94, 0.3); width: 100%;
}
.stButton > button:hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 8px 25px rgba(244, 63, 94, 0.4); }
.stButton > button:active { transform: translateY(1px); }

/* Compact date carousel buttons */
.carousel-btn button { padding: 0.25rem 0.5rem; font-size: 1rem; }
</style>
''', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Time logic helpers
# ---------------------------------------------------------------------------
def get_target_week() -> str:
    """
    Mon-Fri: returns this week's Monday.
    Sat-Sun: returns next week's Monday.
    Returned as YYYY-MM-DD string.
    """
    today = datetime.now()
    if today.weekday() >= 5:  # 5=Sat, 6=Sun
        days_ahead = 7 - today.weekday() 
        target = today + timedelta(days=days_ahead)
    else:
        target = today - timedelta(days=today.weekday())
    return target.strftime("%Y-%m-%d")


def shift_week(current_monday_str: str, weeks: int) -> str:
    """Shift a YYYY-MM-DD date by N weeks."""
    dt = datetime.strptime(current_monday_str, "%Y-%m-%d")
    new_dt = dt + timedelta(weeks=weeks)
    return new_dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Session State Defaults
# ---------------------------------------------------------------------------
if "viewed_monday" not in st.session_state:
    st.session_state.viewed_monday = get_target_week()

for key, default in [
    ("parsed_ingredients", ""),
    ("photos_analyzed", False),
    ("current_user", None),
    ("user_profile", {"liked": [], "disliked": [], "preferences": {}}),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# API Setup
# ---------------------------------------------------------------------------
api_key = ""
try:
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
except Exception:
    api_key = os.environ.get("GEMINI_API_KEY", "")

client = None
if api_key and api_key != "YOUR_API_KEY_HERE":
    try:
        client = genai.Client(api_key=api_key)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Firestore client (singleton)
# ---------------------------------------------------------------------------
def _get_db():
    if not FIREBASE_AVAILABLE:
        st.error("Firebase SDK not installed — run: uv pip install firebase-admin")
        return None
    try:
        sa_info = dict(st.secrets["firebase"])
        if not firebase_admin._apps:
            cred = credentials.Certificate(sa_info)
            firebase_admin.initialize_app(cred)
        return fb_firestore.client()
    except Exception as e:
        st.error(f"Firestore init failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Firestore operations
# ---------------------------------------------------------------------------
def get_user_profile(user_id: str) -> dict:
    db = _get_db()
    empty = {"liked": [], "disliked": [], "preferences": {}}
    if db is None or not user_id: return empty
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            d = doc.to_dict()
            return {
                "liked": d.get("liked_recipes", []),
                "disliked": d.get("disliked_recipes", []),
                "preferences": d.get("preferences", {}),
            }
        return empty
    except Exception:
        return empty


def save_user_preferences(user_id: str, prefs: dict):
    db = _get_db()
    if db is None or not user_id: return
    db.collection("users").document(user_id).set({"preferences": prefs}, merge=True)


def update_recipe_rating(user_id: str, recipe_uid: str, rating_type: str):
    db = _get_db()
    if db is None or not user_id: return
    try:
        ref = db.collection("users").document(user_id)
        ArrayUnion  = fb_firestore.ArrayUnion
        ArrayRemove = fb_firestore.ArrayRemove
        if rating_type == "like":
            ref.set({"liked_recipes": ArrayUnion([recipe_uid]), "disliked_recipes": ArrayRemove([recipe_uid])}, merge=True)
        elif rating_type == "dislike":
            ref.set({"disliked_recipes": ArrayUnion([recipe_uid]), "liked_recipes": ArrayRemove([recipe_uid])}, merge=True)
        elif rating_type == "remove_like":
            ref.set({"liked_recipes": ArrayRemove([recipe_uid])}, merge=True)
        elif rating_type == "remove_dislike":
            ref.set({"disliked_recipes": ArrayRemove([recipe_uid])}, merge=True)
        st.session_state.user_profile = get_user_profile(user_id)
    except Exception as e:
        st.error(f"Rating update failed: {e}")


def get_meal_plan_for_week(user_id: str, week_start_str: str) -> Tuple[Optional[str], list, str]:
    """Returns (document_id, plan_data_list, inventory_string)"""
    db = _get_db()
    if db is None or not user_id: return None, [], ""
    try:
        docs = (db.collection("meal_plans")
                  .where(filter=fb_firestore.FieldFilter("user_id", "==", user_id))
                  .where(filter=fb_firestore.FieldFilter("week_start", "==", week_start_str))
                  .limit(1)
                  .stream())
        for doc in docs:
            d = doc.to_dict()
            return doc.id, d.get("plan_data", []), d.get("inventory", "")
    except Exception:
        pass
    return None, [], ""


def save_meal_plan(user_id: str, week_start: str, inventory: str, plan_data: list):
    db = _get_db()
    if db is None or not user_id: return
    db.collection("meal_plans").add({
        "user_id": user_id,
        "datestamp": fb_firestore.SERVER_TIMESTAMP,
        "week_start": week_start,
        "inventory": inventory,
        "plan_data": plan_data,
    })


def update_meal_plan_in_db(doc_id: str, new_plan_data: list):
    """Overwrite the plan_data array for an existing meal plan document."""
    db = _get_db()
    if db is None or not doc_id: return
    db.collection("meal_plans").document(doc_id).update({
        "plan_data": new_plan_data,
        "datestamp": fb_firestore.SERVER_TIMESTAMP, # Bumps modified time
    })


# ---------------------------------------------------------------------------
# Recipe local/cloud loading & filtering (unchanged)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_recipes_from_firestore() -> List[dict]:
    db = _get_db()
    if db is None: return []
    fields = ["uid", "name", "ingredients", "nutritional_info", "prep_time", "cook_time", "source_url"]
    docs = db.collection("recipes").select(fields).stream()
    recipes = []
    for doc in docs:
        r = doc.to_dict()
        if not r: continue
        recipes.append({
            "uid": r.get("uid", doc.id), "name": r.get("name", "Unknown"), 
            "ingredients": r.get("ingredients", ""), "nutrition_info": r.get("nutritional_info", ""),
            "prep_time": r.get("prep_time", ""), "cook_time": r.get("cook_time", ""),
            "source_url": r.get("source_url", ""), "_source": "firestore",
        })
    return recipes

@st.cache_data(show_spinner=False)
def get_recipe_image_from_firestore(uid: str) -> Optional[str]:
    db = _get_db()
    if db is None: return None
    try:
        doc = db.collection("recipes").document(uid).get(field_paths=["photo_data"])
        if doc.exists: return doc.to_dict().get("photo_data") or None
    except Exception: pass
    return None

@st.cache_data(show_spinner=False)
def load_recipes_from_local(data_dir: str = "Data") -> List[dict]:
    if not os.path.exists(data_dir): return []
    recipes = []
    for filename in os.listdir(data_dir):
        path = os.path.join(data_dir, filename)
        if not filename.endswith(".paprikarecipes"): continue
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".paprikarecipe"): continue
                try:
                    compressed_data = zf.read(name)
                    r = json.loads(gzip.decompress(compressed_data).decode("utf-8"))
                    recipes.append({
                        "uid": r.get("uid", name), "name": r.get("name", "Unknown"),
                        "ingredients": r.get("ingredients", ""), "nutrition_info": r.get("nutritional_info", ""),
                        "prep_time": r.get("prep_time", ""), "cook_time": r.get("cook_time", ""),
                        "source_url": r.get("source_url", ""), "archive_path": path, "inner_path": name, "_source": "local",
                    })
                except Exception: pass
    return recipes

def load_recipes() -> List[dict]:
    fr = load_recipes_from_firestore()
    if fr: return fr
    return load_recipes_from_local()

@st.cache_data(show_spinner=False)
def get_recipe_image(recipe_uid: str, archive_path: str = "", inner_path: str = "") -> Optional[str]:
    if not archive_path: return get_recipe_image_from_firestore(recipe_uid)
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            cd = zf.read(inner_path)
            return json.loads(gzip.decompress(cd).decode("utf-8")).get("photo_data") or None
    except Exception: pass
    return None

def filter_recipes(recipes: List[dict], available_ingredients: str, max_recipes: int = 150) -> List[dict]:
    if len(recipes) <= max_recipes: return recipes
    avail_words = set(re.findall(r'\w+', available_ingredients.lower()))
    scored = []
    for r in recipes:
        score = sum(1 for w in avail_words if len(w) > 3 and (w in r['ingredients'].lower() or w in r['name'].lower()))
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:max_recipes]]


# ---------------------------------------------------------------------------
# Sidebar Identity
# ---------------------------------------------------------------------------
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
    st.session_state.viewed_monday = get_target_week() # Reset to current week on change
    st.rerun()

# Ensure profile is fully loaded loaded
if not st.session_state.user_profile.get("liked") and not st.session_state.user_profile.get("disliked"):
    st.session_state.user_profile = get_user_profile(st.session_state.current_user)

prefs = st.session_state.user_profile.get("preferences", {})
meal_type     = prefs.get("meal_type", "Main Only")
calories_goal = prefs.get("calories_goal", 2000)
nutrition_info= prefs.get("nutrition_info", "")
pantry_staples_str = prefs.get("pantry_staples", 
    "olive oil, salt, black pepper, all-purpose flour, butter, garlic, onions, soy sauce, sugar, dried oregano, dried basil, cumin, water, vinegar, rice")
pantry_staples = [s.strip() for s in pantry_staples_str.split(",") if s.strip()]

st.sidebar.markdown("---")
st.sidebar.caption(f"**Meal structure:** {meal_type}")
st.sidebar.caption(f"**Calories/day:** {calories_goal} kcal")
if nutrition_info: st.sidebar.caption(f"**Constraints:** {nutrition_info}")

if not api_key or api_key == "YOUR_API_KEY_HERE":
    st.sidebar.error("⚠️ API Key not found in `.streamlit/secrets.toml`!")


# ---------------------------------------------------------------------------
# The Popup Planner Dialog
# ---------------------------------------------------------------------------
@st.dialog("🪄 Plan Menu for the Week")
def plan_week_dialog(monday_date_str: str, all_recipes: List[dict]):
    st.write(f"Generating a menu for the week starting **{monday_date_str}**.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_files = st.file_uploader("Upload Fridge Photos 📸", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    with col2:
        camera_photo = st.camera_input("Take a picture! 📱")

    all_photos = list(uploaded_files or [])
    if camera_photo: all_photos.append(camera_photo)

    if all_photos and not st.session_state.photos_analyzed:
        with st.spinner("🤖 Analyzing your groceries with Gemini Vision..."):
            try:
                images = [Image.open(f) for f in all_photos]
                prompt = ("Analyze these images. List all identifiable ingredients WITH approximate quantities. "
                          "Return ONLY a comma-separated list, e.g.: 2 apples, 1/2 gallon milk.")
                resp = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt] + images)
                st.session_state.parsed_ingredients = resp.text
                st.session_state.photos_analyzed = True
            except Exception as e:
                st.error(f"Vision parsing error: {e}")

    editable_ingredients = st.text_area("Edit your fresh ingredients (comma-separated):", 
                                        value=st.session_state.parsed_ingredients, height=100)
    
    if st.button("🚀 Generate Menu", use_container_width=True):
        st.session_state.parsed_ingredients = editable_ingredients
        with st.spinner("🧠 Designing menu..."):
            user_profile = st.session_state.user_profile
            disliked_uids = set(user_profile.get("disliked", []))
            liked_uids = user_profile.get("liked", [])

            filtered_library = [r for r in all_recipes if r["uid"] not in disliked_uids]
            
            inventory_payload = f"Fresh Ingredients: {editable_ingredients}\nAssumed staples: {', '.join(pantry_staples)}"
            filtered_recipes = filter_recipes(filtered_library, inventory_payload, max_recipes=150)
            slim_recipes = [{"uid": r["uid"], "name": r["name"], "prep_time": r["prep_time"]} for r in filtered_recipes]
            
            liked_names = [r["name"] for r in all_recipes if r["uid"] in liked_uids]
            liked_injection = f"\nThe user loves these: {', '.join(liked_names)}. Prioritize matching ingredients to these if possible." if liked_names else ""
            
            system_instruction = f'''You are an intelligent, agentic meal planner.
Inventory:
{inventory_payload}
{liked_injection}

Constraints:
- Structure: {meal_type}
- Target: {calories_goal} kcal
- Other criteria: {nutrition_info}

Task: Output a 5-day weekday meal plan (Monday to Friday). Focus on the inventory but include meats/other ingredients.
Output STRICT valid JSON ONLY. Format:
[ {{"day": "Monday", "recipe_uid": "UID", "reasoning": "Brief reason"}}, ... ]'''

            try:
                response = client.models.generate_content(model="gemini-2.5-pro", contents=[system_instruction, "Recipes:\n" + json.dumps(slim_recipes)])
                raw_text = response.text.strip()
                if raw_text.startswith("```json"): raw_text = raw_text[7:-3]
                elif raw_text.startswith("```"): raw_text = raw_text[3:-3]
                
                new_plan = json.loads(raw_text.strip())
                # Save to DB
                save_meal_plan(
                    user_id=st.session_state.current_user,
                    week_start=monday_date_str,
                    inventory=inventory_payload,
                    plan_data=new_plan
                )
                
                # Cleanup state so next time dialog opens it's fresh
                st.session_state.parsed_ingredients = ""
                st.session_state.photos_analyzed = False
                st.rerun() # Closes modal
            except Exception as e:
                st.error(f"Generation error: {e}")


# ---------------------------------------------------------------------------
# Recipe card renderer
# ---------------------------------------------------------------------------
def render_recipe_card(recipe: dict, reason: str, idx: int, 
                       plan_doc_id: str, full_plan_data: list,
                       inventory_snapshot: str,
                       all_recipes: List[dict],
                       base_date_str: str):
    
    uid = recipe.get("uid", "")
    day_name = recipe.get("_day", "Unknown")
    
    with st.container(border=True):
        col_img, col_info = st.columns([1, 4])
        
        with col_img:
            b64_image = get_recipe_image(recipe_uid=uid, archive_path=recipe.get("archive_path", ""), inner_path=recipe.get("inner_path", ""))
            if b64_image: st.image(base64.b64decode(b64_image), width="stretch")
            else: st.caption("No photo")

        with col_info:
            if recipe.get("source_url"): st.markdown(f"### [{recipe['name']}]({recipe['source_url']})")
            else: st.subheader(recipe["name"])
            st.caption(f"⏱️ Prep: {recipe.get('prep_time','N/A')}m | Cook: {recipe.get('cook_time','N/A')}m")
            if reason: st.write(f"**Why this?** {reason}")

            # Rating buttons
            profile = st.session_state.user_profile
            is_liked = uid in profile.get("liked", [])
            is_disliked = uid in profile.get("disliked", [])
            user_id = st.session_state.current_user
            
            rcol1, rcol2, _ = st.columns([1, 1, 8])
            with rcol1:
                liked_label = "✅" if is_liked else "👍"
                if st.button(liked_label, key=f"lk_{uid}_{idx}_{plan_doc_id}"):
                    update_recipe_rating(user_id, uid, "remove_like" if is_liked else "like")
                    st.rerun()
            with rcol2:
                disliked_label = "❌" if is_disliked else "👎"
                if st.button(disliked_label, key=f"dk_{uid}_{idx}_{plan_doc_id}"):
                    update_recipe_rating(user_id, uid, "remove_dislike" if is_disliked else "dislike")
                    st.rerun()

            # Date check for replacement allowance
            # Monday = index 0. So day_offset = idx (assuming 5 days M-F are idx 0-4)
            meal_date = datetime.strptime(base_date_str, "%Y-%m-%d") + timedelta(days=idx)
            today_date = datetime.now().date()
            is_past_meal = meal_date.date() < today_date
            
            if not is_past_meal and client:
                with st.expander("🔀 Replace this meal..."):
                    guidance = st.text_input("Constraints (e.g., 'Make it vegetarian'):", key=f"gd_{uid}_{idx}_{plan_doc_id}")
                    if st.button("Generate Alternative", key=f"rp_{uid}_{idx}_{plan_doc_id}"):
                        with st.spinner("Finding remote alternative..."):
                            disliked_uids = set(profile.get("disliked", []))
                            scheduled_uids = [p.get("recipe_uid", "") for p in full_plan_data]
                            excluded = set(scheduled_uids) | disliked_uids
                            
                            filtered = filter_recipes(all_recipes, inventory_snapshot, 150)
                            slim = [{"uid": r["uid"], "name": r["name"]} for r in filtered if r["uid"] not in excluded]
                            
                            prompt = (f"The user rejected '{recipe['name']}' for {day_name}.\n"
                                      f"Inventory: {inventory_snapshot}\nConstraints: {guidance}\n"
                                      f"EXCLUDE these UIDs: {', '.join(f'{u}' for u in excluded)}\n"
                                      f"Return ONLY one JSON object: {{\"day\": \"{day_name}\", \"recipe_uid\": \"...\", \"reasoning\": \"...\"}}")
                            try:
                                resp = client.models.generate_content(model="gemini-2.5-pro", contents=[prompt, json.dumps(slim)])
                                r_text = resp.text.strip()
                                if r_text.startswith("```json"): r_text = r_text[7:-3]
                                elif r_text.startswith("```"): r_text = r_text[3:-3]
                                
                                new_meal_node = json.loads(r_text.strip())
                                # Immediate Database update
                                full_plan_data[idx] = new_meal_node
                                update_meal_plan_in_db(plan_doc_id, full_plan_data)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to find alternative: {e}")
            elif is_past_meal:
                st.caption("*(Meals in the past cannot be replaced)*")


# ============================================================
# MAIN UI
# ============================================================
st.title("✨ Intelligent Agentic Meal Planner")

if not client:
    st.warning("🔒 Please configure your Gemini API key in `.streamlit/secrets.toml`.")
    st.stop()

tab_recipes, tab_profile = st.tabs(["🍽️ Recipes", "👤 Profile"])

# ----------------------------------------------------------
# TAB 1 — RECIPES CAROUSEL
# ----------------------------------------------------------
with tab_recipes:
    # Carousel Navigation
    viewed_monday = st.session_state.viewed_monday
    vm_dt = datetime.strptime(viewed_monday, "%Y-%m-%d")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.markdown("<div class='carousel-btn'>", unsafe_allow_html=True)
        if st.button("◀ Previous Week", use_container_width=True):
            st.session_state.viewed_monday = shift_week(viewed_monday, -1)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<h3 style='text-align:center;'>Week of {vm_dt.strftime('%d %B %Y')}</h3>", unsafe_allow_html=True)
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
        # Render the weekly plan
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
                    all_recipes=all_recipes, base_date_str=viewed_monday
                )
            else:
                with st.container(border=True):
                    st.error(f"Recipe UID `{uid}` not found in library.")
    else:
        # Empty State
        st.info("No menu planned for this week.")
        if st.button("🪄 Plan This Week", type="primary"):
            plan_week_dialog(viewed_monday, all_recipes)

# ----------------------------------------------------------
# TAB 2 — PROFILE
# ----------------------------------------------------------
with tab_profile:
    st.markdown("### 👤 Your Profile")

    st.markdown("#### 🎛️ Dietary Preferences")
    st.caption("These are saved to your profile and used to drive new plan generation.")

    p_col1, p_col2 = st.columns(2)
    with p_col1:
        pref_meal_type = st.radio("Meal Structure", ["Main Only", "Main + Starter/Dessert"],
                                  index=0 if meal_type == "Main Only" else 1)
        pref_calories = st.slider("Calories/day target", 1500, 3500, calories_goal, 100)
    with p_col2:
        pref_nutrition = st.text_area("Other Nutritional Constraints", value=nutrition_info)
        pref_staples = st.text_area("Pantry Staples", value=pantry_staples_str, height=120)

    if st.button("💾 Save Preferences"):
        new_prefs = {
            "meal_type": pref_meal_type, "calories_goal": pref_calories,
            "nutrition_info": pref_nutrition, "pantry_staples": pref_staples,
        }
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

