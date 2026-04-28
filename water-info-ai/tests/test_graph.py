"""Structural tests for the LangGraph workflow."""

from __future__ import annotations

from app.graph import build_flood_response_graph, flood_response_graph


def test_compiled_graph_is_available():
    assert flood_response_graph is not None


def test_build_graph_returns_compiled_graph():
    compiled_graph = build_flood_response_graph()
    assert compiled_graph is not None


def test_graph_contains_core_nodes():
    node_names = set(flood_response_graph.nodes.keys())
    assert {"supervisor", "data_analyst", "risk_assessor", "plan_generator", "knowledge_retriever", "final_response"} <= node_names
