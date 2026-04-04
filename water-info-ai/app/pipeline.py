"""Sequential flood-response pipeline.

Steps
-----
1. session_init       — emit SSE init event
2. data_analyst       — fetch water data from PostgreSQL + weather
3. risk_assessor      — deterministic risk scoring
4. plan_generator     — template-based emergency plan
5. supervisor (LLM)   — stream natural-language summary
6. [DONE]             — sentinel + internal __result__ marker

The caller iterates the async generator, sending SSE lines to the client.
After iteration the ``result`` attribute is populated for persistence.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import AsyncIterator

import httpx

from app.config import get_settings
from app.database import get_db_service
from app.llm import stream_completion
from app.plan import build_notifications, generate_plan_id, get_response_template
from app.risk import calculate_composite_risk, calculate_rainfall_risk, calculate_water_level_risk

logger = logging.getLogger(__name__)

# ── helpers ───────────────────────────────────────────────────────────────────


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _serialize(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


# ── result model ──────────────────────────────────────────────────────────────


@dataclass
class PipelineResult:
    session_id: str = ""
    response: str = ""
    risk_level: str | None = None
    risk_score: float | None = None
    plan_id: str | None = None
    plan_name: str | None = None
    actions: list[dict] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)
    notifications: list[dict] = field(default_factory=list)


# ── pipeline class ────────────────────────────────────────────────────────────


class FloodPipeline:
    """Run the flood-response pipeline, yielding SSE strings.

    After the generator is exhausted ``self.result`` holds structured data
    suitable for database persistence.
    """

    def __init__(self, query: str, session_id: str) -> None:
        self.query = query
        self.session_id = session_id
        self.result = PipelineResult(session_id=session_id)

    async def run(self) -> AsyncIterator[str]:
        # ── 1. session_init ──────────────────────────────────────────────────
        yield _sse({"type": "session_init", "sessionId": self.session_id})

        # ── 2. data_analyst ──────────────────────────────────────────────────
        yield _sse({"type": "agent_update", "agent": "data_analyst", "status": "active"})
        overview, weather = await self._fetch_data()
        yield _sse({"type": "agent_update", "agent": "data_analyst", "status": "done"})

        station_summary = self._summarise_stations(overview)

        # ── 3. risk_assessor ─────────────────────────────────────────────────
        yield _sse({"type": "agent_update", "agent": "risk_assessor", "status": "active"})
        risk = self._assess_risk(overview, weather)
        yield _sse({
            "type": "risk_update",
            "level": risk["level"],
            "details": risk["key_risks"],
        })
        yield _sse({"type": "agent_update", "agent": "risk_assessor", "status": "done"})

        # ── 4. plan_generator ────────────────────────────────────────────────
        yield _sse({"type": "agent_update", "agent": "plan_generator", "status": "active"})
        plan = self._build_plan(risk)
        yield _sse({
            "type": "plan_update",
            "name": plan["plan_name"],
            "status": "draft",
            "total": len(plan["actions"]),
            "completed": 0,
            "failed": 0,
        })
        yield _sse({"type": "agent_update", "agent": "plan_generator", "status": "done"})

        # ── 5. supervisor (LLM summary) ──────────────────────────────────────
        yield _sse({"type": "agent_update", "agent": "supervisor", "status": "active"})
        summary_parts: list[str] = []
        try:
            prompt = self._build_prompt(station_summary, risk, plan)
            async for token in stream_completion([{"role": "user", "content": prompt}]):
                summary_parts.append(token)
                yield _sse({"type": "agent_message", "agent": "supervisor", "content": token})
        except Exception as exc:
            logger.warning("[%s] LLM stream error: %s", self.session_id, exc)
            fallback = self._build_fallback(risk, plan)
            summary_parts.append(fallback)
            yield _sse({"type": "agent_message", "agent": "supervisor", "content": fallback})
        yield _sse({"type": "agent_update", "agent": "supervisor", "status": "done"})

        # ── 6. populate result & finish ──────────────────────────────────────
        self.result.response = "".join(summary_parts)
        self.result.risk_level = risk["level"]
        self.result.risk_score = risk["score"]
        self.result.plan_id = plan["plan_id"]
        self.result.plan_name = plan["plan_name"]
        self.result.actions = plan["actions"]
        self.result.resources = plan["resources"]
        self.result.notifications = plan["notifications"]

        yield "data: [DONE]\n\n"

    # ── internal helpers ──────────────────────────────────────────────────────

    async def _fetch_data(self) -> tuple[dict, dict]:
        db = get_db_service()
        try:
            overview = await db.get_flood_situation_overview()
        except Exception as exc:
            logger.error("[%s] DB overview failed: %s", self.session_id, exc)
            overview = {"stations": [], "active_alarms": [], "station_count": 0, "alarm_count": 0}

        weather = await self._fetch_weather()
        return overview, weather

    async def _fetch_weather(self) -> dict:
        settings = get_settings()
        api_key = settings.weather_api_key
        location = settings.default_weather_location

        if not api_key:
            return {
                "total_precip_24h_mm": 55.0,
                "forecast_24h": [
                    {"time": "未来0-6h", "precip_mm": 5.0, "description": "小雨"},
                    {"time": "未来6-12h", "precip_mm": 15.0, "description": "中雨"},
                    {"time": "未来12-18h", "precip_mm": 25.0, "description": "大雨"},
                    {"time": "未来18-24h", "precip_mm": 10.0, "description": "中雨转小雨"},
                ],
                "source": "模拟数据",
            }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://devapi.qweather.com/v7/weather/24h",
                    params={"location": location, "key": api_key},
                )
                resp.raise_for_status()
                data = resp.json()
            if data.get("code") != "200":
                return {"total_precip_24h_mm": 0, "source": "error"}
            hourly = data.get("hourly", [])
            total = sum(float(h.get("precip", 0)) for h in hourly)
            return {
                "total_precip_24h_mm": round(total, 1),
                "forecast_24h": [{"time": h.get("fxTime"), "precip_mm": float(h.get("precip", 0))} for h in hourly],
                "source": "和风天气",
            }
        except Exception as exc:
            logger.warning("[%s] weather fetch failed: %s", self.session_id, exc)
            return {"total_precip_24h_mm": 0, "source": "unavailable"}

    def _summarise_stations(self, overview: dict) -> str:
        stations = overview.get("stations", [])
        if not stations:
            return "当前无监测站数据。"
        lines = [f"共 {len(stations)} 个监测站，活跃告警 {overview.get('alarm_count', 0)} 条。"]
        for s in stations[:5]:
            wl = s.get("water_level")
            rf = s.get("rainfall")
            name = s.get("name", s.get("code", "未知站点"))
            parts = [f"**{name}**"]
            if wl is not None:
                warn = s.get("warning_level")
                danger = s.get("danger_level")
                level_str = f"水位 {float(wl):.2f}m"
                if warn:
                    level_str += f"（警戒 {float(warn):.2f}m"
                    if danger:
                        level_str += f" / 危险 {float(danger):.2f}m"
                    level_str += "）"
                parts.append(level_str)
            if rf is not None:
                parts.append(f"雨量 {float(rf):.1f}mm")
            lines.append("  ".join(parts))
        return "\n".join(lines)

    def _assess_risk(self, overview: dict, weather: dict) -> dict:
        stations = overview.get("stations", [])
        alarm_count = overview.get("alarm_count", 0)
        forecast_24h = float(weather.get("total_precip_24h_mm", 0))

        # Aggregate risk scores across all stations
        max_wl_score = 0.0
        max_rf_score = 0.0
        key_risks: list[str] = []

        for s in stations:
            wl = s.get("water_level")
            warn = s.get("warning_level")
            danger = s.get("danger_level")
            rf = s.get("rainfall")
            warn_rf = s.get("rainfall_warning")
            danger_rf = s.get("rainfall_danger")

            if wl is not None and warn and danger:
                res = calculate_water_level_risk(
                    float(wl), float(warn), float(danger)
                )
                score = res["risk_score"]
                if score > max_wl_score:
                    max_wl_score = score
                if score >= 40:
                    name = s.get("name", s.get("code", ""))
                    key_risks.append(f"{name}水位超警戒（当前{float(wl):.2f}m）")

            if rf is not None:
                rf_res = calculate_rainfall_risk(
                    float(rf), float(rf) * 4, forecast_24h
                )
                score = rf_res["risk_score"]
                if score > max_rf_score:
                    max_rf_score = score

        if alarm_count > 0:
            key_risks.append(f"当前存在 {alarm_count} 条活跃告警")
        if forecast_24h >= 50:
            key_risks.append(f"未来24小时预报降雨量 {forecast_24h:.0f}mm")

        composite = calculate_composite_risk(max_wl_score, max_rf_score, alarm_count)
        return {
            "level": composite["risk_level"],
            "score": composite["composite_risk_score"],
            "response_level": composite["response_level"],
            "key_risks": key_risks or ["当前水情平稳，无明显风险"],
        }

    def _build_plan(self, risk: dict) -> dict:
        level = risk["level"]
        if level == "none":
            level = "low"  # always generate at least a basic plan

        plan_id = generate_plan_id()
        template = get_response_template(level)
        response_level = template["response_level"]

        actions = []
        for i, a in enumerate(template["actions"]):
            actions.append({
                "action_id": f"{plan_id}-A{i + 1:02d}",
                "action_type": a["type"],
                "description": a["desc"],
                "priority": a["priority"],
                "responsible_dept": template["command_center"],
                "deadline_minutes": None,
                "status": "pending",
            })

        resources = []
        for r in template["resources"]:
            resources.append({
                "resource_type": r["type"],
                "resource_name": r["name"],
                "quantity": r["quantity"],
                "source_location": "应急物资仓库",
                "target_location": "受灾区域",
                "eta_minutes": None,
            })

        notifications = build_notifications(risk["level"], plan_id)

        return {
            "plan_id": plan_id,
            "plan_name": f"{response_level}防汛应急预案",
            "response_level": response_level,
            "command_center": template["command_center"],
            "actions": actions,
            "resources": resources,
            "notifications": notifications,
        }

    def _build_prompt(self, station_summary: str, risk: dict, plan: dict) -> str:
        return f"""你是一名专业的防汛应急指挥助手。请根据以下实时数据生成简洁专业的防汛应急响应报告（Markdown格式）。

## 当前水情
{station_summary}

## 风险评估
- 综合风险等级：**{risk['level']}**（{risk.get('response_level', '')}）
- 风险评分：{risk['score']:.1f}/100
- 主要风险：{chr(10).join('  - ' + r for r in risk['key_risks'])}

## 应急预案概要
- 预案编号：{plan['plan_id']}
- 响应级别：{plan['response_level']}
- 指挥机构：{plan['command_center']}
- 措施数量：{len(plan['actions'])} 项
- 资源调度：{len(plan['resources'])} 类

用户请求：{self.query}

请生成一份结构清晰的应急响应报告，包含：水情摘要、风险研判、重点措施（列出优先级最高的3-5项）、资源部署要点。语言简洁，面向现场指挥人员。"""

    def _build_fallback(self, risk: dict, plan: dict) -> str:
        level_names = {
            "critical": "极高", "high": "高", "moderate": "中等", "low": "低", "none": "无"
        }
        lines = [
            f"# {plan['plan_name']}\n",
            f"**当前综合洪水风险：{level_names.get(risk['level'], risk['level'])}**  ",
            f"风险评分：{risk['score']:.1f}/100，启动 {plan['response_level']}。\n",
            "## 主要风险",
            *[f"- {r}" for r in risk["key_risks"]],
            "\n## 优先措施",
        ]
        for a in plan["actions"][:5]:
            lines.append(f"- [{a['action_type']}] {a['description']}")
        lines += [
            "\n## 资源调度",
            *[f"- {r['resource_name']} × {r['quantity']} {r['resource_type']}" for r in plan["resources"][:4]],
            f"\n指挥机构：**{plan['command_center']}**",
        ]
        return "\n".join(lines)
