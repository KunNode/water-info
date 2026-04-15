"""Final response aggregation node."""

from __future__ import annotations

from app.state import FloodResponseState
from app.utils.timeout import with_timeout


def _build_section(title: str, body: str | None) -> str | None:
    if not body:
        return None
    return f"## {title}\n{body.strip()}"


def _format_risk_section(state: FloodResponseState) -> str | None:
    risk = state.get("risk_assessment")
    if not risk:
        return None

    lines = [
        f"- 风险等级：{risk.risk_level.value}",
        f"- 风险评分：{risk.risk_score}",
        f"- 趋势：{risk.trend}",
    ]
    if risk.affected_stations:
        lines.append(f"- 影响站点：{', '.join(risk.affected_stations)}")
    if risk.key_risks:
        lines.append(f"- 关键风险：{'; '.join(risk.key_risks)}")
    if risk.reasoning:
        lines.append(f"- 评估说明：{risk.reasoning}")
    return "\n".join(lines)


def _format_plan_section(state: FloodResponseState) -> str | None:
    plan = state.get("emergency_plan")
    if not plan or not plan.plan_id:
        return None

    lines = [
        f"- 预案编号：{plan.plan_id}",
        f"- 预案名称：{plan.plan_name}",
    ]
    if plan.trigger_conditions:
        lines.append(f"- 触发条件：{plan.trigger_conditions}")
    if plan.summary:
        lines.append(f"- 概述：{plan.summary}")
    if plan.actions:
        lines.append("- 处置措施：")
        for index, action in enumerate(plan.actions, start=1):
            lines.append(
                f"  {index}. [{action.priority}级] {action.description}"
                f" | 类型={action.action_type}"
                f" | 责任部门={action.responsible_dept or '待定'}"
            )
    return "\n".join(lines)


def _format_resources_section(state: FloodResponseState) -> str | None:
    resources = state.get("resource_plan", [])
    if not resources:
        return None

    lines = []
    for resource in resources:
        lines.append(
            f"- {resource.resource_type}/{resource.resource_name}"
            f"：{resource.quantity}，{resource.source_location} -> {resource.target_location}"
            f"，ETA {resource.eta_minutes or '待定'} 分钟"
        )
    return "\n".join(lines)


def _format_notifications_section(state: FloodResponseState) -> str | None:
    notifications = state.get("notifications", [])
    if not notifications:
        return None

    lines = []
    for notification in notifications:
        lines.append(
            f"- [{notification.channel}] {notification.target}"
            f"：{notification.content}"
        )
    return "\n".join(lines)


def _format_execution_section(state: FloodResponseState) -> str | None:
    progress = state.get("execution_progress")
    if not progress:
        return None

    lines = [
        f"- 总措施：{progress.total_actions}",
        f"- 已完成：{progress.completed_actions}",
        f"- 执行中：{progress.in_progress_actions}",
        f"- 失败：{progress.failed_actions}",
        f"- 完成率：{progress.progress_pct}%",
    ]
    if progress.issues:
        lines.append(f"- 问题：{'; '.join(progress.issues)}")
    if progress.recommendations:
        lines.append(f"- 建议：{'; '.join(progress.recommendations)}")
    return "\n".join(lines)


def _render_report(state: FloodResponseState) -> str:
    sections = [
        _build_section("水情概况", state.get("data_summary")),
        _build_section("风险评估", _format_risk_section(state)),
        _build_section("应急预案", _format_plan_section(state)),
        _build_section("资源调度", _format_resources_section(state)),
        _build_section("通知方案", _format_notifications_section(state)),
        _build_section("执行进度", _format_execution_section(state)),
        _build_section("异常信息", state.get("error")),
    ]
    content = "\n\n".join(section for section in sections if section)
    if not content:
        content = "## 结果\n暂无可汇总的信息。"
    return f"# 防汛应急响应报告\n\n{content}"


@with_timeout(120)
async def final_response_node(state: FloodResponseState) -> dict:
    final_text = _render_report(state)
    return {
        "final_response": final_text,
        "messages": [{"role": "final_response", "content": final_text}],
    }
