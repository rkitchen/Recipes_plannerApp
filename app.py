import streamlit as st
import os
import zipfile
import gzip
import json
import re
import base64
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

# Apply premium CSS styles for a WOW experience
st.markdown('''
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

html, body, [class*="css"]  {
    font-family: 'Outfit', sans-serif;
    color: #1e293b;
}

[data-testid="stSidebar"] {
    background: #f8fafc !important;
    border-right: 1px solid #e2e8f0;
}

.stApp {
    background: #ffffff;
}

h1, h2, h3 {
    background: linear-gradient(135deg, #f43f5e, #f97316);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800 !important;
}

div[data-baseweb="file-uploader"] {
    background: #f8fafc !important;
    border: 1px dashed #cbd5e1 !important;
    border-radius: 16px !important;
    padding: 10px;
    transition: all 0.3s ease;
}
div[data-baseweb="file-uploader"]:hover {
    border: 1px dashed #f43f5e !important;
    background: #fff1f2 !important;
}

.stButton > button {
    background: linear-gradient(135deg, #f43f5e 0%, #f97316 100%);
    border: none;
    border-radius: 12px;
    color: #ffffff !important;
    padding: 0.75rem 1.5rem;
    font-size: 1.1rem;
    font-weight: 600;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 15px rgba(244, 63, 94, 0.3);
    width: 100%;
}

.stButton > button:hover {
    transform: translateY(-2px) scale(1.02);
    box-shadow: 0 8px 25px rgba(244, 63, 94, 0.4);
}

.stButton > button:active {
    transform: translateY(1px);
}

.stMarkdownContainer {
    background: #ffffff;
    padding: 1.5rem;
    border-radius: 16px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.recipe-card {
    background: #f8fafc;
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid #e2e8f0;
    margin-bottom: 1rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}
</style>
''', unsafe_allow_html=True)

# --- State Management ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'parsed_ingredients' not in st.session_state:
    st.session_state.parsed_ingredients = ""
if 'meal_plan' not in st.session_state:
    st.session_state.meal_plan = []
if 'photos_analyzed' not in st.session_state:
    st.session_state.photos_analyzed = False

# ---------------------------------------------------------------------------
# Firestore client (singleton via firebase-admin)
# ---------------------------------------------------------------------------
def _get_firestore_client():
    """Initialise Firebase app once and return a Firestore client.
    Reads credentials from st.secrets['firebase'] (a TOML table).
    """
    if not FIREBASE_AVAILABLE:
        return None
    try:
        sa_info = dict(st.secrets["firebase"])  # TOML table → dict
        if not firebase_admin._apps:
            cred = credentials.Certificate(sa_info)
            firebase_admin.initialize_app(cred)
        return fb_firestore.client()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Recipe loading: Firestore (primary) → local .paprikarecipes (fallback)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_recipes_from_firestore() -> List[dict]:
    """Pull recipe metadata from Firestore — photo_data intentionally excluded.
    Uses a field mask (.select) so only lightweight fields are transferred.
    Cached for 1 hour to avoid repeated reads on every UI interaction.
    """
    db = _get_firestore_client()
    if db is None:
        return []

    # Field mask: only the fields the app actually uses
    fields = ["uid", "name", "ingredients",
              "nutritional_info", "prep_time", "cook_time", "source_url"]
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
            # photo_data is NOT included here — fetched lazily per recipe
            "_source":       "firestore",
        })
    return recipes


@st.cache_data(show_spinner=False)
def get_recipe_image_from_firestore(uid: str) -> Optional[str]:
    """Fetch ONLY the photo_data field for a single recipe document.
    Cached indefinitely (images don't change) to avoid repeat reads.
    """
    db = _get_firestore_client()
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
    """Fallback: parse local .paprikarecipes archives.
    photo_data is intentionally excluded here to save RAM; images are
    fetched lazily by get_recipe_image().
    """
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
                        "photo_data":   "",   # loaded lazily via get_recipe_image
                        "archive_path": path,
                        "inner_path":   name,
                        "_source":      "local",
                    })
                except Exception:
                    pass
    return recipes


def load_recipes() -> List[dict]:
    """Auto-selects Firestore if credentials exist, else falls back to local files."""
    firestore_recipes = load_recipes_from_firestore()
    if firestore_recipes:
        return firestore_recipes
    return load_recipes_from_local()


@st.cache_data(show_spinner=False)
def get_recipe_image(recipe_uid: str, archive_path: str = "",
                     inner_path: str = "") -> Optional[str]:
    """Returns a base64 image string for a recipe, regardless of backend.
    Lazy: called only for the 5 recipes shown on the meal plan page.

    - Firestore backend: fetches only photo_data for this one document.
    - Local backend: cracks open the zip archive for this one entry.
    """
    # Firestore path — single-document, single-field fetch
    if not archive_path:
        return get_recipe_image_from_firestore(recipe_uid)

    # Local zip path
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            compressed_data = zf.read(inner_path)
            recipe = json.loads(gzip.decompress(compressed_data).decode("utf-8"))
            return recipe.get("photo_data") or None
    except Exception:
        pass

    return None


def filter_recipes(recipes, available_ingredients, max_recipes=150):
    if len(recipes) <= max_recipes:
        return recipes
    avail_words = set(re.findall(r'\w+', available_ingredients.lower()))
    scored = []
    for r in recipes:
        score = sum(1 for w in avail_words if len(w) > 3 and (w in r['ingredients'].lower() or w in r['name'].lower()))
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for score, r in scored[:max_recipes]]

# --- API Setup ---
api_key = ""
try:
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
except:
    api_key = os.environ.get("GEMINI_API_KEY", "")

# --- Sidebar UI ---
st.sidebar.title("⚙️ Settings")
if not api_key or api_key == "YOUR_API_KEY_HERE":
    st.sidebar.error("⚠️ API Key not found in `.streamlit/secrets.toml`!")
    
st.sidebar.markdown("---")
st.sidebar.subheader("Dietary & Meal Goals")
meal_type = st.sidebar.radio("Meal Structure", ["Main Only", "Main + Starter/Dessert"])
calories_goal = st.sidebar.slider("Weekly Calories Goal (per day)", 1500, 3500, 2000, 100)
nutrition_info = st.sidebar.text_area("Other Nutritional Constraints", placeholder="e.g., High protein, low carb", value="")

default_staples = "olive oil, salt, black pepper, all-purpose flour, butter, garlic, onions, soy sauce, sugar, dried oregano, dried basil, cumin, water, vinegar, rice"
staples_input = st.sidebar.text_area("Pantry Staples", default_staples, height=130)
pantry_staples = [s.strip() for s in staples_input.split(",") if s.strip()]

if st.sidebar.button("🔄 Reset to Step 1"):
    st.session_state.step = 1
    st.session_state.parsed_ingredients = ""
    st.session_state.photos_analyzed = False
    st.rerun()

st.sidebar.markdown("---")


# ================== MAIN APP UI ==================
st.title("✨ Intelligent Agentic Meal Planner")

if not api_key or api_key == "YOUR_API_KEY_HERE":
    st.warning("🔒 Please open `.streamlit/secrets.toml` and paste your Gemini API key there to proceed.")
    st.stop()
    
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to load API client: {e}")
    st.stop()


# ---------------- STEP 1: INVENTORY & PARSING ----------------
if st.session_state.step == 1:
    st.markdown("### Step 1: Tell us what you have!")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_files = st.file_uploader("Upload Fridge/Pantry Photos 📸", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    with col2:
        camera_photo = st.camera_input("Or take a picture of your fridge! 📱")
        
    all_photos = []
    if uploaded_files:
        all_photos.extend(uploaded_files)
    if camera_photo:
        all_photos.append(camera_photo)

    if all_photos:
        st.success(f"📸 {len(all_photos)} photos provided!")
        # Show thumbnails natively
        img_cols = st.columns(min(len(all_photos), 4))
        for idx, f in enumerate(all_photos[:4]):
            with img_cols[idx]:
                st.image(f, use_container_width=True)

    if all_photos and not st.session_state.photos_analyzed:
        with st.spinner("🤖 Analyzing your groceries with Gemini Vision..."):
            try:
                images = [Image.open(f) for f in all_photos]
                prompt = ("Analyze these images of a fridge, pantry, or groceries. "
                          "List all the identifiable food items and ingredients you can see, INCLUDING approximate quantities. "
                          "Return ONLY a clean, comma-separated list of ingredients, like: 2 apples, 1/2 gallon milk, 1 loaf of bread, 12 eggs.")
                vision_response = client.models.generate_content(
                     model='gemini-2.5-flash',
                     contents=[prompt] + images,
                )
                st.session_state.parsed_ingredients = vision_response.text
                st.session_state.photos_analyzed = True
                st.rerun()
            except Exception as e:
                st.error(f"Vision parsing error: {e}")
                
    st.markdown("---")
    st.markdown("### Active Inventory")
    
    editable_ingredients = st.text_area(
        "Edit your available fresh ingredients here (comma-separated):", 
        value=st.session_state.parsed_ingredients, 
        height=100
    )
    st.caption("Pantry staples from sidebar are automatically included. We only use these to find recipes.")
    
    if st.button("🚀 Generate Meal Plan!"):
        st.session_state.parsed_ingredients = editable_ingredients
        
        with st.spinner("🧠 Planning your perfect week..."):
            all_recipes = load_recipes()
            if not all_recipes:
                st.error("No recipes found in the 'Data' folder!")
                st.stop()
                
            inventory = f"Fresh Ingredients: {st.session_state.parsed_ingredients}\nAssumed staples: {', '.join(pantry_staples)}"
            filtered_recipes = filter_recipes(all_recipes, inventory, max_recipes=150)
            
            # Remove giant fields from prompt JSON to save insane amounts of tokens
            slim_recipes = [{"uid": r["uid"], "name": r["name"], "prep_time": r["prep_time"]} for r in filtered_recipes]
            recipes_json = json.dumps(slim_recipes)
            
            system_instruction = f'''You are an intelligent, agentic meal planner.
You have access to the user's available inventory of seasonal vegetables from a weekly delivery:
{inventory}

And the following constraints:
- Meal Structure: {meal_type}
- Caloric Goal: {calories_goal} kcal
- Other Nutrition constraints: {nutrition_info}

Your task:
- Output a 5-day weekday meal plan (Monday to Friday). 
- Please prioritise recipes that make best use of the vegetables in the inventory, but please also suggest recipes that use meats and other ingredients that are not in the inventory.
- You MUST output STRICT valid JSON and NOTHING ELSE. No markdown formatting blocks around it.

Format exactly like this list of objects:
[
  {{"day": "Monday", "recipe_uid": "UID of chosen recipe", "reasoning": "Quick reason why"}},
  ...
]

Do not include any characters outside the JSON payload. Only pick valid UIDs from the provided list.'''

            try:
                response = client.models.generate_content(
                    model='gemini-2.5-pro',
                    contents=[system_instruction, "Recipes to choose from:\n" + recipes_json],
                )
                
                # Parse JSON array safely
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:-3]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:-3]
                    
                st.session_state.meal_plan = json.loads(raw_text.strip())
                st.session_state.step = 2
                st.rerun()
            except Exception as e:
                st.error(f"Error during JSON generation. Let's try again! ({e})")
                

# ---------------- STEP 2: MEAL PLAN CURATION ----------------
elif st.session_state.step == 2:
    st.markdown("### 📅 Your Weekly Meal Plan")
    st.markdown("Review your menu! If you don't like a day, you can ask the agent to replace it.")
    
    all_recipes = load_recipes()
    recipe_dict = {r['uid']: r for r in all_recipes}
    
    for idx, day_plan in enumerate(st.session_state.meal_plan):
        day = day_plan.get("day", "Unknown Day")
        uid = day_plan.get("recipe_uid", "")
        reason = day_plan.get("reasoning", "")
        
        recipe = recipe_dict.get(uid, None)
        
        st.markdown(f"#### **{day}**")
        with st.container(border=True):
            col1, col2 = st.columns([1, 4])
            
            if recipe:
                with col1:
                    # Lazy: fetches only this recipe's photo_data from
                    # Firestore (single-field read) or local zip archive
                    b64_image = get_recipe_image(
                        recipe_uid=recipe["uid"],
                        archive_path=recipe.get("archive_path", ""),
                        inner_path=recipe.get("inner_path", ""),
                    )
                    if b64_image:
                        image_data = base64.b64decode(b64_image)
                        st.image(image_data, use_container_width=True)
                    else:
                        st.info("No Photo Available")
                        
                with col2:
                    if recipe.get("source_url"):
                        st.markdown(f"### [{recipe['name']}]({recipe['source_url']})")
                    else:
                        st.subheader(recipe["name"])
                    st.caption(f"⏱️ Prep: {recipe.get('prep_time','N/A')}m | Cook: {recipe.get('cook_time','N/A')}m")
                    st.write(f"**Why this?** {reason}")
                    
                    # Replacer UI
                    with st.expander("🔀 Replace this meal..."):
                        guidance = st.text_input(f"Guidance (e.g., 'Make it vegetarian' or 'Use more chicken'):", key=f"guide_{idx}")
                        if st.button("Generate Alternative", key=f"btn_{idx}"):
                            with st.spinner("Finding an alternative..."):
                                inventory = f"Fresh: {st.session_state.parsed_ingredients}\nStaples: {', '.join(pantry_staples)}"
                                filtered_recipes = filter_recipes(all_recipes, inventory, max_recipes=150)
                                slim_recipes = [{"uid": r["uid"], "name": r["name"]} for r in filtered_recipes]
                                
                                # All UIDs already scheduled this week (including the one being replaced)
                                scheduled_uids = [
                                    p.get("recipe_uid", "")
                                    for p in st.session_state.meal_plan
                                    if p.get("recipe_uid")
                                ]
                                excluded_uids_str = ", ".join(f"'{u}'" for u in scheduled_uids)

                                replace_prompt = f"""
                                The user rejected the recipe '{recipe['name']}' for {day}.
                                Inventory limits: {inventory}. Constraints: {guidance}.
                                Pick ONE new recipe from the JSON list.
                                EXCLUDE ALL of these UIDs (already used this week): {excluded_uids_str}.
                                Return ONLY one JSON object: {{"day": "{day}", "recipe_uid": "...", "reasoning": "..."}}
                                """
                                
                                try:
                                    resp = client.models.generate_content(
                                        model='gemini-2.5-pro',
                                        contents=[replace_prompt, json.dumps(slim_recipes)]
                                    )
                                    r_text = resp.text.strip()
                                    if r_text.startswith("```json"): r_text = r_text[7:-3]
                                    elif r_text.startswith("```"): r_text = r_text[3:-3]
                                    
                                    new_plan = json.loads(r_text.strip())
                                    st.session_state.meal_plan[idx] = new_plan
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to find alternative: {e}")
            else:
                with col2:
                    st.error("Recipe UID not found in library! Try generating an alternative.")
