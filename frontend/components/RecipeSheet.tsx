"use client";

/**
 * RecipeSheet — a bottom sheet that slides up to show full recipe details.
 * Fetches full recipe data (directions, servings, notes, etc.) on open.
 */

import { useState, useEffect, useRef } from "react";
import { fetchRecipeDetail } from "@/lib/api";
import type { RecipeDetail } from "@/lib/types";

interface RecipeSheetProps {
  uid: string | null;
  onClose: () => void;
}

export default function RecipeSheet({ uid, onClose }: RecipeSheetProps) {
  const [recipe, setRecipe] = useState<RecipeDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const sheetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!uid) {
      setRecipe(null);
      return;
    }
    setLoading(true);
    setError("");
    fetchRecipeDetail(uid)
      .then(setRecipe)
      .catch((e) => setError(e.message || "Failed to load recipe"))
      .finally(() => setLoading(false));
  }, [uid]);

  // Lock body scroll when open
  useEffect(() => {
    if (uid) {
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = "";
      };
    }
  }, [uid]);

  if (!uid) return null;

  return (
    <div className="sheet-overlay" onClick={onClose} id="recipe-sheet-overlay">
      <div
        className="sheet"
        ref={sheetRef}
        onClick={(e) => e.stopPropagation()}
        onTouchMove={(e) => e.stopPropagation()}
        id="recipe-sheet"
      >
        {/* Header with close button */}
        <div className="sheet-header">
          <div className="sheet-handle" />
          <button
            className="sheet-close-btn"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="sheet-loading">
            <div className="spinner spinner--large" />
            <p>Loading recipe...</p>
          </div>
        ) : error ? (
          <div className="sheet-error">
            <p>{error}</p>
          </div>
        ) : recipe ? (
          <>
            {/* Hero image */}
            {recipe.photo_data && (
              <div className="sheet-hero">
                <img
                  src={`data:image/jpeg;base64,${recipe.photo_data}`}
                  alt={recipe.name}
                />
              </div>
            )}

            <div className="sheet-body">
              <h2 className="sheet-title">{recipe.name}</h2>

              {/* Meta badges */}
              <div className="sheet-meta">
                {recipe.prep_time && (
                  <span className="sheet-badge">⏱️ Prep {recipe.prep_time}m</span>
                )}
                {recipe.cook_time && (
                  <span className="sheet-badge">🔥 Cook {recipe.cook_time}m</span>
                )}
                {recipe.servings && (
                  <span className="sheet-badge">🍽️ {recipe.servings}</span>
                )}
              </div>

              {recipe.categories.length > 0 && (
                <div className="sheet-categories">
                  {recipe.categories.map((cat) => (
                    <span key={cat} className="sheet-category-tag">
                      {cat}
                    </span>
                  ))}
                </div>
              )}

              {/* Ingredients */}
              {recipe.ingredients && (
                <section className="sheet-section">
                  <h3 className="sheet-section-title">🥘 Ingredients</h3>
                  <div className="sheet-ingredients">
                    {recipe.ingredients.split("\n").map((line, i) =>
                      line.trim() ? (
                        <div key={i} className="sheet-ingredient-line">
                          {line}
                        </div>
                      ) : null
                    )}
                  </div>
                </section>
              )}

              {/* Directions */}
              {recipe.directions && (
                <section className="sheet-section">
                  <h3 className="sheet-section-title">📝 Directions</h3>
                  <div className="sheet-directions">
                    {recipe.directions.split("\n").map((line, i) =>
                      line.trim() ? (
                        <p key={i} className="sheet-direction-step">
                          {line}
                        </p>
                      ) : null
                    )}
                  </div>
                </section>
              )}

              {/* Notes */}
              {recipe.notes && (
                <section className="sheet-section">
                  <h3 className="sheet-section-title">📌 Notes</h3>
                  <p className="sheet-notes">{recipe.notes}</p>
                </section>
              )}

              {/* Nutritional Info */}
              {recipe.nutritional_info && (
                <section className="sheet-section">
                  <h3 className="sheet-section-title">📊 Nutrition</h3>
                  <p className="sheet-nutrition">{recipe.nutritional_info}</p>
                </section>
              )}

              {/* Source link */}
              {recipe.source_url && (
                <a
                  href={recipe.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="sheet-source-link"
                >
                  🔗 View Original Recipe
                </a>
              )}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
