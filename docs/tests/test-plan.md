---
title: FloodMind 智慧水利系统 · 测试用例集
status: v1
owner: TBD
created: 2026-04-26
---

# FloodMind 测试用例集

本文档覆盖 **water-info-platform / water-info-ai / water-info-admin** 三个服务及其交互。共计 **108** 条用例，按模块组织，每条用例标注了优先级（P0/P1/P2）和类型（unit / api / e2e / ui / perf / sec）。

---

## 1. 测试策略

### 1.1 测试金字塔

| 层 | 占比 | 工具 | 谁执行 |
|---|---|---|---|
| Unit | 60% | JUnit 5 / pytest / Vitest | 开发 |
| Integration（含 API） | 30% | Testcontainers (PG) / pytest + httpx / Vitest + MSW | 开发 + QA |
| E2E / UI | 10% | Playwright | QA |

### 1.2 优先级

- **P0 阻塞**：核心业务路径，发布前必须 100% 通过；冒烟测试每次 CI 跑
- **P1 主流**：常见用户流程与边界条件；每次 release 前回归
- **P2 优化**：极端边界、性能、易用性；按月跑

### 1.3 测试环境

| 环境 | 用途 | 数据 | LLM |
|---|---|---|---|
| local-dev | 开发自测 | docker-compose 起 PG 15 + Redis 7 | DeepSeek 真 key |
| ci | PR 验收 | Testcontainers 临时容器 | mock |
| staging | 集成 / 预发 | 复制 prod 脱敏数据 + 翠屏湖 demo | 真 key（限流） |
| prod | 线上 | — | 真 key |

### 1.4 测试数据约定

- 翠屏湖 8 站点：`ST_RAIN_CP_01/02`、`ST_WL_CP_01/02`、`ST_FLOW_CP_01`、`ST_RES_CP_01`、`ST_GATE_CP_01`、`ST_PUMP_CP_01`（已在 `V4__legacy_public_seed_test_data.sql`）
- 测试用户：`admin/admin123`（ADMIN）、`operator/op123`（OPERATOR）、`viewer/view123`（VIEWER）
- 阈值规则：水位 ≥ 4.5m HIGH / ≥ 4.8m CRITICAL；雨量 ≥ 30mm/h HIGH / ≥ 50mm/h CRITICAL

---

## 2. 测试范围

| 范围 | 包含 | 不包含 |
|---|---|---|
| 后端 | 全部 REST + WebSocket + 业务逻辑 + 缓存 + 鉴权 | 第三方依赖内部实现（Spring/Mybatis） |
| AI | 智能体路由 / 工具调用 / 状态合并 / SSE / RAG | DeepSeek 模型本身的输出质量（仅测调用契约） |
| 前端 | 路由 / 鉴权 / 主题 / 大屏 / 关键交互 / SSE/WS 接入 | 浏览器底层兼容（仅 Chromium 当前版） |
| 集成 | 平台 ↔ AI ↔ 数据库 ↔ 前端 全链路 | 边缘网络异常注入（留作混沌测试） |
| 性能 | 接口 P95 / 大屏渲染帧率 / 批量上传吞吐 | 长时稳定性（>24h） |

---

## 3. 测试用例

### 3.1 认证与授权（auth）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-AUTH-001 | 用户名密码登录成功返回 JWT | P0 | api | POST /api/v1/auth/login `{admin, admin123}` → 200 + token + refreshToken |
| TC-AUTH-002 | 错误密码返回 401 | P0 | api | 同上但密码错 → 401，错误码 `AUTH_INVALID_CREDENTIALS` |
| TC-AUTH-003 | 不存在的用户名返回 401（不泄露用户存在性） | P0 | sec | 返回信息与 002 完全一致 |
| TC-AUTH-004 | 登录限流：5 次/分钟 | P1 | sec | 同 IP 1 分钟内 6 次失败登录 → 第 6 次 429 |
| TC-AUTH-005 | JWT 过期后访问受保护接口返回 401 | P0 | api | 用过期 token 调 /me → 401 + `AUTH_TOKEN_EXPIRED` |
| TC-AUTH-006 | refreshToken 换新 access token | P1 | api | 用 refreshToken 调 refresh 接口 → 200 + 新 access token |
| TC-AUTH-007 | logout 后旧 token 失效 | P0 | sec | logout → 旧 token 调 /me → 401 |
| TC-AUTH-008 | 篡改 JWT 签名返回 401 | P0 | sec | 修改 payload 任一字段 → 401 |
| TC-AUTH-009 | /api/v1/auth/me 返回当前用户基本信息 | P0 | api | 含 id / username / realName / role / permissions |

### 3.2 用户与 RBAC

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-USER-001 | ADMIN 创建用户成功 | P0 | api | POST /api/v1/users → 201，密码加密存储 |
| TC-USER-002 | OPERATOR 创建用户被拒 | P0 | sec | OPERATOR token → 403 + `RBAC_FORBIDDEN` |
| TC-USER-003 | VIEWER 修改阈值规则被拒 | P0 | sec | 任何写操作均 → 403 |
| TC-USER-004 | VIEWER 可以读站点列表 | P0 | api | GET /api/v1/stations → 200 |
| TC-USER-005 | 用户名重复返回 409 | P1 | api | 创建已存在 username → 409 + `USER_DUPLICATE` |
| TC-USER-006 | 删除用户为软删除 | P1 | api | DELETE → 200，DB 中 `deleted=1` 而非物理删除 |
| TC-USER-007 | 角色变更立即生效（无需重登） | P1 | sec | 改角色后下一次请求按新角色鉴权 |

### 3.3 站点管理（station）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-STA-001 | 创建站点（WATER_LEVEL）成功 | P0 | api | POST → 201，UUID 自动生成 |
| TC-STA-002 | 站点编码 unique 约束 | P0 | api | 创建相同 code → 409 + `STATION_CODE_DUPLICATE` |
| TC-STA-003 | 必填字段校验 | P0 | api | 缺 name → 400 + 字段级错误 |
| TC-STA-004 | 经纬度边界值校验 | P1 | api | lng=181 / lat=-91 → 400 |
| TC-STA-005 | 列表分页 size 上限 100 | P1 | api | size=10000 → 400 或截断到 100 |
| TC-STA-006 | 按类型筛选 | P1 | api | type=WATER_LEVEL → 仅返回水位站 |
| TC-STA-007 | 缓存命中：连续两次 GET /{id} | P1 | perf | 第二次响应 < 50ms（Redis 命中） |
| TC-STA-008 | 修改站点触发缓存失效 | P0 | api | PUT 后立刻 GET → 返回新值（缓存被 evict） |
| TC-STA-009 | 删除站点为软删除 | P0 | api | DELETE → 200，列表查询不再出现 |
| TC-STA-010 | 删除带活跃告警的站点 | P1 | api | 应允许或要求先关闭告警，行为需明确（建议拒绝） |

### 3.4 传感器（sensor）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-SEN-001 | 注册传感器到站点 | P0 | api | POST → 201，stationId 关联正确 |
| TC-SEN-002 | 心跳更新 lastHeartbeatAt | P1 | api | PUT /heartbeat → 时间戳刷新 |
| TC-SEN-003 | 离线检测：超过 5 min 无心跳标 OFFLINE | P1 | api | 模拟后调状态接口 → OFFLINE |
| TC-SEN-004 | 删除站点级联到传感器 | P1 | api | 软删站点后传感器 status 变 INACTIVE |

### 3.5 观测数据（observation）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-OBS-001 | 单条观测数据写入 | P0 | api | POST /observations → 201 |
| TC-OBS-002 | 批量上传 100 条成功 | P0 | api | POST /batch (100 records) → 201 |
| TC-OBS-003 | 批量上传超 5000 条返回 400 | P0 | api | 5001 条 → 400 + `OBS_BATCH_LIMIT` |
| TC-OBS-004 | 批量中含非法 stationId 的部分回滚 | P0 | api | 事务回滚，无任何条目入库 |
| TC-OBS-005 | 时间倒序查询返回最新优先 | P1 | api | GET /observations?sort=desc → 第 1 条最新 |
| TC-OBS-006 | 按时间区间筛选 | P1 | api | start/end 准确包含/排除边界 |
| TC-OBS-007 | /latest/batch 返回每个 (站,指标) 的最新值 | P0 | api | 8 站点 → 8 条记录 |
| TC-OBS-008 | observed_at 索引命中（不全表扫） | P1 | perf | EXPLAIN ANALYZE 确认走 idx_obs_station_metric_time |
| TC-OBS-009 | 异常值（NaN / Infinity）拒绝写入 | P1 | api | value=NaN → 400 |

### 3.6 阈值规则（threshold-rules）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-THR-001 | 创建规则成功 | P0 | api | POST → 201 |
| TC-THR-002 | enable/disable 切换 | P0 | api | PUT /enable → 200 + enabled=true |
| TC-THR-003 | 同站同指标允许多个等级（HIGH/CRITICAL 共存） | P0 | api | 创建 2 条同 (站,指标) 不同 level → 都 OK |
| TC-THR-004 | 操作符校验：>= / > / <= / < | P1 | api | 仅允许枚举值 |
| TC-THR-005 | 删除规则后告警链路立即跳过该规则 | P0 | api | 删除后再写超阈观测 → 不触发告警 |
| TC-THR-006 | 修改规则触发缓存失效 | P0 | api | 修改 threshold 后立即生效 |
| TC-THR-007 | 找出某站某指标已启用规则 `findEnabledRules` | P0 | unit | 数据库直接验证 SQL 行为 |

### 3.7 告警（alarm）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-ALM-001 | 上传超阈观测自动产生 OPEN 告警 | P0 | api | 写入 4.9m 水位（> 4.8 CRIT） → 告警自动创建 |
| TC-ALM-002 | 同站同指标 OPEN 状态唯一（去重） | P0 | api | 连续 3 次超阈 → 仅 1 条 OPEN 告警 |
| TC-ALM-003 | 告警等级升级：HIGH → CRITICAL | P0 | api | 先写 4.6 → HIGH，再写 4.9 → 同条告警 level 升级 |
| TC-ALM-004 | ACK 状态机：OPEN → ACK | P0 | api | POST /ack → 200 + ackBy/ackAt 字段 |
| TC-ALM-005 | CLOSE 状态机：ACK → CLOSED | P0 | api | POST /close → 200 + closedAt |
| TC-ALM-006 | OPEN → CLOSED 直跳合法 | P1 | api | 跳过 ACK 应允许 |
| TC-ALM-007 | CLOSED 状态再 ACK 返回 409 | P1 | api | 状态机不可逆，409 + `ALARM_INVALID_TRANSITION` |
| TC-ALM-008 | WebSocket /ws/alarms 实时推送 | P0 | e2e | 订阅后写超阈观测 → 客户端 1s 内收到 alarm.created |
| TC-ALM-009 | WebSocket 断线自动重连 | P1 | e2e | 服务重启后客户端 5s 内重连 |
| TC-ALM-010 | 告警查询按 level/status 筛选 | P1 | api | 多条件组合返回正确子集 |

### 3.8 审计日志（audit）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-AUD-001 | 写操作自动记录审计日志 | P0 | api | 创建站点 → audit_log 表新增一条 |
| TC-AUD-002 | 审计日志包含 traceId 和操作人 | P0 | api | log 中可查到对应操作 |
| TC-AUD-003 | 审计日志只读（无 PUT/DELETE 接口） | P1 | sec | 仅 GET，写操作返回 405 |
| TC-AUD-004 | 审计查询 RBAC：仅 ADMIN 可查全部 | P0 | sec | OPERATOR 仅看到自己操作 |

### 3.9 AI 服务 · 多智能体（water-info-ai）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-AI-001 | Supervisor 路由数据查询到 DataAnalyst | P0 | unit | "查翠屏湖水位" → state.next_agent=data_analyst |
| TC-AI-002 | RiskAssessor 给出 5 级风险等级之一 | P0 | unit | 输入态势数据 → output.risk_level ∈ {none,low,moderate,high,critical} |
| TC-AI-003 | PlanGenerator 含必填字段（actions/resources/timeline） | P0 | unit | 缺字段时校验失败抛 ValidationError |
| TC-AI-004 | 工具 fetch_water_level 返回真实数据 | P0 | integration | mock asyncpg 池，验证 SQL 正确 |
| TC-AI-005 | 工具调用失败优雅降级 | P0 | integration | DB 连接断开 → 返回 error 字段而非抛异常 |
| TC-AI-006 | LangGraph 完整工作流：查询→分析→风险→预案 | P0 | integration | 完整跑通，state 各阶段都有数据 |
| TC-AI-007 | SSE 流式接口正常断流 | P1 | api | 客户端断连后服务端 5s 内释放资源 |
| TC-AI-008 | Reducer 合并多 agent 消息不丢失 | P1 | unit | 同时 3 个 agent 写 messages → 合并后顺序正确 |
| TC-AI-009 | RAG 检索：上传文档→查询命中 | P1 | integration | 上传 III 级响应制度文档 → 查 "III 级" 命中 |
| TC-AI-010 | LLM 限流时降级到本地缓存预案 | P2 | integration | mock 429 → 返回缓存预案 + 警告 |
| TC-AI-011 | conversations 持久化到 Redis | P0 | integration | 创建会话→重启服务→历史可恢复 |
| TC-AI-012 | 长会话上下文截断（保留最近 N 轮） | P1 | unit | 第 50 轮时仅保留最后 20 轮 + 系统提示 |

### 3.10 AI 综合研判（aiassessment）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-AIA-001 | POST /api/v1/ai-assessments 写入成功（仅内网/Service Token） | P0 | api | 带 token → 201；不带 → 401 |
| TC-AIA-002 | 同站点同 source 同分钟去重（upsert） | P0 | api | 1 分钟内 2 次写入相同 (station,source) → 第 2 次 update 而非 insert |
| TC-AIA-003 | 列表按 since 过滤 | P1 | api | ?since=ISO 时间 → 仅返回之后的记录 |
| TC-AIA-004 | 关联站点不存在返回 400 | P1 | api | 不存在的 stationId → 400 |
| TC-AIA-005 | WebSocket /ws/ai-assessments 实时推送（如已实现） | P1 | e2e | 写入触发推送 |

### 3.11 前端 admin（web）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-FE-001 | 主题三态切换：auto / light / dark | P0 | ui | 点击顶栏分段控件循环；`html.dark` class 同步切换 |
| TC-FE-002 | auto 模式跟随系统 prefers-color-scheme | P0 | ui | OS 切换暗色 → 页面 1s 内联动 |
| TC-FE-003 | 主题偏好持久化到 localStorage `fm-theme` | P0 | ui | 切到 light 后刷新 → 仍 light |
| TC-FE-004 | 浅色下品牌色加深为 `#1d5bd6`（HIG） | P1 | ui | 视觉回归比对 token |
| TC-FE-005 | RBAC 指令隐藏不可见按钮 | P0 | ui | VIEWER 进入 → 无创建按钮 |
| TC-FE-006 | 路由守卫：未登录跳 /login | P0 | ui | 直接访问 /dashboard → 重定向 |
| TC-FE-007 | API 401 自动登出并跳转 | P0 | ui | 模拟 token 过期返回 → 用户被踢出 |
| TC-FE-008 | 列表分页交互：页码切换、size 切换 | P1 | ui | 数据 + URL 参数同步 |

### 3.12 大屏 bigscreen

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-BS-001 | 1920×1080 满屏渲染无溢出 | P0 | ui | 三列布局完整可见 |
| TC-BS-002 | LakeStage 站点 marker 按等级渲染 | P0 | ui | CRIT 红圈+脉冲 / HIGH 黄 / MED 蓝 / 普通绿 |
| TC-BS-003 | 告警河流空告警显示 ALL CLEAR | P1 | ui | 无 OPEN 告警时显示绿色文字 |
| TC-BS-004 | 告警河流 marquee 无缝循环 | P1 | ui | 30s 后无明显跳跃 |
| TC-BS-005 | AI 综合研判由最高级别告警驱动 | P0 | ui | CRITICAL 出现 → 卡片显示 "EVENT TRIGGERED + HIGH" |
| TC-BS-006 | 全屏切换可用且 ESC 退出 | P1 | ui | 顶栏按钮 + 浏览器原生 ESC |
| TC-BS-007 | 30s 数据刷新不闪屏 | P1 | ui | 不重置 ECharts 实例，仅 setOption |

### 3.13 定时险情扫描（依赖 docs/tasks/scheduled-risk-monitoring.md，待实现先定义用例）

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-SRS-001 | 轻量层 90s 周期扫描启动 | P0 | integration | 应用启动后日志显示 ScheduledRiskScanJob 注册 |
| TC-SRS-002 | 命中阈值生成告警 ≤ 2 min | P0 | integration | 写超阈观测 → ≤2min 出现 OPEN 告警 |
| TC-SRS-003 | 同站同级别 30 min 内仅 1 条告警 | P0 | integration | 30s 间隔写 5 次超阈 → 仅 1 条 OPEN |
| TC-SRS-004 | high/critical 触发 RiskEscalatedEvent → AI | P0 | integration | mock AI 端点验证 POST 触达 |
| TC-SRS-005 | AI 服务宕机不阻塞告警链路 | P0 | integration | 关闭 AI → 平台告警仍正常生成 |
| TC-SRS-006 | AI 周期任务 15 min 跑一次 risk_only_graph | P1 | integration | 等待 16 min → assessment_writer 至少调一次 |
| TC-SRS-007 | 事件触发任务 60s 去抖 | P1 | unit | 同站点 60s 内 3 次事件 → 仅 1 次 graph 调用 |
| TC-SRS-008 | 配置开关一键关停两层 | P1 | api | `lightweight.enabled=false` 后无告警生成 |

### 3.14 跨服务集成

| ID | 用例 | 优先级 | 类型 | 步骤摘要 / 预期 |
|---|---|---|---|---|
| TC-INT-001 | 端到端：写观测 → 告警 → WS 推 → 前端弹窗 | P0 | e2e | 全链路 ≤ 5s |
| TC-INT-002 | AI 调平台 REST 写 ai-assessment 成功 | P0 | integration | 平台收到记录并推 WS |
| TC-INT-003 | 前端 SSE 接 AI 流式响应（用户提问） | P0 | e2e | Chunk 顺序到达 + 完整结果 |
| TC-INT-004 | 平台访问 AI 服务超时降级（5s） | P1 | integration | mock 慢响应 → 5s 后超时不阻塞 |
| TC-INT-005 | 数据库迁移 V1~V7 顺序应用成功 | P0 | integration | Flyway 启动无错；表结构正确 |

### 3.15 性能（perf）

| ID | 用例 | 目标 | 优先级 | 工具 |
|---|---|---|---|---|
| TC-PERF-001 | GET /stations P95 ≤ 100ms（10k 数据） | P95<100ms | P0 | k6 / wrk |
| TC-PERF-002 | POST /observations/batch 5000 条 ≤ 5s | <5s | P0 | k6 |
| TC-PERF-003 | /flood/query 简单问答 ≤ 8s | <8s | P1 | curl + time |
| TC-PERF-004 | 100 并发登录无失败 | 0 错误 | P1 | k6 |
| TC-PERF-005 | 大屏页面初始化 LCP ≤ 2.5s | <2.5s | P1 | Lighthouse |
| TC-PERF-006 | LakeStage 60fps 稳定（1080p） | ≥55fps | P1 | Chrome DevTools FPS |

### 3.16 安全（sec）

| ID | 用例 | 优先级 | 类型 | 验证 |
|---|---|---|---|---|
| TC-SEC-001 | SQL 注入：站点名输 `'; DROP TABLE--` | P0 | sec | 安全转义，DB 完整 |
| TC-SEC-002 | XSS：评论字段输 `<script>` | P0 | sec | 前端渲染时转义为文本 |
| TC-SEC-003 | CSRF：跨域 POST 未带 CSRF token / Origin 校验 | P0 | sec | 拒绝（403） |
| TC-SEC-004 | 越权访问：OPERATOR 用 stationId 查别人审计日志 | P0 | sec | 403 |
| TC-SEC-005 | 弱密码拒绝创建（< 8 位 / 纯数字） | P1 | sec | 400 + 校验错误 |
| TC-SEC-006 | 密码哈希用 BCrypt（cost ≥ 10） | P0 | sec | DB 直查确认 `$2a$10$...` |
| TC-SEC-007 | 文件上传（KB 文档）类型白名单 | P1 | sec | 上传 .exe → 400 |
| TC-SEC-008 | 速率限制：5 req/min 登录 | P1 | sec | 6 次失败 → 429 |

---

## 4. 冒烟测试套件 · 每次部署必跑

每次发布到 staging / prod 之前必须通过这 **15 条 P0**：

```
TC-AUTH-001  登录成功
TC-AUTH-007  logout 后 token 失效
TC-USER-002  RBAC 阻止越权
TC-STA-001   创建站点
TC-OBS-002   批量上传成功
TC-OBS-007   /latest/batch 返回每站最新值
TC-THR-001   创建阈值规则
TC-ALM-001   超阈自动告警
TC-ALM-004   ACK 状态机
TC-ALM-008   WS 实时推送
TC-AI-001    Supervisor 路由
TC-AI-006    完整工作流
TC-FE-001    主题三态切换
TC-FE-006    路由守卫
TC-INT-001   端到端告警链路
```

执行命令：

```bash
# 后端
cd water-info-platform && ./mvnw test -Dtest='SmokeTestSuite'

# AI
cd water-info-ai && pytest tests/ -m smoke -v

# 前端
cd water-info-admin && npx playwright test --project=smoke
```

---

## 5. 回归测试套件 · 每次 release 前

含全部 **P0 + P1**（约 78 条），目标 **45 min 内** 跑完。

CI 矩阵：

```yaml
- backend:    JUnit + Testcontainers (PG 15)
- ai:         pytest -m "not slow"     [并发 4]
- frontend:   Vitest + Playwright (chromium)
- integration: docker-compose up; pytest tests/integration
```

---

## 6. 测试数据准备

### 6.1 种子数据脚本

```sql
-- 已存在
V4__legacy_public_seed_test_data.sql

-- 新增（建议加入 V8）
INSERT INTO threshold_rule (...) VALUES
  ('TR_WL_HIGH', 'ST_WL_CP_01', 'WATER_LEVEL', '>=', 4.5, 'HIGH', true),
  ('TR_WL_CRIT', 'ST_WL_CP_01', 'WATER_LEVEL', '>=', 4.8, 'CRITICAL', true),
  ('TR_RAIN_HIGH', 'ST_RAIN_CP_02', 'RAINFALL', '>=', 30, 'HIGH', true),
  ('TR_RAIN_CRIT', 'ST_RAIN_CP_02', 'RAINFALL', '>=', 50, 'CRITICAL', true);
```

### 6.2 测试用 fixtures（pytest）

`water-info-ai/tests/conftest.py` 应提供：

```
- mock_db_pool         (asyncpg pool 注入假数据)
- mock_platform_client (HTTP 调用拦截)
- mock_llm             (DeepSeek 返回固定响应)
- sample_state         (FloodResponseState 示例)
```

### 6.3 前端 MSW handlers

`water-info-admin/src/mocks/handlers.ts` 拦截 `/api/v1/*`，按测试用例返回固定 JSON。

---

## 7. 自动化覆盖目标

| 服务 | 行覆盖率 | 分支覆盖率 | 工具 |
|---|---|---|---|
| water-info-platform | ≥ 70% | ≥ 60% | JaCoCo |
| water-info-ai | ≥ 75% | ≥ 65% | pytest --cov |
| water-info-admin | ≥ 60% | ≥ 50% | Vitest --coverage |

CI 在 PR 上跑覆盖率检查；下降 > 2pp 阻塞合并。

---

## 8. 缺陷管理

- 缺陷追踪：GitHub Issues + label `bug`、`severity/p0`、`module/<x>`
- P0：发现后 4 小时内响应；24 小时修复或回滚
- P1：3 天内修复
- P2：纳入下个迭代
- 每条 P0 缺陷修复后必须新增对应回归测试用例并加入此文档

---

## 9. 待补充（v2 计划）

- 混沌测试：网络延迟 / 数据库主备切换 / Redis 故障
- 长时稳定性：72h 压测验证内存泄漏
- 多语言（i18n）覆盖
- 移动端响应式（管理端目前仅桌面优先）
- WebSocket 重连 + 消息顺序保证
- 灾备演练：DB 全量恢复时间 ≤ 30 min
