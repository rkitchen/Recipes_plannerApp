"""
Meal plans router — view, generate, and replace meal plans.
"""

import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from middleware.auth import get_current_user
from models import (
    MealPlanResponse, MealPlanDay,
    GeneratePlanRequest, ReplaceMealRequest,
)
from services.firestore import (
    get_recipes, get_meal_plan, save_meal_plan,
    update_meal_plan, get_user_profile,
)
from services.gemini import generate_meal_plan, replace_meal, extract_ingredients_from_image

router = APIRouter(prefix="/api/meal-plan", tags=["meal-plans"])


@router.get("", response_model=MealPlanResponse)
async def get_plan(
    week_start: str,
    user_uid: str = Depends(get_current_user),
):
    """Fetch the meal plan for a given week."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", week_start):
        raise HTTPException(400, "week_start must be YYYY-MM-DD")
    doc_id, plan_data, inventory = get_meal_plan(user_uid, week_start)
    return MealPlanResponse(
        doc_id=doc_id,
        plan_data=[MealPlanDay(**d) for d in plan_data] if plan_data else [],
        inventory=inventory,
    )


@router.post("/generate", response_model=MealPlanResponse)
async def generate_plan(
    req: GeneratePlanRequest,
    user_uid: str = Depends(get_current_user),
):
    """Generate a new 5-day meal plan using Gemini."""
    all_recipes = get_recipes()
    profile = get_user_profile(user_uid)

    disliked_uids = set(profile.get("disliked", []))
    liked_uids = profile.get("liked", [])

    filtered = [r for r in all_recipes if r["uid"] not in disliked_uids]

    # Build inventory string
    inventory_payload = (
        f"Fresh Ingredients: {req.fresh_ingredients}\n\n"
        f"Assumed staples: {req.pantry_staples}"
    )

    # Filter to top candidates by ingredient overlap
    filtered = _filter_recipes(filtered, inventory_payload, max_recipes=150)

    liked_names = [r["name"] for r in all_recipes if r["uid"] in liked_uids]
    disliked_names = [r["name"] for r in all_recipes if r["uid"] in disliked_uids]

    prefs = profile.get("preferences", {})
    meal_plan_notes = prefs.get("meal_plan_notes", "")

    plan_data = generate_meal_plan(
        recipes=filtered,
        inventory=inventory_payload,
        liked_names=liked_names,
        disliked_names=disliked_names,
        meal_type=req.meal_type,
        calories_goal=req.calories_goal,
        nutrition_info=req.nutrition_info,
        meal_plan_notes=meal_plan_notes,
    )

    doc_id = save_meal_plan(
        user_id=user_uid,
        week_start=req.week_start,
        inventory=inventory_payload,
        plan_data=plan_data,
    )

    return MealPlanResponse(
        doc_id=doc_id,
        plan_data=[MealPlanDay(**d) for d in plan_data],
        inventory=inventory_payload,
    )


@router.post("/{doc_id}/replace")
async def replace_day(
    doc_id: str,
    req: ReplaceMealRequest,
    user_uid: str = Depends(get_current_user),
):
    """Replace a single day's meal in an existing plan."""
    # We need to read the existing plan to get context
    # The doc_id should match the plan the user is viewing
    from services.firestore import get_db
    db = get_db()

    try:
        doc = db.collection("meal_plans").document(doc_id).get()
        if not doc.exists:
            raise HTTPException(404, "Meal plan not found")

        plan = doc.to_dict()
        if plan.get("user_id") != user_uid:
            raise HTTPException(403, "Not your meal plan")

        plan_data = plan.get("plan_data", [])
        if req.day_index < 0 or req.day_index >= len(plan_data):
            raise HTTPException(400, "Invalid day_index")

        old_entry = plan_data[req.day_index]
        old_name = old_entry.get("recipe_uid", "Unknown")
        day_name = old_entry.get("day", "Unknown")
        inventory = plan.get("inventory", "")

        # Find the recipe name
        all_recipes = get_recipes()
        recipe_dict = {r["uid"]: r for r in all_recipes}
        old_recipe = recipe_dict.get(old_name, {})
        original_name = old_recipe.get("name", old_name)

        profile = get_user_profile(user_uid)
        disliked_uids = set(profile.get("disliked", []))
        scheduled_uids = {p.get("recipe_uid", "") for p in plan_data}
        excluded = scheduled_uids | disliked_uids

        candidates = _filter_recipes(all_recipes, inventory, 150)

        new_entry = replace_meal(
            original_name=original_name,
            day_name=day_name,
            inventory=inventory,
            guidance=req.guidance,
            excluded_uids=list(excluded),
            candidate_recipes=candidates,
        )

        plan_data[req.day_index] = new_entry
        update_meal_plan(doc_id, plan_data)

        return {"success": True, "updated_day": new_entry}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Replace failed: {e}")


@router.post("/vision")
async def vision_ingredients(
    file: UploadFile = File(...),
    user_uid: str = Depends(get_current_user),
):
    """
    Accepts an image of a fridge/pantry and extracts fresh ingredients via Gemini.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Uploaded file must be an image.")

    try:
        image_bytes = await file.read()
        extracted = extract_ingredients_from_image(image_bytes, file.content_type)
        return {"ingredients": extracted}
    except Exception as e:
        raise HTTPException(500, f"Vision extraction failed: {e}")


def _filter_recipes(
    recipes: list[dict], available_ingredients: str, max_recipes: int = 150
) -> list[dict]:
    """Rank recipes by ingredient overlap and return the top N."""
    if len(recipes) <= max_recipes:
        return recipes
    avail_words = set(re.findall(r"\w+", available_ingredients.lower()))
    scored = []
    for r in recipes:
        haystack = (r.get("ingredients", "") + " " + r.get("name", "")).lower()
        score = sum(1 for w in avail_words if len(w) > 3 and w in haystack)
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:max_recipes]]
