"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

try:
    from dotenv import load_dotenv
    load_dotenv()  # 本地运行时从 .env 文件加载；Docker 中已由 compose 注入，无副作用
except ImportError:
    pass


@dataclass
class Settings:
    # LLM (OpenAI-compatible)
    openai_api_key: str = ""
    openai_api_base: str = "https://api.deepseek.com/v1"
    openai_model: str = "deepseek-chat"
    llm_timeout: float = 120.0
    embedding_api_key: str = ""
    embedding_api_base: str = ""
    embedding_model: str = ""
    embedding_dim: int = 1024

    # PostgreSQL
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "water_info"
    pg_user: str = "postgres"
    pg_password: str = "postgres"
    db_command_timeout: float = 30.0

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""

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
    rag_top_k: int = 5
    rag_min_score: float = 0.25
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 80
    rag_max_calls_per_session: int = 2
    rag_preflight_risk_enabled: bool = False
    risk_scan_periodic_minutes: int = 15
    risk_scan_periodic_enabled: bool = True
    risk_scan_event_debounce_seconds: int = 60
    langgraph_postgres_enabled: bool = False

    # Platform Kernel Feature Flags (default-off for incremental rollout)
    structured_output_enabled: bool = False
    skill_registry_enabled: bool = False
    dispatch_state_machine_enabled: bool = False
    audit_tables_enabled: bool = False
    plan_reviewer_enabled: bool = False


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    openai_api_base = os.environ.get("OPENAI_API_BASE", "https://api.deepseek.com/v1")
    return Settings(
        openai_api_key=openai_api_key,
        openai_api_base=openai_api_base,
        openai_model=os.environ.get("OPENAI_MODEL", "deepseek-chat"),
        llm_timeout=float(os.environ.get("LLM_TIMEOUT", "120")),
        embedding_api_key=os.environ.get("EMBEDDING_API_KEY", openai_api_key),
        embedding_api_base=os.environ.get("EMBEDDING_API_BASE", openai_api_base),
        embedding_model=os.environ.get("EMBEDDING_MODEL", ""),
        embedding_dim=int(os.environ.get("EMBEDDING_DIM", "1024")),
        pg_host=os.environ.get("PG_HOST", "localhost"),
        pg_port=int(os.environ.get("PG_PORT", "5432")),
        pg_database=os.environ.get("PG_DATABASE", "water_info"),
        pg_user=os.environ.get("PG_USER", "postgres"),
        pg_password=os.environ.get("PG_PASSWORD", "postgres"),
        db_command_timeout=float(os.environ.get("DB_COMMAND_TIMEOUT", "30")),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        redis_password=os.environ.get("REDIS_PASSWORD", ""),
        weather_api_key=os.environ.get("WEATHER_API_KEY", ""),
        default_weather_location=os.environ.get("DEFAULT_WEATHER_LOCATION", "101010100"),
        water_platform_base_url=os.environ.get("WATER_PLATFORM_BASE_URL", "http://localhost:8080"),
        water_platform_username=os.environ.get("WATER_PLATFORM_USERNAME", "admin"),
        water_platform_password=os.environ.get("WATER_PLATFORM_PASSWORD", "admin123"),
        host=os.environ.get("AI_SERVICE_HOST", "0.0.0.0"),
        port=int(os.environ.get("AI_SERVICE_PORT", "8100")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        rag_top_k=int(os.environ.get("RAG_TOP_K", "5")),
        rag_min_score=float(os.environ.get("RAG_MIN_SCORE", "0.25")),
        rag_chunk_size=int(os.environ.get("RAG_CHUNK_SIZE", "500")),
        rag_chunk_overlap=int(os.environ.get("RAG_CHUNK_OVERLAP", "80")),
        rag_max_calls_per_session=int(os.environ.get("RAG_MAX_CALLS_PER_SESSION", "2")),
        rag_preflight_risk_enabled=os.environ.get("RAG_PREFLIGHT_RISK_ENABLED", "false").lower() == "true",
        risk_scan_periodic_minutes=int(os.environ.get("RISK_SCAN_PERIODIC_MINUTES", "15")),
        risk_scan_periodic_enabled=os.environ.get("RISK_SCAN_PERIODIC_ENABLED", "true").lower() == "true",
        risk_scan_event_debounce_seconds=int(os.environ.get("RISK_SCAN_EVENT_DEBOUNCE_SECONDS", "60")),
        langgraph_postgres_enabled=os.environ.get("LANGGRAPH_POSTGRES_ENABLED", "false").lower() == "true",
        structured_output_enabled=_env_bool("STRUCTURED_OUTPUT_ENABLED"),
        skill_registry_enabled=_env_bool("SKILL_REGISTRY_ENABLED"),
        dispatch_state_machine_enabled=_env_bool("DISPATCH_STATE_MACHINE_ENABLED"),
        audit_tables_enabled=_env_bool("AUDIT_TABLES_ENABLED"),
        plan_reviewer_enabled=_env_bool("PLAN_REVIEWER_ENABLED"),
    )
