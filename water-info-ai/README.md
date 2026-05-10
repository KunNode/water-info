# 水务 AI 防洪应急服务

`water-info-ai` 是防汛应急系统的 Python AI 服务。它基于 FastAPI 和 LangGraph，将会话记忆、实时水情数据、RAG 知识库、风险规则和 LLM 组合成多智能体防洪研判工作流。

## 当前能力

- LangGraph 图编排，不再使用旧的顺序流水线。
- 支持非流式 REST 查询和 SSE 流式查询。
- 直接读取 PostgreSQL 中的监测、告警、阈值、资源和知识库数据。
- 通过 Java 平台 API 保持需要业务一致性的写操作。
- 支持 OpenAI-compatible LLM，默认配置指向 DeepSeek。
- 支持 RAG：Markdown、TXT、PDF、DOCX 上传，切块、嵌入、检索和证据引用。
- 支持会话历史、长期记忆、执行轨迹和风险巡检。
- 支持 PostgreSQL LangGraph checkpointer，可通过 `LANGGRAPH_POSTGRES_ENABLED=true` 开启。

## 架构

```text
water-info-admin
  |
  | /api/v1/flood/query
  | /api/v1/flood/query/stream
  v
water-info-platform
  |
  | proxy / auth / unified response
  v
water-info-ai
  |
  v
LangGraph
  memory_loader
  -> supervisor
  -> conversation_assistant
  -> data_analyst
  -> knowledge_retriever
  -> risk_assessor
  -> plan_generator
  -> resource_dispatcher
  -> notification
  -> execution_monitor
  -> parallel_dispatch
  -> final_response
  -> memory_writer
```

并非每次查询都会经过所有节点。`supervisor` 会根据用户意图、已有状态和执行结果动态选择下一步。

## 目录结构

```text
water-info-ai/
├── app/
│   ├── agents/                 # LangGraph 节点
│   ├── api/                    # FastAPI router
│   ├── memory/                 # 会话与长期记忆
│   ├── rag/                    # 文档加载、切块、嵌入、检索
│   ├── services/               # 数据库、平台客户端、LLM、预案持久化、风险巡检
│   ├── tools/                  # Agent 可调用工具
│   ├── utils/                  # JSON 解析、超时工具
│   ├── config.py               # 环境变量配置
│   ├── database.py             # asyncpg 数据服务
│   ├── graph.py                # LangGraph 图定义
│   ├── main.py                 # FastAPI 入口
│   ├── state.py                # 共享状态和领域模型
│   ├── risk.py                 # 风险规则与回退
│   └── plan.py                 # 预案结构与回退
├── tests/
├── pyproject.toml
├── uv.lock
└── README.md
```

## 核心节点

| 节点 | 职责 |
| --- | --- |
| `memory_loader` | 加载当前会话短期上下文和用户可见长期记忆 |
| `supervisor` | 意图识别、站点聚焦、路由和收敛 |
| `conversation_assistant` | 问候、闲聊、能力说明、模糊需求澄清 |
| `data_analyst` | 查询站点、观测、阈值、告警、天气等上下文 |
| `knowledge_retriever` | 从知识库召回可引用证据 |
| `risk_assessor` | 基于实时数据、规则和证据生成风险评估 |
| `plan_generator` | 生成结构化应急预案 |
| `resource_dispatcher` | 生成资源调度建议并对接资源工具 |
| `notification` | 生成预警通知方案 |
| `execution_monitor` | 汇总预案执行进度和问题 |
| `parallel_dispatch` | 后续并行 fan-out 的占位节点 |
| `final_response` | 整理最终回答、依据和下一步建议 |
| `memory_writer` | 从本轮结果中提取高价值记忆并持久化 |

## 共享状态

共享状态定义在 [app/state.py](./app/state.py)。常用字段包括：

- `session_id`、`user_id`、`username`
- `user_query`、`messages`、`iteration`
- `intent`、`next_agent`、`supervisor_reasoning`
- `focus_station`、`data_summary`、`overview_data`
- `weather_forecast`、`risk_assessment`
- `emergency_plan`、`resource_plan`、`notifications`
- `evidence`、`evidence_context`
- `execution_progress`、`execution_traces`
- `memory_context`、`memory_write_result`
- `final_response`、`error`

节点约定：只写自己负责的状态片段，最终由 API 层把结构化对象转换为 REST/SSE 响应。

## 环境变量

复制模板：

```bash
cp .env.example .env
```

关键配置：

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | LLM API Key | empty |
| `OPENAI_API_BASE` | OpenAI-compatible base URL | `https://api.deepseek.com/v1` |
| `OPENAI_MODEL` | Chat model | `deepseek-chat` |
| `LLM_TIMEOUT` | LLM timeout seconds | `120` |
| `EMBEDDING_API_KEY` | RAG embedding API Key | falls back to `OPENAI_API_KEY` |
| `EMBEDDING_API_BASE` | Embedding API base URL | falls back to `OPENAI_API_BASE` |
| `EMBEDDING_MODEL` | Embedding model | empty |
| `EMBEDDING_DIM` | Embedding dimension | `1024` |
| `PG_HOST` / `PG_PORT` | PostgreSQL host and port | `localhost` / `5432` |
| `PG_DATABASE` | PostgreSQL database | `water_info` |
| `PG_USER` / `PG_PASSWORD` | PostgreSQL credentials | `postgres` / `postgres` |
| `REDIS_URL` / `REDIS_PASSWORD` | Redis session/cache settings | local Redis URL / empty |
| `WATER_PLATFORM_BASE_URL` | Java platform URL | `http://localhost:8080` |
| `WATER_PLATFORM_USERNAME` / `WATER_PLATFORM_PASSWORD` | Platform service login | `admin` / `admin123` |
| `AI_SERVICE_HOST` / `AI_SERVICE_PORT` | FastAPI bind address | `0.0.0.0` / `8100` |
| `LANGGRAPH_POSTGRES_ENABLED` | Enable Postgres checkpointer/store | `false` |
| `RAG_TOP_K` / `RAG_MIN_SCORE` | RAG retrieval limits | `5` / `0.25` |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | RAG chunking parameters | `500` / `80` |
| `RISK_SCAN_PERIODIC_ENABLED` | Enable scheduled risk scan | `true` |
| `RISK_SCAN_PERIODIC_MINUTES` | Risk scan interval | `15` |

## 运行

### 安装依赖

```bash
uv sync --extra dev
```

### 启动服务

```bash
uv run python -m app.main
```

或：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8100
```

访问：

- Swagger UI: `http://localhost:8100/docs`
- Health: `http://localhost:8100/health`

## API

### Flood Query

```http
POST /api/v1/flood/query
Content-Type: application/json

{
  "query": "分析当前水情并生成防洪应急预案",
  "session_id": "optional-session-id"
}
```

流式查询：

```http
POST /api/v1/flood/query/stream
Content-Type: application/json
Accept: text/event-stream
```

SSE 事件类型：

- `session_init`
- `agent_update`
- `agent_message`
- `risk_update`
- `plan_update`
- `evidence_update`
- `trace_update`

### Knowledge Base

- `POST /api/v1/kb/documents`
- `GET /api/v1/kb/documents`
- `GET /api/v1/kb/documents/{document_id}`
- `DELETE /api/v1/kb/documents/{document_id}`
- `POST /api/v1/kb/documents/{document_id}/reindex`
- `POST /api/v1/kb/search`
- `GET /api/v1/kb/stats`

CLI 导入：

```bash
uv run python -m app.rag.cli ingest /path/to/manual.md
```

### Plans and Conversations

- `GET /api/v1/plans`
- `GET /api/v1/plans/count`
- `GET /api/v1/plans/{plan_id}`
- `POST /api/v1/plans/{plan_id}/execute`
- `PATCH /api/v1/plans/{plan_id}/status`
- `DELETE /api/v1/plans/{plan_id}`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{session_id}`
- `GET /api/v1/conversations/{session_id}/messages`
- `PATCH /api/v1/conversations/{session_id}`
- `DELETE /api/v1/conversations/{session_id}`
- `GET /api/v1/sessions`
- `GET /api/v1/sessions/count`
- `GET /api/v1/sessions/{session_id}`

### Memory

- `GET /api/v1/memory?session_id=...`
- `GET /api/v1/memory/user`
- `PATCH /api/v1/memory/{memory_id}`
- `DELETE /api/v1/memory/{memory_id}`

Memory items are scoped by user and session namespaces. They are useful for preferences, previous decisions, and recent conversation continuity, but current risk assessment must still rely on live data and rules.

### Risk Scan

- `POST /api/v1/flood/risk-scan/trigger`

The scheduler can also run periodic scans according to `RISK_SCAN_PERIODIC_ENABLED` and `RISK_SCAN_PERIODIC_MINUTES`.

## RAG Notes

RAG tables are created by the Java platform migrations. The AI service performs:

1. Document loading from upload or CLI input.
2. Chunking with configured size and overlap.
3. Embedding through the configured embedding endpoint.
4. Hybrid retrieval with vector recall, keyword recall, and RRF fusion.
5. Evidence injection into `risk_assessor`, `plan_generator`, and `conversation_assistant`.

If no embedding API is configured, the service can still answer with live data and rule-based fallbacks, but evidence-backed retrieval will be limited.

## Testing and Quality

```bash
uv run pytest tests/ -v
uv run pytest tests/test_graph.py -v
uv run pytest tests/test_main_api.py -v
uv run ruff check app/ tests/
uv run ruff format app/ tests/
```

The test suite includes graph routing, agents, RAG helpers, memory service, platform client, risk tools, plan persistence, risk scan scheduler, and API behavior.

## Docker

The root `docker-compose.yml` builds this service as `ai`:

```bash
docker-compose build ai
docker-compose up -d postgres platform ai
docker-compose logs -f ai
```

In Docker, compose injects database, Redis, platform URL, service port, and `LANGGRAPH_POSTGRES_ENABLED=true`.

## Design Boundaries

- LLM output is grounded by structured data, RAG evidence, and validation.
- `app/risk.py` and `app/plan.py` are safety boundaries and fallback paths, not the primary product experience.
- Direct PostgreSQL reads are allowed for low-latency analysis.
- Writes that must obey platform business rules should go through `water-info-platform`.
- Memory context may guide phrasing and continuity, but it must not override live monitoring data.
