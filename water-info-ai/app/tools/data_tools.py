"""数据采集工具

供 DataAnalyst 智能体调用。

数据源策略 (混合模式):
- 读操作 (查询/获取): 默认走 PostgreSQL (延迟最低，支持综合查询)
- 写操作 (确认/关闭告警): 必须走后端 API (保持业务逻辑一致性)

数据源选择:
  | 操作类型 | 数据源 | 原因 |
  |---------|--------|------|
  | 读取监测站/传感器/观测/告警/阈值 | PostgreSQL | 延迟最低，支持复杂SQL综合查询 |
  | 确认告警 | 后端 API | 触发业务逻辑，记录操作日志 |
  | 关闭告警 | 后端 API | 触发业务逻辑，状态流转 |
"""

from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime

from langchain_core.tools import tool
from loguru import logger

from app.services.database import get_db_service


def _serialize(obj):
    """JSON 序列化辅助：处理 Decimal / datetime 等类型"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


@tool
async def fetch_flood_overview() -> str:
    """获取防洪态势全景概览。
    一次性返回所有监测站信息、最新水位/雨量/流量、阈值配置、活跃告警等。
    这是数据分析的首选入口工具，可以快速掌握全局态势。
    """
    db = get_db_service()
    try:
        overview = await db.get_flood_situation_overview()
        logger.info(f"防洪态势概览: {overview['station_count']}个站点, {overview['alarm_count']}条活跃告警")
        return json.dumps(overview, ensure_ascii=False, default=_serialize)
    except Exception as e:
        logger.error(f"获取防洪态势概览失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
async def fetch_station_observations(
    station_id: str,
    metric_type: str = "",
    hours: int = 24,
) -> str:
    """获取指定监测站的历史观测数据。

    Args:
        station_id: 监测站ID
        metric_type: 指标类型 (WATER_LEVEL / RAINFALL / FLOW)，留空获取全部
        hours: 查询最近多少小时的数据，默认24小时

    Returns:
        观测数据列表的JSON字符串
    """
    db = get_db_service()
    try:
        records = await db.get_observations(
            station_id=station_id,
            metric_type=metric_type or None,
            hours=hours,
        )
        logger.info(f"站点 {station_id} 获取到 {len(records)} 条观测数据")
        return json.dumps(records, ensure_ascii=False, default=_serialize)
    except Exception as e:
        logger.error(f"获取观测数据失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
async def fetch_water_level_trend(station_id: str, hours: int = 6) -> str:
    """获取指定站点的水位变化趋势。

    Args:
        station_id: 监测站ID
        hours: 查询最近多少小时的趋势，默认6小时

    Returns:
        时间序列数据的JSON字符串，用于分析水位涨落速率
    """
    db = get_db_service()
    try:
        records = await db.get_water_level_trend(station_id, hours)
        logger.info(f"站点 {station_id} 水位趋势: {len(records)} 条记录")
        return json.dumps(records, ensure_ascii=False, default=_serialize)
    except Exception as e:
        logger.error(f"获取水位趋势失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
async def fetch_rainfall_stats(station_id: str) -> str:
    """获取指定站点的1小时/6小时/24小时累计降雨量。

    Args:
        station_id: 监测站ID

    Returns:
        JSON字符串，包含 rainfall_1h, rainfall_6h, rainfall_24h
    """
    db = get_db_service()
    try:
        stats = await db.get_rainfall_stats(station_id)
        logger.info(f"站点 {station_id} 降雨统计: {stats}")
        return json.dumps(stats or {}, ensure_ascii=False, default=_serialize)
    except Exception as e:
        logger.error(f"获取降雨统计失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
async def fetch_active_alarms(station_id: str = "") -> str:
    """获取当前活跃告警列表。

    Args:
        station_id: 可选，指定监测站ID过滤。留空获取所有站点告警。

    Returns:
        告警列表的JSON字符串，包含告警等级、状态、消息等
    """
    db = get_db_service()
    try:
        records = await db.get_active_alarms(station_id or None)
        logger.info(f"获取到 {len(records)} 条活跃告警")
        return json.dumps(records, ensure_ascii=False, default=_serialize)
    except Exception as e:
        logger.error(f"获取告警失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
async def fetch_threshold_rules(station_id: str = "") -> str:
    """获取阈值规则配置（警戒水位、危险水位、降雨阈值等）。

    Args:
        station_id: 可选，指定监测站ID过滤。留空获取所有规则。

    Returns:
        阈值规则列表的JSON字符串
    """
    db = get_db_service()
    try:
        records = await db.get_threshold_rules(station_id or None)
        logger.info(f"获取到 {len(records)} 条阈值规则")
        return json.dumps(records, ensure_ascii=False, default=_serialize)
    except Exception as e:
        logger.error(f"获取阈值规则失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
async def fetch_sensors_status(station_id: str = "") -> str:
    """获取传感器状态信息（类型、采样间隔、最后在线时间）。

    Args:
        station_id: 可选，指定监测站ID过滤。

    Returns:
        传感器列表的JSON字符串
    """
    db = get_db_service()
    try:
        records = await db.get_sensors(station_id or None)
        logger.info(f"获取到 {len(records)} 个传感器状态")
        return json.dumps(records, ensure_ascii=False, default=_serialize)
    except Exception as e:
        logger.error(f"获取传感器状态失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 写操作工具 — 必须走后端 API (保持业务逻辑一致性)
# ═══════════════════════════════════════════════════════════════════════════════


@tool
async def acknowledge_alarm(alarm_id: str) -> str:
    """确认告警。

    将告警状态从 OPEN 流转为 ACK (已确认)。
    注意: 此操作会触发后端业务逻辑，必须走后端 API。

    Args:
        alarm_id: 告警ID

    Returns:
        JSON格式的确认结果
    """
    from app.services.platform_client import get_platform_client

    try:
        client = get_platform_client()
        result = await client.acknowledge_alarm(alarm_id)
        logger.info(f"告警 {alarm_id} 已确认")
        return json.dumps({"success": True, "alarm_id": alarm_id, "result": result}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"确认告警失败: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def close_alarm(alarm_id: str) -> str:
    """关闭告警。

    将告警状态从 OPEN/ACK 流转为 CLOSED (已关闭)。
    注意: 此操作会触发后端业务逻辑，必须走后端 API。

    Args:
        alarm_id: 告警ID

    Returns:
        JSON格式的关闭结果
    """
    from app.services.platform_client import get_platform_client

    try:
        client = get_platform_client()
        result = await client.close_alarm(alarm_id)
        logger.info(f"告警 {alarm_id} 已关闭")
        return json.dumps({"success": True, "alarm_id": alarm_id, "result": result}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"关闭告警失败: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# 导出所有工具
data_collection_tools = [
    # 读操作 - 走 PostgreSQL (延迟最低，支持综合查询)
    fetch_flood_overview,
    fetch_station_observations,
    fetch_water_level_trend,
    fetch_rainfall_stats,
    fetch_active_alarms,
    fetch_threshold_rules,
    fetch_sensors_status,
    # 写操作 - 走后端 API (保持业务逻辑一致性)
    acknowledge_alarm,
    close_alarm,
]
