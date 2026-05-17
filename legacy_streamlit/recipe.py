import streamlit as st
import os
import zipfile
import gzip
import json
import re
from typing import Optional, List

from db import _get_db

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
