"""
Users router — profile, preferences, and recipe ratings.
"""

from fastapi import APIRouter, Depends
from middleware.auth import get_current_user
from models import UserProfile, UserPreferences, RatingUpdate
from services.firestore import (
    get_user_profile, save_user_preferences, update_recipe_rating,
)

router = APIRouter(prefix="/api/user", tags=["users"])


@router.get("/profile", response_model=UserProfile)
async def get_profile(user_uid: str = Depends(get_current_user)):
    """Fetch the current user's profile (liked/disliked + preferences)."""
    profile = get_user_profile(user_uid)
    return UserProfile(
        liked=profile.get("liked", []),
        disliked=profile.get("disliked", []),
        preferences=UserPreferences(**profile.get("preferences", {}))
        if profile.get("preferences")
        else UserPreferences(),
    )


@router.put("/preferences")
async def update_preferences(
    prefs: UserPreferences,
    user_uid: str = Depends(get_current_user),
):
    """Save the current user's dietary preferences."""
    save_user_preferences(user_uid, prefs.model_dump())
    return {"success": True}


@router.put("/rating")
async def update_rating(
    rating: RatingUpdate,
    user_uid: str = Depends(get_current_user),
):
    """Update a recipe rating (like/dislike/remove)."""
    update_recipe_rating(user_uid, rating.recipe_uid, rating.rating_type)
    return {"success": True}
