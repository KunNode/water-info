# 决策记录

## 已采用决策

| 决策 | 原因 | 维护提醒 |
| --- | --- | --- |
| AI 服务直接读 PostgreSQL | 降低实时研判延迟 | 不要让 AI 绕过平台写入关键业务状态 |
| Java 平台代理 AI API | 统一认证、RBAC、限流和前端入口 | 新增 AI API 时同步 Java 代理和前端 API |
| LangGraph 多 Agent 编排 | 支持动态路由、状态共享和可观测执行轨迹 | 节点只写自己负责的状态片段 |
| PostgreSQL Flyway 管迁移 | 保持部署时 schema 可追踪 | 不修改已发布迁移，新增版本演进 |
| Nginx 统一入口 | 支持同源访问、SSE、WebSocket、安全头和限流 | 流式接口必须关闭缓冲 |
| Vue 前端按模块封装 API | 降低页面和接口耦合 | 新模块优先加入 `src/api/` 和类型定义 |

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 默认密码未覆盖 | 生产安全风险 | 部署前强制设置 `PG_PASSWORD`、`REDIS_PASSWORD`、`ADMIN_PASSWORD`、`JWT_SECRET` |
| AI 直接读库依赖 schema | 迁移后 AI 查询可能失效 | 迁移时同步检查 `app/services/database.py` 和 tools |
| SSE 超时或缓冲 | AI 指挥台无流式反馈 | 保持 Nginx special location，客户端设置长超时 |
| LLM/Embedding Key 缺失 | AI/RAG 能力不可用 | 健康检查和启动日志明确提示配置状态 |
| 前端角色隐藏不等于授权 | 权限绕过风险 | 后端 `@PreAuthorize` 和服务校验为准 |
| 大批量观测数据 | 写入性能和锁竞争 | 保持批量上限，必要时分片或后台导入 |

## 文档维护规则

- 新增对外 API：更新 [接口与集成](api-integration.md)。
- 新增服务或端口：更新 [系统总览](system-overview.md)、[架构与数据流](architecture.md)、[部署与运维](deployment-operations.md)。
- 新增迁移：更新 [数据模型与迁移](data-model.md)。
- 调整 LangGraph 节点：更新 [AI 服务](ai-service.md)。
- 调整前端路由：更新 [管理端](admin-frontend.md)。

