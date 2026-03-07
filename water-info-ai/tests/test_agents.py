"""Unit tests for AI agents"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.agents.supervisor import SupervisorAgent
from app.agents.data_analyst import DataAnalystAgent
from app.agents.risk_assessor import RiskAssessorAgent
from app.agents.plan_generator import PlanGeneratorAgent
from app.state import FloodResponseState, RiskLevel, PlanStatus


class TestSupervisorAgent:
    """Tests for Supervisor Agent"""

    @pytest.mark.asyncio
    async def test_supervisor_routes_to_data_analyst_for_data_query(self):
        """Should route to data analyst when user asks for data"""
        agent = SupervisorAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "分析当前水情数据",
            "messages": [],
            "iteration": 0,
        }

        result = await agent.invoke(state)

        assert result["next_agent"] == "data_analyst"
        assert "data" in result.get("messages", [{}])[0].get("content", "").lower()

    @pytest.mark.asyncio
    async def test_supervisor_routes_to_plan_generator_for_plan_request(self):
        """Should route to plan generator when user asks for emergency plan"""
        agent = SupervisorAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "生成防洪应急预案",
            "messages": [],
            "iteration": 0,
        }

        result = await agent.invoke(state)

        assert result["next_agent"] == "plan_generator"

    @pytest.mark.asyncio
    async def test_supervisor_routes_to_risk_assessor_for_risk_query(self):
        """Should route to risk assessor when user asks about risk"""
        agent = SupervisorAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "评估洪水风险等级",
            "messages": [],
            "iteration": 0,
        }

        result = await agent.invoke(state)

        assert result["next_agent"] == "risk_assessor"


class TestDataAnalystAgent:
    """Tests for Data Analyst Agent"""

    @pytest.mark.asyncio
    @patch("app.agents.data_analyst.get_db_service")
    async def test_data_analyst_fetches_station_data(self, mock_get_db):
        """Should fetch station data from database"""
        mock_db = AsyncMock()
        mock_db.get_all_stations = AsyncMock(return_value=[
            {"id": "1", "code": "ST001", "name": "Station 1", "type": "WATER_LEVEL"}
        ])
        mock_get_db.return_value = mock_db

        agent = DataAnalystAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "获取站点数据",
            "messages": [],
            "iteration": 0,
        }

        result = await agent.invoke(state)

        assert "station_data" in result
        assert len(result["station_data"]) > 0

    @pytest.mark.asyncio
    @patch("app.agents.data_analyst.get_db_service")
    async def test_data_analyst_fetches_alarm_data(self, mock_get_db):
        """Should fetch active alarms"""
        mock_db = AsyncMock()
        mock_db.get_active_alarms = AsyncMock(return_value=[
            {"id": "a1", "level": "WARNING", "status": "OPEN", "message": "High water level"}
        ])
        mock_get_db.return_value = mock_db

        agent = DataAnalystAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "查看告警",
            "messages": [],
            "iteration": 0,
        }

        result = await agent.invoke(state)

        assert "alarm_data" in result


class TestRiskAssessorAgent:
    """Tests for Risk Assessor Agent"""

    @pytest.mark.asyncio
    async def test_risk_assessor_calculates_high_risk(self):
        """Should calculate high risk when thresholds exceeded"""
        agent = RiskAssessorAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "评估风险",
            "messages": [],
            "iteration": 0,
            "station_data": [
                {
                    "station_id": "1",
                    "station_name": "Test Station",
                    "water_level": 15.0,
                    "water_level_warning": 10.0,
                    "water_level_danger": 14.0,
                }
            ],
            "alarm_data": [
                {"level": "WARNING", "status": "OPEN"},
                {"level": "CRITICAL", "status": "OPEN"},
            ],
        }

        result = await agent.invoke(state)

        assert "risk_assessment" in result
        assert result["risk_assessment"].risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    @pytest.mark.asyncio
    async def test_risk_assessor_calculates_low_risk(self):
        """Should calculate low risk when all normal"""
        agent = RiskAssessorAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "评估风险",
            "messages": [],
            "iteration": 0,
            "station_data": [
                {
                    "station_id": "1",
                    "station_name": "Test Station",
                    "water_level": 5.0,
                    "water_level_warning": 10.0,
                    "water_level_danger": 14.0,
                }
            ],
            "alarm_data": [],
        }

        result = await agent.invoke(state)

        assert "risk_assessment" in result
        assert result["risk_assessment"].risk_level in [RiskLevel.LOW, RiskLevel.NONE]


class TestPlanGeneratorAgent:
    """Tests for Plan Generator Agent"""

    @pytest.mark.asyncio
    async def test_plan_generator_creates_plan(self):
        """Should create emergency plan"""
        agent = PlanGeneratorAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "生成预案",
            "messages": [],
            "iteration": 0,
            "risk_assessment": {
                "risk_level": RiskLevel.HIGH,
                "risk_score": 75.0,
                "affected_stations": ["station1", "station2"],
            },
            "station_data": [
                {"station_id": "1", "station_name": "Station 1"},
                {"station_id": "2", "station_name": "Station 2"},
            ],
        }

        result = await agent.invoke(state)

        assert "emergency_plan" in result
        assert result["emergency_plan"].plan_id
        assert result["emergency_plan"].status == PlanStatus.DRAFT

    @pytest.mark.asyncio
    async def test_plan_generator_includes_actions(self):
        """Should include emergency actions in plan"""
        agent = PlanGeneratorAgent()

        state: FloodResponseState = {
            "session_id": "test-session",
            "user_query": "生成预案",
            "messages": [],
            "iteration": 0,
            "risk_assessment": {
                "risk_level": RiskLevel.CRITICAL,
                "risk_score": 90.0,
                "affected_stations": ["station1"],
            },
            "station_data": [
                {"station_id": "1", "station_name": "Critical Station"},
            ],
        }

        result = await agent.invoke(state)

        assert len(result["emergency_plan"].actions) > 0
        # Should include evacuation action for critical risk
        action_types = [a.action_type for a in result["emergency_plan"].actions]
        assert any(at in action_types for at in ["evacuation", "gate_control", "patrol"])
