/**
 * API fetch wrappers — all calls go through here.
 * 
 * - Uses NEXT_PUBLIC_API_URL env var for the backend base URL
 * - Auto-attaches the Firebase ID token for authentication
 * - Handles JSON parsing and error responses
 */

import { auth } from "./firebase";
import type {
  RecipeSlim,
  RecipeImage,
  MealPlanResponse,
  GeneratePlanRequest,
  ReplaceMealRequest,
  GroceryListRequest,
  GroceryListResponse,
  GroceryListStateResponse,
  UserProfile,
  UserPreferences,
  RatingUpdate,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

/**
 * Core fetch wrapper that attaches the Firebase auth token.
 */
async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const user = auth.currentUser;
  if (!user) {
    throw new Error("Not authenticated");
  }

  const token = await user.getIdToken();

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json();
}

// ── Recipes ─────────────────────────────────────────────────────────

export async function fetchRecipes(): Promise<RecipeSlim[]> {
  return apiFetch<RecipeSlim[]>("/api/recipes");
}

export async function fetchRecipeImage(uid: string): Promise<RecipeImage> {
  return apiFetch<RecipeImage>(`/api/recipes/${uid}/image`);
}

// ── Meal Plans ──────────────────────────────────────────────────────

export async function fetchMealPlan(weekStart: string): Promise<MealPlanResponse> {
  return apiFetch<MealPlanResponse>(`/api/meal-plan?week_start=${weekStart}`);
}

export async function generateMealPlan(req: GeneratePlanRequest): Promise<MealPlanResponse> {
  return apiFetch<MealPlanResponse>("/api/meal-plan/generate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function replaceMeal(
  docId: string,
  req: ReplaceMealRequest
): Promise<{ success: boolean; updated_day: any }> {
  return apiFetch(`/api/meal-plan/${docId}/replace`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function extractIngredientsVision(file: File): Promise<{ ingredients: string }> {
  const user = auth.currentUser;
  if (!user) throw new Error("No user logged in");
  const token = await user.getIdToken();

  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/meal-plan/vision`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Vision extraction failed");
  }

  return res.json();
}

// ── Grocery List ────────────────────────────────────────────────────

export async function generateGroceryList(
  req: GroceryListRequest
): Promise<GroceryListResponse> {
  return apiFetch<GroceryListResponse>("/api/grocery-list", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function fetchGroceryList(): Promise<GroceryListStateResponse> {
  return apiFetch<GroceryListStateResponse>("/api/grocery-list");
}

export async function updateGroceryChecks(checkedKeys: string[]): Promise<void> {
  await apiFetch("/api/grocery-list/checks", {
    method: "PUT",
    body: JSON.stringify({ checked_items: checkedKeys }),
  });
}

// ── Users ───────────────────────────────────────────────────────────

export async function fetchUserProfile(): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/user/profile");
}

export async function saveUserPreferences(prefs: UserPreferences): Promise<void> {
  await apiFetch("/api/user/preferences", {
    method: "PUT",
    body: JSON.stringify(prefs),
  });
}

export async function updateRecipeRating(rating: RatingUpdate): Promise<void> {
  await apiFetch("/api/user/rating", {
    method: "PUT",
    body: JSON.stringify(rating),
  });
}
