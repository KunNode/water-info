"""Tests for platform client URL construction."""

from __future__ import annotations

from app.services.platform_client import WaterPlatformClient


def test_build_url_includes_api_prefix():
    client = WaterPlatformClient()

    assert client._build_url("/auth/login") == "http://localhost:8080/api/v1/auth/login"
    assert client._build_url("alarms/123/ack") == "http://localhost:8080/api/v1/alarms/123/ack"
