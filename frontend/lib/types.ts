/**
 * TypeScript interfaces matching the backend Pydantic models.
 */

// ── Recipes ─────────────────────────────────────────────────────────

export interface RecipeSlim {
  uid: string;
  name: string;
  prep_time: string;
  cook_time: string;
  source_url: string;
  ingredients: string;
}

export interface RecipeImage {
  uid: string;
  photo_data: string | null;
}

// ── Meal Plans ──────────────────────────────────────────────────────

export interface MealPlanDay {
  day: string;
  recipe_uid: string;
  reasoning: string;
}

export interface MealPlanResponse {
  doc_id: string | null;
  plan_data: MealPlanDay[];
  inventory: string;
}

export interface GeneratePlanRequest {
  week_start: string;
  fresh_ingredients: string;
  pantry_staples: string;
  meal_type: string;
  calories_goal: number;
  nutrition_info: string;
}

export interface ReplaceMealRequest {
  doc_id: string;
  day_index: number;
  guidance: string;
}

// ── Grocery List ────────────────────────────────────────────────────

export interface GroceryItem {
  name: string;
  quantity: string;
  checked: boolean;
}

export interface GroceryCategory {
  name: string;
  items: GroceryItem[];
}

export interface GroceryListResponse {
  categories: GroceryCategory[];
}

export interface GroceryListStateResponse {
  categories: GroceryCategory[];
  checked_items: string[];
}

export interface GroceryListRequest {
  recipe_uids: string[];
  pantry_staples: string;
}

// ── Users ───────────────────────────────────────────────────────────

export interface UserPreferences {
  meal_type: string;
  calories_goal: number;
  nutrition_info: string;
  pantry_staples: string;
}

export interface UserProfile {
  liked: string[];
  disliked: string[];
  preferences: UserPreferences;
}

export interface RatingUpdate {
  recipe_uid: string;
  rating_type: "like" | "dislike" | "remove_like" | "remove_dislike";
}
