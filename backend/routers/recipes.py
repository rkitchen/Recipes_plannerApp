"""
Recipes router — list all recipes and fetch individual recipe images.
"""

from fastapi import APIRouter, Depends, HTTPException
from middleware.auth import get_current_user
from models import RecipeSlim, RecipeDetail, RecipeImageResponse
from services.firestore import get_recipes, get_recipe_image, get_recipe_detail

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeSlim])
async def list_recipes(user_uid: str = Depends(get_current_user)):
    """Return all recipes (slim projection — no photo data)."""
    recipes = get_recipes()
    return [RecipeSlim(**r) for r in recipes]


@router.get("/{uid}", response_model=RecipeDetail)
async def recipe_detail(uid: str, user_uid: str = Depends(get_current_user)):
    """Return full recipe details for a single recipe."""
    detail = get_recipe_detail(uid)
    if not detail:
        raise HTTPException(404, f"Recipe {uid} not found")
    return RecipeDetail(**detail)


@router.get("/{uid}/image", response_model=RecipeImageResponse)
async def recipe_image(uid: str, user_uid: str = Depends(get_current_user)):
    """Return the base64 photo_data for a single recipe."""
    photo = get_recipe_image(uid)
    return RecipeImageResponse(uid=uid, photo_data=photo)
