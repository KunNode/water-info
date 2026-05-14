# Implementation Plan: Plan Human Review

## Overview

本实现计划将 `.kiro/specs/plan-human-review/design.md` 转化为一组按依赖顺序执行的编码任务，目标是在不改动现有 `draft → approved → executing → completed` 生命周期的前提下，为 AI 生成的应急预案叠加一条人工审核通道（编辑 / 批准 / 审计）。

交付边界按服务拆分：
- **water-info-ai**（Python 3.11 + FastAPI + asyncpg + hypothesis）：业务规则与持久化。
- **water-info-platform**（Java 21 + Spring Boot + WebFlux）：鉴权与透传，沿用 `AiUserContext`/`AiServiceClient`。
- **water-info-admin**（Vue 3 + TypeScript + Element Plus + Vitest + fast-check）：视图与交互。

规范约定：
- 每个任务末尾以 `_Requirements:_` 标注其对应的 EARS 条目，`_Properties:_` 标注其对应的 P1–P6。
- 测试子任务以 `*` 后缀标记为可选；核心实现任务从不标记可选。
- 属性测试子任务以 `[PBT]` 前缀标签标记，遵循 design.md §Testing Strategy 的 ≥100 例约定。
- 任务顺序即执行顺序；下方 "Task Dependency Graph" 以 JSON 波次形式给出可并行执行的最小依赖集合。

## Task Dependency Graph

Serial chains (tasks that edit the same file must run in different waves):
- `water-info-ai/app/database.py` — 1.1 → 1.2 → 3.3 (adds `list_plan_audits`)
- `water-info-ai/app/services/plan_review.py` — 2.3 → 2.4 → 2.5
- `water-info-ai/app/main.py` — 3.1 → 3.2 → 3.3 → 3.8
- `water-info-platform/.../AiServiceClient.java` — 6.1 → 6.2 → 6.3
- `water-info-platform/.../FloodAiController.java` — 7.1 → 7.2 → 7.3
- `water-info-admin/src/api/flood.ts` — 9.2 → 9.3
- `water-info-admin/src/views/ai/plan/index.vue` — 10.1 → 10.3 → 10.4 → 10.5 → 10.6 → 10.7 → 10.8

```json
{
  "waves": [
    { "id": 0,  "tasks": ["1.1", "2.1", "5.1", "5.2", "5.3", "9.1", "9.2"] },
    { "id": 1,  "tasks": ["1.2", "2.2", "6.1", "9.3", "10.1"] },
    { "id": 2,  "tasks": ["1.3", "2.3", "6.2", "7.1", "10.2", "10.3"] },
    { "id": 3,  "tasks": ["2.4", "6.3", "7.2", "10.4"] },
    { "id": 4,  "tasks": ["2.5", "7.3", "10.5"] },
    { "id": 5,  "tasks": ["2.6", "7.4", "7.5", "10.6"] },
    { "id": 6,  "tasks": ["3.1", "10.7"] },
    { "id": 7,  "tasks": ["3.2", "10.8"] },
    { "id": 8,  "tasks": ["3.3", "10.9"] },
    { "id": 9,  "tasks": ["3.4", "3.5", "3.6"] },
    { "id": 10, "tasks": ["3.8", "12.1"] },
    { "id": 11, "tasks": ["3.9", "12.2"] }
  ]
}
```

## Tasks

### Group A · water-info-ai (Python / FastAPI)

- [x] 1. Database schema & DDL bootstrap
  - [x] 1.1 Extend `ensure_plan_tables()` with optimistic-lock column
    - 在 `water-info-ai/app/database.py::ensure_plan_tables()` 中追加 `ALTER TABLE emergency_plan ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 0;`（沿用库内 `ADD COLUMN IF NOT EXISTS` 迁移惯例，不引入 Flyway）。
    - 在 `save_emergency_plan()` 初始路径中显式写入 `version = 0`；在 `update_plan_status()` 及执行后台任务路径中保持 version 不变（批准/编辑两条路径单独 +1）。
    - _Requirements: 1.5, 3.8_
    - _Properties: P6_

  - [x] 1.2 Add `plan_audit_record`, `plan_audit_change`, `plan_audit_draft` tables + immutability triggers
    - 在 `ensure_plan_tables()` 尾部追加 design.md §5.2 所列三张表的 `CREATE TABLE IF NOT EXISTS` DDL 及索引。
    - 追加 `plan_audit_no_update()` 函数与 `plan_audit_record` / `plan_audit_change` 上的 `BEFORE UPDATE` 触发器；触发器均使用 `CREATE OR REPLACE` / `DROP TRIGGER IF EXISTS … CREATE TRIGGER` 幂等模式。
    - 明确：不为 `plan_audit_record` / `plan_audit_change` 添加任何 `DELETE` 触发器以外的白名单；`plan_audit_draft` 不加触发器。
    - _Requirements: 7.1, 7.2, 7.8_
    - _Properties: P5_

  - [x] 1.3 [PBT] Schema immutability property
    - **Property 5 (portion): audit record immutability** — 对任意已写入的 `plan_audit_record` / `plan_audit_change` 行，任何 `UPDATE`/直接 `DELETE` SQL 均被触发器拒绝，行字节级保持不变。
    - 用 `testcontainers`（若无预设则直接挂 test DSN）对照 DB 启动，向表中 seed 任意一条记录，用 hypothesis 生成 `UPDATE … SET <col>=<val>` 的随机合法赋值集合，断言全部抛异常。
    - _Requirements: 7.8_
    - _Properties: P5_

- [x] 2. Diff engine & audit-draft persistence
  - [x] 2.1 Implement pure field-level diff generator
    - 新建 `water-info-ai/app/services/plan_diff.py`，定义 `diff_plan(old: PlanSnapshot, new: PlanSnapshot) -> list[ChangeEntry]`。
    - `ChangeEntry` 字段：`field_path`、`change_type ∈ {'add','delete','modify'}`、`old_value`、`new_value`、`old_index`、`new_index`（见 design.md §5.4 字段路径约定）。
    - 纯函数，不访问数据库；对 summary、actions、resources、notifications 四段分别计算；对列表条目以业务主键 (action_id / resource_id / notification_id) 对齐，仅顺序变化时输出 `change_type='modify'` 且 `old_index != new_index`。
    - _Requirements: 7.3, 7.4_
    - _Properties: P3, P5_

  - [x] 2.2 [PBT] Diff completeness & roundtrip
    - **Property 3 (diff portion): read-back consistency** — 对任意 `(old, patch)` 对，若 `patch` 字段级合法，则 `apply(old, patch)` 的结果在按 `diff_plan(old, applied)` 计算后，差分集合准确覆盖 patch 的 upsert/delete 集合且不产生多余条目。
    - 使用 hypothesis 构造预案生成器（summary 长度 0/1/50000 边界、actions 大小 0–10、priority 1–5 边界、id 可复用/新增/删除）。
    - _Requirements: 7.3, 7.4_
    - _Properties: P3, P5_

  - [x] 2.3 Implement `PlanReviewService.edit_draft()` with buffered audit
    - 新建 `water-info-ai/app/services/plan_review.py`，定义 `PlanReviewService.edit_draft(plan_id, version, patch, reviewer)`。
    - 事务内执行：`BEGIN` → `SELECT … FOR UPDATE` 取当前快照 → 校验 version 一致且状态 ∈ {draft} → 应用 patch → `diff_plan(old, new)` → 批量 `INSERT INTO plan_audit_draft` → `UPDATE emergency_plan SET version = version + 1` → `COMMIT`；任何校验失败触发 `ROLLBACK`。
    - 对 upsert/delete 的不存在 id → 抛应用异常映射到 404 `ENTRY_NOT_FOUND`（见 design.md Error Handling）。
    - _Requirements: 3.2, 3.3, 3.4, 3.6, 3.7, 3.8, 7.3, 7.4_
    - _Properties: P3, P6_

  - [x] 2.4 Implement `PlanReviewService.edit_approved()` with direct audit write
    - 事务内执行：`BEGIN` → `FOR UPDATE` → 校验 version + 状态 ∈ {approved} + 角色（纵深防御）→ 应用 patch → `diff_plan` → 直接写入一条 `plan_audit_record(action='edit_after_approve', opinion=NULL)` 及其 `plan_audit_change` 行（**不经过 `plan_audit_draft`**）→ `version+=1` → `COMMIT`。
    - _Requirements: 6.3, 6.5, 6.6, 7.3, 7.4_
    - _Properties: P2, P3, P5_

  - [x] 2.5 Implement `PlanReviewService.approve()`
    - 事务内执行：`BEGIN` → `FOR UPDATE` → 校验 status=='draft' + version 匹配 + `opinion.strip().length ∈ [1,500]` → 读取本预案全部 `plan_audit_draft` 条目 → 插入一条 `plan_audit_record(action='approve', opinion=stripped)` → 将 draft 条目迁移为 `plan_audit_change` 行（按时间顺序）→ `DELETE FROM plan_audit_draft WHERE plan_id=$1` → `status='approved'` + `version+=1` → `COMMIT`。
    - 即使 draft 条目集合为空，仍落一条 `plan_audit_record`（Req 7.1 "恰好一条"）。
    - 返回 `{plan_id, status, version, audit_record_id}`。
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 7.1, 7.2_
    - _Properties: P4, P5, P6_

  - [x] 2.6 [PBT] Audit invariants after edit/approve
    - **Property 5: audit record completeness & uniqueness** — 对任意成功完成的 `edit_draft → … → approve` 或单次 `edit_approved`，断言：(a) 恰好新增一条 `plan_audit_record`；(b) `reviewer_user_id`/`username` 按字节等于请求头；(c) approve 路径 opinion == stripped；edit_after_approve 路径 opinion IS NULL；(d) 差分集合与 Property 3 的差分相等。
    - 使用 hypothesis 生成器生成任意 patch 序列 + 最终 approve。
    - _Requirements: 4.4, 7.1, 7.2, 7.3, 7.4, 8.2_
    - _Properties: P5_

- [x] 3. FastAPI routes & error handling
  - [x] 3.1 Add `PATCH /api/v1/plans/{plan_id}` endpoint
    - 在 `water-info-ai/app/main.py` 新增 `update_plan_content(plan_id, body, http_request)` 路由，入口调用 `_get_user_from_request()` 校验身份（Req 8.3/8.4 映射到 400 `MISSING_IDENTITY` / `UNKNOWN_REVIEWER`）。
    - 路由仅解析入参为 `PlanEditRequest`（详见 design.md §1.1），委托到 `PlanReviewService.edit_draft()` 或 `edit_approved()`；按状态分派。
    - 校验失败的字段级错误聚合为 422，响应体带 `fields[]` 字段路径。
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8, 6.1, 6.3, 6.6, 8.3, 8.4_
    - _Properties: P2, P3, P6_

  - [x] 3.2 Add `POST /api/v1/plans/{plan_id}/approve` endpoint
    - 同上接入 `_get_user_from_request`，解析 `{version, opinion}` 后调用 `PlanReviewService.approve()`，返回 `{planId, status, version, auditRecordId}`。
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 8.3, 8.4_
    - _Properties: P4, P5, P6_

  - [x] 3.3 Add `GET /api/v1/plans/{plan_id}/audits` endpoint
    - 委托到 `DatabaseService.list_plan_audits(plan_id)`（新增方法），按 `reviewed_at DESC` 返回 `plan_audit_record` + 关联 `plan_audit_change`，空集时返回 `{records: []}`。
    - 身份头缺失仍返回 400；鉴权由 Java 侧 `@PreAuthorize` 负责。
    - _Requirements: 7.5_
    - _Properties: P5_

  - [x] 3.4 Unit tests for reviewer identity gate
    - 表驱动测试：空 `X-User-Id`、空 `X-Username`、超 255 字符、user 表不存在 的 user_id，逐一断言各路由返回 400 `MISSING_IDENTITY` / `UNKNOWN_REVIEWER` 且 DB 无副作用。
    - _Requirements: 8.3, 8.4_
    - _Properties: P5_

  - [x] 3.5 [PBT] Opinion acceptance domain
    - **Property 4: opinion validity** — 对任意字符串 `opinion`，approve 被接受当且仅当 `opinion.strip().length ∈ [1,500]`；否则 422 + 状态保持 draft + 无审计行。
    - hypothesis 生成纯空白、边界长度（0/1/500/501）、混合前后空白、多字节字符。
    - _Requirements: 4.6, 4.7_
    - _Properties: P4_

  - [x] 3.6 [PBT] Version + state gating for edit & approve
    - **Property 6: optimistic lock + init invariants** 与 **Property 3 (status portion)** — 对任意并发编辑/批准调用序列（`r1→r2` 读到同一 version），只有一个请求成功且 `version+=1`；失败方不产生 draft 条目、不改内容、不落审计。
    - hypothesis 生成 `(request_a, request_b)` 对，模拟在内存 SQLite/postgres 上的串行化重放。
    - _Requirements: 1.5, 3.7, 3.8, 4.5, 6.1_
    - _Properties: P2, P3, P6_

  - [x] 3.8 Remove `PATCH /api/v1/plans/{plan_id}/status`
    - 删除 `main.py` 中 `update_plan_status_endpoint` 函数及装饰器；内部的状态跃迁仍通过 `db.update_plan_status()` 在执行后台任务 / 批准流程内部调用（这些调用点保持不变）。
    - 移除该路由对应的测试用例（如存在于 `tests/test_main_api.py`）。
    - _Requirements: 9.1_（设计决策 D1）

  - [x] 3.9 Error-code mapping integration test
    - 表驱动集成测试覆盖 400/401/403/404/409/422 全部错误码（见 design.md Error Handling 表），断言响应体 `data.errorCode` 与 HTTP 状态码对齐。
    - _Requirements: 3.6, 3.7, 3.8, 4.5, 4.6, 4.7, 6.1, 7.8, 8.3, 8.4_
    - _Properties: P2, P3, P4_

- [x] 4. Checkpoint — Python service green
  - Ensure all tests pass, ask the user if questions arise.

### Group B · water-info-platform (Java / Spring Boot)

- [x] 5. Proxy DTOs
  - [x] 5.1 Add `PlanEditRequest` + nested upsert/delete DTOs
    - 新建 `com.waterinfo.platform.module.ai.dto.PlanEditRequest`，字段与 design.md §1.1 请求体对齐；使用 `@JsonProperty` 映射 snake_case；`version` 用 `@NotNull` 注解。
    - 嵌套 `ActionsPatch` / `ResourcesPatch` / `NotificationsPatch`，内部 `upsert: List<...>` + `delete: List<...>`。
    - _Requirements: 3.1, 3.3, 3.4_

  - [x] 5.2 Add `PlanApproveRequest` + `PlanApproveResponse` DTOs
    - 字段 `int version` / `String opinion` / `String planId` / `String status` / `long auditRecordId`。
    - _Requirements: 4.3, 4.4_

  - [x] 5.3 Add `PlanAuditListResponse` + `PlanAuditRecord` + `PlanAuditChange` DTOs
    - 字段与 design.md §1.3 响应对齐；`changes: List<PlanAuditChange>`。
    - _Requirements: 7.5_

- [x] 6. `AiServiceClient` proxy methods
  - [x] 6.1 Add `updatePlan(id, PlanEditRequest)`
    - 仿 `getPlans()` / `executePlan()` 结构：通过 `aiUserContext.getCurrentUser().flatMap(...)`，`webClient.patch().uri("/api/v1/plans/{id}", id).headers(h -> addUserHeaders(h, user)).bodyValue(request)`，将 Python 返回的 JSON 映射回 `FloodPlanResponse`（复用 `mapPlanDetail`）。
    - _Requirements: 3.1, 3.2, 8.1_
    - _Properties: P2_

  - [x] 6.2 Add `approvePlan(id, PlanApproveRequest)`
    - `webClient.post().uri("/api/v1/plans/{id}/approve", id)…` → 映射为 `PlanApproveResponse`。
    - _Requirements: 4.3, 4.4, 8.1_
    - _Properties: P2, P4_

  - [x] 6.3 Add `listPlanAudits(id)`
    - `webClient.get().uri("/api/v1/plans/{id}/audits", id)…` → 映射为 `PlanAuditListResponse`。
    - _Requirements: 7.5, 8.1_
    - _Properties: P2_

- [x] 7. `FloodAiController` routes
  - [x] 7.1 Add `PATCH /api/v1/plans/{id}` with `@PreAuthorize("hasAnyRole('ADMIN','OPERATOR')")`
    - 委托到 `aiServiceClient.updatePlan(id, request)`，包装为 `ApiResponse::success`。
    - _Requirements: 3.1, 3.2, 5.1, 5.3, 5.5, 6.4, 6.6, 8.1_
    - _Properties: P2_

  - [x] 7.2 Add `POST /api/v1/plans/{id}/approve` with `@PreAuthorize("hasAnyRole('ADMIN','OPERATOR')")`
    - 委托到 `aiServiceClient.approvePlan(id, request)`。
    - _Requirements: 4.3, 5.2, 5.3, 5.5, 8.1_
    - _Properties: P2, P4_

  - [x] 7.3 Add `GET /api/v1/plans/{id}/audits` with `@PreAuthorize("hasAnyRole('ADMIN','OPERATOR','VIEWER')")`
    - 委托到 `aiServiceClient.listPlanAudits(id)`。
    - _Requirements: 7.5, 7.6_
    - _Properties: P2_

  - [x] 7.4 `@PreAuthorize` matrix unit tests (`@SpringBootTest` + `MockMvc`)
    - 表驱动：对 (role ∈ {ANON, VIEWER, OPERATOR, ADMIN}) × (endpoint ∈ {edit, approve, audits}) 断言 200/401/403 命中；WireMock mock Python 响应为 200 以剥离下游。
    - _Requirements: 2.2, 2.5, 5.1, 5.2, 5.3, 5.5, 7.6, 9.2, 9.3_
    - _Properties: P2_

  - [x] 7.5 WireMock assertion: identity headers propagate
    - 集成测试用 WireMock 捕获 Python 端点收到的请求，断言 `X-User-Id` 与 `X-Username` 均非空、长度 ≤ 255 且等于 `SecurityUser` 的当前值。
    - _Requirements: 8.1_
    - _Properties: P5_

- [x] 8. Checkpoint — Java proxy green
  - Ensure all tests pass, ask the user if questions arise.

### Group C · water-info-admin (Vue 3 + TypeScript)

- [x] 9. API client layer
  - [x] 9.1 Extend TypeScript types in `src/types/models.ts`
    - 新增 `PlanEditRequest` / `PlanApproveRequest` / `PlanApproveResponse` / `PlanAuditRecord` / `PlanAuditChange` / `PlanAuditListResponse`；与 Java DTO 字段同名同型。
    - 在 `FloodPlan` 接口上加 `version: number` 字段。
    - _Requirements: 3.1, 4.3, 7.5_

  - [x] 9.2 Remove `updatePlanStatus()` from `src/api/flood.ts`
    - 删除 `updatePlanStatus` 函数定义与其 export；在整个仓库 grep 确认无外部调用后再删除。
    - _Requirements: 9.1_（设计决策 D1）

  - [x] 9.3 Add `updatePlan()` / `approvePlan()` / `getPlanAudits()` in `src/api/flood.ts`
    - `updatePlan(id, body) → patch<FloodPlan>('/plans/${id}', body, withAuth())`。
    - `approvePlan(id, body) → post<PlanApproveResponse>('/plans/${id}/approve', body, withAuth())`。
    - `getPlanAudits(id) → get<PlanAuditListResponse>('/plans/${id}/audits', withAuth())`。
    - _Requirements: 3.1, 4.3, 7.5_

- [x] 10. `src/views/ai/plan/index.vue` rework
  - [x] 10.1 Replace status `el-select` with read-only `el-tag`
    - 移除 `el-select` / `el-option` 组（两处：行内与抽屉头）；用 `<el-tag>` 按 `statusLabel(row.status)` 渲染。
    - 删除 `handleStatusChange` 及其 import；删除 `updatePlanStatus` 的 import。
    - _Requirements: 1.1, 1.2, 9.1_
    - _Properties: P1_

  - [x] 10.2 [PBT] Status label function
    - **Property 1: `labelOf(s) === "草案" ⇔ s === "draft"`** — 用 `fast-check` 生成任意字符串，断言仅 `"draft"` 映射到 `"草案"`。
    - 测试文件：`water-info-admin/tests/unit/plan-status-label.spec.ts`。
    - _Requirements: 1.1, 1.2, 9.1_
    - _Properties: P1_

  - [x] 10.3 Add `viewMode` / `editMode` local state + edit form scaffold
    - 详情抽屉内以 `draftPlan = cloneDeep(currentPlan)` 进入 `editMode`；顶部显示 `<el-tag type="warning">编辑中</el-tag>`，批准按钮在 `editMode` 下隐藏（`v-if="!editMode"`）。
    - 四段内容改为可编辑表单：summary 用 `el-input type="textarea" :autosize="{minRows:10,maxRows:40}"`；actions/resources/notifications 用 `el-table` + "新增行 / 删除行" 按钮。
    - _Requirements: 3.1, 9.2, 9.3, 9.4_（设计决策 D2）

  - [x] 10.4 Dirty-state guard (cancel / drawer-close / route-leave)
    - `const isDirty = computed(() => !isEqual(draftPlan, currentPlan))`；`handleCancel` / drawer `before-close` / `onBeforeRouteLeave` 在 `isDirty` 时弹 `ElMessageBox.confirm('存在未保存修改，确认放弃？')`。
    - _Requirements: 9.5_

  - [x] 10.5 Wire `updatePlan()` save action with version
    - 保存时构造 `PlanEditRequest` diff-style payload（仅带改动的子集 + `version = currentPlan.version`），调用 `updatePlan(id, payload)`；成功后以返回的 Plan 刷新 `currentPlan` 与 `draftPlan`，`ElMessage.success('保存成功')` ≥ 2s；失败 `ElMessage.error(err.message)` 且保留 `draftPlan` 不回滚。
    - _Requirements: 3.2, 3.5, 3.6, 3.8_

  - [x] 10.6 Approval dialog
    - 独立 `<el-dialog>`，表单项：`opinion` 用 `el-input type="textarea" :maxlength="500" show-word-limit`。
    - 提交按钮 `:disabled="!opinionValid || loading"`，其中 `opinionValid = opinion.trim().length ∈ [1,500]`。
    - 提交期间禁用全部表单控件；成功 `ElMessage.success('批准成功')` ≥ 2s 并关闭对话框 + 刷新详情；失败 `ElMessage.error(err.message)` 且保留 `opinion` 字段不清空。
    - _Requirements: 4.1, 4.2, 9.6, 9.7, 9.8, 9.9_
    - _Properties: P4_

  - [x] 10.7 Role × status action visibility
    - 根据 `useUserStore().roles` 与 `currentPlan.status` 控制 "编辑" / "批准" / "执行" 按钮显隐（见 design.md §3 可见性表）。
    - _Requirements: 2.5, 5.3, 6.2, 6.4, 9.2, 9.3_
    - _Properties: P2_

  - [x] 10.8 Audit-trail tab in detail drawer
    - 抽屉内加 `<el-tabs>` 两个 tab：`详情` / `审计记录`；`审计记录` 懒加载调用 `getPlanAudits(id)`，按 `reviewed_at DESC` 以 `<el-timeline>` 渲染；空集时显示 `<el-empty description="暂无审计记录" />`。
    - 每条记录展开显示 `opinion`（approve 才有）与 `changes`（按 field_path 分组）。
    - _Requirements: 7.5, 7.7_

  - [x] 10.9 Component tests for save / approve UX timing
    - 使用 vitest + `@vue/test-utils` + 假时钟：断言成功 toast ≥ 2s、loading 中提交按钮 disabled、失败时 opinion 字段保留原值。
    - _Requirements: 3.5, 9.7, 9.8, 9.9_

- [x] 11. Checkpoint — Admin console green
  - Ensure all tests pass, ask the user if questions arise.

### Group D · Cross-cutting

- [x] 12. End-to-end & dead-code verification
  - [x] 12.1 End-to-end smoke (automated, not manual)
    - 在 `water-info-ai/tests/` 追加 `test_plan_review_smoke.py`：seed 一条 draft 预案 → 用 `TestClient` 调用 `PATCH /plans/{id}`（修改 summary + actions）→ 再次 `PATCH` 以累计 draft 差分 → `POST /plans/{id}/approve` → `GET /plans/{id}/audits` 断言恰好一条记录，changes 覆盖两次编辑的并集且 `from_status='draft'`、`to_status='approved'`。
    - _Requirements: 1.5, 3.2, 4.3, 4.4, 7.1, 7.2, 7.3, 7.4, 7.5_
    - _Properties: P3, P5, P6_

  - [x] 12.2 Dead-code & contract regression grep
    - 仓库范围 grep 确认：
      - `water-info-ai` 下不再存在 `update_plan_status_endpoint` 与 `PATCH /api/v1/plans/{plan_id}/status` 字面量；
      - `water-info-admin/src` 下不再存在 `updatePlanStatus` 或 `handleStatusChange`（仅 plan 视图）；
      - `water-info-ai/app/**` 下不存在 `import jwt` / `from jose` / `PyJWT`（Req 8.5 回归检查）。
    - 以 `pytest` / `vitest` 中断言式单元测试或 `scripts/check-dead-code.sh` 形式固化。
    - _Requirements: 8.5, 9.1_

- [x] 13. Final checkpoint — Full system green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP; they do not block dependent waves in the scheduling graph.
- `[PBT]` tag identifies property-based-test tasks (hypothesis for Python, fast-check for Vue) — all use ≥ 100 examples per design.md §Testing Strategy.
- Every implementation sub-task references both the requirement clauses it fulfills (`_Requirements:_`) and the correctness properties it validates (`_Properties:_`), per design.md §Correctness Properties.
- Checkpoints (4, 8, 11, 13) are manual verification gates and therefore excluded from the dependency graph.
- Dependency graph tasks 12.1 / 12.2 run after all per-service waves complete; they are the last two waves because they observe end-to-end behavior.
