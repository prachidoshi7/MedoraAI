"""
MedoraAI — Application Configuration
Loads settings from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Application ---
    APP_NAME: str = "MedoraAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "info"

    # --- Security ---
    SECRET_KEY: str = "medoraai-hackathon-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 8

    # --- Database ---
    DATA_DIR: str = Field(default="./data", description="Root directory for runtime data")

    # --- ML Models ---
    CHEST_MODEL_PATH: Optional[str] = Field(
        default=None,
        description="Path to fine-tuned chest X-ray model weights (.pt). If None, uses timm pretrained."
    )
    BRAIN_MODEL_PATH: Optional[str] = Field(
        default=None,
        description="Path to brain tumor model (.keras). EfficientNetB3 4-class classifier."
    )

    # --- LLM API Keys (try in order: Gemini → Groq → Claude → OpenAI → template fallback) ---
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for multimodal image-aware reports"
    )
    GEMINI_MODEL: str = Field(
        default="gemini-3-flash-preview",
        description="Preferred Gemini model for image-aware reports"
    )
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="Groq API key for Llama 3.1 (fastest, free tier available)"
    )
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude 3 Haiku"
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for GPT-4o-mini"
    )

    # --- Demo User ---
    DEMO_USER: str = "demo"
    DEMO_PASSWORD: str = "demo123"

    # --- Server ---
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # --- File Upload ---
    MAX_FILE_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: list[str] = [".png", ".jpg", ".jpeg", ".dcm"]

    model_config = {
        "env_file": ("../.env", ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @property
    def database_url(self) -> str:
        db_path = os.path.join(self.DATA_DIR, "app.db")
        return f"sqlite:///{db_path}"

    @property
    def uploads_dir(self) -> str:
        return os.path.join(self.DATA_DIR, "uploads")

    @property
    def heatmaps_dir(self) -> str:
        return os.path.join(self.DATA_DIR, "heatmaps")

    @property
    def thumbnails_dir(self) -> str:
        return os.path.join(self.DATA_DIR, "thumbnails")

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    def has_llm_key(self) -> bool:
        """Check if any LLM API key is configured."""
        return bool(self.GEMINI_API_KEY or self.GROQ_API_KEY or self.ANTHROPIC_API_KEY or self.OPENAI_API_KEY)

    def get_llm_provider_name(self) -> str:
        """Return the name of the first available LLM provider."""
        if self.GEMINI_API_KEY:
            return "gemini"
        elif self.GROQ_API_KEY:
            return "groq"
        elif self.ANTHROPIC_API_KEY:
            return "claude"
        elif self.OPENAI_API_KEY:
            return "openai"
        return "template"

    def resolve_path(self, path: Optional[str]) -> Optional[str]:
        """Resolve relative repo paths regardless of the backend working directory."""
        if not path:
            return None
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(PROJECT_ROOT, path))

    @property
    def chest_model_path(self) -> Optional[str]:
        return self.resolve_path(self.CHEST_MODEL_PATH)

    @property
    def brain_model_path(self) -> Optional[str]:
        return self.resolve_path(self.BRAIN_MODEL_PATH)


# Singleton instance
settings = Settings()
