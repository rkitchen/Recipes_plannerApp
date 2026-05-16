"""
FastAPI application entry point.

Initialises Firebase Admin SDK and Gemini client at startup,
configures CORS, and mounts all API routers.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from services.firestore import init_firebase
from services.gemini import init_gemini


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init Firebase + Gemini. Shutdown: nothing special."""
    init_firebase()
    init_gemini()
    yield


app = FastAPI(
    title="Meal Planner API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────
from routers.recipes import router as recipes_router
from routers.meal_plans import router as meal_plans_router
from routers.grocery import router as grocery_router
from routers.users import router as users_router

app.include_router(recipes_router)
app.include_router(meal_plans_router)
app.include_router(grocery_router)
app.include_router(users_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
