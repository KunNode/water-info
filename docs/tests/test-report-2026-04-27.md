---
title: FloodMind 智慧水利系统 · 测试执行报告
status: pass-with-residual-risk
test_date: 2026-04-27
tester: Codex
source_plan: docs/tests/test-plan.md
---

# FloodMind 测试执行报告

## 1. 测试结论

本轮在修复缺陷后，对 `water-info-platform`、`water-info-ai`、`water-info-admin` 以及 Docker 运行环境进行了回归验证。总体结论为 **通过，但仍存在未覆盖风险**。

- Docker 全栈可重建、可启动，`platform`、`ai`、`postgres`、`redis`、`nginx` 均处于 healthy/up 状态。
- 后端业务异常状态码修复后，错误登录已从 HTTP 200 改为 HTTP 401。
- AI 侧 Decimal / datetime / Enum 等对象已可转为 JSON 安全结构，相关回归测试通过，重启后未再出现 Decimal 序列化异常日志。
- 前端补齐 ESLint 与 Playwright smoke 配置后，lint、生产构建和路由 smoke 均通过。
- 未执行正式并发压测、WebSocket 全链路测试、浏览器视觉断言和覆盖率门禁，不能支撑“完整 57 个功能用例 + 性能表格”的论文结论。

## 2. 测试环境

| 项 | 值 |
|---|---|
| 工作目录 | `/project/code-work` |
| 执行日期 | 2026-04-27 |
| 容器编排 | Docker Compose |
| 后端 | Spring Boot / Java 17 / Maven |
| AI 服务 | FastAPI / Python / uv / pytest / ruff |
| 前端 | Vue 3 / TypeScript / Vite / ESLint / Playwright |
| 数据依赖 | PostgreSQL / Redis |

## 3. 自动化测试结果

| 模块 | 命令 / 检查 | 结果 | 证据 |
|---|---|---|---|
| Platform 编译 | `mvn -q -DskipTests test-compile` | PASS | 测试代码可编译 |
| Platform smoke | `mvn -s settings-docker.xml -Dtest=SmokeTestSuite test` | PASS | `Tests run: 1, Failures: 0, Errors: 0, Skipped: 0` |
| AI lint | `uv run ruff check app tests` | PASS | `All checks passed!` |
| AI 全量测试 | `OPENAI_API_KEY= EMBEDDING_API_KEY= uv run pytest -q tests` | PASS | `69 passed, 3 skipped` |
| AI smoke | `OPENAI_API_KEY= EMBEDDING_API_KEY= uv run pytest tests/ -m smoke -q` | PASS | `7 passed, 65 deselected` |
| Admin lint | `npm run lint` | PASS | ESLint 无错误 |
| Admin build | `npm run build` | PASS | Vite 构建成功，`2263 modules transformed` |
| Admin smoke | `PLAYWRIGHT_BASE_URL=http://localhost:5173 npx playwright test --project=smoke` | PASS | `1 passed` |
| Admin prod audit | `npm audit --omit=dev` | PASS | `found 0 vulnerabilities` |
| Admin full audit | `npm audit` | RESIDUAL RISK | 仍有 2 个 dev moderate，修复需 Vite major upgrade |

本轮可统计的自动化测试为：AI 69 个 pytest 用例、后端 1 个 smoke 用例、前端 1 个 Playwright smoke 用例，共 **71 个通过、3 个跳过**。另外，lint、构建、生产依赖安全审计和 Docker 运行态检查均通过。

## 4. Docker 运行态验证

| 服务 | 状态 | 端口 |
|---|---|---|
| `water-platform` | healthy | `8080:8080` |
| `water-ai` | healthy | `8100:8100` |
| `water-admin` | up | `5173:80` |
| `water-nginx` | healthy | `80:80` |
| `water-postgres` | healthy | `5432:5432` |
| `water-redis` | healthy | `6379:6379` |

| 检查项 | 结果 |
|---|---|
| `GET http://localhost:8080/actuator/health` | HTTP 200，`status=UP`，DB/Redis UP |
| `GET http://localhost:8100/health` | HTTP 200，`status=ok` |
| 错误登录 `admin / wrong-password` | HTTP 401，body `code=1200` |
| 正确登录 `admin / Admin@123456` | HTTP 200，返回 accessToken |
| `/login` 与 `/bigscreen` 前端路由 smoke | HTTP 200，页面包含 Vue 根节点 |
| AI 重启后异常日志筛查 | 未检出 `Decimal`、`TypeError`、`risk scan failed` |

## 5. 已修复问题回归

| 编号 | 问题 | 修复验证 | 结果 |
|---|---|---|---|
| BUG-001 | AI 周期扫描写回含 `Decimal` 时 JSON 序列化失败 | 新增 `to_plain_data` 回归测试；容器重启后筛查日志 | PASS |
| BUG-002 | 业务异常统一返回 HTTP 200，错误登录不符合 401 语义 | 后端 handler 单测 + Docker API smoke | PASS |
| BUG-003 | AI `smoke` / `integration` marker 未注册 | `pytest -m smoke` 可选中 7 个测试且无 unknown marker warning | PASS |
| BUG-004 | 前端缺少 ESLint 配置 | `npm run lint` 通过 | PASS |
| BUG-005 | 前端缺少 Playwright smoke project | `npx playwright test --project=smoke` 通过 | PASS |
| BUG-006 | 生产依赖存在 npm audit 风险 | `npm audit fix` 后 `npm audit --omit=dev` 为 0 漏洞 | PASS |

## 6. 与测试计划差距

| 测试计划要求 | 当前状态 |
|---|---|
| 108 条完整用例 | 仅补齐关键 smoke 与回归测试，未全部自动化 |
| 后端 API 全模块测试 | 当前只新增异常状态码 smoke，未覆盖全部站点/观测/告警/审计流程 |
| 前端视觉和交互测试 | 仅覆盖路由可访问，未做像素级、交互级或 WebSocket/SSE 浏览器断言 |
| 性能压测 | 未执行 k6/wrk/Locust 并发压测 |
| 覆盖率门禁 | 未配置 JaCoCo、pytest-cov、前端 coverage 阈值 |
| dev 依赖安全 | Vite/esbuild dev moderate 仍存在，强制修复会引入 Vite 大版本升级风险 |

## 7. 后续建议

1. 将测试计划中的账号修订为实际种子数据：`admin/Admin@123456`、`operator01/Operator@123456`、`viewer01/Viewer@123456`。
2. 增加后端 API 集成测试，覆盖认证、RBAC、站点、观测、告警、AI assessment 写回。
3. 增加真实端到端测试：观测写入 → 告警生成 → WebSocket 推送 → 前端展示 → AI 研判写回。
4. 单独安排性能测试，不要在论文中继续使用未执行的并发耗时表。
5. 评估 Vite 大版本升级，或在论文/报告中明确 dev 依赖风险不影响生产包审计结论。
