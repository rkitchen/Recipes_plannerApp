import streamlit as st
import os
import zipfile
import gzip
import json
import re
import base64
import datetime
from PIL import Image
try:
    from io import BytesIO
except ImportError:
    pass
from google import genai
from google.genai import types
from typing import Optional, List

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
# Password Gate — must run before ANYTHING else in the script
# ---------------------------------------------------------------------------
def _check_password() -> bool:
    """Returns True only if the user has already authenticated this session."""
    if st.session_state.get("authenticated", False):
        return True

    try:
        app_password = st.secrets["APP_PASSWORD"]
    except (KeyError, Exception):
        return True  # No password configured — open access

    st.markdown(
        "<h2 style='text-align:center; margin-top: 20vh;'>🍽️ Meal Planner</h2>"
        "<p style='text-align:center; color:#64748b;'>Enter the access password to continue.</p>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 1, 1])
    with col:
        entered = st.text_input("Password", type="password", label_visibility="collapsed",
                                placeholder="Enter password…")
        if st.button("Unlock →", width="stretch"):
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
</style>
''', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Defaults
# ---------------------------------------------------------------------------
for key, default in [
    ("step", 1),
    ("parsed_ingredients", ""),
    ("meal_plan", []),
    ("photos_analyzed", False),
    ("current_user", None),
    ("user_profile", {"liked": [], "disliked": [], "preferences": {}}),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Firestore client (singleton)
# ---------------------------------------------------------------------------
def _get_db():
    """Returns a Firestore client or None if Firebase is unavailable."""
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
# User profile helpers
# ---------------------------------------------------------------------------
def get_user_profile(user_id: str) -> dict:
    """Fetch user doc (liked/disliked/preferences). Never cached — must be live."""
    db = _get_db()
    empty = {"liked": [], "disliked": [], "preferences": {}}
    if db is None or not user_id:
        return empty
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            d = doc.to_dict()
            return {
                "liked":       d.get("liked_recipes", []),
                "disliked":    d.get("disliked_recipes", []),
                "preferences": d.get("preferences", {}),
            }
        return empty
    except Exception:
        return empty


def save_user_preferences(user_id: str, prefs: dict):
    """Write the preferences sub-dict to the user's Firestore doc."""
    db = _get_db()
    if db is None or not user_id:
        return
    try:
        db.collection("users").document(user_id).set({"preferences": prefs}, merge=True)
    except Exception as e:
        st.error(f"Could not save preferences: {e}")


def update_recipe_rating(user_id: str, recipe_uid: str, rating_type: str):
    """
    Toggle a recipe rating for a user.
    rating_type: 'like' | 'dislike' | 'remove_like' | 'remove_dislike'
    """
    db = _get_db()
    if db is None:
        st.error("Cannot rate: Firestore unavailable.")
        return
    if not user_id:
        st.error("Cannot rate: no user selected.")
        return
    try:
        ref = db.collection("users").document(user_id)
        ArrayUnion  = fb_firestore.ArrayUnion
        ArrayRemove = fb_firestore.ArrayRemove
        if rating_type == "like":
            ref.set({"liked_recipes":    ArrayUnion([recipe_uid]),
                     "disliked_recipes": ArrayRemove([recipe_uid])}, merge=True)
        elif rating_type == "dislike":
            ref.set({"disliked_recipes": ArrayUnion([recipe_uid]),
                     "liked_recipes":    ArrayRemove([recipe_uid])}, merge=True)
        elif rating_type == "remove_like":
            ref.set({"liked_recipes": ArrayRemove([recipe_uid])}, merge=True)
        elif rating_type == "remove_dislike":
            ref.set({"disliked_recipes": ArrayRemove([recipe_uid])}, merge=True)
        # Refresh session state
        st.session_state.user_profile = get_user_profile(user_id)
    except Exception as e:
        st.error(f"Rating update failed: {e}")


# ---------------------------------------------------------------------------
# Meal plan persistence
# ---------------------------------------------------------------------------
def save_meal_plan(user_id: str, plan_data: list):
    """Write a new meal plan document to Firestore."""
    db = _get_db()
    if db is None or not user_id:
        return
    try:
        db.collection("meal_plans").add({
            "user_id":   user_id,
            "datestamp": fb_firestore.SERVER_TIMESTAMP,
            "plan_data": plan_data,
        })
    except Exception as e:
        st.warning(f"Could not save meal plan to history: {e}")


def get_meal_plan_history(user_id: str, limit: int = 8) -> list:
    """Query meal_plans for this user, ordered newest first."""
    db = _get_db()
    if db is None or not user_id:
        return []
    try:
        docs = (db.collection("meal_plans")
                  .where("user_id", "==", user_id)
                  .order_by("datestamp", direction="DESCENDING")
                  .limit(limit)
                  .stream())
        return [d.to_dict() for d in docs if d.to_dict()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Recipe loading: Firestore (primary) → local .paprikarecipes (fallback)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_recipes_from_firestore() -> List[dict]:
    db = _get_db()
    if db is None:
        return []
    fields = ["uid", "name", "ingredients", "nutritional_info",
              "prep_time", "cook_time", "source_url"]
    docs = db.collection("recipes").select(fields).stream()
    recipes = []
    for doc in docs:
        r = doc.to_dict()
        if not r:
            continue
        recipes.append({
            "uid":           r.get("uid", doc.id),
            "name":          r.get("name", "Unknown"),
            "ingredients":   r.get("ingredients", ""),
            "nutrition_info": r.get("nutritional_info", ""),
            "prep_time":     r.get("prep_time", ""),
            "cook_time":     r.get("cook_time", ""),
            "source_url":    r.get("source_url", ""),
            "_source":       "firestore",
        })
    return recipes


@st.cache_data(show_spinner=False)
def get_recipe_image_from_firestore(uid: str) -> Optional[str]:
    db = _get_db()
    if db is None:
        return None
    try:
        doc = db.collection("recipes").document(uid).get(field_paths=["photo_data"])
        if doc.exists:
            return doc.to_dict().get("photo_data") or None
    except Exception:
        pass
    return None


@st.cache_data(show_spinner=False)
def load_recipes_from_local(data_dir: str = "Data") -> List[dict]:
    if not os.path.exists(data_dir):
        return []
    recipes = []
    for filename in os.listdir(data_dir):
        path = os.path.join(data_dir, filename)
        if not filename.endswith(".paprikarecipes"):
            continue
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".paprikarecipe"):
                    continue
                try:
                    compressed_data = zf.read(name)
                    recipe = json.loads(gzip.decompress(compressed_data).decode("utf-8"))
                    recipes.append({
                        "uid":          recipe.get("uid", name),
                        "name":         recipe.get("name", "Unknown"),
                        "ingredients":  recipe.get("ingredients", ""),
                        "nutrition_info": recipe.get("nutritional_info", ""),
                        "prep_time":    recipe.get("prep_time", ""),
                        "cook_time":    recipe.get("cook_time", ""),
                        "source_url":   recipe.get("source_url", ""),
                        "archive_path": path,
                        "inner_path":   name,
                        "_source":      "local",
                    })
                except Exception:
                    pass
    return recipes


def load_recipes() -> List[dict]:
    firestore_recipes = load_recipes_from_firestore()
    if firestore_recipes:
        return firestore_recipes
    return load_recipes_from_local()


@st.cache_data(show_spinner=False)
def get_recipe_image(recipe_uid: str, archive_path: str = "",
                     inner_path: str = "") -> Optional[str]:
    if not archive_path:
        return get_recipe_image_from_firestore(recipe_uid)
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            compressed_data = zf.read(inner_path)
            recipe = json.loads(gzip.decompress(compressed_data).decode("utf-8"))
            return recipe.get("photo_data") or None
    except Exception:
        pass
    return None


def filter_recipes(recipes: List[dict], available_ingredients: str,
                   max_recipes: int = 150) -> List[dict]:
    if len(recipes) <= max_recipes:
        return recipes
    avail_words = set(re.findall(r'\w+', available_ingredients.lower()))
    scored = []
    for r in recipes:
        score = sum(1 for w in avail_words
                    if len(w) > 3 and (w in r['ingredients'].lower() or w in r['name'].lower()))
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:max_recipes]]


# ---------------------------------------------------------------------------
# Shared UI component: recipe card with rating buttons
# ---------------------------------------------------------------------------
def render_recipe_card(recipe: dict, reason: str, idx: int, card_key_prefix: str,
                       show_replace: bool = True, all_recipes: Optional[List[dict]] = None,
                       client=None, pantry_staples: Optional[List[str]] = None,
                       meal_type: str = "Main Only", calories_goal: int = 2000,
                       nutrition_info: str = ""):
    """Render a recipe card with image, title, rating buttons, and optional replacer."""
    user_id = st.session_state.get("current_user", "")
    profile = st.session_state.get("user_profile", {"liked": [], "disliked": []})
    liked_uids    = profile.get("liked", [])
    disliked_uids = profile.get("disliked", [])

    uid = recipe.get("uid", "")

    with st.container(border=True):
        col_img, col_info = st.columns([1, 4])

        with col_img:
            b64_image = get_recipe_image(
                recipe_uid=uid,
                archive_path=recipe.get("archive_path", ""),
                inner_path=recipe.get("inner_path", ""),
            )
            if b64_image:
                st.image(base64.b64decode(b64_image), width="stretch")
            else:
                st.caption("No photo")

        with col_info:
            # Title
            if recipe.get("source_url"):
                st.markdown(f"### [{recipe['name']}]({recipe['source_url']})")
            else:
                st.subheader(recipe["name"])

            st.caption(f"⏱️ Prep: {recipe.get('prep_time','N/A')}m | Cook: {recipe.get('cook_time','N/A')}m")
            if reason:
                st.write(f"**Why this?** {reason}")

            # Rating buttons
            is_liked    = uid in liked_uids
            is_disliked = uid in disliked_uids
            r_col1, r_col2, r_col3 = st.columns([1, 1, 8])
            with r_col1:
                liked_label = "✅" if is_liked else "👍"
                if st.button(liked_label, key=f"{card_key_prefix}_like_{uid}_{idx}",
                             help="Like this recipe"):
                    action = "remove_like" if is_liked else "like"
                    update_recipe_rating(user_id, uid, action)
                    st.rerun()
            with r_col2:
                disliked_label = "❌" if is_disliked else "👎"
                if st.button(disliked_label, key=f"{card_key_prefix}_dislike_{uid}_{idx}",
                             help="Dislike this recipe"):
                    action = "remove_dislike" if is_disliked else "dislike"
                    update_recipe_rating(user_id, uid, action)
                    st.rerun()

            # Replacer (only on active plan)
            if show_replace and all_recipes and client:
                with st.expander("🔀 Replace this meal..."):
                    guidance = st.text_input(
                        "Guidance (e.g., 'Make it vegetarian'):",
                        key=f"{card_key_prefix}_guidance_{uid}_{idx}")
                    if st.button("Generate Alternative",
                                 key=f"{card_key_prefix}_replace_{uid}_{idx}"):
                        with st.spinner("Finding an alternative..."):
                            inventory = (f"Fresh: {st.session_state.parsed_ingredients}\n"
                                         f"Staples: {', '.join(pantry_staples or [])}")
                            filtered = filter_recipes(all_recipes, inventory, max_recipes=150)
                            # Exclude the entire current week + disliked
                            scheduled_uids = [p.get("recipe_uid", "")
                                              for p in st.session_state.meal_plan]
                            excluded = set(scheduled_uids) | set(disliked_uids)
                            excluded_str = ", ".join(f"'{u}'" for u in excluded)
                            slim = [{"uid": r["uid"], "name": r["name"]}
                                    for r in filtered if r["uid"] not in excluded]
                            replace_prompt = (
                                f"The user rejected '{recipe['name']}' for this meal slot.\n"
                                f"Inventory: {inventory}. Constraints: {guidance}.\n"
                                f"EXCLUDE ALL of these UIDs: {excluded_str}.\n"
                                f"Return ONLY one JSON object: "
                                f'{{ "day": "{recipe.get("_day","")}", '
                                f'"recipe_uid": "...", "reasoning": "..." }}'
                            )
                            try:
                                resp = client.models.generate_content(
                                    model="gemini-2.5-pro",
                                    contents=[replace_prompt, json.dumps(slim)]
                                )
                                r_text = resp.text.strip()
                                if r_text.startswith("```json"):
                                    r_text = r_text[7:-3]
                                elif r_text.startswith("```"):
                                    r_text = r_text[3:-3]
                                new_plan = json.loads(r_text.strip())
                                st.session_state.meal_plan[idx] = new_plan
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to find alternative: {e}")


# ---------------------------------------------------------------------------
# API setup
# ---------------------------------------------------------------------------
api_key = ""
try:
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
except Exception:
    api_key = os.environ.get("GEMINI_API_KEY", "")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("⚙️ Settings")

# --- User selector (from secrets.toml [users] table) ---
try:
    # secrets.toml format: user_id = "Display Name"
    # e.g.  user_becky = "Becky"
    id_to_name = dict(st.secrets["users"])
    name_to_id = {v: k for k, v in id_to_name.items()}
except Exception:
    name_to_id = {"Default": "user_default"}

selected_name = st.sidebar.selectbox("👤 User", list(name_to_id.keys()))
new_user_id   = name_to_id[selected_name]

# Switch user — reset plan and reload profile
if st.session_state.current_user != new_user_id:
    st.session_state.current_user    = new_user_id
    st.session_state.step            = 1
    st.session_state.meal_plan       = []
    st.session_state.parsed_ingredients = ""
    st.session_state.photos_analyzed = False
    st.session_state.user_profile    = get_user_profile(new_user_id)
    st.rerun()

# Ensure profile is loaded (first run after auth)
if not st.session_state.user_profile.get("liked") and not st.session_state.user_profile.get("disliked"):
    profile_check = get_user_profile(st.session_state.current_user)
    if profile_check != st.session_state.user_profile:
        st.session_state.user_profile = profile_check

# Sidebar shows persisted preferences (read-only — editing in Profile tab)
prefs = st.session_state.user_profile.get("preferences", {})
meal_type     = prefs.get("meal_type", "Main Only")
calories_goal = prefs.get("calories_goal", 2000)
nutrition_info = prefs.get("nutrition_info", "")
pantry_staples_str = prefs.get("pantry_staples",
    "olive oil, salt, black pepper, all-purpose flour, butter, garlic, onions, "
    "soy sauce, sugar, dried oregano, dried basil, cumin, water, vinegar, rice")
pantry_staples = [s.strip() for s in pantry_staples_str.split(",") if s.strip()]

st.sidebar.markdown("---")
st.sidebar.caption(f"**Meal structure:** {meal_type}")
st.sidebar.caption(f"**Calories/day:** {calories_goal} kcal")
if nutrition_info:
    st.sidebar.caption(f"**Constraints:** {nutrition_info}")

if st.sidebar.button("🔄 Start New Plan"):
    st.session_state.step = 1
    st.session_state.meal_plan = []
    st.session_state.parsed_ingredients = ""
    st.session_state.photos_analyzed = False
    st.rerun()

st.sidebar.markdown("---")

if not api_key or api_key == "YOUR_API_KEY_HERE":
    st.sidebar.error("⚠️ API Key not found in `.streamlit/secrets.toml`!")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
st.title("✨ Intelligent Agentic Meal Planner")

if not api_key or api_key == "YOUR_API_KEY_HERE":
    st.warning("🔒 Please configure your Gemini API key in `.streamlit/secrets.toml`.")
    st.stop()

try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to load API client: {e}")
    st.stop()


# ============================================================
# STEP 1 — Inventory & photo parsing
# ============================================================
if st.session_state.step == 1:
    st.markdown("### Step 1: Tell us what you have!")

    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_files = st.file_uploader(
            "Upload Fridge/Pantry Photos 📸", type=["jpg", "jpeg", "png"],
            accept_multiple_files=True)
    with col2:
        camera_photo = st.camera_input("Or take a picture of your fridge! 📱")

    all_photos = list(uploaded_files or [])
    if camera_photo:
        all_photos.append(camera_photo)

    if all_photos:
        st.success(f"📸 {len(all_photos)} photo(s) provided!")
        img_cols = st.columns(min(len(all_photos), 4))
        for i, f in enumerate(all_photos[:4]):
            with img_cols[i]:
                st.image(f, width="stretch")

    if all_photos and not st.session_state.photos_analyzed:
        with st.spinner("🤖 Analyzing your groceries with Gemini Vision..."):
            try:
                images  = [Image.open(f) for f in all_photos]
                prompt  = ("Analyze these images of a fridge, pantry, or groceries. "
                           "List all identifiable ingredients WITH approximate quantities. "
                           "Return ONLY a comma-separated list, e.g.: 2 apples, 1/2 gallon milk.")
                resp    = client.models.generate_content(
                    model="gemini-2.5-flash", contents=[prompt] + images)
                st.session_state.parsed_ingredients = resp.text
                st.session_state.photos_analyzed    = True
                st.rerun()
            except Exception as e:
                st.error(f"Vision parsing error: {e}")

    st.markdown("---")
    st.markdown("### Active Inventory")
    editable_ingredients = st.text_area(
        "Edit your available fresh ingredients here (comma-separated):",
        value=st.session_state.parsed_ingredients, height=100)
    st.caption("Pantry staples (set in Profile) are automatically included.")

    if st.button("🚀 Generate Meal Plan!"):
        st.session_state.parsed_ingredients = editable_ingredients

        with st.spinner("🧠 Planning your perfect week..."):
            all_recipes = load_recipes()
            if not all_recipes:
                st.error("No recipes found!")
                st.stop()

            user_profile   = st.session_state.user_profile
            disliked_uids  = set(user_profile.get("disliked", []))
            liked_uids     = user_profile.get("liked", [])

            # Hard filter: remove disliked recipes entirely
            filtered_library = [r for r in all_recipes if r["uid"] not in disliked_uids]

            inventory = (f"Fresh Ingredients: {st.session_state.parsed_ingredients}\n"
                         f"Assumed staples: {', '.join(pantry_staples)}")
            filtered_recipes = filter_recipes(filtered_library, inventory, max_recipes=150)
            slim_recipes     = [{"uid": r["uid"], "name": r["name"],
                                  "prep_time": r["prep_time"]} for r in filtered_recipes]
            recipes_json     = json.dumps(slim_recipes)

            # Liked recipes prompt injection
            liked_names = [r["name"] for r in all_recipes if r["uid"] in liked_uids]
            liked_injection = ""
            if liked_names:
                names_str = ", ".join(liked_names)
                liked_injection = (
                    f"\nThe user explicitly loves these recipes: {names_str}. "
                    "Strongly prioritise matching current ingredients to at least one of these favourites."
                )

            system_instruction = f'''You are an intelligent, agentic meal planner.
You have access to the user's available inventory of seasonal vegetables from a weekly delivery:
{inventory}
{liked_injection}

Constraints:
- Meal Structure: {meal_type}
- Caloric Goal: {calories_goal} kcal
- Other Nutrition constraints: {nutrition_info}

Your task:
- Output a 5-day weekday meal plan (Monday to Friday).
- Prioritise recipes that use the vegetables in the inventory, but also suggest recipes using meats and other ingredients.
- You MUST output STRICT valid JSON and NOTHING ELSE. No markdown code blocks.

Format:
[
  {{"day": "Monday", "recipe_uid": "UID", "reasoning": "Brief reason"}},
  ...
]

Only pick valid UIDs from the provided list.'''

            try:
                response  = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=[system_instruction, "Recipes:\n" + recipes_json])
                raw_text  = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:-3]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:-3]
                st.session_state.meal_plan = json.loads(raw_text.strip())
                st.session_state.step      = 2
                # Save to Firestore history
                save_meal_plan(st.session_state.current_user, st.session_state.meal_plan)
                st.rerun()
            except Exception as e:
                st.error(f"Generation error: {e}")


# ============================================================
# STEP 2 — Three-tab view: This Week / History / Profile
# ============================================================
elif st.session_state.step == 2:

    all_recipes  = load_recipes()
    recipe_dict  = {r["uid"]: r for r in all_recipes}

    tab_plan, tab_history, tab_profile = st.tabs(["📅 This Week", "🕐 History", "👤 Profile"])

    # ----------------------------------------------------------
    # TAB 1 — This Week
    # ----------------------------------------------------------
    with tab_plan:
        st.markdown("### 📅 Your Weekly Meal Plan")
        st.markdown("Rate recipes to personalise future plans, or ask the agent to swap a day.")

        for idx, day_plan in enumerate(st.session_state.meal_plan):
            day    = day_plan.get("day", "Unknown Day")
            uid    = day_plan.get("recipe_uid", "")
            reason = day_plan.get("reasoning", "")
            recipe = recipe_dict.get(uid)

            st.markdown(f"#### **{day}**")
            if recipe:
                recipe["_day"] = day  # pass day context into replacer
                render_recipe_card(
                    recipe=recipe, reason=reason, idx=idx,
                    card_key_prefix="plan",
                    show_replace=True,
                    all_recipes=all_recipes,
                    client=client,
                    pantry_staples=pantry_staples,
                    meal_type=meal_type,
                    calories_goal=calories_goal,
                    nutrition_info=nutrition_info,
                )
            else:
                with st.container(border=True):
                    st.error(f"Recipe UID `{uid}` not found in library.")

    # ----------------------------------------------------------
    # TAB 2 — History
    # ----------------------------------------------------------
    with tab_history:
        st.markdown("### 🕐 Past Meal Plans")
        history = get_meal_plan_history(st.session_state.current_user)
        if not history:
            st.info("No past plans yet — generate one first!")
        else:
            for plan_doc in history:
                datestamp = plan_doc.get("datestamp")
                date_str  = datestamp.strftime("%A %d %B %Y") if hasattr(datestamp, "strftime") else "Previous plan"
                with st.expander(f"📆 {date_str}"):
                    plan_data = plan_doc.get("plan_data", [])
                    for hidx, day_plan in enumerate(plan_data):
                        day    = day_plan.get("day", "Unknown Day")
                        uid    = day_plan.get("recipe_uid", "")
                        reason = day_plan.get("reasoning", "")
                        recipe = recipe_dict.get(uid)
                        st.markdown(f"**{day}**")
                        if recipe:
                            render_recipe_card(
                                recipe=recipe, reason=reason, idx=hidx,
                                card_key_prefix=f"hist_{date_str}",
                                show_replace=False,
                            )
                        else:
                            st.caption(f"Recipe `{uid}` no longer in library.")

    # ----------------------------------------------------------
    # TAB 3 — Profile
    # ----------------------------------------------------------
    with tab_profile:
        current_user = st.session_state.current_user
        st.markdown("### 👤 Your Profile")

        # ---- Dietary preferences ----
        st.markdown("#### 🎛️ Dietary Preferences")
        st.caption("These are saved to your profile and used when generating meal plans.")

        p_col1, p_col2 = st.columns(2)
        with p_col1:
            pref_meal_type = st.radio(
                "Meal Structure",
                ["Main Only", "Main + Starter/Dessert"],
                index=0 if meal_type == "Main Only" else 1,
                key="pref_meal_type")
            pref_calories = st.slider(
                "Calories/day target", 1500, 3500, calories_goal, 100,
                key="pref_calories")
        with p_col2:
            pref_nutrition = st.text_area(
                "Other Nutritional Constraints",
                placeholder="e.g., High protein, low carb",
                value=nutrition_info,
                key="pref_nutrition")
            pref_staples = st.text_area(
                "Pantry Staples",
                value=pantry_staples_str,
                height=120,
                key="pref_staples")

        if st.button("💾 Save Preferences"):
            new_prefs = {
                "meal_type":     pref_meal_type,
                "calories_goal": pref_calories,
                "nutrition_info": pref_nutrition,
                "pantry_staples": pref_staples,
            }
            save_user_preferences(current_user, new_prefs)
            st.session_state.user_profile["preferences"] = new_prefs
            st.success("✅ Preferences saved!")
            st.rerun()

        st.markdown("---")

        # ---- Liked / Disliked ----
        st.markdown("#### ⭐ Recipe Ratings")
        profile = st.session_state.user_profile
        liked_uids    = profile.get("liked", [])
        disliked_uids = profile.get("disliked", [])

        # Map UIDs → names, sort alphabetically
        def uid_to_name(uid):
            r = recipe_dict.get(uid)
            return r["name"] if r else uid

        liked_sorted    = sorted(liked_uids,    key=uid_to_name)
        disliked_sorted = sorted(disliked_uids, key=uid_to_name)

        r_col_liked, r_col_disliked = st.columns(2)

        with r_col_liked:
            st.markdown("**👍 Liked Recipes**")
            if not liked_sorted:
                st.caption("None yet")
            for luid in liked_sorted:
                name = uid_to_name(luid)
                lc1, lc2 = st.columns([5, 1])
                with lc1:
                    r = recipe_dict.get(luid)
                    if r and r.get("source_url"):
                        st.markdown(f"[{name}]({r['source_url']})")
                    else:
                        st.write(name)
                with lc2:
                    if st.button("✕", key=f"rm_like_{luid}", help="Remove from liked"):
                        update_recipe_rating(current_user, luid, "remove_like")
                        st.rerun()

        with r_col_disliked:
            st.markdown("**👎 Disliked Recipes**")
            if not disliked_sorted:
                st.caption("None yet")
            for duid in disliked_sorted:
                name = uid_to_name(duid)
                dc1, dc2 = st.columns([5, 1])
                with dc1:
                    r = recipe_dict.get(duid)
                    if r and r.get("source_url"):
                        st.markdown(f"[{name}]({r['source_url']})")
                    else:
                        st.write(name)
                with dc2:
                    if st.button("✕", key=f"rm_dislike_{duid}", help="Remove from disliked"):
                        update_recipe_rating(current_user, duid, "remove_dislike")
                        st.rerun()
