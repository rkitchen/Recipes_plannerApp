"""
Grocery list router — generate a smart, categorised shopping list.
"""

from fastapi import APIRouter, Depends, HTTPException
from middleware.auth import get_current_user
from models import GroceryListRequest, GroceryListResponse, GroceryCategory, GroceryItem
from services.firestore import get_recipe_ingredients_batch
from services.grocery_ai import generate_grocery_list

router = APIRouter(prefix="/api/grocery-list", tags=["grocery"])


@router.post("", response_model=GroceryListResponse)
async def create_grocery_list(
    req: GroceryListRequest,
    user_uid: str = Depends(get_current_user),
):
    """
    Generate a smart grocery list from a set of recipe UIDs.
    
    1. Fetches ingredient strings from Firestore for each recipe UID
    2. Sends them to Gemini along with the user's pantry staples
    3. Returns a consolidated, categorised shopping list
    """
    if not req.recipe_uids:
        raise HTTPException(400, "At least one recipe_uid is required")

    # Fetch raw ingredients from Firestore
    ingredient_blocks = get_recipe_ingredients_batch(req.recipe_uids)

    if not ingredient_blocks:
        raise HTTPException(
            404,
            "No ingredients found for the provided recipe UIDs",
        )

    try:
        result = generate_grocery_list(ingredient_blocks, req.pantry_staples)
    except Exception as e:
        raise HTTPException(500, f"AI grocery list generation failed: {e}")

    # Validate / coerce into response model
    categories = []
    for cat in result.get("categories", []):
        items = [
            GroceryItem(
                name=item.get("name", ""),
                quantity=item.get("quantity", ""),
                checked=False,
            )
            for item in cat.get("items", [])
        ]
        if items:
            categories.append(GroceryCategory(name=cat.get("name", "Other"), items=items))

    return GroceryListResponse(categories=categories)
