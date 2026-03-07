"""风险评估智能体

基于数据分析结果，使用风险评估工具量化洪水风险等级。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from loguru import logger

from app.services.llm import get_llm
from app.state import FloodResponseState, RiskAssessment, RiskLevel
from app.tools.risk_tools import risk_assessment_tools
from app.utils.timeout import with_timeout

RISK_ASSESSOR_PROMPT = """你是防洪应急预案系统的 **风险评估智能体**。

你的职责：
1. 基于数据分析智能体提供的水务数据，评估洪水风险
2. 使用计算工具量化风险分数
3. 给出综合风险等级和趋势判断

你拥有以下工具：
- calculate_water_level_risk: 计算水位风险
- calculate_rainfall_risk: 计算降雨风险
- calculate_composite_risk: 计算综合风险

工作流程：
1. 从数据摘要中提取关键指标（水位、雨量、告警数等）
2. 分别调用水位风险和降雨风险计算工具
3. 调用综合风险计算工具得出总体评估
4. 结合专业知识给出趋势判断和关键风险点

输出要求（严格JSON格式）：
{
    "risk_level": "none|low|moderate|high|critical",
    "risk_score": 0-100的浮点数,
    "affected_stations": ["受影响站点ID列表"],
    "key_risks": ["关键风险点描述"],
    "trend": "rising|stable|falling",
    "reasoning": "风险评估推理过程说明"
}
"""


@with_timeout(120)
async def risk_assessor_node(state: FloodResponseState) -> dict:
    """风险评估节点"""
    llm = get_llm()

    agent = create_react_agent(
        model=llm,
        tools=risk_assessment_tools,
        prompt=RISK_ASSESSOR_PROMPT,
    )

    # 将数据分析摘要提供给风险评估
    data_summary = state.get("data_summary", "暂无数据分析结果")
    prompt = f"""请基于以下数据分析结果进行风险评估：

{data_summary}

请使用工具进行量化计算，并输出综合风险评估结果。
如果数据中缺少某些指标（如水位、雨量），请基于可用数据进行评估，并在reasoning中说明。
"""

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=prompt)]
    })

    final_message = result["messages"][-1].content if result["messages"] else ""
    logger.info(f"风险评估完成: {final_message[:200]}")

    # 尝试解析结构化结果
    from app.utils.json_parser import extract_json
    risk_data = extract_json(final_message)
    if risk_data and isinstance(risk_data, dict):
        try:
            risk_assessment = RiskAssessment(
                risk_level=RiskLevel(risk_data.get("risk_level", "none")),
                risk_score=float(risk_data.get("risk_score", 0)),
                affected_stations=risk_data.get("affected_stations", []),
                key_risks=risk_data.get("key_risks", []),
                trend=risk_data.get("trend", "stable"),
                reasoning=risk_data.get("reasoning", final_message),
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"解析风险评估结果失败: {e}")
            risk_assessment = RiskAssessment(reasoning=final_message)
    else:
        risk_assessment = RiskAssessment(reasoning=final_message)

    return {
        "risk_assessment": risk_assessment,
        "current_agent": "risk_assessor",
        "messages": [{"role": "risk_assessor", "content": final_message}],
    }
