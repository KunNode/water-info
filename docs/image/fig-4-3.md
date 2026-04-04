# 图4-3 多智能体角色分工图文字描述

## 对应论文位置
第4章 `4.2.1 多智能体角色划分` 后。

## 建议图型
角色关系图或方框流程图。

## 文字描述
图中以 `Supervisor` 为中心节点，置于顶部或中央，表示任务调度与路由控制。其下按职责分成六个主要执行智能体和一个执行监控智能体：`DataAnalyst` 负责读取站点、观测、告警、规则并输出态势摘要；`RiskAssessor` 负责根据摘要与天气信息生成风险等级、风险分数和关键风险因素；`PlanGenerator` 负责生成预案编号、预案名称、动作列表和摘要；`ResourceDispatcher` 负责给出人员、设备、物资、车辆等资源调度方案；`Notification` 负责确定通知对象、渠道与通知内容；`ExecutionMonitor` 负责跟踪动作完成情况、问题清单和建议；`FinalResponse` 位于底部，负责整合全链路输出为最终响应文本。若希望与代码更贴合，可在 `ResourceDispatcher` 和 `Notification` 之间加一个 `parallel_dispatch` 节点，表示并行调度。

## 必含元素
- `supervisor`
- `data_analyst`
- `risk_assessor`
- `plan_generator`
- `resource_dispatcher`
- `notification`
- `execution_monitor`
- `final_response`
- 可选：`parallel_dispatch`

## 标注建议
- 每个节点下方写一行职责说明，避免只有英文节点名。
- Supervisor 节点旁写“根据 `next_agent` 动态路由”。

## 项目依据
- `water-info-ai/app/graph.py`
- `water-info-ai/app/agents/supervisor.py`
- `water-info-ai/app/agents/data_analyst.py`
- `water-info-ai/app/agents/risk_assessor.py`
- `water-info-ai/app/agents/plan_generator.py`
- `water-info-ai/app/agents/resource_dispatcher.py`
- `water-info-ai/app/agents/notification_agent.py`
- `water-info-ai/app/agents/execution_monitor.py`

