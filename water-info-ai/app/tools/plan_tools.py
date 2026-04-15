"""预案生成与资源调度工具

供 PlanGenerator、ResourceDispatcher 智能体调用。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from langchain_core.tools import tool


@tool
def generate_plan_id() -> str:
    """生成唯一预案编号。

    Returns:
        格式为 EP-YYYYMMDD-XXXX 的预案编号
    """
    date_str = datetime.now().strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:4].upper()
    return f"EP-{date_str}-{short_id}"


@tool
def get_response_template(risk_level: str) -> str:
    """根据风险等级获取标准应急响应模板。

    Args:
        risk_level: 风险等级 (low/moderate/high/critical)

    Returns:
        JSON格式的响应模板，包含标准措施清单
    """
    templates = {
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
                {"type": "monitoring", "desc": "加密监测频次至每15分钟一次, 启用自动报警", "priority": 1},
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
                {"type": "物资", "name": "铅丝笼", "quantity": 500},
                {"type": "设备", "name": "挖掘机", "quantity": 3},
                {"type": "设备", "name": "运输车辆", "quantity": 10},
                {"type": "设备", "name": "冲锋舟", "quantity": 5},
                {"type": "设备", "name": "发电机", "quantity": 4},
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
                {"type": "物资", "name": "铅丝笼", "quantity": 2000},
                {"type": "物资", "name": "救生衣", "quantity": 500},
                {"type": "设备", "name": "挖掘机", "quantity": 8},
                {"type": "设备", "name": "运输车辆", "quantity": 30},
                {"type": "设备", "name": "冲锋舟", "quantity": 15},
                {"type": "设备", "name": "无人机", "quantity": 5},
                {"type": "车辆", "name": "指挥车", "quantity": 3},
            ],
        },
    }

    template = templates.get(risk_level, templates["low"])
    return json.dumps(template, ensure_ascii=False)


@tool
def lookup_emergency_contacts(risk_level: str) -> str:
    """查询应急响应各级联系人和部门。

    Args:
        risk_level: 风险等级 (low/moderate/high/critical)

    Returns:
        JSON格式的联系人列表
    """
    # 模拟数据 — 实际应对接通讯录系统
    contacts = {
        "low": [
            {"dept": "水务局值班室", "role": "值班领导", "name": "张三", "phone": "138****0001"},
            {"dept": "河道管理处", "role": "巡查主管", "name": "李四", "phone": "138****0002"},
        ],
        "moderate": [
            {"dept": "区防汛办", "role": "副主任", "name": "王五", "phone": "138****0003"},
            {"dept": "区应急管理局", "role": "值班负责人", "name": "赵六", "phone": "138****0004"},
            {"dept": "水务局", "role": "分管局长", "name": "钱七", "phone": "138****0005"},
        ],
        "high": [
            {"dept": "市防汛指挥部", "role": "副指挥长", "name": "孙八", "phone": "138****0006"},
            {"dept": "市应急管理局", "role": "局长", "name": "周九", "phone": "138****0007"},
            {"dept": "市水务局", "role": "局长", "name": "吴十", "phone": "138****0008"},
            {"dept": "武警支队", "role": "参谋长", "name": "郑十一", "phone": "138****0009"},
        ],
        "critical": [
            {"dept": "省防汛指挥部", "role": "指挥长", "name": "陈十二", "phone": "138****0010"},
            {"dept": "省应急管理厅", "role": "厅长", "name": "冯十三", "phone": "138****0011"},
            {"dept": "驻地部队", "role": "联络官", "name": "褚十四", "phone": "138****0012"},
            {"dept": "省卫健委", "role": "应急处长", "name": "卫十五", "phone": "138****0013"},
        ],
    }

    level_contacts = contacts.get(risk_level, contacts["low"])
    return json.dumps(level_contacts, ensure_ascii=False)


plan_generation_tools = [
    generate_plan_id,
    get_response_template,
    lookup_emergency_contacts,
]
