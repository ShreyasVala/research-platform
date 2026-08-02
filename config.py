# config.py
# Shared application, LLM API, and storage settings.

from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import AsyncOpenAI


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM API
    openai_api_key: str = ""
    supervisor_model: str = "gpt-4o"
    worker_model: str = "gpt-4o-mini"

    # Search
    tavily_api_key: str = ""

    # App
    app_port: int = 8000
    max_concurrent_workers: int = 3
    max_search_results: int = 5
    reports_dir: str = "./reports"
    uploads_dir: str = "./uploads"
    state_dir: str = "./state"
    storage_backend: str = "local"  # local or s3
    aws_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_prefix: str = "research-platform"

    def make_llm_client(self) -> AsyncOpenAI:
        # A placeholder keeps offline tests importable; real calls require a valid key.
        return AsyncOpenAI(api_key=self.openai_api_key or "not-configured")

    def ensure_dirs(self):
        # Creates uploads/, reports/, state/ if they don't exist
        for d in [self.reports_dir, self.uploads_dir, self.state_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)


# lru_cache = only create Settings once, reuse it everywhere
@lru_cache()
def get_settings() -> Settings:
    return Settings()
