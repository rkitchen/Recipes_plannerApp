"use client";

/**
 * Grocery List page — generate and interact with a smart shopping list.
 * Fetches recipe UIDs from the current week's meal plan, sends to the backend
 * for AI-powered consolidation and categorisation.
 */

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/components/AuthProvider";
import GroceryList from "@/components/GroceryList";
import {
  fetchMealPlan,
  fetchUserProfile,
  generateGroceryList,
  fetchGroceryList,
} from "@/lib/api";
import type { GroceryCategory } from "@/lib/types";
import { getTargetWeek } from "@/lib/dateUtils";

export default function GroceryPage() {
  const { user } = useAuth();
  const [categories, setCategories] = useState<GroceryCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState("");
  const [hasPlan, setHasPlan] = useState<boolean | null>(null);
  const [isOffline, setIsOffline] = useState(false);
  const [initialCheckedItems, setInitialCheckedItems] = useState<string[]>([]);

  const loadFromDb = useCallback(async () => {
    try {
      const res = await fetchGroceryList();
      setCategories(res.categories);
      setInitialCheckedItems(res.checked_items);
    } catch (err) {
      console.error("Failed to load grocery list:", err);
    }
  }, []);

  // Load grocery list from database on mount
  useEffect(() => {
    if (!user) return;
    setInitialLoading(true);
    loadFromDb().finally(() => setInitialLoading(false));

    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    setIsOffline(!navigator.onLine);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [user, loadFromDb]);

  // Check if current week has a plan
  useEffect(() => {
    if (!user) return;
    const weekStart = getTargetWeek();
    fetchMealPlan(weekStart)
      .then((plan) => setHasPlan(plan.plan_data.length > 0))
      .catch(() => setHasPlan(false));
  }, [user]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadFromDb();
    setRefreshing(false);
  };

  const handleGenerate = async () => {
    if (!user) return;
    setLoading(true);
    setError("");

    try {
      const weekStart = getTargetWeek();
      const [plan, profile] = await Promise.all([
        fetchMealPlan(weekStart),
        fetchUserProfile(),
      ]);

      if (!plan.plan_data.length) {
        setError("No meal plan found for this week. Generate a plan first!");
        setLoading(false);
        return;
      }

      const recipeUids = plan.plan_data.map((d) => d.recipe_uid);
      const pantryStaples = profile.preferences.pantry_staples || "";

      const result = await generateGroceryList({
        recipe_uids: recipeUids,
        pantry_staples: pantryStaples,
      });

      setCategories(result.categories);
      setInitialCheckedItems([]);
    } catch (e: any) {
      setError(e.message || "Failed to generate grocery list");
    } finally {
      setLoading(false);
    }
  };

  if (!user) return null;

  return (
    <div className="page" id="grocery-page">
      <h1 className="page-title">🛒 Grocery List</h1>

      {isOffline && (
        <div className="offline-banner" id="offline-banner">
          📶 You&apos;re offline — showing cached data
        </div>
      )}

      {/* Actions */}
      <div className="grocery-actions">
        <div className="grocery-actions-row">
          <button
            className="btn btn--primary"
            onClick={handleGenerate}
            disabled={loading || hasPlan === false}
            id="generate-grocery-btn"
          >
            {loading ? (
              <>
                <span className="spinner" /> Generating with AI...
              </>
            ) : categories.length > 0 ? (
              "🔄 Regenerate List"
            ) : (
              "✨ Generate Grocery List"
            )}
          </button>
          {categories.length > 0 && (
            <button
              className="btn btn--outline grocery-refresh-btn"
              onClick={handleRefresh}
              disabled={refreshing}
              id="refresh-grocery-btn"
              aria-label="Refresh from database"
            >
              {refreshing ? <span className="spinner" /> : "🔃"}
            </button>
          )}
        </div>
        {hasPlan === false && (
          <p className="grocery-hint">
            No meal plan for this week yet. Head to the Meals tab to plan first!
          </p>
        )}
      </div>

      {error && (
        <div className="form-error" id="grocery-error">
          {error}
        </div>
      )}

      {initialLoading ? (
        <div className="page-loading">
          <div className="spinner spinner--large" />
          <p>Loading grocery list...</p>
        </div>
      ) : (
        <>
          <GroceryList 
            categories={categories} 
            initialCheckedItems={initialCheckedItems} 
          />

          {categories.length === 0 && !loading && (
            <div className="empty-state" id="no-grocery-state">
              <span className="empty-state-icon">🛒</span>
              <p>
                Generate a grocery list from your meal plan.
                <br />
                Items will be sorted by supermarket aisle!
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
