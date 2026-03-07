"""LangGraph 多智能体工作流定义

构建 Supervisor 路由的多智能体图，节点间通过共享状态通信。

图结构:
    START → supervisor → (动态路由) → supervisor → ... → final_response → END

Supervisor 在每次迭代中决定下一个子智能体，直到所有必要步骤完成后
路由到 __end__，触发最终汇总。
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from loguru import logger

from app.agents.data_analyst import data_analyst_node
from app.agents.execution_monitor import execution_monitor_node
from app.agents.final_response import final_response_node
from app.agents.notification_agent import notification_node
from app.agents.parallel_dispatch import parallel_dispatch_node
from app.agents.plan_generator import plan_generator_node
from app.agents.resource_dispatcher import resource_dispatcher_node
from app.agents.risk_assessor import risk_assessor_node
from app.agents.supervisor import supervisor_node
from app.state import FloodResponseState


def _route_from_supervisor(state: FloodResponseState) -> str:
    """根据 Supervisor 输出的 next_agent 进行路由"""
    next_agent = state.get("next_agent", "__end__")
    if next_agent == "__end__":
        return "final_response"
    return next_agent


def build_flood_response_graph() -> StateGraph:
    """构建防洪应急预案多智能体工作流图

    Returns:
        编译后的 LangGraph StateGraph
    """
    graph = StateGraph(FloodResponseState)

    # ── 注册节点 ──
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("data_analyst", data_analyst_node)
    graph.add_node("risk_assessor", risk_assessor_node)
    graph.add_node("plan_generator", plan_generator_node)
    graph.add_node("resource_dispatcher", resource_dispatcher_node)
    graph.add_node("notification", notification_node)
    graph.add_node("execution_monitor", execution_monitor_node)
    graph.add_node("parallel_dispatch", parallel_dispatch_node)
    graph.add_node("final_response", final_response_node)

    # ── 入口 ──
    graph.set_entry_point("supervisor")

    # ── Supervisor 条件路由 ──
    graph.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "data_analyst": "data_analyst",
            "risk_assessor": "risk_assessor",
            "plan_generator": "plan_generator",
            "resource_dispatcher": "resource_dispatcher",
            "notification": "notification",
            "execution_monitor": "execution_monitor",
            "parallel_dispatch": "parallel_dispatch",
            "final_response": "final_response",
        },
    )

    # ── 子智能体完成后回到 Supervisor ──
    for agent in [
        "data_analyst",
        "risk_assessor",
        "plan_generator",
        "resource_dispatcher",
        "notification",
        "execution_monitor",
        "parallel_dispatch",
    ]:
        graph.add_edge(agent, "supervisor")

    # ── 最终汇总 → 结束 ──
    graph.add_edge("final_response", END)

    logger.info("防洪应急预案多智能体图构建完成")
    return graph.compile()


# 编译后的全局图实例
flood_response_graph = build_flood_response_graph()
