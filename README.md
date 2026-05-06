# 智慧水利防汛应急管理系统

智慧水利防汛应急管理系统由 Java 业务平台、Python 多智能体 AI 服务和 Vue 管理端组成，覆盖监测站管理、水雨情采集、阈值告警、应急资源调度、AI 风险研判、应急预案生成和知识库检索增强。

## 系统组成

| 服务 | 目录 | 技术栈 | 默认端口 | 说明 |
| --- | --- | --- | --- | --- |
| 业务平台 | `water-info-platform` | Spring Boot 3.2.2 / Java 17 / MyBatis-Plus | `8080` | 统一 REST API、认证鉴权、告警、资源、AI 代理 |
| AI 服务 | `water-info-ai` | FastAPI / LangGraph / Python 3.11 | `8100` | 防汛多 Agent 编排、RAG、会话记忆、风险巡检 |
| 管理端 | `water-info-admin` | Vue 3 / TypeScript / Vite / Element Plus | `5173` | 数据大盘、监测管理、AI 指挥台、资源调度 |
| 反向代理 | `nginx.conf` | Nginx | `80` | API、SSE、WebSocket 和前端入口 |
| 数据组件 | `docker-compose.yml` | PostgreSQL / Redis | `5432` / `6379` | 业务数据、AI 直接读取、缓存与会话 |

## 架构概览

```text
Browser
  |
  | http://localhost:80
  v
Nginx
  |-- /api/v1/* --------------------> water-info-platform (:8080)
  |                                      |-- PostgreSQL / Redis
  |                                      |-- WebSocket /ws/alarms
  |                                      +-- proxy /api/v1/flood, /plans, /kb
  |
  +-- SSE /api/v1/flood/query/stream --> water-info-platform --> water-info-ai (:8100)
                                                       |
                                                       |-- LangGraph agents
                                                       |-- PostgreSQL direct read via asyncpg
                                                       |-- RAG embeddings and memory
                                                       +-- OpenAI-compatible LLM API
```

关键约定：AI 服务可以直接读 PostgreSQL 以降低分析延迟；需要保持业务规则一致性的写操作通过 Java 平台 API 完成。

## 功能范围

- 监测站、传感器、水位/雨量/流量等观测数据管理。
- 批量观测数据写入，单次最多 5000 条。
- 阈值规则与告警状态机，支持 `OPEN -> ACK -> CLOSED`。
- WebSocket 告警推送和 AI 查询 SSE 流式输出。
- RBAC 权限控制，内置 `ADMIN`、`OPERATOR`、`VIEWER` 角色。
- AI 智能指挥台：数据分析、风险评估、预案生成、通知建议、资源调度建议。
- 知识库：支持 Markdown、TXT、PDF、DOCX 上传，向量召回 + 关键词召回 + RRF 融合检索。
- 应急资源管理：物资、人员、车辆设备和调度记录。
- AI 会话管理、长期记忆、执行轨迹和定时风险巡检。

## 快速开始

### 环境要求

- Docker 和 Docker Compose
- Java 17+、Maven 3.8+（本地运行后端时需要）
- Python 3.11+、`uv`（本地运行 AI 服务时需要）
- Node.js 18+、npm（本地运行管理端时需要）

### 一键启动

```bash
cp water-info-ai/.env.example water-info-ai/.env
# 按需填写 OPENAI_API_KEY、EMBEDDING_API_KEY、PG_PASSWORD 等

docker-compose up -d --build
docker-compose logs -f
```

启动后访问：

- 管理端入口: `http://localhost`
- Java API 文档: `http://localhost/swagger-ui.html`
- Knife4j 文档: `http://localhost/doc.html`
- AI Swagger: `http://localhost:8100/docs`

默认管理员账号来自后端初始化配置：

```text
username: admin
password: Admin@123456
```

生产或共享环境必须通过 `ADMIN_PASSWORD`、`JWT_SECRET`、`PG_PASSWORD`、`REDIS_PASSWORD` 覆盖默认值。

### 只启动基础设施

```bash
docker-compose up -d postgres redis
```

### 本地运行后端

```bash
cd water-info-platform
mvn clean compile
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```

后端 API：

- `POST /api/v1/auth/login`
- `GET /api/v1/stations`
- `POST /api/v1/observations/batch`
- `GET /api/v1/alarms`
- `GET /api/v1/resources`
- `POST /api/v1/flood/query`
- `POST /api/v1/flood/query/stream`

### 本地运行 AI 服务

```bash
cd water-info-ai
uv sync --extra dev
cp .env.example .env
uv run python -m app.main
```

### 本地运行管理端

```bash
cd water-info-admin
npm install
npm run dev
```

Vite 开发代理会把 `/api/v1/flood` 转到 AI 服务，把其他 `/api` 转到 Java 平台，把 `/ws` 转到后端 WebSocket。

## 项目结构

```text
code-work/
├── water-info-platform/       # Spring Boot 业务平台
│   ├── src/main/java/...      # 模块化业务代码
│   └── src/main/resources/    # application 配置与 Flyway 迁移
├── water-info-ai/             # FastAPI + LangGraph AI 服务
│   ├── app/agents/            # 多 Agent 节点
│   ├── app/rag/               # 知识库加载、切块、嵌入、检索
│   ├── app/memory/            # 会话与长期记忆
│   └── tests/                 # pytest 测试
├── water-info-admin/          # Vue 3 管理端
│   ├── src/views/             # 页面
│   ├── src/api/               # Axios API 封装
│   └── src/stores/            # Pinia 状态
├── docker-compose.yml
├── nginx.conf
└── README.md
```

## 开发与验证

### 后端

```bash
cd water-info-platform
mvn clean compile
mvn test
mvn test -Dtest=StationServiceTest
mvn package -DskipTests
```

### AI 服务

```bash
cd water-info-ai
uv run pytest tests/ -v
uv run ruff check app/ tests/
uv run ruff format app/ tests/
```

### 管理端

```bash
cd water-info-admin
npm run build
npm run lint
npm run format
```

注意：仓库中的 `water-info-admin` 已包含 ESLint 配置；如在其他环境缺失配置，`npm run lint` 会失败，需要先补齐配置再执行。

## 数据库迁移

后端使用 Flyway 自动执行 `water-info-platform/src/main/resources/db/migration/` 下的迁移。当前迁移覆盖核心水利表、RBAC、兼容视图/测试数据、性能索引、翠屏湖示例数据、RAG 知识库、风险巡检和资源管理。

新增迁移命名格式：

```text
V{N}__{description}.sql
```

当前序列存在历史空档（例如没有 `V6`），新增迁移应使用下一个未使用版本号。

## 常用运维命令

```bash
docker-compose ps
docker-compose logs -f platform
docker-compose logs -f ai
docker-compose logs -f nginx
docker-compose down
```

健康检查：

- 平台: `GET /actuator/health`
- AI: `GET /health`
- Nginx: `GET /health`

## 风险等级

| 等级 | 响应 | 含义 |
| --- | --- | --- |
| `none` | 无需响应 | 当前数据正常 |
| `low` | IV 级 | 接近警戒线，持续关注 |
| `moderate` | III 级 | 达到警戒线，准备响应 |
| `high` | II 级 | 接近危险线，启动应急协同 |
| `critical` | I 级 | 超过危险线，立即处置 |

## 安全提醒

- 首次部署后立即修改管理员密码。
- 生产环境必须更换 JWT 密钥，并启用 HTTPS。
- 不要提交真实 `.env`、数据库密码、LLM API Key。
- RAG 上传接口和系统管理接口应保持管理员权限限制。

## 子项目文档

- [water-info-platform/README.md](./water-info-platform/README.md)
- [water-info-ai/README.md](./water-info-ai/README.md)
