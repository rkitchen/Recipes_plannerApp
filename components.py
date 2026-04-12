import streamlit as st
import json
import base64
from PIL import Image
from datetime import datetime, timedelta
from typing import List

from db import update_recipe_rating, save_meal_plan, update_meal_plan_in_db
from recipe import get_recipe_image, filter_recipes

def render_recipe_card(recipe: dict, reason: str, idx: int, 
                       plan_doc_id: str, full_plan_data: list,
                       inventory_snapshot: str,
                       all_recipes: List[dict],
                       base_date_str: str,
                       client=None):
    
    uid = recipe.get("uid", "")
    day_name = recipe.get("_day", "Unknown")
    
    with st.container(border=True):
        col_img, col_info = st.columns([1, 4])
        
        with col_img:
            b64_image = get_recipe_image(recipe_uid=uid, archive_path=recipe.get("archive_path", ""), inner_path=recipe.get("inner_path", ""))
            if b64_image: st.image(base64.b64decode(b64_image), width="stretch")
            else: st.caption("No photo")

        with col_info:
            if recipe.get("source_url"): st.markdown(f"### [{recipe['name']}]({recipe['source_url']})")
            else: st.subheader(recipe["name"])
            st.caption(f"⏱️ Prep: {recipe.get('prep_time','N/A')}m | Cook: {recipe.get('cook_time','N/A')}m")
            if reason: st.write(f"**Why this?** {reason}")

            profile = st.session_state.user_profile
            is_liked = uid in profile.get("liked", [])
            is_disliked = uid in profile.get("disliked", [])
            user_id = st.session_state.current_user
            
            rcol1, rcol2, _ = st.columns([1, 1, 8])
            with rcol1:
                liked_label = "✅" if is_liked else "👍"
                if st.button(liked_label, key=f"lk_{uid}_{idx}_{plan_doc_id}"):
                    update_recipe_rating(user_id, uid, "remove_like" if is_liked else "like")
                    st.rerun()
            with rcol2:
                disliked_label = "❌" if is_disliked else "👎"
                if st.button(disliked_label, key=f"dk_{uid}_{idx}_{plan_doc_id}"):
                    update_recipe_rating(user_id, uid, "remove_dislike" if is_disliked else "dislike")
                    st.rerun()

            meal_date = datetime.strptime(base_date_str, "%Y-%m-%d") + timedelta(days=idx)
            today_date = datetime.now().date()
            is_past_meal = meal_date.date() < today_date
            
            if not is_past_meal and client:
                with st.expander("🔀 Replace this meal..."):
                    guidance = st.text_input("Constraints (e.g., 'Make it vegetarian'):", key=f"gd_{uid}_{idx}_{plan_doc_id}")
                    if st.button("Generate Alternative", key=f"rp_{uid}_{idx}_{plan_doc_id}"):
                        with st.spinner("Finding remote alternative..."):
                            disliked_uids = set(profile.get("disliked", []))
                            scheduled_uids = [p.get("recipe_uid", "") for p in full_plan_data]
                            excluded = set(scheduled_uids) | disliked_uids
                            
                            filtered = filter_recipes(all_recipes, inventory_snapshot, 150)
                            slim = [{"uid": r["uid"], "name": r["name"]} for r in filtered if r["uid"] not in excluded]
                            
                            prompt = (f"The user rejected '{recipe['name']}' for {day_name}.\n"
                                      f"Inventory: {inventory_snapshot}\nConstraints: {guidance}\n"
                                      f"EXCLUDE these UIDs: {', '.join(f'{u}' for u in excluded)}\n"
                                      f"Return ONLY one JSON object: {{\"day\": \"{day_name}\", \"recipe_uid\": \"...\", \"reasoning\": \"...\"}}")
                            try:
                                resp = client.models.generate_content(model="gemini-2.5-pro", contents=[prompt, json.dumps(slim)])
                                r_text = resp.text.strip()
                                if r_text.startswith("```json"): r_text = r_text[7:-3]
                                elif r_text.startswith("```"): r_text = r_text[3:-3]
                                
                                new_meal_node = json.loads(r_text.strip())
                                full_plan_data[idx] = new_meal_node
                                update_meal_plan_in_db(plan_doc_id, full_plan_data)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to find alternative: {e}")
            elif is_past_meal:
                st.caption("*(Meals in the past cannot be replaced)*")


@st.dialog("🪄 Plan Menu for the Week")
def plan_week_dialog(monday_date_str: str, all_recipes: List[dict], client, pantry_staples: List[str], meal_type: str, calories_goal: int, nutrition_info: str):
    st.write(f"Generating a menu for the week starting **{monday_date_str}**.")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_files = st.file_uploader("Upload Fridge Photos 📸", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    with col2:
        camera_photo = st.camera_input("Take a picture! 📱")

    all_photos = list(uploaded_files or [])
    if camera_photo: all_photos.append(camera_photo)

    if all_photos and not st.session_state.photos_analyzed:
        with st.spinner("🤖 Analyzing your groceries with Gemini Vision..."):
            try:
                images = [Image.open(f) for f in all_photos]
                prompt = ("Analyze these images. List all identifiable ingredients WITH approximate quantities. "
                          "Return ONLY a comma-separated list, e.g.: 2 apples, 1/2 gallon milk.")
                resp = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt] + images)
                st.session_state.parsed_ingredients = resp.text
                st.session_state.photos_analyzed = True
            except Exception as e:
                st.error(f"Vision parsing error: {e}")

    editable_ingredients = st.text_area("Edit your fresh ingredients (comma-separated):", 
                                        value=st.session_state.parsed_ingredients, height=100)
    
    if st.button("🚀 Generate Menu", use_container_width=True):
        st.session_state.parsed_ingredients = editable_ingredients
        with st.spinner("🧠 Designing menu..."):
            user_profile = st.session_state.user_profile
            disliked_uids = set(user_profile.get("disliked", []))
            liked_uids = user_profile.get("liked", [])

            filtered_library = [r for r in all_recipes if r["uid"] not in disliked_uids]
            
            inventory_payload = f"Fresh Ingredients: {editable_ingredients}\nAssumed staples: {', '.join(pantry_staples)}"
            filtered_recipes = filter_recipes(filtered_library, inventory_payload, max_recipes=150)
            slim_recipes = [{"uid": r["uid"], "name": r["name"], "prep_time": r["prep_time"]} for r in filtered_recipes]
            
            liked_names = [r["name"] for r in all_recipes if r["uid"] in liked_uids]
            liked_injection = f"\nThe user loves these: {', '.join(liked_names)}. Prioritize matching ingredients to these if possible." if liked_names else ""
            
            system_instruction = f'''You are an intelligent, agentic meal planner.
Inventory:
{inventory_payload}
{liked_injection}

Constraints:
- Structure: {meal_type}
- Target: {calories_goal} kcal
- Other criteria: {nutrition_info}

Task: Output a 5-day weekday meal plan (Monday to Friday). Focus on the inventory but include meats/other ingredients.
Output STRICT valid JSON ONLY. Format:
[ {{"day": "Monday", "recipe_uid": "UID", "reasoning": "Brief reason"}}, ... ]'''

            try:
                response = client.models.generate_content(model="gemini-2.5-pro", contents=[system_instruction, "Recipes:\n" + json.dumps(slim_recipes)])
                raw_text = response.text.strip()
                if raw_text.startswith("```json"): raw_text = raw_text[7:-3]
                elif raw_text.startswith("```"): raw_text = raw_text[3:-3]
                
                new_plan = json.loads(raw_text.strip())
                save_meal_plan(
                    user_id=st.session_state.current_user,
                    week_start=monday_date_str,
                    inventory=inventory_payload,
                    plan_data=new_plan
                )
                
                st.session_state.parsed_ingredients = ""
                st.session_state.photos_analyzed = False
                st.rerun()
            except Exception as e:
                st.error(f"Generation error: {e}")
