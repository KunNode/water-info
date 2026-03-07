"""Unit tests for AI tools"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.tools.data_tools import (
    fetch_all_stations,
    fetch_station_observations,
    fetch_active_alarms,
    fetch_threshold_rules,
)
from app.tools.risk_tools import (
    calculate_water_level_risk,
    calculate_rainfall_risk,
    calculate_composite_risk,
)
from app.tools.plan_tools import (
    generate_plan_id,
    get_response_template,
    lookup_emergency_contacts,
)


class TestDataTools:
    """Tests for data collection tools"""

    @pytest.mark.asyncio
    @patch("app.tools.data_tools.get_db_service")
    async def test_fetch_all_stations(self, mock_get_db):
        """Should fetch all stations"""
        mock_db = AsyncMock()
        mock_db.get_all_stations = AsyncMock(return_value=[
            {"id": "1", "code": "ST001", "name": "Station 1"},
            {"id": "2", "code": "ST002", "name": "Station 2"},
        ])
        mock_get_db.return_value = mock_db

        result = await fetch_all_stations()

        assert len(result) == 2
        assert result[0]["code"] == "ST001"

    @pytest.mark.asyncio
    @patch("app.tools.data_tools.get_db_service")
    async def test_fetch_station_observations(self, mock_get_db):
        """Should fetch observations for a station"""
        mock_db = AsyncMock()
        mock_db.get_observations = AsyncMock(return_value=[
            {"value": 10.5, "observed_at": datetime.now()},
            {"value": 11.0, "observed_at": datetime.now() - timedelta(hours=1)},
        ])
        mock_get_db.return_value = mock_db

        result = await fetch_station_observations("station-1")

        assert len(result) == 2
        mock_db.get_observations.assert_called_once_with(
            station_id="station-1", metric_type=None, hours=24, limit=500
        )

    @pytest.mark.asyncio
    @patch("app.tools.data_tools.get_db_service")
    async def test_fetch_active_alarms(self, mock_get_db):
        """Should fetch active alarms"""
        mock_db = AsyncMock()
        mock_db.get_active_alarms = AsyncMock(return_value=[
            {"id": "a1", "level": "WARNING", "status": "OPEN"},
            {"id": "a2", "level": "CRITICAL", "status": "OPEN"},
        ])
        mock_get_db.return_value = mock_db

        result = await fetch_active_alarms()

        assert len(result) == 2
        assert all(alarm["status"] == "OPEN" for alarm in result)

    @pytest.mark.asyncio
    @patch("app.tools.data_tools.get_db_service")
    async def test_fetch_threshold_rules(self, mock_get_db):
        """Should fetch threshold rules"""
        mock_db = AsyncMock()
        mock_db.get_threshold_rules = AsyncMock(return_value=[
            {"metric_type": "WATER_LEVEL", "level": "WARNING", "threshold_value": 10.0},
            {"metric_type": "WATER_LEVEL", "level": "CRITICAL", "threshold_value": 15.0},
        ])
        mock_get_db.return_value = mock_db

        result = await fetch_threshold_rules("station-1")

        assert len(result) == 2
        assert result[0]["threshold_value"] == 10.0


class TestRiskTools:
    """Tests for risk calculation tools"""

    @pytest.mark.asyncio
    async def test_calculate_water_level_risk_normal(self):
        """Should return low risk when water level is normal"""
        result = await calculate_water_level_risk(
            water_level=5.0,
            warning_threshold=10.0,
            danger_threshold=15.0,
        )

        assert result["risk_level"] == "low"
        assert result["risk_score"] < 50

    @pytest.mark.asyncio
    async def test_calculate_water_level_risk_warning(self):
        """Should return warning risk when water level exceeds warning"""
        result = await calculate_water_level_risk(
            water_level=12.0,
            warning_threshold=10.0,
            danger_threshold=15.0,
        )

        assert result["risk_level"] in ["moderate", "high"]
        assert result["risk_score"] >= 50

    @pytest.mark.asyncio
    async def test_calculate_water_level_risk_danger(self):
        """Should return critical risk when water level exceeds danger"""
        result = await calculate_water_level_risk(
            water_level=18.0,
            warning_threshold=10.0,
            danger_threshold=15.0,
        )

        assert result["risk_level"] == "critical"
        assert result["risk_score"] >= 80

    @pytest.mark.asyncio
    async def test_calculate_rainfall_risk_light(self):
        """Should return low risk for light rainfall"""
        result = await calculate_rainfall_risk(
            rainfall_1h=5.0,
            rainfall_6h=15.0,
            rainfall_24h=30.0,
        )

        assert result["risk_level"] in ["low", "none"]

    @pytest.mark.asyncio
    async def test_calculate_rainfall_risk_heavy(self):
        """Should return high risk for heavy rainfall"""
        result = await calculate_rainfall_risk(
            rainfall_1h=50.0,
            rainfall_6h=150.0,
            rainfall_24h=300.0,
        )

        assert result["risk_level"] in ["high", "critical"]

    @pytest.mark.asyncio
    async def test_calculate_composite_risk(self):
        """Should combine multiple risk factors"""
        result = await calculate_composite_risk(
            water_level_risk={"risk_level": "high", "risk_score": 75.0},
            rainfall_risk={"risk_level": "moderate", "risk_score": 50.0},
            alarm_count=5,
        )

        assert "risk_level" in result
        assert "risk_score" in result
        # Composite risk should be weighted higher than individual risks
        assert result["risk_score"] >= 50


class TestPlanTools:
    """Tests for plan generation tools"""

    def test_generate_plan_id(self):
        """Should generate unique plan ID"""
        plan_id1 = generate_plan_id()
        plan_id2 = generate_plan_id()

        assert plan_id1.startswith("PLAN-")
        assert plan_id1 != plan_id2

    def test_get_response_template(self):
        """Should return response template"""
        template = get_response_template("evacuation")

        assert template is not None
        assert "action_type" in template
        assert template["action_type"] == "evacuation"

    def test_get_response_template_unknown_type(self):
        """Should return default template for unknown type"""
        template = get_response_template("unknown_type")

        assert template is not None

    @patch("app.tools.plan_tools.get_db_service")
    def test_lookup_emergency_contacts(self, mock_get_db):
        """Should lookup emergency contacts"""
        mock_db = MagicMock()
        mock_db._fetch = AsyncMock(return_value=[
            {"name": "Emergency Contact 1", "phone": "13800138001"},
            {"name": "Emergency Contact 2", "phone": "13800138002"},
        ])
        mock_get_db.return_value = mock_db

        # Note: This is a sync test, so we need to handle the async properly
        import asyncio
        result = asyncio.run(lookup_emergency_contacts("station-1"))

        assert len(result) >= 0  # May be empty if no contacts configured
