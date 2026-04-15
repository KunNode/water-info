"""应用配置"""

from __future__ import annotations

import sys
from contextvars import ContextVar
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


TRACE_ID_VAR: ContextVar[str] = ContextVar("trace_id", default="")


class Settings(BaseSettings):
    """全局配置，自动从 .env 加载"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- LLM ----
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # 本地模型 (可选)
    local_llm_base_url: str = ""
    local_llm_model: str = ""

    # ---- PostgreSQL ----
    pg_host: str = "47.104.64.17"
    pg_port: int = 5432
    pg_database: str = "water_info"
    pg_user: str = "root"
    pg_password: str = "123456"

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""

    # ---- LLM 超时与重试 ----
    llm_timeout: int = 60
    llm_max_retries: int = 2
    agent_timeout: int = 120
    db_command_timeout: int = 30

    # ---- 气象数据 ----
    weather_api_key: str = ""
    default_weather_location: str = "101010100"  # 和风天气城市 ID（默认北京）

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        )

    @property
    def pg_dsn_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        )

    # ---- FastAPI ----
    ai_service_host: str = "0.0.0.0"
    ai_service_port: int = 8100

    # ---- 水务平台后端 API ----
    water_platform_base_url: str = "http://localhost:8080"
    water_platform_username: str = "admin"
    water_platform_password: str = "admin123"

    # ---- LangSmith ----
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "water-info-ai"

    # ---- 日志配置 ----
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"

    @property
    def llm_base_url(self) -> str:
        return self.local_llm_base_url or self.openai_api_base

    @property
    def llm_model(self) -> str:
        return self.local_llm_model or self.openai_model


def configure_logging() -> None:
    """配置 Loguru 统一日志格式"""
    import os
    import uuid
    import io

    from loguru import logger

    def _inject_trace_id(record: dict) -> None:
        """为每条日志注入 trace_id，确保格式模板中该字段始终存在"""
        record["extra"].setdefault("trace_id", TRACE_ID_VAR.get() or uuid.uuid4().hex[:16])

    stdout_sink = sys.stdout
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except OSError:
            stdout_sink = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    # 移除默认处理器，注册全局 patcher
    logger.remove()
    logger.configure(extra={"trace_id": ""}, patcher=_inject_trace_id)

    settings = get_settings()

    if settings.log_format == "json":
        # Windows/sandbox 环境下开启 enqueue 会触发 multiprocessing 管道权限错误，
        # 这里统一使用同步输出，避免导入阶段就失败。
        logger.add(
            stdout_sink,
            format="{message}",
            serialize=True,
            level=settings.log_level,
            enqueue=False,
        )
    else:
        # 控制台格式输出（适合开发）
        # encoding="utf-8" 避免 Windows GBK 控制台 UnicodeEncodeError
        logger.add(
            stdout_sink,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | [<cyan>{extra[trace_id]}</cyan>] <level>{message}</level>",
            level=settings.log_level,
            encoding="utf-8",
            enqueue=False,
        )

    # 文件日志（确保目录存在）
    os.makedirs("logs", exist_ok=True)
    logger.add(
        "logs/ai-service.log",
        rotation="100 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[trace_id]} | {message}",
        level=settings.log_level,
        encoding="utf-8",
        enqueue=False,
    )

    logger.info(f"日志系统初始化完成, 格式: {settings.log_format}")


def get_trace_id() -> str:
    """获取当前 trace_id"""
    return TRACE_ID_VAR.get()


def set_trace_id(trace_id: str) -> None:
    """设置当前 trace_id"""
    TRACE_ID_VAR.set(trace_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
