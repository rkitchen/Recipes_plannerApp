"""
Firestore service — all database reads/writes.
Ported from the Streamlit db.py, with no Streamlit dependencies.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from config import get_settings

_db = None


def init_firebase() -> None:
    """Initialise Firebase Admin SDK. Call once at app startup."""
    global _db
    if not firebase_admin._apps:
        settings = get_settings()
        cred = credentials.Certificate(settings.firebase_credentials)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()


def get_db() -> firestore.Client:
    if _db is None:
        init_firebase()
    return _db


# ── Recipes ──────────────────────────────────────────────────────────────

def get_recipes() -> list[dict]:
    """Return all recipes (slim projection, no photo_data)."""
    db = get_db()
    fields = [
        "uid", "name", "ingredients", "nutritional_info",
        "prep_time", "cook_time", "source_url",
    ]
    docs = db.collection("recipes").select(fields).stream()
    recipes = []
    for doc in docs:
        r = doc.to_dict()
        if not r:
            continue
        recipes.append({
            "uid": r.get("uid", doc.id),
            "name": r.get("name", "Unknown"),
            "ingredients": r.get("ingredients", ""),
            "prep_time": str(r.get("prep_time", "")),
            "cook_time": str(r.get("cook_time", "")),
            "source_url": r.get("source_url", ""),
        })
    return recipes


def get_recipe_image(uid: str) -> str | None:
    """Return base64 photo_data for a single recipe, or None."""
    db = get_db()
    try:
        doc = db.collection("recipes").document(uid).get(
            field_paths=["photo_data"]
        )
        if doc.exists:
            return doc.to_dict().get("photo_data") or None
    except Exception:
        pass
    return None


def get_recipe_detail(uid: str) -> dict | None:
    """Return full recipe details for a single recipe, or None."""
    db = get_db()
    try:
        doc = db.collection("recipes").document(uid).get()
        if doc.exists:
            r = doc.to_dict()
            categories = r.get("categories", [])
            if isinstance(categories, str):
                categories = [c.strip() for c in categories.split(",") if c.strip()]
            return {
                "uid": r.get("uid", uid),
                "name": r.get("name", "Unknown"),
                "prep_time": str(r.get("prep_time", "")),
                "cook_time": str(r.get("cook_time", "")),
                "source_url": r.get("source_url", ""),
                "ingredients": r.get("ingredients", ""),
                "directions": r.get("directions", ""),
                "servings": str(r.get("servings", "")),
                "nutritional_info": r.get("nutritional_info", ""),
                "notes": r.get("notes", ""),
                "categories": categories,
                "photo_data": r.get("photo_data"),
            }
    except Exception:
        pass
    return None


def get_recipe_ingredients_batch(uids: list[str]) -> list[str]:
    """Fetch ingredient strings for a batch of recipe UIDs."""
    db = get_db()
    ingredients = []
    for uid in uids:
        try:
            doc = db.collection("recipes").document(uid).get(
                field_paths=["ingredients", "name"]
            )
            if doc.exists:
                d = doc.to_dict()
                ing = d.get("ingredients", "")
                if ing:
                    name = d.get("name", uid)
                    ingredients.append(f"--- {name} ---\n{ing}")
        except Exception:
            continue
    return ingredients


# ── Meal Plans ───────────────────────────────────────────────────────────

def get_meal_plan(user_id: str, week_start: str) -> tuple[str | None, list, str]:
    """Returns (document_id, plan_data_list, inventory_string)."""
    db = get_db()
    try:
        docs = (
            db.collection("meal_plans")
            .where(filter=firestore.FieldFilter("user_id", "==", user_id))
            .where(filter=firestore.FieldFilter("week_start", "==", week_start))
            .limit(1)
            .stream()
        )
        for doc in docs:
            d = doc.to_dict()
            return doc.id, d.get("plan_data", []), d.get("inventory", "")
    except Exception:
        pass
    return None, [], ""


def save_meal_plan(
    user_id: str, week_start: str, inventory: str, plan_data: list
) -> str:
    """Create a new meal plan document. Returns the new document ID."""
    db = get_db()
    _, ref = db.collection("meal_plans").add({
        "user_id": user_id,
        "datestamp": firestore.SERVER_TIMESTAMP,
        "week_start": week_start,
        "inventory": inventory,
        "plan_data": plan_data,
    })
    return ref.id


def update_meal_plan(doc_id: str, new_plan_data: list) -> None:
    """Overwrite plan_data for an existing meal plan."""
    db = get_db()
    db.collection("meal_plans").document(doc_id).update({
        "plan_data": new_plan_data,
        "datestamp": firestore.SERVER_TIMESTAMP,
    })


# ── Grocery Lists ────────────────────────────────────────────────────────

def get_grocery_list(user_id: str) -> tuple[list, list]:
    """Returns (categories, checked_items)."""
    db = get_db()
    if not user_id:
        return [], []
    try:
        doc = db.collection("grocery_lists").document(user_id).get()
        if doc.exists:
            d = doc.to_dict()
            return d.get("categories", []), d.get("checked_items", [])
    except Exception:
        pass
    return [], []

def save_grocery_list(user_id: str, categories: list) -> None:
    """Completely replace the active grocery list and clear checked items."""
    db = get_db()
    if not user_id:
        return
    db.collection("grocery_lists").document(user_id).set({
        "categories": categories,
        "checked_items": [],
        "datestamp": firestore.SERVER_TIMESTAMP,
    })

def update_grocery_list_checks(user_id: str, checked_items: list) -> None:
    """Update only the checked items array."""
    db = get_db()
    if not user_id:
        return
    db.collection("grocery_lists").document(user_id).set({
        "checked_items": checked_items,
        "datestamp": firestore.SERVER_TIMESTAMP,
    }, merge=True)


# ── Users ────────────────────────────────────────────────────────────────

def get_user_profile(user_id: str) -> dict:
    """Fetch a user's profile (liked/disliked recipes + preferences)."""
    db = get_db()
    empty = {"liked": [], "disliked": [], "preferences": {}}
    if not user_id:
        return empty
    try:
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            d = doc.to_dict()
            return {
                "liked": d.get("liked_recipes", []),
                "disliked": d.get("disliked_recipes", []),
                "preferences": d.get("preferences", {}),
            }
        else:
            # Auto-provision new user on first fetch
            from firebase_admin import auth
            try:
                user_record = auth.get_user(user_id)
                email = user_record.email
            except Exception as e:
                print(f"Failed to fetch user email from auth: {e}")
                email = "unknown"
            
            print(f"Auto-provisioning user document for {user_id} with email {email}")
            doc_ref.set({
                "email": email,
                "liked_recipes": [],
                "disliked_recipes": [],
                "preferences": {}
            })
            return empty
    except Exception as e:
        print(f"CRITICAL ERROR in get_user_profile: {e}")
        import traceback
        traceback.print_exc()
        return empty


def save_user_preferences(user_id: str, prefs: dict) -> None:
    db = get_db()
    if not user_id:
        return
    db.collection("users").document(user_id).set(
        {"preferences": prefs}, merge=True
    )


def update_recipe_rating(user_id: str, recipe_uid: str, rating_type: str) -> None:
    db = get_db()
    if not user_id:
        return
    ref = db.collection("users").document(user_id)
    ArrayUnion = firestore.ArrayUnion
    ArrayRemove = firestore.ArrayRemove

    if rating_type == "like":
        ref.set({
            "liked_recipes": ArrayUnion([recipe_uid]),
            "disliked_recipes": ArrayRemove([recipe_uid]),
        }, merge=True)
    elif rating_type == "dislike":
        ref.set({
            "disliked_recipes": ArrayUnion([recipe_uid]),
            "liked_recipes": ArrayRemove([recipe_uid]),
        }, merge=True)
    elif rating_type == "remove_like":
        ref.set({"liked_recipes": ArrayRemove([recipe_uid])}, merge=True)
    elif rating_type == "remove_dislike":
        ref.set({"disliked_recipes": ArrayRemove([recipe_uid])}, merge=True)
