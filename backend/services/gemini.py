"""
Gemini service — wraps the Google GenAI client for meal plan generation and replacement.
Prompt logic ported from the Streamlit components.py.
"""

import json
import re
from google import genai
from google.genai import types
from config import get_settings

_client = None


def init_gemini() -> None:
    """Initialise the Gemini client. Call once at app startup."""
    global _client
    settings = get_settings()
    if settings.GEMINI_API_KEY:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)


def get_client() -> genai.Client:
    if _client is None:
        init_gemini()
    return _client


def _parse_json_response(text: str) -> list | dict:
    """Strip markdown fences and parse JSON from an LLM response."""
    raw = text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


def generate_meal_plan(
    recipes: list[dict],
    inventory: str,
    liked_names: list[str],
    disliked_names: list[str] | None = None,
    meal_type: str = "Main Only",
    calories_goal: int = 2000,
    nutrition_info: str = "",
    meal_plan_notes: str = "",
) -> list[dict]:
    """
    Generate a 5-day meal plan using Gemini 2.5 Pro.
    Returns a list of {day, recipe_uid, reasoning} dicts.
    """
    client = get_client()

    liked_injection = ""
    if liked_names:
        liked_injection = (
            f"\nFavourite recipes: {', '.join(liked_names)}. "
            "Try and include a recipe that is similar to one of these if possible."
        )

    disliked_injection = ""
    if disliked_names:
        disliked_injection = (
            f"\nDisliked recipes (NEVER suggest these): {', '.join(disliked_names)}."
        )

    notes_injection = ""
    if meal_plan_notes:
        notes_injection = f"\nUser preferences: {meal_plan_notes}"

    slim = [{"uid": r["uid"], "name": r["name"], "prep_time": r.get("prep_time", "")} for r in recipes]

    system_instruction = f"""You are an intelligent and creative personal chef. You are acting as an agentic meal planner.

Inventory:
{inventory}
{liked_injection}
{disliked_injection}
{notes_injection}

Constraints:
- Structure: {meal_type}
- Target: {calories_goal} kcal/day
- Other criteria: {nutrition_info}

Rules:
- You MUST only select recipes from the provided recipe list below — do not invent recipes.
- Prioritise using the fresh ingredients before they spoil; supplement with pantry staples and additional ingredients as needed.
- The user can easily purchase meat or fish despite not appearing in the inventory.
- Ensure variety across the week: avoid repeating proteins, cuisines, or cooking styles on consecutive days.
- Each day's "reasoning" should briefly explain why the recipe was chosen (e.g. which fresh ingredients it uses).

Task:
Output a 5-day weekday meal plan (Monday to Friday).
Output STRICT valid JSON ONLY — no markdown, no commentary. Format:
[ {{"day": "Monday", "recipe_uid": "UID", "reasoning": "Brief reason"}}, ... ]
"""

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[system_instruction, "Recipes:\n" + json.dumps(slim)],
    )
    return _parse_json_response(response.text)


def replace_meal(
    original_name: str,
    day_name: str,
    inventory: str,
    guidance: str,
    excluded_uids: list[str],
    candidate_recipes: list[dict],
) -> dict:
    """
    Generate a replacement meal for a specific day.
    Returns a single {day, recipe_uid, reasoning} dict.
    """
    client = get_client()

    slim = [{"uid": r["uid"], "name": r["name"]} for r in candidate_recipes if r["uid"] not in excluded_uids]

    prompt = (
        f"The user rejected '{original_name}' for {day_name}.\n"
        f"Inventory: {inventory}\nConstraints: {guidance}\n"
        f"EXCLUDE these UIDs: {', '.join(excluded_uids)}\n"
        f'Return ONLY one JSON object: {{"day": "{day_name}", "recipe_uid": "...", "reasoning": "..."}}'
    )

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[prompt, json.dumps(slim)],
    )
    return _parse_json_response(response.text)


def call_gemini(prompt: str, data: str, model: str = "gemini-2.5-flash") -> str:
    """Generic Gemini call. Returns raw text response."""
    client = get_client()
    response = client.models.generate_content(
        model=model,
        contents=[prompt, data],
    )
    return response.text

def extract_ingredients_from_image(image_bytes: bytes, mime_type: str) -> str:
    """
    Sends an image to Gemini Vision to extract a comma-separated list of ingredients.
    """
    client = get_client()
    prompt = (
        "Analyze these images. List all identifiable ingredients WITH approximate quantities. "
        "Return ONLY a comma-separated list, e.g.: 2 apples, 1/2 gallon milk."
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
    )
    return response.text.strip()
