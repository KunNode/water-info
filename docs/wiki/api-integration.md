# 接口与集成

## 统一访问入口

生产访问推荐：

```text
Browser -> Nginx :80 -> water-info-platform :8080 -> water-info-ai :8100
```

浏览器通常只需要访问 Nginx 暴露的同源地址。Java 平台承担认证、RBAC、限流、统一响应和 AI 代理。

## 平台 API 分组

| 分组 | 典型接口 |
| --- | --- |
| Auth | `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout` |
| Users | `GET/POST /api/v1/users`, `PUT/DELETE /api/v1/users/{id}` |
| Roles | `GET /api/v1/roles`, `GET /api/v1/roles/{id}` |
| Orgs/Depts | `GET/POST/PUT/DELETE /api/v1/orgs`, `GET/POST/PUT/DELETE /api/v1/depts` |
| Stations | `GET/POST /api/v1/stations`, `GET/PUT/DELETE /api/v1/stations/{id}` |
| Sensors | `GET/POST /api/v1/sensors`, `PUT /api/v1/sensors/{id}/status`, `PUT /api/v1/sensors/{id}/heartbeat` |
| Observations | `POST /api/v1/observations/batch`, `GET /api/v1/observations`, `GET /api/v1/observations/latest` |
| Thresholds | `GET/POST /api/v1/threshold-rules`, `PUT /api/v1/threshold-rules/{id}/enable` |
| Alarms | `GET /api/v1/alarms`, `POST /api/v1/alarms/{id}/ack`, `POST /api/v1/alarms/{id}/close` |
| Resources | `GET/POST /api/v1/resources`, `GET /api/v1/resources/stats`, `GET /api/v1/resources/available` |
| Dispatches | `GET/POST /api/v1/resource-dispatches`, `PATCH /api/v1/resource-dispatches/{id}/status` |
| Audit | `GET /api/v1/audit-logs` |
| AI Assessments | `GET/POST /api/v1/ai-assessments` |

## AI 代理 API

Java 平台代理以下 AI 能力：

| 分组 | 接口 |
| --- | --- |
| Flood query | `POST /api/v1/flood/query`, `POST /api/v1/flood/query/stream` |
| Plans | `GET /api/v1/plans`, `GET /api/v1/plans/{id}`, `POST /api/v1/plans/{id}/execute` |
| Sessions | `GET /api/v1/sessions/{id}` |
| Conversations | `GET/POST /api/v1/conversations`, `GET/PATCH/DELETE /api/v1/conversations/{sessionId}` |
| Knowledge base | `POST/GET/DELETE /api/v1/kb/documents`, `POST /api/v1/kb/search`, `GET /api/v1/kb/stats` |

## SSE 事件

AI 流式查询入口：

```http
POST /api/v1/flood/query/stream
Accept: text/event-stream
```

常见事件：

| 事件 | 用途 |
| --- | --- |
| `session_init` | 初始化会话 |
| `agent_update` | Agent 进度更新 |
| `agent_message` | Agent 文本输出 |
| `risk_update` | 风险评估更新 |
| `plan_update` | 预案生成更新 |
| `evidence_update` | 知识库证据更新 |
| `trace_update` | 执行轨迹/思考摘要 |

## WebSocket

告警推送：

```text
ws://<host>/ws/alarms
```

Nginx 负责透传 WebSocket upgrade header。前端通过 `useWebSocket.ts` 维护连接和事件处理。

## 调用方建议

- 外部系统优先调用 Java 平台 API，不要绕过平台直接写数据库。
- 流式 AI 需要客户端支持 SSE 和较长超时。
- 知识库上传使用 multipart form-data。
- 接口权限以服务端为准，前端权限只用于体验优化。
- 在生产环境使用 Nginx 的 `/health`、平台 `/actuator/health` 和 AI `/health` 做分层诊断。

