---
title: FloodMind 智慧水利系统 · 缺陷与漏洞修复报告
status: completed-with-residual-risk
date: 2026-04-27
---

# 缺陷与漏洞修复报告

## 1. 修复概述

本轮修复重点围绕测试执行中暴露的阻断项：业务异常 HTTP 状态码不准确、AI 结构化数据写回时 JSON 序列化失败、前端缺少 lint/smoke 自动化入口，以及生产依赖安全审计风险。

## 2. 修复清单

| 编号 | 模块 | 问题 | 修复内容 | 验证 |
|---|---|---|---|---|
| FIX-001 | Platform | `BusinessException` 返回 HTTP 200，错误登录无法被客户端按 401 处理 | `GlobalExceptionHandler` 改为返回 `ResponseEntity`，按业务错误码映射 400/401/403/404/409 | 单测 + Docker API smoke |
| FIX-002 | Platform | 后端 smoke 测试入口缺失/不可稳定运行 | 增加 `SmokeTestSuite` 和异常 handler 测试；固定 JUnit Platform / Surefire 版本 | `SmokeTestSuite` 通过 |
| FIX-003 | AI | `Decimal` 写入 JSON payload 时抛 `TypeError` | 扩展 `to_plain_data`，支持 `Decimal`、`date/datetime`、`Enum`、tuple、dataclass、list、dict 递归转换 | 新增 `test_assessment_writer.py` |
| FIX-004 | AI | pytest marker 未注册，`pytest -m smoke` 无法作为冒烟入口 | 在 `pyproject.toml` 注册 `smoke`、`integration` marker；给 API smoke 测试打标 | `7 passed, 65 deselected` |
| FIX-005 | AI | Ruff 静态检查失败 | 运行 ruff 自动修复并清理残留 lint 问题 | `uv run ruff check app tests` 通过 |
| FIX-006 | Admin | 缺少 ESLint 配置导致 `npm run lint` 不可用 | 增加 `.eslintrc.cjs`，并修复无限循环写法的 lint 报告 | `npm run lint` 通过 |
| FIX-007 | Admin | 缺少前端 smoke 自动化入口 | 增加 Playwright 配置和 `/login`、`/bigscreen` 路由 smoke 用例 | `npx playwright test --project=smoke` 通过 |
| FIX-008 | Admin | 生产依赖安全审计存在漏洞 | 执行 `npm audit fix`，升级可安全升级的依赖 | `npm audit --omit=dev` 为 0 漏洞 |

## 3. 修改文件

| 路径 | 说明 |
|---|---|
| `water-info-platform/src/main/java/com/waterinfo/platform/common/exception/GlobalExceptionHandler.java` | 修复业务异常 HTTP 状态码映射 |
| `water-info-platform/pom.xml` | 固定测试运行相关版本，补充 JUnit Platform launcher 与 Surefire |
| `water-info-platform/src/test/java/com/waterinfo/platform/SmokeTestSuite.java` | 新增后端 smoke 测试 |
| `water-info-platform/src/test/java/com/waterinfo/platform/common/exception/GlobalExceptionHandlerTest.java` | 新增异常状态码回归测试 |
| `water-info-ai/app/state.py` | 修复 JSON 安全转换 |
| `water-info-ai/tests/test_assessment_writer.py` | 新增 AI 写回序列化回归测试 |
| `water-info-ai/pyproject.toml` | 注册 pytest marker，调整 ruff 行宽 |
| `water-info-ai/tests/test_main_api.py` | 标记 smoke 测试 |
| `water-info-ai/app/main.py` 等 | ruff 自动整理导入、空白和未使用变量 |
| `water-info-admin/.eslintrc.cjs` | 新增 ESLint 配置 |
| `water-info-admin/playwright.config.cjs` | 新增 Playwright smoke project |
| `water-info-admin/tests/e2e/smoke.spec.cjs` | 新增前端路由 smoke |
| `water-info-admin/src/composables/useSSE.ts` | 改写 `while (true)`，满足 lint |
| `water-info-admin/src/views/ai/command/index.vue` | 改写 typewriter 循环，满足 lint |
| `water-info-admin/package.json`、`package-lock.json` | 增加 Playwright dev 依赖并更新审计修复后的依赖树 |

## 4. 验证证据

| 类型 | 命令 | 结果 |
|---|---|---|
| 后端 smoke | `mvn -s settings-docker.xml -Dtest=SmokeTestSuite test` | PASS，1 个测试通过 |
| AI lint | `uv run ruff check app tests` | PASS |
| AI 全量测试 | `OPENAI_API_KEY= EMBEDDING_API_KEY= uv run pytest -q tests` | PASS，69 passed / 3 skipped |
| AI smoke | `OPENAI_API_KEY= EMBEDDING_API_KEY= uv run pytest tests/ -m smoke -q` | PASS，7 passed |
| 前端 lint | `npm run lint` | PASS |
| 前端 build | `npm run build` | PASS |
| 前端 smoke | `PLAYWRIGHT_BASE_URL=http://localhost:5173 npx playwright test --project=smoke` | PASS，1 passed |
| Docker build | `docker compose up -d --build platform ai admin nginx` | PASS，关键容器 healthy/up |
| Platform health | `curl http://localhost:8080/actuator/health` | PASS，`status=UP` |
| AI health | `curl http://localhost:8100/health` | PASS，`status=ok` |
| 错误登录 | `POST /api/v1/auth/login` with wrong password | PASS，HTTP 401 |
| 生产依赖审计 | `npm audit --omit=dev` | PASS，0 vulnerabilities |

## 5. 剩余风险

| 风险 | 影响 | 建议 |
|---|---|---|
| `npm audit` 仍报告 dev 依赖 `vite/esbuild` moderate | 影响开发构建链路，不影响 `--omit=dev` 生产依赖审计结果 | 单独评估 Vite 大版本升级，避免仓促强制升级 |
| 后端完整集成测试不足 | 站点、观测、告警、审计、AI assessment 等业务链路仍缺少自动化保护 | 下一轮补 API integration suite |
| 前端 smoke 仅验证路由可访问 | 未验证登录交互、SSE/WS、图表渲染和大屏视觉质量 | 增加浏览器交互和截图断言 |
| 未执行性能压测 | 无法证明论文中并发性能数字 | 使用 k6/wrk/Locust 补正式性能实验 |
| 覆盖率门禁缺失 | 无法量化测试充分性 | 增加 JaCoCo、pytest-cov、前端 coverage |

## 6. 简化与清理

- 删除 Playwright 临时 `test-results` 产物，避免提交运行噪声。
- 没有引入业务新依赖；新增的 `@playwright/test` 仅用于前端 dev smoke 测试。
- AI 与前端自动格式化仅处理 lint 所需的导入、空白和循环写法，没有改变业务流程。
