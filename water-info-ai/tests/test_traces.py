"""Tests for the trace builder and TracedCall context manager."""

from __future__ import annotations

import pytest

from app.tools.trace import TracedCall, make_trace


class TestMakeTrace:
    def test_returns_correct_structure(self):
        trace = make_trace(
            phase="tool_call",
            status="completed",
            title="获取数据",
            detail="5 条记录",
            tool_name="fetch_data",
            metadata={"key": "val"},
        )
        assert trace["phase"] == "tool_call"
        assert trace["status"] == "completed"
        assert trace["title"] == "获取数据"
        assert trace["detail"] == "5 条记录"
        assert trace["tool_name"] == "fetch_data"
        assert trace["metadata"] == {"key": "val"}

    def test_defaults(self):
        trace = make_trace(phase="data_query", title="查询")
        assert trace["status"] == "completed"
        assert trace["detail"] == ""
        assert trace["tool_name"] is None
        assert trace["metadata"] == {}


class TestTracedCall:
    def test_records_timing_on_success(self):
        with TracedCall(
            phase="tool_call",
            tool_name="test_tool",
            title="测试调用",
            input_summary="id=1",
        ) as tc:
            tc.complete(output_summary="返回 3 行")

        assert tc.trace["status"] == "completed"
        assert tc.trace["tool_name"] == "test_tool"
        assert tc.trace["metadata"]["input_summary"] == "id=1"
        assert tc.trace["metadata"]["output_summary"] == "返回 3 行"
        assert tc.trace["metadata"]["duration_ms"] >= 0

    def test_records_timing_on_exception(self):
        with pytest.raises(ValueError):
            with TracedCall(
                phase="tool_call",
                tool_name="failing_tool",
                title="失败调用",
            ) as tc:
                raise ValueError("something went wrong")

        assert tc.trace["status"] == "failed"
        assert "something went wrong" in tc.trace["detail"]
        assert tc.trace["metadata"]["duration_ms"] >= 0

    def test_complete_sets_detail(self):
        with TracedCall(
            phase="tool_call",
            tool_name="t",
            title="t",
        ) as tc:
            tc.complete(detail="some detail")

        assert tc.trace["detail"] == "some detail"
