# 图4-1 系统总体架构图文字描述

## 对应论文位置
第4章 `4.1.1 总体架构概述` 后。

## 建议图型
系统架构图，推荐上下分层或左右分层框图。

## 文字描述
图顶部是“浏览器用户”，通过两种入口访问系统：开发环境可访问 `admin:5173`，统一访问入口通过 `Nginx:80`。第二层是“前端管理端”，标明基于 Vue3、Vite、Pinia、Element Plus。第三层是“接入与代理层”，以 Nginx 为中心，向下分别转发普通 REST 请求、SSE 流式请求和 WebSocket 实时消息。第四层是两个核心服务：左侧为 `water-info-platform`，运行在 `8080` 端口，基于 Spring Boot，负责认证授权、站点管理、观测数据、阈值规则、告警、审计和 AI 代理；右侧为 `water-info-ai`，运行在 `8100` 端口，基于 FastAPI 与 LangGraph，负责多智能体协同、风险评估、预案生成、资源调度、通知与执行监控。底层是 `PostgreSQL:5432` 与 `Redis:6379`。平台服务连接 PostgreSQL 与 Redis；AI 服务同样连接 PostgreSQL 和 Redis，并在图中以醒目标注说明“AI 读取实时数据可直接访问数据库，但业务写回需通过平台 API”。图右下角可补充 LLM API 外部依赖。

## 必含元素
- `Nginx:80`、`platform:8080`、`ai-service:8100`、`postgres:5432`、`redis:6379`。
- 前端与平台之间的 REST。
- 前端与平台之间的 WebSocket `/ws/alarms`。
- 前端与平台之间的 SSE `/api/v1/flood/query/stream`。
- AI 服务与数据库的直连读取。
- AI 服务与平台的 HTTP 调用。

## 标注建议
- 在 Nginx 到 SSE 链路上标注“关闭 buffering”。
- 在平台与 AI 服务之间标注“Java 后端代理 AI 接口”。

## 项目依据
- `docker-compose.yml`
- `nginx.conf`
- `water-info-platform/src/main/resources/application.yml`
- `water-info-ai/app/services/platform_client.py`

