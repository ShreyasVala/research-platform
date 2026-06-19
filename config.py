# config.py
# Every other file imports settings from here.
# This is the ONLY place you set which LLM provider to use.
# Change LLM_PROVIDER in .env and the entire system switches.

from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from openai import AsyncOpenAI


class Settings(BaseSettings):
    # Read from .env file automatically
    llm_provider: str = "ollama"

    # Ollama (free, local)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_supervisor_model: str = "llama3.2"
    ollama_worker_model: str = "llama3.2"

    # OpenAI (paid, Phase 5 only)
    openai_api_key: str = ""
    openai_supervisor_model: str = "gpt-4o"
    openai_worker_model: str = "gpt-4o-mini"

    # Search
    tavily_api_key: str = ""

    # App
    app_port: int = 8000
    max_concurrent_workers: int = 3
    max_search_results: int = 5
    reports_dir: str = "./reports"
    uploads_dir: str = "./uploads"
    state_dir: str = "./state"

    class Config:
        env_file = ".env"          # reads your .env file
        env_file_encoding = "utf-8"

    # These pick the right model name based on which provider is active
    @property
    def supervisor_model(self) -> str:
        if self.llm_provider == "ollama":
            return self.ollama_supervisor_model
        return self.openai_supervisor_model

    @property
    def worker_model(self) -> str:
        if self.llm_provider == "ollama":
            return self.ollama_worker_model
        return self.openai_worker_model

    def make_llm_client(self) -> AsyncOpenAI:
        # Ollama speaks the OpenAI API format — same Python SDK works for both
        # You just point it at a different URL
        if self.llm_provider == "ollama":
            return AsyncOpenAI(
                base_url=self.ollama_base_url,
                api_key="ollama",  # Ollama ignores this value but the SDK needs it
            )
        return AsyncOpenAI(api_key=self.openai_api_key)

    def ensure_dirs(self):
        # Creates uploads/, reports/, state/ if they don't exist
        for d in [self.reports_dir, self.uploads_dir, self.state_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)


# lru_cache = only create Settings once, reuse it everywhere
@lru_cache()
def get_settings() -> Settings:
    return Settings()