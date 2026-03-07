"""数据分析智能体

负责从水务平台采集实时/历史数据，进行汇总分析，
为后续风险评估提供数据基础。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from loguru import logger

from app.services.llm import get_llm
from app.state import FloodResponseState, StationData
from app.tools.data_tools import data_collection_tools
from app.tools.weather_tools import weather_tools
from app.utils.timeout import with_timeout

DATA_ANALYST_PROMPT = """你是防洪应急预案系统的 **数据分析智能体**。

你的职责：
1. 从 PostgreSQL 数据库获取最新的监测站、传感器、观测数据和告警信息
2. 分析水位趋势、降雨情况、传感器健康状态
3. 生成结构化的数据摘要，供风险评估智能体使用

你拥有以下工具：
- fetch_flood_overview: 【首选】获取防洪态势全景概览（站点+最新数据+阈值+告警，一次性获取）
- fetch_station_observations: 获取指定站点的历史观测数据
- fetch_water_level_trend: 获取指定站点的水位变化趋势
- fetch_rainfall_stats: 获取指定站点的1h/6h/24h累计降雨量
- fetch_active_alarms: 获取当前活跃告警
- fetch_threshold_rules: 获取阈值规则
- fetch_sensors_status: 获取传感器状态
- fetch_weather_forecast: 获取未来24小时降雨预报
- fetch_weather_warning: 获取当前气象预警信息

工作流程：
1. 先调用 fetch_flood_overview 获取全景概览
2. 调用 fetch_weather_forecast 和 fetch_weather_warning 获取气象预报和预警
3. 对水位接近警戒/危险线的重点站点，调用 fetch_water_level_trend 获取趋势
4. 对降雨量较大的站点，调用 fetch_rainfall_stats 获取累计降雨
5. 汇总形成数据分析报告

输出要求：
- 列出各站点当前水位与警戒/危险水位的对比
- 标注水位变化趋势（上涨/稳定/下降）
- 统计降雨量情况
- 列出活跃告警
- 标注数据异常或传感器离线情况
- 包含气象预报和预警信息（如有）
"""


@with_timeout(120)
async def data_analyst_node(state: FloodResponseState) -> dict:
    """数据分析节点：采集并分析水务数据"""
    llm = get_llm()

    # 构建 ReAct Agent
    agent = create_react_agent(
        model=llm,
        tools=data_collection_tools + weather_tools,
        prompt=DATA_ANALYST_PROMPT,
    )

    user_query = state.get("user_query", "请分析当前水情数据")

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=f"请根据用户请求进行数据采集与分析：{user_query}")]
    })

    # 提取最终分析结果
    final_message = result["messages"][-1].content if result["messages"] else ""
    logger.info(f"数据分析完成，摘要长度: {len(final_message)}")

    return {
        "data_summary": final_message,
        "current_agent": "data_analyst",
        "messages": [{"role": "data_analyst", "content": final_message}],
    }
