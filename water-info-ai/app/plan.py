"""Deterministic emergency plan fallbacks."""

from __future__ import annotations

from datetime import datetime, timezone

_TEMPLATES: dict[str, dict] = {
    "critical": {
        "response_level": "I级响应",
        "command_center": "市防汛抗旱指挥部",
        "actions": [
            {"type": "command", "desc": "启动最高级别联合会商和值班调度", "priority": 1},
            {"type": "evacuation", "desc": "组织危险区域人员立即转移避险", "priority": 1},
            {"type": "engineering", "desc": "抢险队伍前置到重点堤段和低洼区域", "priority": 1},
        ],
        "resources": [
            {"type": "人员", "name": "综合抢险队", "quantity": 80},
            {"type": "物资", "name": "编织袋", "quantity": 5000},
            {"type": "设备", "name": "移动排涝泵", "quantity": 12},
        ],
    },
    "high": {
        "response_level": "II级响应",
        "command_center": "市防汛指挥部",
        "actions": [
            {"type": "command", "desc": "启动防汛应急会商和加密巡查", "priority": 1},
            {"type": "warning", "desc": "向重点区域发布风险预警", "priority": 2},
            {"type": "engineering", "desc": "检查闸泵站和排涝通道运行状态", "priority": 2},
        ],
        "resources": [
            {"type": "人员", "name": "抢险队", "quantity": 40},
            {"type": "物资", "name": "砂石料", "quantity": 200},
            {"type": "设备", "name": "巡查车辆", "quantity": 6},
        ],
    },
    "moderate": {
        "response_level": "III级响应",
        "command_center": "区防汛办",
        "actions": [
            {"type": "monitoring", "desc": "加密监测站点水位和雨量采集", "priority": 2},
            {"type": "inspection", "desc": "巡查重点河段、涵闸和低洼易涝点", "priority": 2},
            {"type": "standby", "desc": "通知抢险队伍和物资仓库保持待命", "priority": 3},
        ],
        "resources": [
            {"type": "人员", "name": "巡查组", "quantity": 16},
            {"type": "物资", "name": "防汛沙袋", "quantity": 800},
            {"type": "设备", "name": "便携水泵", "quantity": 4},
        ],
    },
    "low": {
        "response_level": "IV级响应",
        "command_center": "水务局值班室",
        "actions": [
            {"type": "monitoring", "desc": "维持常态监测并关注天气变化", "priority": 3},
            {"type": "standby", "desc": "确认值班人员和联络渠道畅通", "priority": 3},
        ],
        "resources": [
            {"type": "人员", "name": "值班巡查人员", "quantity": 6},
            {"type": "物资", "name": "基础防汛物资包", "quantity": 20},
        ],
    },
    "none": {
        "response_level": "常态监测",
        "command_center": "水务局值班室",
        "actions": [
            {"type": "monitoring", "desc": "保持常规水雨情监测", "priority": 4},
            {"type": "record", "desc": "记录监测结果并按班次交接", "priority": 4},
        ],
        "resources": [
            {"type": "人员", "name": "值班人员", "quantity": 2},
        ],
    },
}


def generate_plan_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"EP-{timestamp}"


def get_response_template(risk_level: str) -> dict:
    return _TEMPLATES.get(str(risk_level).lower(), _TEMPLATES["low"])


def build_notifications(risk_level: str, plan_id: str) -> list[dict]:
    level = str(risk_level).lower()
    template = get_response_template(level)
    channels = {
        "critical": ["sms", "wechat", "broadcast"],
        "high": ["sms", "wechat"],
        "moderate": ["wechat", "sms"],
        "low": ["wechat"],
        "none": ["wechat"],
    }.get(level, ["wechat"])
    targets = {
        "critical": ["市防汛指挥部", "应急管理局", "重点区域责任人"],
        "high": ["市防汛指挥部", "区应急管理局"],
        "moderate": ["区防汛办", "水务局"],
        "low": ["水务局值班室"],
        "none": ["水务局值班室"],
    }.get(level, ["水务局值班室"])
    content = f"{plan_id} 已触发{template['response_level']}，请按预案落实监测、巡查和处置。"
    return [
        {
            "target": target,
            "channel": channels[min(index, len(channels) - 1)],
            "content": content,
            "status": "pending",
        }
        for index, target in enumerate(targets)
    ]
