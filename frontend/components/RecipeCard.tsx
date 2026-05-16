"use client";

/**
 * RecipeCard — displays a single day's recipe with image, rating, and replace functionality.
 * Glassmorphism card design with smooth interactions.
 */

import { useState, useEffect } from "react";
import { fetchRecipeImage, updateRecipeRating, replaceMeal } from "@/lib/api";
import type { MealPlanDay, RecipeSlim } from "@/lib/types";

interface RecipeCardProps {
  day: MealPlanDay;
  dayIndex: number;
  recipe: RecipeSlim | undefined;
  docId: string | null;
  userLiked: string[];
  userDisliked: string[];
  isPast: boolean;
  onPlanUpdated: () => void;
}

export default function RecipeCard({
  day,
  dayIndex,
  recipe,
  docId,
  userLiked,
  userDisliked,
  isPast,
  onPlanUpdated,
}: RecipeCardProps) {
  const [imageData, setImageData] = useState<string | null>(null);
  const [showReplace, setShowReplace] = useState(false);
  const [guidance, setGuidance] = useState("");
  const [replacing, setReplacing] = useState(false);
  const [ratingLoading, setRatingLoading] = useState(false);

  const uid = day.recipe_uid;
  const isLiked = userLiked.includes(uid);
  const isDisliked = userDisliked.includes(uid);

  useEffect(() => {
    if (uid) {
      fetchRecipeImage(uid)
        .then((res) => setImageData(res.photo_data))
        .catch(() => {});
    }
  }, [uid]);

  const handleRating = async (type: "like" | "dislike" | "remove_like" | "remove_dislike") => {
    setRatingLoading(true);
    try {
      await updateRecipeRating({ recipe_uid: uid, rating_type: type });
      onPlanUpdated();
    } catch (e) {
      console.error("Rating failed:", e);
    } finally {
      setRatingLoading(false);
    }
  };

  const handleReplace = async () => {
    if (!docId) return;
    setReplacing(true);
    try {
      await replaceMeal(docId, { doc_id: docId, day_index: dayIndex, guidance });
      onPlanUpdated();
    } catch (e) {
      console.error("Replace failed:", e);
    } finally {
      setReplacing(false);
    }
  };

  const onRatingClick = () => {
    if (isLiked) handleRating("remove_like");
    else handleRating("like");
  };

  const onDislikeClick = () => {
    if (isDisliked) handleRating("remove_dislike");
    else handleRating("dislike");
  };

  if (!recipe) {
    return (
      <div className="recipe-card recipe-card--error" id={`recipe-card-${dayIndex}`}>
        <div className="recipe-card-body">
          <h3 className="recipe-card-day">{day.day}</h3>
          <p className="recipe-card-missing">Recipe not found: {uid}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`recipe-card ${isPast ? "recipe-card--past" : ""}`}
      id={`recipe-card-${dayIndex}`}
    >
      {/* Image */}
      <div className="recipe-card-image">
        {imageData ? (
          <img
            src={`data:image/jpeg;base64,${imageData}`}
            alt={recipe.name}
            loading="lazy"
          />
        ) : (
          <div className="recipe-card-image-placeholder">
            <span>🍳</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="recipe-card-body">
        <span className="recipe-card-day-badge">{day.day}</span>

        {recipe.source_url ? (
          <a href={recipe.source_url} target="_blank" rel="noopener noreferrer" className="recipe-card-title">
            {recipe.name}
          </a>
        ) : (
          <h3 className="recipe-card-title">{recipe.name}</h3>
        )}

        <div className="recipe-card-meta">
          <span>⏱️ Prep {recipe.prep_time || "–"}m</span>
          <span>🔥 Cook {recipe.cook_time || "–"}m</span>
        </div>

        {day.reasoning && (
          <p className="recipe-card-reason">
            <strong>Why?</strong> {day.reasoning}
          </p>
        )}

        {/* Rating buttons */}
        <div className="recipe-card-rating">
          <button
            className={`rating-btn ${isLiked ? "rating-btn--active-like" : ""}`}
            onClick={onRatingClick}
            disabled={ratingLoading}
            aria-label="Like recipe"
            id={`like-btn-${dayIndex}`}
          >
            👍
          </button>
          <button
            className={`rating-btn ${isDisliked ? "rating-btn--active-dislike" : ""}`}
            onClick={onDislikeClick}
            disabled={ratingLoading}
            aria-label="Dislike recipe"
            id={`dislike-btn-${dayIndex}`}
          >
            👎
          </button>
        </div>

        {/* Replace section */}
        {!isPast && docId && (
          <div className="recipe-card-replace">
            <button
              className="replace-toggle"
              onClick={() => setShowReplace(!showReplace)}
              id={`replace-toggle-${dayIndex}`}
            >
              🔀 {showReplace ? "Cancel" : "Replace this meal"}
            </button>
            {showReplace && (
              <div className="replace-form">
                <input
                  type="text"
                  placeholder="Constraints (e.g. 'Make it vegetarian')..."
                  value={guidance}
                  onChange={(e) => setGuidance(e.target.value)}
                  className="replace-input"
                  id={`replace-input-${dayIndex}`}
                />
                <button
                  className="replace-submit"
                  onClick={handleReplace}
                  disabled={replacing}
                  id={`replace-submit-${dayIndex}`}
                >
                  {replacing ? "Finding alternative..." : "Generate Alternative"}
                </button>
              </div>
            )}
          </div>
        )}

        {isPast && (
          <p className="recipe-card-past-label">Past meal</p>
        )}
      </div>
    </div>
  );
}
