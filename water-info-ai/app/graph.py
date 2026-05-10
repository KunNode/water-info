"""LangGraph workflow assembly for flood response."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.conversation_assistant import conversation_assistant_node
from app.agents.data_analyst import data_analyst_node
from app.agents.execution_monitor import execution_monitor_node
from app.agents.final_response import final_response_node
from app.agents.knowledge_retriever import knowledge_retriever_node
from app.agents.memory import memory_loader_node, memory_writer_node
from app.agents.notification import notification_node
from app.agents.parallel_dispatch import parallel_dispatch_node
from app.agents.plan_generator import plan_generator_node
from app.agents.plan_reviewer import plan_reviewer_node
from app.agents.resource_dispatcher import resource_dispatcher_node
from app.agents.risk_assessor import risk_assessor_node
from app.agents.safety_checker import safety_checker_node
from app.agents.supervisor import supervisor_node
from app.platform.agent_audit import audited_agent
from app.state import FloodGraphState


def _route_from_supervisor(state: dict) -> str:
    next_agent = state.get("next_agent")
    if not next_agent or next_agent == "__end__":
        return "final_response"
    return str(next_agent)


def _route_from_memory_loader(state: dict) -> str:
    """Route after ``memory_loader`` — short-circuit to END on unrecoverable
    memory load failures (Req 4.4).

    When ``memory_loader_node`` catches a ``MemoryLoadError`` it writes an
    ``error`` string of the form ``"memory_load_failed: <source>"`` and sets
    ``next_agent="__end__"``. A plain ``add_edge("memory_loader", "supervisor")``
    would ignore those signals and keep the graph running, so non-streaming
    consumers (``/api/v1/flood/query``) could end up persisting a fabricated
    assistant reply. Routing to ``END`` here is the belt-and-suspenders fix
    that protects every graph consumer, not just the SSE path.
    """
    error = str(state.get("error") or "")
    if error.startswith("memory_load_failed:") or state.get("next_agent") == "__end__":
        return "__end__"
    return "supervisor"


def build_flood_response_graph(*, checkpointer=None, store=None):
    graph = StateGraph(FloodGraphState)
    graph.add_node("memory_loader", audited_agent("memory_loader", memory_loader_node))
    graph.add_node("supervisor", audited_agent("supervisor", supervisor_node))
    graph.add_node("conversation_assistant", audited_agent("conversation_assistant", conversation_assistant_node))
    graph.add_node("data_analyst", audited_agent("data_analyst", data_analyst_node))
    graph.add_node("risk_assessor", audited_agent("risk_assessor", risk_assessor_node))
    graph.add_node("plan_generator", audited_agent("plan_generator", plan_generator_node))
    graph.add_node("resource_dispatcher", audited_agent("resource_dispatcher", resource_dispatcher_node))
    graph.add_node("notification", audited_agent("notification", notification_node))
    graph.add_node("execution_monitor", audited_agent("execution_monitor", execution_monitor_node))
    graph.add_node("parallel_dispatch", audited_agent("parallel_dispatch", parallel_dispatch_node))
    graph.add_node("knowledge_retriever", audited_agent("knowledge_retriever", knowledge_retriever_node))
    graph.add_node("plan_reviewer", audited_agent("plan_reviewer", plan_reviewer_node))
    graph.add_node("safety_checker", audited_agent("safety_checker", safety_checker_node))
    graph.add_node("final_response", audited_agent("final_response", final_response_node))
    graph.add_node("memory_writer", audited_agent("memory_writer", memory_writer_node))

    graph.add_edge(START, "memory_loader")
    graph.add_conditional_edges(
        "memory_loader",
        _route_from_memory_loader,
        {"__end__": END, "supervisor": "supervisor"},
    )
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
            "plan_reviewer": "plan_reviewer",
            "safety_checker": "safety_checker",
            "final_response": "final_response",
        },
    )
    graph.add_edge("conversation_assistant", "final_response")
    graph.add_edge("data_analyst", "supervisor")
    graph.add_edge("risk_assessor", "supervisor")
    graph.add_edge("plan_generator", "supervisor")
    graph.add_edge("resource_dispatcher", "supervisor")
    graph.add_edge("notification", "supervisor")
    graph.add_edge("execution_monitor", "supervisor")
    graph.add_edge("parallel_dispatch", "supervisor")
    graph.add_edge("plan_reviewer", "supervisor")
    graph.add_edge("safety_checker", "supervisor")
    graph.add_conditional_edges(
        "knowledge_retriever",
        lambda s: "final_response" if s.get("rag_target", "answer") == "answer" else "supervisor",
        {"final_response": "final_response", "supervisor": "supervisor"},
    )
    graph.add_edge("final_response", "memory_writer")
    graph.add_edge("memory_writer", END)
    return graph.compile(checkpointer=checkpointer, store=store)


flood_response_graph = build_flood_response_graph()


def build_risk_only_graph():
    graph = StateGraph(FloodGraphState)
    graph.add_node("data_analyst", audited_agent("data_analyst", data_analyst_node))
    graph.add_node("risk_assessor", audited_agent("risk_assessor", risk_assessor_node))
    graph.add_node("final_response", audited_agent("final_response", final_response_node))
    graph.add_edge(START, "data_analyst")
    graph.add_edge("data_analyst", "risk_assessor")
    graph.add_edge("risk_assessor", "final_response")
    graph.add_edge("final_response", END)
    return graph.compile()


def build_risk_event_graph():
    graph = StateGraph(FloodGraphState)
    graph.add_node("data_analyst", audited_agent("data_analyst", data_analyst_node))
    graph.add_node("risk_assessor", audited_agent("risk_assessor", risk_assessor_node))
    graph.add_node("plan_generator", audited_agent("plan_generator", plan_generator_node))
    graph.add_node("final_response", audited_agent("final_response", final_response_node))
    graph.add_edge(START, "data_analyst")
    graph.add_edge("data_analyst", "risk_assessor")
    graph.add_edge("risk_assessor", "plan_generator")
    graph.add_edge("plan_generator", "final_response")
    graph.add_edge("final_response", END)
    return graph.compile()


risk_only_graph = build_risk_only_graph()
risk_event_graph = build_risk_event_graph()
