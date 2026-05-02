"""Tests for optional LangGraph Postgres persistence configuration."""

from __future__ import annotations

from app.config import get_settings
from app.langgraph_persistence import _build_conn_string


def test_langgraph_postgres_flag_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("LANGGRAPH_POSTGRES_ENABLED", raising=False)
    get_settings.cache_clear()

    try:
        assert get_settings().langgraph_postgres_enabled is False
    finally:
        get_settings.cache_clear()


def test_langgraph_postgres_connection_string_escapes_credentials(monkeypatch):
    monkeypatch.setenv("PG_USER", "root user")
    monkeypatch.setenv("PG_PASSWORD", "p@ss word")
    monkeypatch.setenv("PG_HOST", "postgres")
    monkeypatch.setenv("PG_PORT", "5432")
    monkeypatch.setenv("PG_DATABASE", "water info")
    get_settings.cache_clear()

    try:
        assert _build_conn_string() == "postgresql://root+user:p%40ss+word@postgres:5432/water+info?sslmode=disable"
    finally:
        get_settings.cache_clear()
