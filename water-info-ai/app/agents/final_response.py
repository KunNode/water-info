"""最终响应汇总节点

在所有智能体完成工作后，汇总生成面向用户的最终响应。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.services.llm import get_creative_llm
from app.state import FloodResponseState
from app.utils.timeout import with_timeout

FINAL_RESPONSE_PROMPT = """你是防洪应急预案系统的 **汇总输出助手**。

请将各智能体的工作成果汇总为一份结构清晰、内容完整的中文报告。

报告格式：

# 防洪应急响应报告

## 一、水情概况
(基于数据分析结果)

## 二、风险评估
(风险等级、分数、关键风险点)

## 三、应急预案
(预案名称、响应等级、措施清单)

## 四、资源调度方案
(人员/物资/设备调度表)

## 五、预警通知方案
(通知渠道、目标、内容)

## 六、后续建议
(监控重点、注意事项)

要求：
- 语言正式、专业，符合防汛应急文件风格
- 关键数据用数字明确标注
- 如果某部分没有数据，标注"暂无相关信息"
"""


@with_timeout(120)
async def final_response_node(state: FloodResponseState) -> dict:
    """汇总最终响应"""
    llm = get_creative_llm()

    # 收集所有智能体的输出
    sections = []

    if state.get("data_summary"):
        sections.append(f"## 数据分析结果\n{state['data_summary']}")

    if state.get("risk_assessment"):
        ra = state["risk_assessment"]
        sections.append(
            f"## 风险评估结果\n"
            f"- 风险等级: {ra.risk_level.value}\n"
            f"- 风险分数: {ra.risk_score}\n"
            f"- 受影响站点: {', '.join(ra.affected_stations) or '无'}\n"
            f"- 趋势: {ra.trend}\n"
            f"- 关键风险: {'; '.join(ra.key_risks) or '无'}\n"
            f"- 评估说明: {ra.reasoning}"
        )

    if state.get("emergency_plan") and state["emergency_plan"].plan_id:
        ep = state["emergency_plan"]
        actions_str = "\n".join(
            f"  {i+1}. [{a.priority}级] {a.description} — {a.responsible_dept}"
            for i, a in enumerate(ep.actions)
        )
        sections.append(
            f"## 应急预案\n"
            f"- 预案编号: {ep.plan_id}\n"
            f"- 预案名称: {ep.plan_name}\n"
            f"- 触发条件: {ep.trigger_conditions}\n"
            f"- 措施清单:\n{actions_str}\n"
            f"- 概述: {ep.summary}"
        )

    if state.get("resource_plan"):
        resource_lines = "\n".join(
            f"  - {r.resource_type}/{r.resource_name}: {r.quantity}个/套, "
            f"从{r.source_location}→{r.target_location}, 预计{r.eta_minutes}分钟到达"
            for r in state["resource_plan"]
        )
        sections.append(f"## 资源调度方案\n{resource_lines}")

    if state.get("notifications"):
        notif_lines = "\n".join(
            f"  - [{n.channel}] → {n.target}: {n.content[:80]}..."
            for n in state["notifications"]
        )
        sections.append(f"## 预警通知方案\n{notif_lines}")

    if state.get("execution_progress"):
        ep = state["execution_progress"]
        sections.append(
            f"## 执行进度\n"
            f"- 总措施: {ep.total_actions}, 已完成: {ep.completed_actions}, "
            f"进行中: {ep.in_progress_actions}, 失败: {ep.failed_actions}\n"
            f"- 完成率: {ep.progress_pct}%"
        )

    context = "\n\n".join(sections) if sections else "暂无各智能体输出数据"

    messages = [
        SystemMessage(content=FINAL_RESPONSE_PROMPT),
        HumanMessage(content=f"用户原始请求: {state.get('user_query', '')}\n\n各智能体工作成果:\n{context}"),
    ]

    response = await llm.ainvoke(messages)
    final_text = response.content

    logger.info(f"最终响应生成完成，长度: {len(final_text)}")

    return {
        "final_response": final_text,
        "messages": [{"role": "final_response", "content": final_text}],
    }
