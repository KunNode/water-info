# 图1-1 论文研究内容与技术路线图文字描述

## 对应论文位置
第1章 `1.3 研究内容` 后。

## 建议图型
技术路线图，推荐使用横向流程图或分阶段路线图。

## 文字描述
整张图以“基于多智能体协同的防洪应急预案生成与执行系统研究路线”为总标题，自左向右分成五个阶段。第一阶段是研究背景与问题提出，突出“监测与决策脱节、预案静态化、执行闭环不足”三类问题。第二阶段是研究目标，概括为“构建业务平台 + AI 服务 + 前端管理端协同的一体化防洪应急系统”。第三阶段是系统设计与实现，展示 Spring Boot 平台、FastAPI + LangGraph AI 服务、Vue3 前端、PostgreSQL、Redis、WebSocket、SSE 等核心技术。第四阶段是多智能体协同链路，依次放置 Supervisor、DataAnalyst、RiskAssessor、PlanGenerator、ResourceDispatcher、Notification、ExecutionMonitor。第五阶段是系统验证，标明功能联调、自动化测试、端到端冒烟测试和典型场景验证。

## 必含元素
- 问题层：监测数据、风险研判、应急预案、执行反馈。
- 技术层：Spring Boot、FastAPI、LangGraph、Vue3、PostgreSQL、Redis。
- 方法层：多智能体协同、共享状态、动态路由、实时通信。
- 验证层：`57 passed, 3 deselected` 与典型场景验证。

## 标注建议
- 每个阶段顶部使用短标题，如“问题分析”“系统设计”“实现技术”“协同机制”“验证评估”。
- 在技术实现阶段补一句“AI 直读数据库，业务写回经平台”。

## 项目依据
- `docs/thesis/thesis-complete.md`
- `docker-compose.yml`
- `water-info-ai/app/graph.py`
- `water-info-admin/src/views/ai/command/index.vue`

