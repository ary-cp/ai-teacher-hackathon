"""Central configuration. Everything is env-driven so the demo box and the
judge's laptop behave identically."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""
    groq_model_teach: str = "llama-3.3-70b-versatile"
    groq_model_fast: str = "llama-3.1-8b-instant"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    chroma_dir: str = "./data/chroma"
    upload_dir: str = "./data/uploads"
    audio_dir: str = "./data/audio"

    chunk_size: int = 1100
    chunk_overlap: int = 180
    retrieve_k: int = 6

    cors_origins: str = "http://localhost:3000"

    # --- derived helpers ---
    @property
    def chroma_path(self) -> Path:
        return self._abs(self.chroma_dir)

    @property
    def upload_path(self) -> Path:
        return self._abs(self.upload_dir)

    @property
    def audio_path(self) -> Path:
        return self._abs(self.audio_dir)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @staticmethod
    def _abs(p: str) -> Path:
        path = Path(p)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
