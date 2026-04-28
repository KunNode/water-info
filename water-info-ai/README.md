# 水务 AI 防洪应急服务

基于 FastAPI + LangGraph 的防洪应急多 Agent AI 服务。

当前实现已经从“顺序流水线”切换到“共享状态 + 多节点图编排”的结构，前端继续通过 REST 和 SSE 接口接入，平台侧继续由 `water-info-platform` 代理和鉴权。

## 当前状态

- 已完全切到 LangGraph 图编排，唯一主入口在 [app/graph.py](./app/graph.py)
- 已接入的核心节点：
  - `supervisor`
  - `conversation_assistant`
  - `data_analyst`
  - `risk_assessor`
  - `plan_generator`
  - `final_response`
- 已补齐骨架、后续可继续增强的节点：
  - `resource_dispatcher`
  - `notification`
  - `execution_monitor`
  - `parallel_dispatch`
- FastAPI 主入口已改为基于图执行，见 [app/main.py](./app/main.py)
- 现有前端依赖的 SSE 事件协议仍然保留：
  - `session_init`
  - `agent_update`
  - `risk_update`
  - `plan_update`
  - `agent_message`

## 架构概览

```text
water-info-admin (Vue)
        |
        |  /api/v1/flood/query
        |  /api/v1/flood/query/stream
        v
water-info-platform (Spring Boot)
        |
        |  proxy / auth / unified API
        v
water-info-ai (FastAPI)
        |
        |  LangGraph
        v
Supervisor
  -> ConversationAssistant
  -> DataAnalyst
  -> RiskAssessor
  -> PlanGenerator
  -> ResourceDispatcher
  -> Notification
  -> ExecutionMonitor
  -> FinalResponse
        |
        +-> PostgreSQL / weather / platform APIs
```

## 目录结构

```text
water-info-ai/
├── app/
│   ├── agents/                # LangGraph 节点
│   │   ├── supervisor.py
│   │   ├── conversation_assistant.py
│   │   ├── data_analyst.py
│   │   ├── risk_assessor.py
│   │   ├── plan_generator.py
│   │   ├── resource_dispatcher.py
│   │   ├── notification.py
│   │   ├── execution_monitor.py
│   │   ├── parallel_dispatch.py
│   │   └── final_response.py
│   ├── services/              # 服务层
│   │   ├── llm.py
│   │   ├── platform_client.py
│   │   └── session.py
│   ├── tools/                 # 工具注册
│   │   ├── data_tools.py
│   │   ├── risk_tools.py
│   │   ├── plan_tools.py
│   │   └── simple_tool.py
│   ├── utils/
│   │   └── json_parser.py
│   ├── config.py
│   ├── database.py
│   ├── graph.py
│   ├── main.py
│   ├── models.py
│   ├── plan.py
│   ├── risk.py
│   └── state.py
├── tests/
├── pyproject.toml
└── README.md
```

## 节点职责

| 节点 | 职责 | 说明 |
| --- | --- | --- |
| `supervisor` | 路由和收敛 | 决定下一步交给哪个节点 |
| `conversation_assistant` | 对话助理 | 处理问候、闲聊、能力说明和模糊需求澄清 |
| `data_analyst` | 数据采集与摘要 | 获取站点、阈值、告警、天气等上下文 |
| `risk_assessor` | 风险评估 | 用结构化数据做 grounded 判断，模型负责组织风险结论 |
| `plan_generator` | 预案生成 | 由模型生成结构化预案，模板与规则只作为约束和回退 |
| `resource_dispatcher` | 资源调度 | 当前为骨架实现 |
| `notification` | 通知方案 | 当前已生成结构化通知记录 |
| `execution_monitor` | 执行监控 | 当前为骨架实现 |
| `parallel_dispatch` | 并行分发占位节点 | 用于后续资源和通知并行 fan-out |
| `final_response` | 最终回答 | 以助手口吻组织结论、依据和下一步建议 |

## 共享状态

共享状态定义在 [app/state.py](./app/state.py)，主要字段包括：

- `session_id`
- `user_query`
- `messages`
- `iteration`
- `data_summary`
- `overview_data`
- `weather_forecast`
- `risk_assessment`
- `emergency_plan`
- `resource_plan`
- `notifications`
- `final_response`
- `next_agent`
- `error`

设计原则是：

- 节点只改自己负责的状态片段
- 风险、预案等关键结果尽量保留结构化对象
- SSE 和 REST 响应在入口层统一转换

## RAG 知识库

当前 AI 服务已经接入一层可检索、可引用的知识库：

- 支持 `Markdown / TXT / PDF / DOCX` 文档上传
- 文档会被切块后写入 `kb_document / kb_chunk / kb_embedding / kb_ingest_job`
- 检索走“向量召回 + 关键词召回 + RRF 融合”
- LangGraph 新增 `knowledge_retriever` 节点
- `risk_assessor`、`plan_generator`、`conversation_assistant` 会在合适场景注入证据片段
- SSE 新增 `evidence_update` 事件，前端可以展示命中的引用片段

### 知识库 API

- `POST /api/v1/kb/documents`
- `GET /api/v1/kb/documents`
- `GET /api/v1/kb/documents/{id}`
- `DELETE /api/v1/kb/documents/{id}`
- `POST /api/v1/kb/documents/{id}/reindex`
- `POST /api/v1/kb/search`
- `GET /api/v1/kb/stats`

### CLI

```bash
cd water-info-ai
uv run python -m app.rag.cli ingest /path/to/manual.md
```

### RAG 相关环境变量

```env
EMBEDDING_API_KEY=your-siliconflow-api-key
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
RAG_TOP_K=5
RAG_MIN_SCORE=0.25
RAG_CHUNK_SIZE=500
RAG_CHUNK_OVERLAP=80
```

## 当前工作流

一次查询会按用户意图动态走不同路径，例如：

```text
START
  -> supervisor
  -> conversation_assistant
  -> END

START
  -> supervisor
  -> data_analyst
  -> supervisor
  -> risk_assessor
  -> supervisor
  -> final_response
  -> END

START
  -> supervisor
  -> data_analyst
  -> supervisor
  -> risk_assessor
  -> supervisor
  -> plan_generator
  -> supervisor
  -> resource_dispatcher / notification
  -> supervisor
  -> final_response
  -> END
```

其中：

- `supervisor` 负责意图识别、站点聚焦和节点路由
- 普通闲聊会直接转到对话型 agent，而不会误触发数据分析
- 结构化工具层继续提供数据、规则和模板约束，但主回答口径由多 agent 协作完成

## API

### 1. 健康检查

```bash
GET /health
```

### 2. 非流式查询

```bash
POST /api/v1/flood/query
Content-Type: application/json

{
  "query": "分析当前水情并生成防洪应急预案",
  "session_id": "optional-session-id"
}
```

### 3. 流式查询

```bash
POST /api/v1/flood/query/stream
Content-Type: application/json
Accept: text/event-stream
```

返回的 SSE 事件包括：

- `session_init`
- `agent_update`
- `risk_update`
- `plan_update`
- `agent_message`

### 4. 预案与会话接口

- `GET /api/v1/plans`
- `GET /api/v1/plans/count`
- `GET /api/v1/plans/{plan_id}`
- `POST /api/v1/plans/{plan_id}/execute`
- `PATCH /api/v1/plans/{plan_id}/status`
- `DELETE /api/v1/plans/{plan_id}`
- `GET /api/v1/sessions`
- `GET /api/v1/sessions/count`
- `GET /api/v1/sessions/{session_id}`

## 运行方式

### 1. 安装依赖

```bash
cd water-info-ai
uv sync
```

### 2. 配置环境变量

复制模板：

```bash
cp .env.example .env
```

至少需要确认这些配置：

- `PG_HOST`
- `PG_PORT`
- `PG_DATABASE`
- `PG_USER`
- `PG_PASSWORD`
- `WATER_PLATFORM_BASE_URL`
- `WATER_PLATFORM_USERNAME`
- `WATER_PLATFORM_PASSWORD`
- `OPENAI_API_KEY`（可选；未配置时会走回退逻辑）

### 3. 启动服务

```bash
uv run python -m app.main
```

或：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8100
```

启动后可访问：

- `http://localhost:8100/docs`

## 开发说明

### 规则与模型的分工

当前实现采用“模型决策 + 工具/RAG grounding + 结构化校验”的思路：

- Supervisor：优先由 LLM 基于用户意图和 workflow_state 决定下一个 agent
- 数据与知识：监测数据、RAG 证据片段、风险规则分数作为 grounding 输入模型
- 结构化校验：风险 JSON、预案 JSON 必须通过字段、类型和业务边界检查
- 规则兜底：[app/risk.py](./app/risk.py) 和 [app/plan.py](./app/plan.py) 只作为安全边界与失败回退

这样做的好处是：

- 让模型真正参与意图判断、风险结论和预案生成
- 保留业务约束，不让模型脱离真实数据和制度依据胡说
- 避免系统退化成关键词路由和模板字段拼接器

## 测试

如果本地已安装开发依赖：

```bash
python -m pytest
```

建议优先关注：

- `tests/test_graph.py`
- `tests/test_graph_routing.py`
- `tests/test_agents.py`
- `tests/test_supervisor_routing.py`
- `tests/test_main_api.py`

## 技术栈

- Python 3.11+
- FastAPI
- LangGraph
- Pydantic v2
- asyncpg
- httpx

## 后续建议

当前 README 与当前代码实现已经对齐，旧顺序流水线已经移除。下一步更值得做的是：

1. 把 `resource_dispatcher`、`execution_monitor` 从占位实现补成真实业务节点。
2. 把 `parallel_dispatch` 改成真正的并行 fan-out，而不是占位节点。
3. 增加更完整的会话记忆与 checkpoint 能力。
4. 继续降低固定模板式 fallback 的占比，让更多回答由 agent 协作生成。
