"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    # LLM (OpenAI-compatible)
    openai_api_key: str = ""
    openai_api_base: str = "https://api.deepseek.com/v1"
    openai_model: str = "deepseek-chat"
    llm_timeout: float = 120.0

    # PostgreSQL
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "water_info"
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    db_command_timeout: float = 30.0

    # Weather (和风天气, optional)
    weather_api_key: str = ""
    default_weather_location: str = "101010100"

    # Water Platform (Spring Boot)
    water_platform_base_url: str = "http://localhost:8080"
    water_platform_username: str = "admin"
    water_platform_password: str = "admin123"

    # Service
    host: str = "0.0.0.0"
    port: int = 8100
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_api_base=os.environ.get("OPENAI_API_BASE", "https://api.deepseek.com/v1"),
        openai_model=os.environ.get("OPENAI_MODEL", "deepseek-chat"),
        llm_timeout=float(os.environ.get("LLM_TIMEOUT", "120")),
        pg_host=os.environ.get("PG_HOST", "localhost"),
        pg_port=int(os.environ.get("PG_PORT", "5432")),
        pg_database=os.environ.get("PG_DATABASE", "water_info"),
        pg_user=os.environ.get("PG_USER", "postgres"),
        pg_password=os.environ.get("PG_PASSWORD", "postgres"),
        db_command_timeout=float(os.environ.get("DB_COMMAND_TIMEOUT", "30")),
        weather_api_key=os.environ.get("WEATHER_API_KEY", ""),
        default_weather_location=os.environ.get("DEFAULT_WEATHER_LOCATION", "101010100"),
        water_platform_base_url=os.environ.get("WATER_PLATFORM_BASE_URL", "http://localhost:8080"),
        water_platform_username=os.environ.get("WATER_PLATFORM_USERNAME", "admin"),
        water_platform_password=os.environ.get("WATER_PLATFORM_PASSWORD", "admin123"),
        host=os.environ.get("AI_SERVICE_HOST", "0.0.0.0"),
        port=int(os.environ.get("AI_SERVICE_PORT", "8100")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
