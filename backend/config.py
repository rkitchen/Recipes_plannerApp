"""
Application configuration loaded from environment variables.
Uses Pydantic Settings for validation and type coercion.
"""

import json
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """All configuration is read from environment variables or a .env file."""

    # Firebase Admin SDK — provide EITHER a file path OR an inline JSON string
    FIREBASE_SERVICE_ACCOUNT_PATH: Optional[str] = None
    FIREBASE_SERVICE_ACCOUNT_JSON: Optional[str] = None

    # Gemini API
    GEMINI_API_KEY: str = ""

    # CORS — comma-separated origins
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Server
    PORT: int = 8080

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def firebase_credentials(self) -> dict | str:
        """Return parsed service account info for firebase_admin.credentials.Certificate."""
        if self.FIREBASE_SERVICE_ACCOUNT_JSON:
            return json.loads(self.FIREBASE_SERVICE_ACCOUNT_JSON)
        if self.FIREBASE_SERVICE_ACCOUNT_PATH:
            return self.FIREBASE_SERVICE_ACCOUNT_PATH
        raise ValueError(
            "Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_SERVICE_ACCOUNT_JSON"
        )

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
