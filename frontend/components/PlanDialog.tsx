"use client";

/**
 * PlanDialog — modal for generating a new meal plan.
 * Allows entering fresh ingredients and triggers Gemini generation.
 */

import { useRef, useState } from "react";
import { generateMealPlan, extractIngredientsVision } from "@/lib/api";
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
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);

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

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setScanning(true);
    setError("");
    try {
      const res = await extractIngredientsVision(file);
      if (res.ingredients) {
        setFreshIngredients((prev) => 
          prev ? `${prev}, ${res.ingredients}` : res.ingredients
        );
      }
    } catch (err: any) {
      setError(err.message || "Failed to scan image");
    } finally {
      setScanning(false);
      if (cameraInputRef.current) cameraInputRef.current.value = "";
      if (galleryInputRef.current) galleryInputRef.current.value = "";
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

          <div className="dialog-label-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label className="dialog-label" htmlFor="fresh-ingredients-input" style={{ marginBottom: 0, flex: 1 }}>
              Fresh ingredients available:
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                className="btn btn--secondary" 
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                onClick={() => galleryInputRef.current?.click()}
                disabled={scanning || generating}
              >
                {scanning ? "🔍..." : "📁 Gallery"}
              </button>
              <button 
                className="btn btn--secondary" 
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                onClick={() => cameraInputRef.current?.click()}
                disabled={scanning || generating}
              >
                {scanning ? "🔍 Scanning..." : "📸 Camera"}
              </button>
            </div>
            
            <input 
              type="file" 
              accept="image/*" 
              capture="environment" 
              style={{ display: 'none' }} 
              ref={cameraInputRef}
              onChange={handleImageUpload}
            />
            <input 
              type="file" 
              accept="image/*" 
              style={{ display: 'none' }} 
              ref={galleryInputRef}
              onChange={handleImageUpload}
            />
          </div>
          <textarea
            id="fresh-ingredients-input"
            className="dialog-textarea"
            placeholder="e.g., 2 chicken breasts, 1 bag spinach, half a lemon..."
            value={freshIngredients}
            onChange={(e) => setFreshIngredients(e.target.value)}
            rows={4}
            disabled={scanning || generating}
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
