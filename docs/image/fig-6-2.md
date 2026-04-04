# 图6-2 典型场景端到端验证图文字描述

## 对应论文位置
第6章 `6.5.2 场景验证过程` 后。

## 建议图型
组合图，推荐“左侧前端过程截图 + 右侧结果摘要卡片”。

## 文字描述
该图应体现一次完整的端到端查询验证。左侧放置 AI 智能指挥台在执行查询“制定完整的防汛应急响应方案”时的页面截图，要求能看到用户输入、智能体进度、风险等级和预案状态。右侧放置一个结果摘要框，列出端到端冒烟测试中观测到的关键指标：`elapsed_seconds: 1.62`、`risk_level: moderate`、`risk_score: 46.3`、`plan_id: EP-20260312-A40E`、`actions_count: 6`、`resources_count: 6`、`notifications_count: 2`。若版面允许，可在左下角再补一条流程说明：“Supervisor -> DataAnalyst -> RiskAssessor -> PlanGenerator -> ResourceDispatcher/Notification -> FinalResponse”。这张图的目标不是展示某个单一页面，而是证明系统已经从用户查询、智能体协同、风险研判、预案生成到结果返回形成完整闭环。

## 必含元素
- 用户输入语句。
- 智能体进度状态。
- 风险等级与预案状态面板。
- 右侧结果统计卡片。
- 预案编号和数量型指标。

## 标注建议
- 在结果卡片顶部加标题“端到端冒烟测试结果”。
- 在页面截图上可用箭头指出风险区域和预案区域。

## 项目依据
- `water-info-ai/TEST_REPORT.md`
- `water-info-admin/src/views/ai/command/index.vue`
- `water-info-admin/src/composables/useSSE.ts`
- `water-info-ai/app/main.py`

