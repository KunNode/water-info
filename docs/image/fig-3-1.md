# 图3-1 防洪应急目标业务流程图文字描述

## 对应论文位置
第3章 `3.1.3 目标业务流程分析` 后。

## 建议图型
业务流程图，推荐 Mermaid `flowchart`。

## 文字描述
流程从“站点监测数据接入”开始，输入来源包括站点、传感器、观测数据和阈值规则。随后进入“异常触发”节点，分为两条入口，一条是观测值超过阈值触发告警，另一条是用户主动从 AI 智能指挥台发起查询。两个入口汇合后进入“数据分析”阶段，由系统整理站点概览、告警信息、规则信息和天气信息，输出防洪态势摘要。之后进入“风险评估”，根据水位、雨量、趋势和规则结果给出风险等级与风险分数。若风险较高，则进入“预案生成”，输出应急措施、责任部门、时限要求。后续并行进入“资源调度”和“通知发布”，分别生成资源清单与通知对象/渠道。最终进入“执行监控”，持续跟踪动作完成情况、问题清单和改进建议，并将结果返回前端页面，形成“监测异常 -> 处置执行 -> 状态反馈”的闭环。

## 必含元素
- 数据入口：站点、观测、阈值、告警。
- 触发条件：阈值告警或人工查询。
- 智能处理阶段：数据分析、风险评估、预案生成。
- 执行阶段：资源调度、通知发布、执行监控。
- 输出阶段：前端展示、预案结果、反馈闭环。

## 标注建议
- 在“异常触发”节点旁标注“阈值规则触发”。
- 在“执行监控”节点旁标注“支持会话追踪与状态回传”。

## 项目依据
- `water-info-platform/src/main/java/com/waterinfo/platform/module/observation/controller/ObservationController.java`
- `water-info-platform/src/main/java/com/waterinfo/platform/module/alarm/controller/AlarmController.java`
- `water-info-ai/app/graph.py`
- `water-info-admin/src/views/ai/command/index.vue`

