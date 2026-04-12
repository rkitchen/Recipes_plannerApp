# ✨ Intelligent Agentic Meal Planner

A stateful, AI-powered Streamlit web application that acts as your personal chef and meal planner. It uses the **Gemini 2.5 Pro & Flash** models to visually parse photos of your fridge/pantry, cross-reference your available ingredients with your `.paprikarecipes` library (stored locally or in Firestore), and dynamically generate a 5-day weekly meal plan tailored to your dietary goals.

---

## 🚀 Features

*   **📸 Vision-Powered Inventory:** Upload photos or use your device camera to snap pictures of your fridge or pantry. The app uses Gemini Vision to instantly extract an ingredient list with approximate quantities.
*   **🧠 Intelligent Generation:** Gemini Pro acts as an agentic planner, selecting recipes from your library that prioritize your fresh ingredients while filling in the gaps to create a balanced week.
*   **📆 Infinite Week Carousel:** Navigate forward and backward in time. The app defaults to showing the *current* week (if Mon-Fri) or anticipates the *next* week (if Sat-Sun).
*   **🔀 Smart Meal Replacements:** Don't like a suggested meal? Give the agent constraints (e.g., *"Make it vegetarian"*), and it will execute a database-backed replacement that permanently swaps the recipe in your schedule without duplicating meals you've already eaten this week.
*   **⭐ Personal Profiles & Ratings:** 
    *   Set per-user dietary goals (calories, meal structure, constraints).
    *   Rate recipes with 👍 or 👎. 
    *   Disliked recipes are permanently banned from future generations.
    *   Liked recipes are injected into the agent's prompt to bias future generations towards your favorites.
*   **☁️ Firestore Backed:** User profiles, historical meal plans, and the entire recipe library can be safely persisted in a cloud database.

---

## 📂 Project Architecture

To ensure high maintainability, the application logic is split into strict, single-responsibility modules:

| Module | Responsibility |
|:---|:---|
| `app.py` | The main entry point. Handles the top-level Streamlit layouts, sidebar configuration, CSS styling, and tab/carousel rendering. |
| `components.py` | The complex UI widgets. Houses the `@st.dialog` popup for scanning ingredients/generating menus, and the interactive `render_recipe_card` with rating logic. |
| `db.py` | The Data layer. Manages all `firebase-admin` connections, reads/writes to user profiles, and executes transactional updates to meal plans. |
| `recipe.py` | The Recipe engine. Handles loading recipes from `.paprikarecipes` zip archives or the cloud, matching ingredient strings, and extracting images. |
| `auth.py` | Security. Contains the master password gate that runs before the app executes. |
| `utils.py` | Assorted pure-Python helper functions like datetime manipulation for the calendar carousel. |

---

## 🛠️ Setup & Installation

### Requirements
*   Python **3.10+** (Recommended: 3.12, as pinned in `.python-version`)
*   `uv` (or `pip`)

### 1. Install Dependencies
Using `uv`:
```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. Configure Secrets
Create `.streamlit/secrets.toml` in the project root:

```toml
# Security Gate
APP_PASSWORD = "your-password"

# Gemini API
GEMINI_API_KEY = "AIzaSy..."

# Users List (add IDs as keys and Display Names as values)
[users]
user_becky = "Becky C"
user_rob = "Rob K"

# Firestore Service Account (Optional but recommended)
[firebase]
type = "service_account"
project_id = "meal-planner..."
private_key = "-----BEGIN PRIVATE KEY..."
client_email = "..."
# ... etc
```

### 3. Provide Recipe Data
*   **Cloud (Firebase):** Sync your recipes up to a `recipes` Firestore collection.
*   **Local (Fallback):** Place exported `.paprikarecipes` archive files in a folder named `Data/` in the project root. The app will automatically read them if Firestore is unreachable.

### 4. Run the App
```bash
streamlit run app.py
```
*(On first load with Firestore, you may be prompted in the UI to click a link to generate a needed Composite Index for the meal plan history).*
