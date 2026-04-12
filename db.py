import streamlit as st
from typing import Optional, Tuple

try:
    import firebase_admin
    from firebase_admin import credentials, firestore as fb_firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

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
        "datestamp": fb_firestore.SERVER_TIMESTAMP, 
    })
