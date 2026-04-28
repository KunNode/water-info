"""测试图路由函数"""

from __future__ import annotations

from app.graph import _route_from_supervisor


class TestRouteFromSupervisor:
    """测试 _route_from_supervisor 函数"""

    def test_end_routes_to_final_response(self):
        state = {"next_agent": "__end__"}
        assert _route_from_supervisor(state) == "final_response"

    def test_data_analyst_route(self):
        state = {"next_agent": "data_analyst"}
        assert _route_from_supervisor(state) == "data_analyst"

    def test_risk_assessor_route(self):
        state = {"next_agent": "risk_assessor"}
        assert _route_from_supervisor(state) == "risk_assessor"

    def test_plan_generator_route(self):
        state = {"next_agent": "plan_generator"}
        assert _route_from_supervisor(state) == "plan_generator"

    def test_resource_dispatcher_route(self):
        state = {"next_agent": "resource_dispatcher"}
        assert _route_from_supervisor(state) == "resource_dispatcher"

    def test_notification_route(self):
        state = {"next_agent": "notification"}
        assert _route_from_supervisor(state) == "notification"

    def test_execution_monitor_route(self):
        state = {"next_agent": "execution_monitor"}
        assert _route_from_supervisor(state) == "execution_monitor"

    def test_parallel_dispatch_route(self):
        state = {"next_agent": "parallel_dispatch"}
        assert _route_from_supervisor(state) == "parallel_dispatch"

    def test_knowledge_retriever_route(self):
        state = {"next_agent": "knowledge_retriever"}
        assert _route_from_supervisor(state) == "knowledge_retriever"

    def test_missing_next_agent_defaults_to_final_response(self):
        state = {}
        assert _route_from_supervisor(state) == "final_response"
