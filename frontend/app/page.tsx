"use client";

/**
 * Home page — Meal Plan view.
 * Shows the week carousel, recipe cards for each day, and a "Plan This Week" button.
 */

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import WeekCarousel from "@/components/WeekCarousel";
import RecipeCard from "@/components/RecipeCard";
import PlanDialog from "@/components/PlanDialog";
import RecipeSheet from "@/components/RecipeSheet";
import { fetchMealPlan, fetchRecipes, fetchUserProfile } from "@/lib/api";
import type { MealPlanResponse, RecipeSlim, UserProfile } from "@/lib/types";

function getTargetWeek(): string {
  const today = new Date();
  const day = today.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
  if (day === 0 || day === 6) {
    // Weekend: show next Monday
    const daysAhead = day === 0 ? 1 : 2;
    const next = new Date(today);
    next.setDate(today.getDate() + daysAhead);
    return next.toISOString().split("T")[0];
  }
  // Weekday: show this Monday
  const monday = new Date(today);
  monday.setDate(today.getDate() - (day - 1));
  return monday.toISOString().split("T")[0];
}

export default function MealsPage() {
  const { user } = useAuth();
  const [weekStart, setWeekStart] = useState(getTargetWeek);
  const [plan, setPlan] = useState<MealPlanResponse | null>(null);
  const [recipes, setRecipes] = useState<RecipeSlim[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showPlanDialog, setShowPlanDialog] = useState(false);
  const [selectedUid, setSelectedUid] = useState<string | null>(null);

  const recipeMap = recipes.reduce(
    (map, r) => ({ ...map, [r.uid]: r }),
    {} as Record<string, RecipeSlim>
  );

  const loadData = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const [planRes, recipesRes, profileRes] = await Promise.all([
        fetchMealPlan(weekStart),
        recipes.length > 0 ? Promise.resolve(recipes) : fetchRecipes(),
        profile ? Promise.resolve(profile) : fetchUserProfile(),
      ]);
      setPlan(planRes);
      if (Array.isArray(recipesRes)) setRecipes(recipesRes);
      if (profileRes && "liked" in profileRes) setProfile(profileRes);
    } catch (e) {
      console.error("Failed to load data:", e);
    } finally {
      setLoading(false);
    }
  }, [user, weekStart]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleWeekChange = (newWeek: string) => {
    setWeekStart(newWeek);
    setPlan(null);
  };

  const today = new Date();

  if (!user) return null;

  return (
    <div className="page" id="meals-page">
      <h1 className="page-title">✨ Meal Planner</h1>

      <WeekCarousel weekStart={weekStart} onWeekChange={handleWeekChange} />

      {loading ? (
        <div className="page-loading">
          <div className="spinner spinner--large" />
          <p>Loading meal plan...</p>
        </div>
      ) : plan && plan.plan_data.length > 0 ? (
        <div className="recipe-list" id="recipe-list">
          {plan.plan_data.map((day, idx) => {
            const mealDate = new Date(weekStart + "T00:00:00");
            mealDate.setDate(mealDate.getDate() + idx);
            const isPast = mealDate < today;

            return (
              <RecipeCard
                key={`${day.recipe_uid}-${idx}`}
                day={day}
                dayIndex={idx}
                recipe={recipeMap[day.recipe_uid]}
                docId={plan.doc_id}
                userLiked={profile?.liked || []}
                userDisliked={profile?.disliked || []}
                isPast={isPast}
                onPlanUpdated={loadData}
                onViewRecipe={setSelectedUid}
              />
            );
          })}
        </div>
      ) : (
        <div className="empty-state" id="no-plan-state">
          <span className="empty-state-icon">📅</span>
          <p>No menu planned for this week.</p>
          <button
            className="btn btn--primary"
            onClick={() => setShowPlanDialog(true)}
            id="plan-week-btn"
          >
            🪄 Plan This Week
          </button>
        </div>
      )}

      {profile && (
        <PlanDialog
          weekStart={weekStart}
          preferences={profile.preferences}
          isOpen={showPlanDialog}
          onClose={() => setShowPlanDialog(false)}
          onPlanGenerated={loadData}
        />
      )}

      <RecipeSheet uid={selectedUid} onClose={() => setSelectedUid(null)} />
    </div>
  );
}
