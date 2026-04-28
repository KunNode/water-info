"""LangGraph workflow assembly for flood response."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.conversation_assistant import conversation_assistant_node
from app.agents.data_analyst import data_analyst_node
from app.agents.execution_monitor import execution_monitor_node
from app.agents.final_response import final_response_node
from app.agents.knowledge_retriever import knowledge_retriever_node
from app.agents.notification import notification_node
from app.agents.parallel_dispatch import parallel_dispatch_node
from app.agents.plan_generator import plan_generator_node
from app.agents.resource_dispatcher import resource_dispatcher_node
from app.agents.risk_assessor import risk_assessor_node
from app.agents.supervisor import supervisor_node
from app.state import FloodGraphState


def _route_from_supervisor(state: dict) -> str:
    next_agent = state.get("next_agent")
    if not next_agent or next_agent == "__end__":
        return "final_response"
    return str(next_agent)


def build_flood_response_graph():
    graph = StateGraph(FloodGraphState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("conversation_assistant", conversation_assistant_node)
    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("risk_assessor", risk_assessor_node)
    graph.add_node("plan_generator", plan_generator_node)
    graph.add_node("resource_dispatcher", resource_dispatcher_node)
    graph.add_node("notification", notification_node)
    graph.add_node("execution_monitor", execution_monitor_node)
    graph.add_node("parallel_dispatch", parallel_dispatch_node)
    graph.add_node("knowledge_retriever", knowledge_retriever_node)
    graph.add_node("final_response", final_response_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "conversation_assistant": "conversation_assistant",
            "data_analyst": "data_analyst",
            "risk_assessor": "risk_assessor",
            "plan_generator": "plan_generator",
            "resource_dispatcher": "resource_dispatcher",
            "notification": "notification",
            "execution_monitor": "execution_monitor",
            "parallel_dispatch": "parallel_dispatch",
            "knowledge_retriever": "knowledge_retriever",
            "final_response": "final_response",
        },
    )
    graph.add_edge("conversation_assistant", END)
    graph.add_edge("data_analyst", "supervisor")
    graph.add_edge("risk_assessor", "supervisor")
    graph.add_edge("plan_generator", "supervisor")
    graph.add_edge("resource_dispatcher", "supervisor")
    graph.add_edge("notification", "supervisor")
    graph.add_edge("execution_monitor", "supervisor")
    graph.add_edge("parallel_dispatch", "supervisor")
    graph.add_conditional_edges(
        "knowledge_retriever",
        lambda s: "final_response" if s.get("rag_target", "answer") == "answer" else "supervisor",
        {"final_response": "final_response", "supervisor": "supervisor"},
    )
    graph.add_edge("final_response", END)
    return graph.compile()


flood_response_graph = build_flood_response_graph()


def build_risk_only_graph():
    graph = StateGraph(FloodGraphState)
    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("risk_assessor", risk_assessor_node)
    graph.add_node("final_response", final_response_node)
    graph.add_edge(START, "data_analyst")
    graph.add_edge("data_analyst", "risk_assessor")
    graph.add_edge("risk_assessor", "final_response")
    graph.add_edge("final_response", END)
    return graph.compile()


def build_risk_event_graph():
    graph = StateGraph(FloodGraphState)
    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("risk_assessor", risk_assessor_node)
    graph.add_node("plan_generator", plan_generator_node)
    graph.add_node("final_response", final_response_node)
    graph.add_edge(START, "data_analyst")
    graph.add_edge("data_analyst", "risk_assessor")
    graph.add_edge("risk_assessor", "plan_generator")
    graph.add_edge("plan_generator", "final_response")
    graph.add_edge("final_response", END)
    return graph.compile()


risk_only_graph = build_risk_only_graph()
risk_event_graph = build_risk_event_graph()
