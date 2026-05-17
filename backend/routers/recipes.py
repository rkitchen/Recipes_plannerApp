"""
Recipes router — list all recipes and fetch individual recipe images.
"""

import base64
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from PIL import Image
from middleware.auth import get_current_user
from models import RecipeSlim, RecipeDetail, RecipeImageResponse
from services.firestore import get_recipes, get_recipe_image, get_recipe_detail

router = APIRouter(prefix="/api/recipes", tags=["recipes"])

# In-memory thumbnail cache: (uid, size) -> base64 string
_thumb_cache: dict[tuple[str, int], str] = {}


def _make_thumbnail(photo_b64: str, size: int = 300) -> str:
    """Downsample a base64 JPEG to a square-ish thumbnail, return base64."""
    raw = base64.b64decode(photo_b64)
    img = Image.open(io.BytesIO(raw))
    img.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


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
async def recipe_image(
    uid: str,
    w: int = Query(default=0, ge=0, le=1200, description="Max width for thumbnail. 0 = full size."),
    user_uid: str = Depends(get_current_user),
):
    """Return the base64 photo_data for a single recipe, optionally down-sampled."""
    photo = get_recipe_image(uid)
    if not photo:
        return RecipeImageResponse(uid=uid, photo_data=None)

    # Full size requested (or no resize)
    if w == 0:
        return RecipeImageResponse(uid=uid, photo_data=photo)

    # Check cache
    cache_key = (uid, w)
    if cache_key in _thumb_cache:
        return RecipeImageResponse(uid=uid, photo_data=_thumb_cache[cache_key])

    # Generate thumbnail
    try:
        thumb = _make_thumbnail(photo, size=w)
        _thumb_cache[cache_key] = thumb
        return RecipeImageResponse(uid=uid, photo_data=thumb)
    except Exception:
        # Fallback to full size if thumbnailing fails
        return RecipeImageResponse(uid=uid, photo_data=photo)
