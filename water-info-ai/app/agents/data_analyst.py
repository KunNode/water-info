"""Data analyst node."""

from __future__ import annotations

from difflib import SequenceMatcher

from app.database import get_db_service
from app.services.llm import get_llm
from app.state import to_plain_data


def _normalize(text: str | None) -> str:
    return "".join(ch.lower() for ch in str(text or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _pick_focus_station(overview: dict, state: dict) -> dict | None:
    stations = overview.get("stations", [])
    query = state.get("focus_station_query") or state.get("user_query") or ""
    normalized_query = _normalize(query)
    if not normalized_query:
        return None

    best_station = None
    best_score = 0.0
    for station in stations:
        name = station.get("name", "")
        code = station.get("code", "")
        normalized_name = _normalize(name)
        normalized_code = _normalize(code)
        score = 0.0
        if normalized_name and normalized_name in normalized_query:
            score = max(score, 1.0)
        if normalized_code and normalized_code in normalized_query:
            score = max(score, 0.98)
        if normalized_name:
            score = max(score, SequenceMatcher(None, normalized_query, normalized_name).ratio())
        if normalized_code:
            score = max(score, SequenceMatcher(None, normalized_query, normalized_code).ratio())
        if score > best_score:
            best_station = station
            best_score = score

    return best_station if best_score >= 0.45 else None


def _summarise_overview(overview: dict) -> str:
    stations = overview.get("stations", [])
    alarms = overview.get("active_alarms", [])
    ranked: list[tuple[float, str]] = []
    for station in stations:
        score = 0.0
        water_level = station.get("water_level")
        warning_level = station.get("warning_level")
        danger_level = station.get("danger_level")
        rainfall = station.get("rainfall")
        rainfall_warning = station.get("rainfall_warning")
        if water_level is not None and warning_level:
            denominator = max(float(warning_level), 0.01)
            score += float(water_level) / denominator
        if water_level is not None and danger_level:
            denominator = max(float(danger_level), 0.01)
            score += float(water_level) / denominator
        if rainfall is not None and rainfall_warning:
            denominator = max(float(rainfall_warning), 0.01)
            score += float(rainfall) / denominator
        elif rainfall is not None:
            score += float(rainfall) / 50.0

        name = station.get("name", station.get("code", "未知站点"))
        ranked.append((score, name))

    top_station_names = {name for _, name in sorted(ranked, reverse=True)[:3]}
    top_stations = [
        station for station in stations
        if station.get("name", station.get("code", "未知站点")) in top_station_names
    ]

    lines = [
        "我先看了当前整体水情。",
        f"目前纳管监测站点 {overview.get('station_count', len(stations))} 个，活跃告警 {overview.get('alarm_count', len(alarms))} 条。",
    ]

    if top_stations:
        station_bits: list[str] = []
        for station in top_stations:
            name = station.get("name", station.get("code", "未知站点"))
            parts = [name]
            if station.get("water_level") is not None:
                water_part = f"水位 {float(station['water_level']):.2f}m"
                if station.get("warning_level") is not None:
                    water_part += f" / 警戒 {float(station['warning_level']):.2f}m"
                parts.append(water_part)
            if station.get("rainfall") is not None:
                parts.append(f"雨量 {float(station['rainfall']):.1f}mm")
            station_bits.append("，".join(parts))
        lines.append("当前最值得关注的站点包括：" + "；".join(station_bits) + "。")

    if alarms:
        alarm_text = "；".join(str(alarm.get("message", "告警触发")) for alarm in alarms[:3])
        lines.append("活跃告警主要集中在：" + alarm_text + "。")
    else:
        lines.append("当前没有发现明显的全局告警聚集。")

    return "\n\n".join(lines)


def _summarise_focus_station(station: dict, overview: dict) -> str:
    station_id = station.get("id")
    alarms = [
        alarm for alarm in overview.get("active_alarms", [])
        if str(alarm.get("station_id")) == str(station_id)
    ]
    lines = [
        f"## 站点状态",
        f"- 站点名称：{station.get('name', station.get('code', '未知站点'))}",
        f"- 站点编码：{station.get('code', '---')}",
        f"- 行政区域：{station.get('admin_region', '---')}",
        f"- 状态：{station.get('status', '---')}",
    ]
    if station.get("water_level") is not None:
        water_line = f"- 当前水位：{float(station['water_level']):.2f}m"
        if station.get("warning_level") is not None:
            water_line += f" | 警戒：{float(station['warning_level']):.2f}m"
        if station.get("danger_level") is not None:
            water_line += f" | 危险：{float(station['danger_level']):.2f}m"
        lines.append(water_line)
    if station.get("rainfall") is not None:
        rain_line = f"- 当前雨量：{float(station['rainfall']):.1f}mm"
        if station.get("rainfall_warning") is not None:
            rain_line += f" | 雨量警戒：{float(station['rainfall_warning']):.1f}mm"
        lines.append(rain_line)
    if station.get("flow_rate") is not None:
        lines.append(f"- 流量：{float(station['flow_rate']):.2f}")
    if alarms:
        lines.append("- 活跃告警：")
        lines.extend([f"  - {alarm.get('message', '告警触发')}" for alarm in alarms[:3]])
    else:
        lines.append("- 当前无活跃告警")
    return "\n".join(lines)


def _summarise_focus_station_answer(station: dict, overview: dict) -> str:
    station_name = station.get("name", station.get("code", "该站点"))
    parts = [f"我先看了 {station_name} 的最新状态。"]
    if station.get("water_level") is not None:
        water_part = f"当前水位 {float(station['water_level']):.2f}m"
        if station.get("warning_level") is not None:
            water_part += f"，警戒水位 {float(station['warning_level']):.2f}m"
        if station.get("danger_level") is not None:
            water_part += f"，危险水位 {float(station['danger_level']):.2f}m"
        parts.append(water_part + "。")
    if station.get("rainfall") is not None:
        rain_part = f"当前雨量 {float(station['rainfall']):.1f}mm"
        if station.get("rainfall_warning") is not None:
            rain_part += f"，雨量警戒 {float(station['rainfall_warning']):.1f}mm"
        parts.append(rain_part + "。")
    alarms = [
        alarm for alarm in overview.get("active_alarms", [])
        if str(alarm.get("station_id")) == str(station.get("id"))
    ]
    if alarms:
        parts.append("当前还有这些活跃告警：" + "；".join(alarm.get("message", "告警触发") for alarm in alarms[:3]) + "。")
    else:
        parts.append("当前没有发现该站点的活跃告警。")
    return "\n\n".join(parts)


def _summarise_grounding_context(overview: dict, weather: dict, intent: str) -> str:
    stations = overview.get("stations", [])
    alarms = overview.get("active_alarms", [])
    forecast = weather.get("forecast", weather)
    precip_24h = forecast.get("total_precip_24h_mm")

    lines = ["我先提炼了和当前任务最相关的背景信息。"]
    if intent == "alarm_overview":
        lines.append(
            f"当前共有 {overview.get('alarm_count', len(alarms))} 条活跃告警，"
            f"覆盖监测站点 {overview.get('station_count', len(stations))} 个。"
        )
        if precip_24h is not None:
            lines.append(f"未来 24 小时预报降雨量约 {float(precip_24h):.0f}mm，短时内告警压力仍可能继续上升。")
    elif intent == "risk_assessment":
        lines.append(
            f"当前共有 {overview.get('alarm_count', len(alarms))} 条活跃告警，"
            f"监测站点 {overview.get('station_count', len(stations))} 个。"
        )
        if precip_24h is not None:
            lines.append(f"未来 24 小时预报降雨量约 {float(precip_24h):.0f}mm，这会直接影响风险研判。")
    elif intent in {"plan_generation", "resource_dispatch", "notification"}:
        lines.append(
            f"当前已有 {overview.get('alarm_count', len(alarms))} 条活跃告警，"
            "需要优先围绕风险较高区域准备措施、资源和通知。"
        )
        if precip_24h is not None:
            lines.append(f"未来 24 小时降雨预报约 {float(precip_24h):.0f}mm，可作为预案触发背景。")
    else:
        lines.append(
            f"当前纳管监测站点 {overview.get('station_count', len(stations))} 个，"
            f"活跃告警 {overview.get('alarm_count', len(alarms))} 条。"
        )

    if alarms:
        label = "代表性告警包括："
        if intent == "alarm_overview":
            label = "当前重点告警包括："
        lines.append(label + "；".join(str(alarm.get("message", "告警触发")) for alarm in alarms[:3]) + "。")
    elif intent == "alarm_overview":
        lines.append("当前没有发现活跃告警。")
    return "\n\n".join(lines)


async def _build_deterministic_bundle(_: dict) -> dict:
    db = get_db_service()
    overview = await db.get_flood_situation_overview()
    weather = {
        "forecast": {
            "total_precip_24h_mm": 55.0,
            "source": "模拟天气",
        }
    }
    return {
        "overview_data": overview,
        "weather_forecast": weather,
        "data_summary": _summarise_overview(overview),
    }


async def data_analyst_node(state: dict) -> dict:
    bundle = await _build_deterministic_bundle(state)
    focus_station = _pick_focus_station(bundle["overview_data"], state)
    intent = str(state.get("intent", "overview"))
    deterministic_summary = (
        _summarise_focus_station_answer(focus_station, bundle["overview_data"])
        if focus_station
        else (
            bundle["data_summary"]
            if intent == "overview"
            else _summarise_grounding_context(bundle["overview_data"], bundle["weather_forecast"], intent)
        )
    )

    summary = deterministic_summary
    llm = get_llm()
    if llm.is_enabled:
        try:
            response = await llm.ainvoke(
                {
                    "user_query": state.get("user_query", ""),
                    "intent": intent,
                    "focus_station_query": state.get("focus_station_query"),
                    "focus_station": to_plain_data(focus_station),
                    "overview_data": to_plain_data(bundle["overview_data"]),
                    "weather_forecast": to_plain_data(bundle["weather_forecast"]),
                },
                system_prompt=(
                    "你是防汛数据分析智能体。"
                    "请基于输入的水位、雨量、告警和天气信息，输出一段给指挥台展示的 Markdown 数据摘要。"
                    "如果用户问的是某个具体站点，就聚焦该站点的状态、阈值、告警和趋势，避免只给全局总览。"
                    "如果用户问的是总体情况，再给更完整的态势总览和重点站点。"
                    "如果用户在问告警态势，就重点回答告警数量、分布、代表性告警和短期变化，不要泛化成普通总览。"
                    "如果用户并不是在问总体情况，而是在问风险、预案、资源或通知，就只提炼支撑当前任务的背景，不要先铺一段笼统的全局总览。"
                    "不要编造不存在的数据。"
                ),
                temperature=0.2,
            )
            content = getattr(response, "content", "").strip()
            if content:
                summary = content
        except Exception:
            summary = deterministic_summary

    return {
        **bundle,
        "focus_station": focus_station,
        "data_summary": summary,
        "current_agent": "data_analyst",
        "messages": [{"role": "data_analyst", "content": summary}],
    }
