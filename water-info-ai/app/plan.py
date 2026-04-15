"""Template-based emergency plan generation — no LLM required."""

from __future__ import annotations

import uuid
from datetime import datetime


def generate_plan_id() -> str:
    """Generate a unique plan ID: EP-YYYYMMDD-XXXX."""
    return f"EP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"


def get_response_template(risk_level: str) -> dict:
    """Return the standard response template for the given risk level."""
    templates: dict[str, dict] = {
        "low": {
            "response_level": "IV级响应",
            "command_center": "水务局值班室",
            "actions": [
                {"type": "monitoring", "desc": "加密监测频次至每小时一次", "priority": 3},
                {"type": "patrol", "desc": "安排巡查人员对重点堤段进行巡查", "priority": 3},
                {"type": "notification", "desc": "通知相关部门关注水情变化", "priority": 4},
                {"type": "standby", "desc": "防汛物资就位检查", "priority": 4},
            ],
            "resources": [
                {"type": "人员", "name": "巡查人员", "quantity": 4},
                {"type": "设备", "name": "巡查车辆", "quantity": 2},
            ],
        },
        "moderate": {
            "response_level": "III级响应",
            "command_center": "区防汛指挥部",
            "actions": [
                {"type": "monitoring", "desc": "加密监测频次至每30分钟一次", "priority": 2},
                {"type": "patrol", "desc": "全线堤防巡查，记录险情", "priority": 2},
                {"type": "gate_control", "desc": "调整水闸开度，加大泄洪量", "priority": 2},
                {"type": "standby", "desc": "抢险队伍集结待命", "priority": 2},
                {"type": "notification", "desc": "发布黄色预警，通知低洼地区居民做好准备", "priority": 3},
                {"type": "resource_deploy", "desc": "调运防汛沙袋、编织袋至重点堤段", "priority": 3},
            ],
            "resources": [
                {"type": "人员", "name": "巡查人员", "quantity": 12},
                {"type": "人员", "name": "抢险队员", "quantity": 30},
                {"type": "物资", "name": "沙袋", "quantity": 5000},
                {"type": "物资", "name": "编织袋", "quantity": 3000},
                {"type": "设备", "name": "巡查车辆", "quantity": 4},
                {"type": "设备", "name": "抢险车辆", "quantity": 2},
            ],
        },
        "high": {
            "response_level": "II级响应",
            "command_center": "市防汛抗旱指挥部",
            "actions": [
                {"type": "monitoring", "desc": "加密监测频次至每15分钟一次，启用自动报警", "priority": 1},
                {"type": "patrol", "desc": "24小时不间断堤防巡查", "priority": 1},
                {"type": "gate_control", "desc": "全面调控水闸、泵站运行", "priority": 1},
                {"type": "evacuation", "desc": "组织危险区域群众转移避险", "priority": 1},
                {"type": "resource_deploy", "desc": "大批量调运防汛抢险物资", "priority": 1},
                {"type": "notification", "desc": "发布橙色预警，启动应急广播", "priority": 1},
                {"type": "standby", "desc": "消防、武警、民兵预备队集结", "priority": 2},
                {"type": "engineering", "desc": "组织专业队伍对险工险段实施加固", "priority": 2},
            ],
            "resources": [
                {"type": "人员", "name": "巡查人员", "quantity": 30},
                {"type": "人员", "name": "抢险队员", "quantity": 100},
                {"type": "人员", "name": "转移安置人员", "quantity": 20},
                {"type": "物资", "name": "沙袋", "quantity": 20000},
                {"type": "物资", "name": "编织袋", "quantity": 10000},
                {"type": "设备", "name": "挖掘机", "quantity": 3},
                {"type": "设备", "name": "运输车辆", "quantity": 10},
                {"type": "设备", "name": "冲锋舟", "quantity": 5},
            ],
        },
        "critical": {
            "response_level": "I级响应",
            "command_center": "省防汛抗旱指挥部",
            "actions": [
                {"type": "monitoring", "desc": "全域实时监控，5分钟更新频次", "priority": 1},
                {"type": "evacuation", "desc": "立即启动全面转移预案，转移所有危险区域群众", "priority": 1},
                {"type": "gate_control", "desc": "实施超标准洪水调度方案", "priority": 1},
                {"type": "engineering", "desc": "全力组织堤防抢险加固", "priority": 1},
                {"type": "resource_deploy", "desc": "紧急调集省级防汛物资储备", "priority": 1},
                {"type": "notification", "desc": "发布红色预警，全媒体发布应急信息", "priority": 1},
                {"type": "rescue", "desc": "部署水上救援力量待命", "priority": 1},
                {"type": "medical", "desc": "启动卫生防疫应急预案", "priority": 2},
                {"type": "logistics", "desc": "开设临时安置点，保障转移群众基本生活", "priority": 2},
                {"type": "traffic", "desc": "实施交通管制，确保应急通道畅通", "priority": 2},
            ],
            "resources": [
                {"type": "人员", "name": "巡查人员", "quantity": 60},
                {"type": "人员", "name": "抢险队员", "quantity": 300},
                {"type": "人员", "name": "消防救援", "quantity": 50},
                {"type": "人员", "name": "医疗救护", "quantity": 20},
                {"type": "物资", "name": "沙袋", "quantity": 50000},
                {"type": "物资", "name": "编织袋", "quantity": 30000},
                {"type": "设备", "name": "挖掘机", "quantity": 8},
                {"type": "设备", "name": "冲锋舟", "quantity": 15},
                {"type": "设备", "name": "无人机", "quantity": 5},
            ],
        },
    }
    return templates.get(risk_level, templates["low"])


def build_notifications(risk_level: str, plan_id: str) -> list[dict]:
    """Build notification records based on risk level."""
    channels_by_level = {
        "critical": ["SMS", "WeChat", "broadcast"],
        "high": ["SMS", "WeChat"],
        "moderate": ["WeChat", "SMS"],
        "low": ["WeChat"],
        "none": [],
    }
    targets_by_level = {
        "critical": ["省防汛指挥部", "市应急管理局", "武警支队", "沿岸居民"],
        "high": ["市防汛指挥部", "区应急管理局", "沿岸居民"],
        "moderate": ["区防汛办", "水务局", "相关部门"],
        "low": ["水务局值班室", "河道管理处"],
        "none": [],
    }
    channels = channels_by_level.get(risk_level, [])
    targets = targets_by_level.get(risk_level, [])
    content_map = {
        "critical": "【红色预警】当前洪水风险极高，请立即启动I级应急响应，组织全面转移。",
        "high": "【橙色预警】当前洪水风险较高，请启动II级应急响应，加强防守和疏散准备。",
        "moderate": "【黄色预警】当前洪水风险中等，请启动III级应急响应，加强巡查和物资准备。",
        "low": "【蓝色预警】当前水位偏高，请关注水情变化，做好防汛准备。",
        "none": "",
    }
    content = content_map.get(risk_level, "")
    records = []
    for target in targets:
        for channel in channels:
            records.append({
                "target": target,
                "channel": channel.lower(),
                "content": content,
                "status": "pending",
            })
    return records
