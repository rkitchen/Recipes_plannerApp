"use client";

/**
 * Profile page — dietary preferences, liked/disliked recipes, and sign out.
 */

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchUserProfile,
  fetchRecipes,
  saveUserPreferences,
  updateRecipeRating,
} from "@/lib/api";
import RecipeSheet from "@/components/RecipeSheet";
import type { UserProfile, RecipeSlim } from "@/lib/types";

export default function ProfilePage() {
  const { user, signOut } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [recipes, setRecipes] = useState<RecipeSlim[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Form state
  const [mealType, setMealType] = useState("Main Only");
  const [caloriesGoal, setCaloriesGoal] = useState(2000);
  const [nutritionInfo, setNutritionInfo] = useState("");
  const [pantryStaples, setPantryStaples] = useState("");
  const [mealPlanNotes, setMealPlanNotes] = useState("");
  const [selectedUid, setSelectedUid] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const [prof, recs] = await Promise.all([
        fetchUserProfile(),
        fetchRecipes(),
      ]);
      setProfile(prof);
      setRecipes(recs);

      // Populate form
      setMealType(prof.preferences.meal_type || "Main Only");
      setCaloriesGoal(prof.preferences.calories_goal || 2000);
      setNutritionInfo(prof.preferences.nutrition_info || "");
      setPantryStaples(prof.preferences.pantry_staples || "");
      setMealPlanNotes(prof.preferences.meal_plan_notes || "");
    } catch (e) {
      console.error("Failed to load profile:", e);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await saveUserPreferences({
        meal_type: mealType,
        calories_goal: caloriesGoal,
        nutrition_info: nutritionInfo,
        pantry_staples: pantryStaples,
        meal_plan_notes: mealPlanNotes,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error("Save failed:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveRating = async (uid: string, type: "remove_like" | "remove_dislike") => {
    try {
      await updateRecipeRating({ recipe_uid: uid, rating_type: type });
      loadProfile();
    } catch (e) {
      console.error("Remove rating failed:", e);
    }
  };

  const recipeMap = recipes.reduce(
    (map, r) => ({ ...map, [r.uid]: r }),
    {} as Record<string, RecipeSlim>
  );

  const uidToName = (uid: string) => recipeMap[uid]?.name || uid;

  if (!user) return null;

  if (loading) {
    return (
      <div className="page" id="profile-page">
        <h1 className="page-title">👤 Profile</h1>
        <div className="page-loading">
          <div className="spinner spinner--large" />
        </div>
      </div>
    );
  }

  return (
    <div className="page" id="profile-page">
      <h1 className="page-title">👤 Profile</h1>

      <div className="profile-email">
        Signed in as <strong>{user.email}</strong>
      </div>

      {/* Preferences */}
      <section className="profile-section" id="preferences-section">
        <h2 className="section-title">🎛️ Dietary Preferences</h2>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label" htmlFor="meal-type-select">
              Meal Structure
            </label>
            <select
              id="meal-type-select"
              className="form-select"
              value={mealType}
              onChange={(e) => setMealType(e.target.value)}
            >
              <option value="Main Only">Main Only</option>
              <option value="Main + Starter/Dessert">Main + Starter/Dessert</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="calories-input">
              Calories/day target
            </label>
            <input
              id="calories-input"
              type="number"
              className="form-input"
              min={1000}
              max={5000}
              step={100}
              value={caloriesGoal}
              onChange={(e) => setCaloriesGoal(Number(e.target.value))}
            />
          </div>

          <div className="form-group form-group--full">
            <label className="form-label" htmlFor="nutrition-input">
              Other Nutritional Constraints
            </label>
            <textarea
              id="nutrition-input"
              className="form-textarea"
              placeholder="e.g., low carb, no gluten..."
              value={nutritionInfo}
              onChange={(e) => setNutritionInfo(e.target.value)}
              rows={2}
            />
          </div>

          <div className="form-group form-group--full">
            <label className="form-label" htmlFor="pantry-input">
              Pantry Staples
            </label>
            <textarea
              id="pantry-input"
              className="form-textarea"
              placeholder="olive oil, salt, pepper, flour..."
              value={pantryStaples}
              onChange={(e) => setPantryStaples(e.target.value)}
              rows={3}
            />
          </div>

          <div className="form-group form-group--full">
            <label className="form-label" htmlFor="meal-notes-input">
              Meal Plan Preferences
            </label>
            <textarea
              id="meal-notes-input"
              className="form-textarea"
              placeholder="e.g., We love Mediterranean food, prefer quick weeknight meals under 30 min, would like at least one vegetarian day..."
              value={mealPlanNotes}
              onChange={(e) => setMealPlanNotes(e.target.value)}
              rows={3}
            />
          </div>
        </div>

        <button
          className="btn btn--primary"
          onClick={handleSave}
          disabled={saving}
          id="save-prefs-btn"
        >
          {saving ? (
            <span className="spinner" />
          ) : saved ? (
            "✅ Saved!"
          ) : (
            "💾 Save Preferences"
          )}
        </button>
      </section>

      {/* Ratings */}
      <section className="profile-section" id="ratings-section">
        <h2 className="section-title">⭐ Recipe Ratings</h2>

        <div className="ratings-grid">
          <div className="ratings-column">
            <h3 className="ratings-heading ratings-heading--liked">👍 Liked</h3>
            {profile && profile.liked.length > 0 ? (
              <ul className="ratings-list">
                {[...profile.liked].sort((a, b) => uidToName(a).localeCompare(uidToName(b))).map((uid) => (
                  <li key={uid} className="ratings-item">
                    <span className="ratings-item-name" onClick={() => setSelectedUid(uid)}>{uidToName(uid)}</span>
                    <button
                      className="ratings-remove"
                      onClick={() => handleRemoveRating(uid, "remove_like")}
                      aria-label={`Remove like for ${uidToName(uid)}`}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="ratings-empty">None yet</p>
            )}
          </div>

          <div className="ratings-column">
            <h3 className="ratings-heading ratings-heading--disliked">👎 Disliked</h3>
            {profile && profile.disliked.length > 0 ? (
              <ul className="ratings-list">
                {[...profile.disliked].sort((a, b) => uidToName(a).localeCompare(uidToName(b))).map((uid) => (
                  <li key={uid} className="ratings-item">
                    <span className="ratings-item-name" onClick={() => setSelectedUid(uid)}>{uidToName(uid)}</span>
                    <button
                      className="ratings-remove"
                      onClick={() => handleRemoveRating(uid, "remove_dislike")}
                      aria-label={`Remove dislike for ${uidToName(uid)}`}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="ratings-empty">None yet</p>
            )}
          </div>
        </div>
      </section>

      {/* Sign out */}
      <section className="profile-section profile-section--signout">
        <button
          className="btn btn--outline"
          onClick={signOut}
          id="sign-out-btn"
        >
          🚪 Sign Out
        </button>
      </section>

      <RecipeSheet uid={selectedUid} onClose={() => setSelectedUid(null)} />
    </div>
  );
}
