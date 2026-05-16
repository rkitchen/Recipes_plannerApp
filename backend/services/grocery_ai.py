"""
Grocery list AI — uses Gemini to consolidate, de-duplicate, and categorise
a raw ingredient list into supermarket aisles.
"""

import json
from services.gemini import get_client


GROCERY_PROMPT = """You are a smart grocery list assistant.

I will give you:
1. A list of raw ingredient lines extracted from multiple recipes.
2. A list of pantry staples that the user already has at home.

Your job:
1. **Remove** any ingredient the user already has (pantry staples). Be smart about matching — "olive oil" matches "extra virgin olive oil", "salt" matches "kosher salt", etc.
2. **Consolidate** duplicate ingredients across recipes. Combine quantities where possible (e.g., "1 onion" + "2 onions" → "3 onions"). If quantities use different units or are vague, list the total sensibly (e.g., "½ cup + 2 tbsp butter" → "¾ cup butter").
3. **Categorise** the remaining items into standard supermarket aisles.

Return STRICT valid JSON only, matching this exact schema:
{
  "categories": [
    {
      "name": "AISLE_NAME",
      "items": [
        {"name": "ingredient name", "quantity": "consolidated amount", "checked": false}
      ]
    }
  ]
}

Use these aisle categories (omit any that have zero items):
- Produce
- Dairy & Eggs
- Meat & Seafood
- Bakery
- Pantry & Canned
- Frozen
- Condiments & Sauces
- Beverages
- Other

Sort items alphabetically within each category. Do NOT include any explanation, only the JSON."""


def generate_grocery_list(ingredient_blocks: list[str], pantry_staples: str) -> dict:
    """
    Takes raw ingredient text blocks (one per recipe) and pantry staples string,
    sends to Gemini, and returns the parsed categorised grocery list.
    """
    client = get_client()

    all_ingredients = "\n\n".join(ingredient_blocks)

    user_message = (
        f"PANTRY STAPLES (user already has these):\n{pantry_staples}\n\n"
        f"RAW INGREDIENTS FROM RECIPES:\n{all_ingredients}"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[GROCERY_PROMPT, user_message],
    )

    raw = response.text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]

    return json.loads(raw.strip())
