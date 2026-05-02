# AI 模块 RAG 功能集成设计与任务

> 状态：Draft · 负责人：AI 服务组 · 目标分支：`feature/ai-rag`
> 范围：`water-info-ai`、PostgreSQL（pgvector）、少量 `water-info-admin` 管理页

## 1. 背景与目标

当前 `water-info-ai` 以 LangGraph 多 Agent 编排为核心（`supervisor → data_analyst / risk_assessor / plan_generator / resource_dispatcher / notification / execution_monitor`），依赖实时 PostgreSQL 数据与 DeepSeek LLM。

问题：

1. `plan_generator` 依赖硬编码 `response_template`（`app/plan.py`），无法引入外部规范、法规、历史预案等长尾知识。
2. `risk_assessor` 对水文/工程专业知识的调用完全依赖 LLM 参数化记忆，易编造。
3. `conversation_assistant` 回答日常咨询（制度、操作手册、流域资料）时缺乏可溯源依据。

目标：为 AI 服务叠加一层可检索、可追溯、可治理的 **RAG 知识层**，让 Agent 在生成前能先检索相关知识并在输出中附上引用。

## 2. 范围

### 2.1 In Scope

1. 新增知识库数据模型与 pgvector 索引，落在现有 `water_info` 库。
2. 独立的文档摄入（ingest）管道：支持 Markdown / PDF / DOCX / TXT，分块、embedding、去重、版本化。
3. 检索服务：向量检索 + 关键词检索的混合召回，可选 rerank。
4. LangGraph 接入：
   - 新增 `@tool` 形式的 `knowledge_search`；
   - 新增 `knowledge_retriever` 节点（可被 `supervisor` 路由，也可被其他 Agent 以工具形式调用）；
   - `plan_generator` / `risk_assessor` / `conversation_assistant` 的 prompt 中加入"证据片段"槽位与引用输出约束。
5. FastAPI 管理接口：文档 CRUD、分块重建、检索调试。
6. `water-info-admin` 增加"知识库管理"页面（最小可用：上传、列表、删除、重建索引）。

### 2.2 Out of Scope

1. 不做多模态（图像/表格 OCR），首版纯文本。
2. 不引入第三方向量库（Milvus / Qdrant / Chroma），统一走 pgvector。
3. 不改动 Spring Boot 业务 API 协议。
4. 不做跨租户权限模型，知识库首版按"全员可读"处理，只在后台区分编辑权限。

## 3. 方案概述

### 3.1 总体数据流

```
(后台上传) ─▶ Ingest Pipeline ─▶ kb_document / kb_chunk(+embedding)
                                         ▲
                                         │ 检索
       Agent(Plan/Risk/Convo) ─▶ knowledge_search tool ─▶ Retriever(混合召回)
                                         │
                                         ▼
                              Evidence 片段注入 Prompt
                                         │
                                         ▼
                              LLM 生成带引用的回答
```

### 3.2 存储方案：pgvector

选择 pgvector 而非独立向量库的原因：

1. 项目已有 PostgreSQL 15，`water-info-ai` 使用 asyncpg 直连，零新增中间件。
2. 可与现有 `emergency_plan` / `conversation_message` 放在同一事务域，便于关联引用。
3. 向量规模预估：文档 ≤ 5k，chunk ≤ 100k，pgvector + ivfflat/hnsw 足够。

迁移脚本（Flyway，放在 `water-info-platform/src/main/resources/db/migration/`）：

- `V6__rag_schema.sql`
  - `CREATE EXTENSION IF NOT EXISTS vector;`
  - 表：
    - `kb_document(id, title, source_type, source_uri, mime, lang, version, status, created_by, created_at, updated_at, deleted)`
    - `kb_chunk(id, document_id, chunk_index, content, token_count, heading_path, metadata JSONB, created_at)`
    - `kb_embedding(chunk_id, model, embedding VECTOR(1024), created_at)` ——embedding 独立表，方便换模型时重建而不碰 chunk。
    - `kb_ingest_job(id, document_id, status, error, started_at, finished_at)`
  - 索引：
    - `CREATE INDEX ON kb_embedding USING hnsw (embedding vector_cosine_ops);`
    - `CREATE INDEX ON kb_chunk USING gin (to_tsvector('simple', content));`（中文用 simple 分词器 + jieba 预处理后写入；或引入 `zhparser`，视部署环境决定，首版用 `simple` + 客户端分词）。
    - `kb_document(status, deleted)`、`kb_chunk(document_id, chunk_index)` 普通索引。

### 3.3 Embedding 模型

首版采用 **OpenAI 兼容的 embedding 接口**，复用现有 LLM 客户端逻辑：

1. 默认：`bge-m3`（通过本地或兼容服务，1024 维，中文友好）。
2. 备选：DeepSeek 若未提供 embedding，则走 `text-embedding-3-small`（1536 维）或本地 `bge-large-zh-v1.5`（1024 维）。
3. 通过配置项 `EMBEDDING_API_BASE` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` 可切换，`kb_embedding.model` 记录模型名以支持多模型共存与迁移。

### 3.4 分块策略

1. Markdown：按标题层级（H1/H2/H3）分层 + 长度兜底（默认 target 500 tokens，overlap 80）。
2. PDF / DOCX：按段落（空行）+ 长度兜底；保留页码到 `metadata.page`。
3. TXT：按固定窗口（target 500，overlap 80）。
4. 每个 chunk 保存 `heading_path`（如 `["防汛应急预案","III 级响应","现场处置"]`），用于在检索结果中做面包屑展示与 LLM 约束。

### 3.5 检索策略（混合召回）

检索器输入：`query, top_k=8, filters?`；输出：`[{chunk_id, score, content, document_title, heading_path, source_uri}]`。

1. 向量召回：`embedding <=> :q_vec` 取 top 20。
2. 关键词召回：`to_tsvector` + `plainto_tsquery`，取 top 20（查询前用 jieba 切词）。
3. 融合：RRF（Reciprocal Rank Fusion，k=60），截断 top_k。
4. 可选 rerank：预留 `RERANK_API_BASE`（如 `bge-reranker-v2-m3`），默认关闭；后续开启只需加一层排序，不改上游。
5. MMR 去冗余：同 document_id 最多保留 3 段。

### 3.6 LangGraph 接入

**新增**：`app/tools/knowledge_tools.py`

```python
@tool
async def knowledge_search(query: str, top_k: int = 5, doc_types: list[str] | None = None) -> list[dict]:
    """检索知识库，返回 [{content, document_title, heading_path, source_uri, score}]"""
```

**新增节点**：`app/agents/knowledge_retriever.py`

- 读取 `state["user_query"]` 或上一个 Agent 的 `query_intent`，调用 `knowledge_search`。
- 写回 `state["evidence"]`：`list[Evidence]`，字段 `content / citation_id / document_title / source_uri / heading_path / score`。

**改造 graph（`app/graph.py`）**：

1. 在 `StateGraph` 中注册 `knowledge_retriever`。
2. `supervisor` 新增一条路由分支 `knowledge_retriever`，用于"纯知识问答"类问题（由 supervisor prompt 决定）。
3. `plan_generator` / `risk_assessor` / `conversation_assistant` 在节点入口内部直接调用 `knowledge_search`，不走额外路由（保持主路径稳定，避免回环）。

**State 变更（`app/state.py`）**：

```python
@dataclass
class Evidence:
    citation_id: str        # [1], [2] …
    content: str
    document_title: str
    source_uri: str
    heading_path: list[str]
    score: float

# FloodGraphState 增加：evidence: list[Evidence]
```

**Prompt 约束（`plan_generator` / `risk_assessor` / `conversation_assistant`）**：

1. 输入增加 `evidence` 段，带编号 `[1][2]…`。
2. 要求：引用需标注形如 `（依据 [1]）`；若无相关证据，必须声明"未命中知识库"；不得编造。
3. 响应 JSON 新增 `citations: [{citation_id, document_title, source_uri}]`。

### 3.7 Ingest 管道

目录：`water-info-ai/app/rag/`

- `loader.py`：按 MIME 解析 PDF（pypdf）/ DOCX（python-docx）/ MD / TXT。
- `splitter.py`：标题感知 + 长度兜底分块。
- `embedder.py`：批量 embedding（concurrency=4，重试 3 次，指数退避）。
- `indexer.py`：写入 `kb_document / kb_chunk / kb_embedding`，事务化，失败回滚 job。
- `jobs.py`：`ingest_document(document_id)` / `reindex_document(document_id)` / `reindex_all(model)`。

触发方式：

1. 管理接口 `POST /api/v1/kb/documents`（上传或传 URL），同步入库 metadata + 异步触发 `ingest_document`（通过 FastAPI `BackgroundTasks`，首版不引入 Celery）。
2. CLI：`python -m app.rag.cli ingest <path>`，用于批量初始化。

### 3.8 对外 API（FastAPI）

路由前缀 `/api/v1/kb`：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/documents` | 上传/注册文档（multipart 或 JSON+URL），返回 `document_id` |
| GET | `/documents` | 列表，支持 `status, source_type, q` |
| GET | `/documents/{id}` | 文档详情（含 chunk 数、embedding 模型、版本） |
| DELETE | `/documents/{id}` | 软删（`deleted=true`），同时下线 chunk/embedding |
| POST | `/documents/{id}/reindex` | 重新切块+embedding |
| POST | `/search` | 调试检索，入参 `{query, top_k, filters}` |
| GET | `/stats` | 文档数、chunk 数、模型分布、近期 ingest 成功率 |

鉴权：复用现有 `X-User-Id` / `X-Username` header 转发模式；写操作要求非空 user。

### 3.9 前端（`water-info-admin`）

新增菜单 "AI 助手 → 知识库管理"：

1. 文档列表（状态、来源、大小、chunk 数、最后重建时间）。
2. 上传（拖拽、单/多文件、带标题与标签）。
3. 检索调试面板（输入 query，可视化展示 top_k 命中 chunk 与得分，便于评测）。
4. 权限：仅 `ADMIN` 可写，`OPERATOR` 可查看调试，`VIEWER` 不可见。

首版不做富文本编辑，不做文档在线预览（链接 `source_uri` 由后端提供或给到原始下载）。

## 4. 实施阶段（建议分 5 个 PR）

### Phase 1：数据层 + pgvector（PR1）

1. Flyway `V6__rag_schema.sql`（pgvector 扩展 + 4 张表 + 索引）。
2. `water-info-ai/app/rag/schema.py`：asyncpg 查询封装，单元测试覆盖。
3. 本地 compose：`docker/postgres/Dockerfile` 基础镜像切换为 `pgvector/pgvector:pg15`（验证 CI 可启动）。

验收：迁移可幂等执行；`SELECT '[0.1,0.2]'::vector` 正常。

### Phase 2：Ingest 管道 + 最小 API（PR2）

1. `loader / splitter / embedder / indexer / jobs` 实现，`.env` 加入 `EMBEDDING_*` 配置。
2. `POST /api/v1/kb/documents` + `POST /api/v1/kb/documents/{id}/reindex`。
3. CLI `python -m app.rag.cli ingest`。
4. 单元测试：用一份示例 Markdown（如 `docs/sample/flood-plan-template.md`）走通全流程。

验收：上传 1 份 MD，`kb_chunk` 按标题分块，`kb_embedding.model` 与配置一致，错误文档可 reindex。

### Phase 3：混合检索 + 调试 API（PR3）

1. `app/rag/retriever.py`：向量 + 关键词 + RRF + MMR。
2. `POST /api/v1/kb/search`，返回命中明细。
3. Benchmarks：构造 20 条人工 Q/A，记录 recall@5、MRR@10 到 `docs/rag/benchmark-baseline.md`。

验收：基线指标落档；调试 API 可稳定复现排序。

### Phase 4：LangGraph 接入（PR4）

1. `app/tools/knowledge_tools.py` + `app/agents/knowledge_retriever.py`。
2. `state.py` 增加 `Evidence` 和 `evidence` 字段。
3. `supervisor` prompt 增加"知识问答"意图 → 路由到 `knowledge_retriever`。
4. `plan_generator` / `risk_assessor` / `conversation_assistant` prompt 改造：注入 evidence、要求带引用、结构化 `citations`。
5. 流式事件新增 `evidence_update` 类型（供前端高亮命中片段）。
6. 回归：现有 `tests/test_agents.py` 全绿；新增 `tests/test_rag_flow.py` 覆盖命中/未命中两类路径。

验收：流式接口前端可看到证据片段；无证据时输出显式"未命中知识库"。

### Phase 5：管理后台 + 运营（PR5）

1. 前端 "知识库管理"菜单 + 上传/列表/删除/重建/检索调试页面。
2. 后端 `GET /stats`、列表/详情接口补齐。
3. 运营文档：`docs/rag/ops.md`（接入新模型、重建索引流程、常见问题）。

验收：管理员可在前端完成一次完整的"上传 → 入库 → 搜索 → 删除"闭环。

## 5. 配置与依赖变更

### 5.1 Python 依赖（`water-info-ai/pyproject.toml`）

新增：

- `pgvector>=0.3`（asyncpg adapter）
- `pypdf>=5.0`
- `python-docx>=1.1`
- `markdown-it-py>=3.0`
- `jieba>=0.42`
- `tiktoken>=0.8`（token 计数，切分用）

### 5.2 环境变量（`.env.example`）

```
EMBEDDING_API_BASE=http://localhost:11434/v1
EMBEDDING_API_KEY=
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024
RERANK_API_BASE=
RERANK_MODEL=
RAG_TOP_K=5
RAG_MIN_SCORE=0.25
```

### 5.3 Docker

- `docker/postgres/` 切到 `pgvector/pgvector:pg15`（或基于 `postgres:15` + `apt install postgresql-15-pgvector`）。
- 首次启动后 Flyway 会自动执行 `V6__rag_schema.sql`，`CREATE EXTENSION` 需要 superuser，默认 `postgres` 用户已具备。

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| Embedding 服务不可用 | ingest 全部失败 | `kb_ingest_job` 记录 error，支持重试；检索回退纯关键词 |
| 知识库污染导致 LLM 被误导 | 生成质量下降 | 每条证据带 `score` 阈值（`RAG_MIN_SCORE`）；prompt 要求"无证据时明确说没有" |
| pgvector 规模超预期 | 查询变慢 | hnsw 索引 + 监控 `kb_chunk` 行数告警；必要时切 ivfflat 或外置向量库（预留抽象层 `Retriever` 接口） |
| 中文分词导致全文召回差 | 混合检索退化为单路 | 查询端 jieba 切词后再构造 `tsquery`；Phase 3 benchmark 直接量化 |
| Agent 流程回归 | 现有预案生成被破坏 | Phase 4 前 `tests/test_agents.py` 必须绿；RAG 对主路径为可选增强而非必选 |

## 7. 验收标准（整体）

1. 上传 ≥ 20 份真实防汛制度/预案/手册文档，知识库规模 ≥ 1000 chunk。
2. 20 条人工 Q/A 下，recall@5 ≥ 0.85、MRR@10 ≥ 0.65。
3. `plan_generator` 输出的 `citations` 字段非空占比 ≥ 80%（对于有相关文档的查询）。
4. 无证据场景下不再出现"编造条例名/文件号"的 bad case（人工抽查 30 条）。
5. 管理端可在 5 分钟内完成"上传一份新 PDF → 在 AI 会话中被检索到"的闭环。

## 8. 任务清单（Checklist）

- [ ] Phase 1：pgvector 启用 + 迁移脚本 + schema 封装
- [ ] Phase 2：ingest 管道（loader/splitter/embedder/indexer）+ 上传/重建 API + CLI
- [ ] Phase 3：混合检索器 + 调试 API + benchmark 基线
- [ ] Phase 4：LangGraph 工具/节点接入 + 三个 Agent prompt 改造 + Evidence 流式事件
- [ ] Phase 5：前端知识库管理页 + 运营文档
- [ ] 回归：`pytest water-info-ai/tests/` 全绿，`npm run build` 通过
- [ ] 文档：`README.md` 增加 RAG 章节、`.env.example` 更新

## 9. 参考

- 现有代码：`app/graph.py`、`app/agents/plan_generator.py`、`app/services/llm.py`、`app/state.py`
- pgvector: <https://github.com/pgvector/pgvector>
- 混合检索 RRF: Cormack et al., "Reciprocal Rank Fusion outperforms Condorcet and Individual Rank Learning Methods"
