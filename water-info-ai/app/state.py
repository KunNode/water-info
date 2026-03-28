"""多智能体系统的共享状态定义

使用 TypedDict 定义 LangGraph 状态，所有智能体节点在同一状态上读写。
"""

from __future__ import annotations

import operator
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ──────────────────────────────────────────────
# 枚举 / 常量
# ──────────────────────────────────────────────

class RiskLevel(str, Enum):
    """洪水风险等级"""
    NONE = "none"          # 无风险
    LOW = "low"            # 低风险 (蓝色)
    MODERATE = "moderate"  # 中风险 (黄色)
    HIGH = "high"          # 高风险 (橙色)
    CRITICAL = "critical"  # 极高风险 (红色)


class PlanStatus(str, Enum):
    """预案状态"""
    DRAFT = "draft"              # 草案
    PENDING_REVIEW = "pending"   # 待审核
    APPROVED = "approved"        # 已批准
    EXECUTING = "executing"      # 执行中
    COMPLETED = "completed"      # 已完成
    CANCELLED = "cancelled"      # 已取消


class AgentName(str, Enum):
    """智能体名称"""
    SUPERVISOR = "supervisor"
    DATA_ANALYST = "data_analyst"
    RISK_ASSESSOR = "risk_assessor"
    PLAN_GENERATOR = "plan_generator"
    RESOURCE_DISPATCHER = "resource_dispatcher"
    NOTIFICATION = "notification"
    EXECUTION_MONITOR = "execution_monitor"
    PARALLEL_DISPATCH = "parallel_dispatch"


# ──────────────────────────────────────────────
# Pydantic 数据模型 (嵌入状态)
# ──────────────────────────────────────────────

class StationData(BaseModel):
    """监测站数据快照"""
    station_id: str
    station_name: str
    water_level: float | None = None
    water_level_warning: float | None = None
    water_level_danger: float | None = None
    rainfall_1h: float | None = None
    rainfall_24h: float | None = None
    flow_rate: float | None = None
    timestamp: datetime | None = None
    status: str = "normal"


class RiskAssessment(BaseModel):
    """风险评估结果"""
    risk_level: RiskLevel = RiskLevel.NONE
    risk_score: float = Field(0.0, ge=0, le=100)
    affected_stations: list[str] = Field(default_factory=list)
    affected_population: int = 0
    affected_area_km2: float = 0.0
    key_risks: list[str] = Field(default_factory=list)
    trend: Literal["rising", "stable", "falling"] = "stable"
    reasoning: str = ""


class EmergencyAction(BaseModel):
    """应急措施"""
    action_id: str
    action_type: str  # evacuation / resource_deploy / gate_control / patrol / ...
    description: str
    priority: int = Field(1, ge=1, le=5)
    responsible_dept: str = ""
    deadline_minutes: int | None = None
    status: str = "pending"


class ResourceAllocation(BaseModel):
    """资源调度方案"""
    resource_type: str  # 人员/设备/物资/车辆
    resource_name: str
    quantity: int
    source_location: str
    target_location: str
    eta_minutes: int | None = None


class EmergencyPlan(BaseModel):
    """应急预案"""
    plan_id: str = ""
    plan_name: str = ""
    risk_level: RiskLevel = RiskLevel.NONE
    trigger_conditions: str = ""
    actions: list[EmergencyAction] = Field(default_factory=list)
    resources: list[ResourceAllocation] = Field(default_factory=list)
    notification_targets: list[str] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.now)
    summary: str = ""


class NotificationRecord(BaseModel):
    """通知记录"""
    target: str
    channel: str  # sms / email / wechat / broadcast
    content: str
    sent_at: datetime | None = None
    status: str = "pending"


class ExecutionProgress(BaseModel):
    """执行进度"""
    total_actions: int = 0
    completed_actions: int = 0
    in_progress_actions: int = 0
    failed_actions: int = 0
    progress_pct: float = 0.0
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# LangGraph 状态 (TypedDict)
# ──────────────────────────────────────────────

def _merge_messages(left: list[dict], right: list[dict]) -> list[dict]:
    """合并消息列表（追加方式）"""
    return left + right


class FloodResponseState(TypedDict, total=False):
    """
    多智能体共享状态

    Annotated 字段使用 reducer 函数控制更新策略:
    - operator.add / _merge_messages → 追加
    - 无 reducer → 直接覆盖
    """

    # ---- 会话控制 ----
    session_id: str
    user_query: str
    messages: Annotated[list[dict], _merge_messages]
    chat_history: list[dict[str, Any]]
    current_agent: AgentName
    next_agent: AgentName | Literal["__end__"]
    iteration: int

    # ---- 数据采集 ----
    station_data: list[StationData]
    overview_data: dict[str, Any]
    alarm_data: list[dict[str, Any]]
    threshold_rules: list[dict[str, Any]]
    weather_forecast: dict[str, Any]
    historical_floods: list[dict[str, Any]]
    data_summary: str

    # ---- 风险评估 ----
    risk_assessment: RiskAssessment

    # ---- 预案 ----
    emergency_plan: EmergencyPlan

    # ---- 资源调度 ----
    resource_plan: list[ResourceAllocation]

    # ---- 通知 ----
    notifications: list[NotificationRecord]

    # ---- 执行监控 ----
    execution_progress: ExecutionProgress

    # ---- 最终输出 ----
    final_response: str
    error: str | None
