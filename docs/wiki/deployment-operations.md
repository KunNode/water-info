# 部署与运维

## Docker Compose 组成

`docker-compose.yml` 启动以下服务：

| 服务 | 容器名 | 端口 | 说明 |
| --- | --- | --- | --- |
| `postgres` | `water-postgres` | `5432` | PostgreSQL 数据库 |
| `redis` | `water-redis` | `6379` | Redis 缓存和会话 |
| `platform` | `water-platform` | `8080` | Spring Boot 业务平台 |
| `ai` | `water-ai` | `8100` | FastAPI AI 服务 |
| `admin` | `water-admin` | `5173 -> 80` | 前端静态服务 |
| `nginx` | `water-nginx` | `80` | 统一入口和反向代理 |

## 一键启动

```bash
cp water-info-ai/.env.example water-info-ai/.env
# 编辑 water-info-ai/.env，填写 LLM/Embedding 配置

docker-compose up -d --build
docker-compose ps
```

访问：

- 管理端：`http://localhost`
- 平台 API 文档：`http://localhost/swagger-ui.html`
- Knife4j：`http://localhost/doc.html`
- AI Swagger：`http://localhost:8100/docs`

## 关键环境变量

| 变量 | 服务 | 说明 |
| --- | --- | --- |
| `PG_PASSWORD` | postgres/platform/ai | PostgreSQL 密码 |
| `REDIS_PASSWORD` | redis/platform/ai | Redis 密码 |
| `ADMIN_PASSWORD` | platform/ai | 初始管理员密码和 AI 服务平台登录密码 |
| `JWT_SECRET` | platform | JWT 签名密钥 |
| `AI_SERVICE_URL` | platform | Java 平台访问 AI 服务地址 |
| `OPENAI_API_KEY` | ai | LLM API Key |
| `OPENAI_API_BASE` | ai | OpenAI-compatible API Base |
| `OPENAI_MODEL` | ai | Chat model |
| `EMBEDDING_API_KEY` | ai | Embedding API Key |
| `LANGGRAPH_POSTGRES_ENABLED` | ai | 是否启用 LangGraph PostgreSQL checkpoint/store |

生产或共享环境必须覆盖默认密码和 JWT 密钥。

## 健康检查

| 层 | 地址 |
| --- | --- |
| Nginx | `GET /health` |
| Platform | `GET /actuator/health` |
| AI | `GET /health` |
| PostgreSQL | `pg_isready -U root -d water_info` |
| Redis | `redis-cli -a <password> ping` |

## 日志

```bash
docker-compose logs -f platform
docker-compose logs -f ai
docker-compose logs -f nginx
docker-compose logs -f postgres
docker-compose logs -f redis
```

平台和 AI 服务分别挂载：

- `platform-logs:/app/logs`
- `ai-logs:/app/logs`

## Nginx 关键配置

- `/api/v1/` 转发到 Java 平台。
- `/api/v1/flood/query/stream` 单独关闭 buffering，支持 SSE。
- `/ws/` 支持 WebSocket upgrade。
- `/swagger-ui/`、`/v3/api-docs`、`/doc.html` 代理到平台 API 文档。
- `/api/v1/auth/login` 有更严格限流。
- 拦截 `.env`、`.git`、`.bak` 等敏感路径。

## 安全基线

- 不要在生产使用默认 `PG_PASSWORD=123456`、`REDIS_PASSWORD=123456`、`Admin@123456`。
- `JWT_SECRET` 必须使用高熵密钥。
- AI Key 只放在服务端环境变量或 `.env`，不要提交到仓库。
- 前端展示 AI/Markdown 内容时保持清洗。
- 外部暴露优先只开放 Nginx `80/443`，数据库和 Redis 不应公网暴露。

