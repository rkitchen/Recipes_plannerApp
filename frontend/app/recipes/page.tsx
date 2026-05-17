"use client";

/**
 * Recipes page — Paprika-style browseable grid of all recipes.
 * Features search filtering and quick like/dislike rating.
 */

import { useState, useEffect, useMemo } from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchRecipes,
  fetchRecipeImage,
  fetchUserProfile,
  updateRecipeRating,
} from "@/lib/api";
import type { RecipeSlim, UserProfile } from "@/lib/types";

export default function RecipesPage() {
  const { user } = useAuth();
  const [recipes, setRecipes] = useState<RecipeSlim[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    (async () => {
      setLoading(true);
      try {
        const [recipesRes, profileRes] = await Promise.all([
          fetchRecipes(),
          fetchUserProfile(),
        ]);
        setRecipes(recipesRes);
        setProfile(profileRes);
      } catch (e) {
        console.error("Failed to load recipes:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const filtered = useMemo(() => {
    if (!search.trim()) return recipes;
    const q = search.toLowerCase();
    return recipes.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        (r.ingredients && r.ingredients.toLowerCase().includes(q))
    );
  }, [recipes, search]);

  const handleRating = async (
    uid: string,
    type: "like" | "dislike" | "remove_like" | "remove_dislike"
  ) => {
    try {
      await updateRecipeRating({ recipe_uid: uid, rating_type: type });
      // Refresh profile to get updated liked/disliked lists
      const updated = await fetchUserProfile();
      setProfile(updated);
    } catch (e) {
      console.error("Rating failed:", e);
    }
  };

  if (!user) return null;

  return (
    <div className="page" id="recipes-page">
      <h1 className="page-title">📖 Recipe Library</h1>

      <div className="recipes-search-wrapper">
        <input
          type="text"
          className="recipes-search-input"
          placeholder="Search recipes by name or ingredient..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          id="recipes-search"
        />
        {search && (
          <button
            className="recipes-search-clear"
            onClick={() => setSearch("")}
            aria-label="Clear search"
          >
            ✕
          </button>
        )}
      </div>

      {!loading && (
        <p className="recipes-count">
          {filtered.length} recipe{filtered.length !== 1 ? "s" : ""}
          {search ? ` matching "${search}"` : ""}
        </p>
      )}

      {loading ? (
        <div className="page-loading">
          <div className="spinner spinner--large" />
          <p>Loading recipes...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state-icon">🔍</span>
          <p>No recipes found.</p>
        </div>
      ) : (
        <div className="recipes-grid" id="recipes-grid">
          {filtered.map((recipe) => (
            <RecipeTile
              key={recipe.uid}
              recipe={recipe}
              isLiked={profile?.liked.includes(recipe.uid) || false}
              isDisliked={profile?.disliked.includes(recipe.uid) || false}
              onRate={handleRating}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Individual Recipe Tile ──────────────────────────────────────────

interface RecipeTileProps {
  recipe: RecipeSlim;
  isLiked: boolean;
  isDisliked: boolean;
  onRate: (
    uid: string,
    type: "like" | "dislike" | "remove_like" | "remove_dislike"
  ) => Promise<void>;
}

function RecipeTile({ recipe, isLiked, isDisliked, onRate }: RecipeTileProps) {
  const [imageData, setImageData] = useState<string | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [ratingLoading, setRatingLoading] = useState(false);

  useEffect(() => {
    fetchRecipeImage(recipe.uid)
      .then((res) => {
        if (res.photo_data) setImageData(res.photo_data);
      })
      .catch(() => {});
  }, [recipe.uid]);

  const handleLike = async () => {
    setRatingLoading(true);
    await onRate(recipe.uid, isLiked ? "remove_like" : "like");
    setRatingLoading(false);
  };

  const handleDislike = async () => {
    setRatingLoading(true);
    await onRate(recipe.uid, isDisliked ? "remove_dislike" : "dislike");
    setRatingLoading(false);
  };

  return (
    <div className="recipe-tile" id={`recipe-tile-${recipe.uid}`}>
      <div className="recipe-tile-image">
        {imageData ? (
          <img
            src={`data:image/jpeg;base64,${imageData}`}
            alt={recipe.name}
            loading="lazy"
            onLoad={() => setImageLoaded(true)}
            className={imageLoaded ? "loaded" : ""}
          />
        ) : (
          <div className="recipe-tile-placeholder">
            <span>🍳</span>
          </div>
        )}

        {/* Overlay gradient + title */}
        <div className="recipe-tile-overlay">
          <h3 className="recipe-tile-name">{recipe.name}</h3>
        </div>

        {/* Rating buttons on the image */}
        <div className="recipe-tile-actions">
          <button
            className={`tile-rating-btn ${isLiked ? "tile-rating-btn--liked" : ""}`}
            onClick={handleLike}
            disabled={ratingLoading}
            aria-label="Like"
          >
            👍
          </button>
          <button
            className={`tile-rating-btn ${isDisliked ? "tile-rating-btn--disliked" : ""}`}
            onClick={handleDislike}
            disabled={ratingLoading}
            aria-label="Dislike"
          >
            👎
          </button>
        </div>
      </div>

      {/* Metadata below the image */}
      <div className="recipe-tile-meta">
        {recipe.prep_time && <span>⏱️ {recipe.prep_time}m</span>}
        {recipe.cook_time && <span>🔥 {recipe.cook_time}m</span>}
        {recipe.source_url && (
          <a
            href={recipe.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="recipe-tile-link"
          >
            🔗
          </a>
        )}
      </div>
    </div>
  );
}
