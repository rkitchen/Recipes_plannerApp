# ✨ Intelligent Agentic Meal Planner

A stateful, full-stack AI web application that acts as your personal chef and meal planner. Built with a **FastAPI** backend and a **Next.js Progressive Web App (PWA)** frontend, it uses **Gemini 2.5 Pro & Flash** models to visually parse photos of your fridge/pantry, cross-reference available ingredients with your recipe library, and dynamically generate a 5-day weekly meal plan tailored to your dietary goals.

---

## 🚀 Features

*   **📸 Vision-Powered Inventory:** Upload photos or use your device camera to snap pictures of your fridge or pantry. The app uses Gemini Vision to instantly extract an ingredient list with approximate quantities.
*   **🧠 Intelligent Generation:** Gemini Pro acts as an agentic planner, selecting recipes from your library that prioritize your fresh ingredients while filling in the gaps to create a balanced week.
*   **🛒 AI Grocery Lists (Cross-Device Sync):** Generate smart, categorised grocery lists directly from your meal plan and pantry staples. Ticked items instantly sync to the cloud, allowing you to plan on your laptop and shop with your phone!
*   **🔐 Secure Authentication:** Fully integrated with **Firebase Authentication**, replacing insecure hardcoded passwords with a robust, per-user email/password login system. New users are automatically provisioned with a secure database profile upon first login.
*   **📆 Infinite Week Carousel:** Navigate forward and backward in time. The app defaults to showing the *current* week (if Mon-Fri) or anticipates the *next* week (if Sat-Sun).
*   **🔀 Smart Meal Replacements:** Don't like a suggested meal? Give the agent constraints (e.g., *"Make it vegetarian"*), and it will execute a database-backed replacement that permanently swaps the recipe in your schedule without duplicating meals you've already eaten this week.
*   **⭐ Personal Profiles & Ratings:** 
    *   Set per-user dietary goals (calories, meal structure, constraints).
    *   Rate recipes with 👍 or 👎. 
    *   Disliked recipes are permanently banned from future generations.
    *   Liked recipes are injected into the agent's prompt to bias future generations towards your favorites.
*   **☁️ Firestore Backed:** User profiles, grocery lists, historical meal plans, and the entire recipe library are safely persisted in a cloud database.

---

## 📂 Project Architecture

The application has been refactored from a monolithic Streamlit app into a modern, decoupled full-stack architecture:

### 🐍 Backend (`/backend`)
A high-performance REST API built with **FastAPI** (Python 3.12).
*   **Auth Middleware:** Intercepts Firebase ID Tokens from the frontend and securely verifies them using the Firebase Admin SDK.
*   **AI Services:** Connects directly to the Google GenAI SDK for rapid prompt execution.
*   **Database Services:** Manages all secure reads/writes to Firestore collections (`users`, `meal_plans`, `recipes`, `grocery_lists`).
*   **Deployment:** Containerised via Docker and deployed serverlessly to **Google Cloud Run**.

### ⚛️ Frontend (`/frontend`)
A sleek, responsive Progressive Web App built with **Next.js 15**, **React**, and **TypeScript**.
*   **PWA Ready:** Can be installed directly to your phone's home screen via Safari/Chrome for a native app experience.
*   **Design System:** Custom CSS (no external CSS frameworks) with a focus on glassmorphism, smooth micro-animations, and a responsive mobile-first layout.
*   **Client-Side Auth:** Manages login state via the Firebase Client SDK.
*   **Deployment:** Optimised and deployed seamlessly to **Firebase App Hosting**.

---

## 🛠️ Local Development Setup

To run the application locally, you will need to start both the backend server and the frontend development server.

### 1. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Configure Backend Secrets:**
Create a `.env` file in the `/backend` directory based on `.env.example`:
```env
GEMINI_API_KEY="AIzaSy..."
ALLOWED_ORIGINS="http://localhost:3000"
FIREBASE_SERVICE_ACCOUNT_JSON="<base64-encoded-string>" 
```

*Note: Because raw JSON can be tricky in environment variables (especially in GitHub Secrets), you must Base64-encode your downloaded Firebase Service Account JSON file. You can do this easily with the provided script:*
```bash
python scripts/encode_firebase_secret.py config/meal-planner-db-37b16-7402a4c6938b.json
# Copy the resulting Base64 string into your .env file or GitHub Secrets
```

**Run the Backend:**
```bash
fastapi dev main.py --port 8080
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

**Configure Frontend Secrets:**
Create a `.env.local` file in the `/frontend` directory:
```env
# Point to your local FastAPI backend
NEXT_PUBLIC_API_URL=http://localhost:8080

# Your public Firebase Client Config
NEXT_PUBLIC_FIREBASE_API_KEY="AIzaSy..."
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="..."
NEXT_PUBLIC_FIREBASE_PROJECT_ID="..."
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="..."
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="..."
NEXT_PUBLIC_FIREBASE_APP_ID="..."
```

**Run the Frontend:**
```bash
npm run dev
```

Visit `http://localhost:3000` in your browser.

---

## 🚢 Deployment

*   **Backend:** Automatically deployed to **Google Cloud Run** via GitHub Actions whenever changes are pushed to the `main` branch affecting the `/backend` directory. (See `.github/workflows/deploy-backend.yml`).
*   **Frontend:** Automatically built and deployed by **Firebase App Hosting** when changes are merged to `main`. Ensure all public environment variables are configured in the Firebase Console App Hosting dashboard, or via a `.env.production` file.
