"""
Pydantic request / response models for all API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Recipes ──────────────────────────────────────────────────────────────

class RecipeSlim(BaseModel):
    uid: str
    name: str
    prep_time: str = ""
    cook_time: str = ""
    source_url: str = ""
    ingredients: str = ""


class RecipeImageResponse(BaseModel):
    uid: str
    photo_data: Optional[str] = None


# ── Meal Plans ───────────────────────────────────────────────────────────

class MealPlanDay(BaseModel):
    day: str
    recipe_uid: str
    reasoning: str = ""


class MealPlanResponse(BaseModel):
    doc_id: Optional[str] = None
    plan_data: list[MealPlanDay] = []
    inventory: str = ""


class GeneratePlanRequest(BaseModel):
    week_start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    fresh_ingredients: str = ""
    pantry_staples: str = "olive oil, salt, black pepper, all-purpose flour, butter, garlic, onions, soy sauce, sugar, dried oregano, dried basil, cumin, water, vinegar, rice"
    meal_type: str = "Main Only"
    calories_goal: int = 2000
    nutrition_info: str = ""


class ReplaceMealRequest(BaseModel):
    doc_id: str
    day_index: int
    guidance: str = ""


# ── Grocery List ─────────────────────────────────────────────────────────

class GroceryListRequest(BaseModel):
    recipe_uids: list[str]
    pantry_staples: str = ""


class GroceryItem(BaseModel):
    name: str
    quantity: str = ""
    checked: bool = False


class GroceryCategory(BaseModel):
    name: str
    items: list[GroceryItem]


class GroceryListResponse(BaseModel):
    categories: list[GroceryCategory]


class GroceryListStateResponse(BaseModel):
    categories: list[GroceryCategory] = []
    checked_items: list[str] = []


class GroceryListSyncRequest(BaseModel):
    checked_items: list[str]


# ── Users ────────────────────────────────────────────────────────────────

class UserPreferences(BaseModel):
    meal_type: str = "Main Only"
    calories_goal: int = 2000
    nutrition_info: str = ""
    pantry_staples: str = ""


class UserProfile(BaseModel):
    liked: list[str] = []
    disliked: list[str] = []
    preferences: UserPreferences = UserPreferences()


class RatingUpdate(BaseModel):
    recipe_uid: str
    rating_type: str = Field(..., pattern=r"^(like|dislike|remove_like|remove_dislike)$")
