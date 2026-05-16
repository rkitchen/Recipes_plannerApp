"use client";

/**
 * PlanDialog — modal for generating a new meal plan.
 * Allows entering fresh ingredients and triggers Gemini generation.
 */

import { useState } from "react";
import { generateMealPlan } from "@/lib/api";
import type { UserPreferences } from "@/lib/types";

interface PlanDialogProps {
  weekStart: string;
  preferences: UserPreferences;
  isOpen: boolean;
  onClose: () => void;
  onPlanGenerated: () => void;
}

export default function PlanDialog({
  weekStart,
  preferences,
  isOpen,
  onClose,
  onPlanGenerated,
}: PlanDialogProps) {
  const [freshIngredients, setFreshIngredients] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleGenerate = async () => {
    setGenerating(true);
    setError("");
    try {
      await generateMealPlan({
        week_start: weekStart,
        fresh_ingredients: freshIngredients,
        pantry_staples: preferences.pantry_staples,
        meal_type: preferences.meal_type,
        calories_goal: preferences.calories_goal,
        nutrition_info: preferences.nutrition_info,
      });
      onPlanGenerated();
      onClose();
    } catch (e: any) {
      setError(e.message || "Failed to generate plan");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="dialog-overlay" onClick={onClose} id="plan-dialog-overlay">
      <div className="dialog" onClick={(e) => e.stopPropagation()} id="plan-dialog">
        <div className="dialog-header">
          <h2>🪄 Plan Menu for the Week</h2>
          <button className="dialog-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="dialog-body">
          <p className="dialog-subtitle">
            Generating a menu for <strong>{weekStart}</strong>
          </p>

          <label className="dialog-label" htmlFor="fresh-ingredients-input">
            Fresh ingredients available:
          </label>
          <textarea
            id="fresh-ingredients-input"
            className="dialog-textarea"
            placeholder="e.g., 2 chicken breasts, 1 bag spinach, half a lemon..."
            value={freshIngredients}
            onChange={(e) => setFreshIngredients(e.target.value)}
            rows={4}
          />

          <div className="dialog-prefs-summary">
            <span>🎯 {preferences.meal_type}</span>
            <span>🔥 {preferences.calories_goal} kcal/day</span>
            {preferences.nutrition_info && (
              <span>📋 {preferences.nutrition_info}</span>
            )}
          </div>

          {error && <p className="dialog-error">{error}</p>}
        </div>

        <div className="dialog-footer">
          <button
            className="btn btn--primary btn--full"
            onClick={handleGenerate}
            disabled={generating}
            id="generate-plan-btn"
          >
            {generating ? (
              <>
                <span className="spinner" /> Generating with Gemini...
              </>
            ) : (
              "🚀 Generate Menu"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
