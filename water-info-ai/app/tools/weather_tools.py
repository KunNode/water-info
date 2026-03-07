"""气象数据工具

从和风天气 API 获取降雨预报和气象预警，无 API key 时返回模拟数据。
"""

from __future__ import annotations

import json
from datetime import datetime

import httpx
from langchain_core.tools import tool
from loguru import logger

from app.config import get_settings


@tool
async def fetch_weather_forecast(location: str = "") -> str:
    """获取未来 24 小时降雨预报。

    Args:
        location: 和风天气城市 ID 或经纬度（如 "101010100"），留空使用默认位置
    """
    settings = get_settings()
    location = location or settings.default_weather_location
    api_key = settings.weather_api_key

    if not api_key:
        logger.info("未配置 weather_api_key，返回模拟气象预报数据")
        return json.dumps({
            "source": "模拟数据",
            "location": location,
            "forecast_24h": [
                {"time": "未来0-6h", "precip_mm": 5.0, "description": "小雨"},
                {"time": "未来6-12h", "precip_mm": 15.0, "description": "中雨"},
                {"time": "未来12-18h", "precip_mm": 25.0, "description": "大雨"},
                {"time": "未来18-24h", "precip_mm": 10.0, "description": "中雨转小雨"},
            ],
            "total_precip_24h_mm": 55.0,
            "note": "此为模拟数据，请配置 weather_api_key 获取真实预报",
        }, ensure_ascii=False)

    try:
        url = "https://devapi.qweather.com/v7/weather/24h"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params={"location": location, "key": api_key})
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "200":
            return json.dumps({"error": f"和风天气 API 返回错误: code={data.get('code')}"}, ensure_ascii=False)

        hourly = data.get("hourly", [])
        forecast = []
        total_precip = 0.0
        for h in hourly:
            precip = float(h.get("precip", 0))
            total_precip += precip
            forecast.append({
                "time": h.get("fxTime", ""),
                "precip_mm": precip,
                "temp_c": h.get("temp"),
                "wind_speed_kmh": h.get("windSpeed"),
                "description": h.get("text", ""),
            })

        return json.dumps({
            "source": "和风天气",
            "location": location,
            "forecast_24h": forecast,
            "total_precip_24h_mm": round(total_precip, 1),
            "update_time": data.get("updateTime", ""),
        }, ensure_ascii=False)

    except Exception as e:
        logger.warning(f"获取气象预报失败: {e}")
        return json.dumps({"error": f"获取气象预报失败: {str(e)}"}, ensure_ascii=False)


@tool
async def fetch_weather_warning(location: str = "") -> str:
    """获取当前气象预警信息。

    Args:
        location: 和风天气城市 ID 或经纬度，留空使用默认位置
    """
    settings = get_settings()
    location = location or settings.default_weather_location
    api_key = settings.weather_api_key

    if not api_key:
        logger.info("未配置 weather_api_key，返回模拟气象预警数据")
        return json.dumps({
            "source": "模拟数据",
            "location": location,
            "warnings": [
                {
                    "type": "暴雨",
                    "level": "橙色",
                    "title": "暴雨橙色预警",
                    "text": "预计未来24小时内将有大到暴雨，请注意防范。",
                    "start_time": datetime.now().isoformat(),
                },
            ],
            "note": "此为模拟数据，请配置 weather_api_key 获取真实预警",
        }, ensure_ascii=False)

    try:
        url = "https://devapi.qweather.com/v7/warning/now"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params={"location": location, "key": api_key})
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "200":
            return json.dumps({"error": f"和风天气 API 返回错误: code={data.get('code')}"}, ensure_ascii=False)

        warnings = []
        for w in data.get("warning", []):
            warnings.append({
                "type": w.get("typeName", ""),
                "level": w.get("level", ""),
                "title": w.get("title", ""),
                "text": w.get("text", ""),
                "start_time": w.get("startTime", ""),
                "end_time": w.get("endTime", ""),
            })

        return json.dumps({
            "source": "和风天气",
            "location": location,
            "warnings": warnings,
            "warning_count": len(warnings),
            "update_time": data.get("updateTime", ""),
        }, ensure_ascii=False)

    except Exception as e:
        logger.warning(f"获取气象预警失败: {e}")
        return json.dumps({"error": f"获取气象预警失败: {str(e)}"}, ensure_ascii=False)


weather_tools = [fetch_weather_forecast, fetch_weather_warning]
