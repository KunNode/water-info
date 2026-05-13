# Design Document

## Overview

本设计在现有应急预案模块上叠加一条人工审核通道：AI 生成的预案以 `draft`（前端文案“草案”）落库，具备 ADMIN/OPERATOR 角色的 Reviewer 可在 draft 或 approved 状态下编辑摘要/行动/资源/通知四个区块，并通过一次“批准”动作将 draft 推进到 approved，同时留下一条不可变更的审计记录。

关键设计立场：

- **不新增状态、不改造现有生命周期**。`draft → approved → executing → completed` 全部沿用当前枚举（Req 1.3/1.4）；“草稿”改文案不改值。
- **服务边界不动**。预案仍归 Python 服务（`water-info-ai`）所有；Java 平台（`water-info-platform`）仍然只做鉴权与代理。
- **身份直接复用 `AiUserContext` + `X-User-Id`/`X-Username` 请求头**（Req 8），不发明新机制。
- **审计写入与业务写入同事务**。批准与审批期间发生的内容改动以同一笔事务落库，保证 Req 7.1“每次批准恰好一条 Audit_Record”且 Change_Log 与事实一致。
- **并发用简单的 `version` 乐观锁**（Req 3.8）。预案行挂一个 `INT NOT NULL DEFAULT 0` 的 version 列，每次写入 +1，客户端在编辑/批准负载里带 version，服务端比对后再提交。

超出范围：不涉及 Flyway 版本号（Python 侧依旧通过 `ensure_plan_tables()` 的 CREATE TABLE IF NOT EXISTS DDL 管理新表），不涉及通知/执行逻辑改造。

## Architecture

```mermaid
sequenceDiagram
    autonumber
    participant UI as Admin Console<br/>(Vue, :5173)
    participant JAVA as Platform Service<br/>(Spring Boot, :8080)
    participant AI as Plan Service<br/>(FastAPI, :8100)
    participant DB as PostgreSQL

    UI->>JAVA: PATCH /api/v1/plans/{id}<br/>Bearer <JWT>, body {version, patch}
    JAVA->>JAVA: JwtFilter → SecurityUser<br/>@PreAuthorize('hasAnyRole ADMIN,OPERATOR')
    JAVA->>AI: PATCH /api/v1/plans/{id}<br/>X-User-Id, X-Username, body
    AI->>DB: BEGIN;<br/>SELECT version FROM emergency_plan WHERE plan_id=$1 FOR UPDATE
    AI->>AI: 校验身份 + 状态 + 版本 + 负载
    AI->>DB: UPDATE plan/children; INSERT plan_audit_draft;<br/>version := version+1; COMMIT
    AI-->>JAVA: 200 {plan, version}
    JAVA-->>UI: ApiResponse<Plan>
```

```mermaid
sequenceDiagram
    autonumber
    participant UI as Admin Console
    participant JAVA as Platform Service
    participant AI as Plan Service
    participant DB as PostgreSQL

    UI->>JAVA: POST /api/v1/plans/{id}/approve<br/>body {version, opinion}
    JAVA->>AI: POST /api/v1/plans/{id}/approve<br/>X-User-Id, X-Username, body
    AI->>DB: BEGIN;<br/>SELECT status, version FROM emergency_plan FOR UPDATE
    AI->>AI: 校验 status==draft ∧ version 匹配 ∧ opinion 长度∈[1,500]
    AI->>DB: UPDATE status=approved, version+=1;<br/>INSERT plan_audit_record(action=approve, changes=JSON[编辑期间累计])<br/>DELETE plan_audit_draft WHERE plan_id=... ;<br/>COMMIT
    AI-->>JAVA: 200 {plan_id, status, audit_record_id}
    JAVA-->>UI: ApiResponse
```

控制流要点：

1. **Java 仅做鉴权与透传**。所有路由复用 `AiServiceClient.addUserHeaders()`；Controller 用 `@PreAuthorize` 限角色；错误透明上抛。
2. **Python 做业务规则守门**。状态闸门（Req 3.7/6.1）、版本校验（Req 3.8）、必填与长度校验（Req 3.1/3.6/4.6/4.7）、身份校验（Req 8.3/8.4）全部在 Python 侧实现，Java 侧不复制。
3. **审计写入锁在预案行上**。所有内容写入与审计写入包在一个 `BEGIN … FOR UPDATE … COMMIT` 事务里，避免并发下 Change_Log 与事实不一致。

## Components and Interfaces

### 1. 新增/调整的 Java 平台路由

全部位于 `FloodAiController`，沿用 `AiServiceClient`：

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| PATCH | `/api/v1/plans/{id}` | ADMIN, OPERATOR | 编辑预案内容（四个区块任意子集） |
| POST | `/api/v1/plans/{id}/approve` | ADMIN, OPERATOR | 批准草案（draft → approved） |
| GET | `/api/v1/plans/{id}/audits` | ADMIN, OPERATOR, VIEWER | 按时间倒序返回审计记录（Req 7.5） |
| POST | `/api/v1/plans/{id}/execute` | ADMIN, OPERATOR | **不变**（Req 5.4） |
| PATCH | `/api/v1/plans/{id}/status` | — | **移除**（设计决策 D1，见下） |

**设计决策 D1：移除 `PATCH /api/v1/plans/{id}/status`。**
Req 9.1 明确要求“移除允许直接改写预案状态值的下拉选择控件”，且 Req 4 要求批准走专用路径。保留该接口只会让状态机被绕过。移除对象：Python 路由 `update_plan_status_endpoint`、Java 代理与前端 `updatePlanStatus()`、`el-select` 状态下拉。内部状态跃迁（`approve` → approved、`execute` → executing、后台任务完成 → completed）全部走各自专用路径或内部调用 `db.update_plan_status()`，不再对外暴露 loose mutation。

#### 1.1 PATCH `/api/v1/plans/{id}` — 编辑预案

请求体（所有字段均可选；仅提交需要修改的部分）：

```jsonc
{
  "version": 3,                  // 必填：乐观锁基准
  "summary": "# ...",            // 可选：整段 Markdown，0..50000
  "actions": {                   // 可选：行动列表的增删改
    "upsert": [
      { "actionId": "a-001", "description": "...", "priority": 1,
        "assignee": "张三", "status": "pending" },
      { "actionId": null, "description": "新增一项", "priority": 2,
        "assignee": "", "status": "pending" }   // actionId=null → 新建
    ],
    "delete": ["a-002"]
  },
  "resources": {
    "upsert": [
      { "resourceId": 17, "type": "sandbag", "name": "沙袋",
        "quantity": 2000, "location": "翠屏仓库" }
    ],
    "delete": [18]
  },
  "notifications": {
    "upsert": [
      { "notificationId": 5, "channel": "sms", "target": "13800000000",
        "message": "...", "status": "pending" }
    ],
    "delete": []
  }
}
```

- `version` 缺失 → 400。
- `version` 不匹配 → 409（Req 3.8）。
- 非 `draft`/`approved` 状态 → 409（Req 3.7、6.1）。
- approved 状态下非 Reviewer 角色 → 403（Req 6.6）——实际上 Java 层的 `@PreAuthorize` 已拦掉非 ADMIN/OPERATOR，这里 Python 侧二次校验作为纵深防御。
- 字段级校验失败 → 422，`details[]` 指向具体字段路径。

响应：完整 PlanDetailResponse + 新的 `version`。

#### 1.2 POST `/api/v1/plans/{id}/approve` — 批准

请求体：

```jsonc
{
  "version": 4,
  "opinion": "同意执行，已补充了北闸站的撤离路径。"
}
```

- `opinion`：`strip()` 后长度 ∈ [1, 500]，否则 422（Req 4.6/4.7）。
- 当前状态非 `draft` → 409（Req 4.5）。
- 版本不匹配 → 409（Req 3.8）。
- 成功：状态更新为 `approved`，版本 +1，写入一条 `plan_audit_record(action='approve')`，Change_Log 字段汇总本次审核期间的所有 `plan_audit_draft` 差分条目（见“变更日志生成策略”）。

响应：

```jsonc
{
  "planId": "plan-xxx",
  "status": "approved",
  "version": 5,
  "auditRecordId": 1042
}
```

#### 1.3 GET `/api/v1/plans/{id}/audits` — 审计记录列表

响应：

```jsonc
{
  "planId": "plan-xxx",
  "records": [
    {
      "id": 1042,
      "action": "approve",          // approve | edit_after_approve
      "reviewerUserId": "u-17",
      "reviewerUsername": "admin",
      "reviewedAt": "2026-05-12T08:00:00Z",
      "opinion": "同意执行…",       // null for edit_after_approve
      "changes": [ /* Change_Log entries，见 Data Models */ ]
    }
  ]
}
```

结果按 `reviewed_at DESC` 排序；空时返回 `records: []` 而非 404（Req 7.5）。

### 2. 新增/调整的 Python 服务路由

新增四条路由，全部位于 `water-info-ai/app/main.py`，沿用 `_get_user_from_request()`：

- `PATCH /api/v1/plans/{plan_id}` → `update_plan_content()`
- `POST  /api/v1/plans/{plan_id}/approve` → `approve_plan()`
- `GET   /api/v1/plans/{plan_id}/audits` → `list_plan_audits()`
- （移除）`PATCH /api/v1/plans/{plan_id}/status`

内部服务层新增一个 `PlanReviewService`（放在 `app/services/plan_review.py`，薄封装，无新抽象层）负责：

- 在一个事务内完成“读取行并加锁 → 版本校验 → 执行字段级增删改 → 生成 Change_Log 条目 → 追加到 `plan_audit_draft` → 返回新版本”；
- 对 approve：“读取并加锁 → 状态校验 → 汇总所有 draft 审计条目 → 写入 `plan_audit_record` → 清理 `plan_audit_draft` → 状态置 approved”；
- 对 edit_after_approve：状态为 `approved` 的编辑直接写一条 `plan_audit_record(action='edit_after_approve')` 并不经过 draft 暂存（Req 6.5 要求“记录一条包含编辑人、编辑时间、被修改字段范围的修改日志条目”，因此两种审核动作共用一张表，用 `action` 列区分）。

### 3. 前端组件改造

针对 `water-info-admin/src/views/ai/plan/index.vue`（Req 9）：

- **移除**：两处 `el-select` 状态下拉（列表行、详情抽屉）；`updatePlanStatus` 调用；`handleStatusChange`。
- **新增**：`viewMode`/`editMode` 本地状态；列表行与详情中以 `<el-tag>` 只读展示状态；`draft` 文案为“草案”，其余不变。
- **编辑模式**（Req 9.4）：`currentPlan` 深拷贝到 `draftPlan`；四块内容改为可编辑表单（`el-input` + `el-input-number` + 小型 `el-table` 带“新增行/删除行”按钮）；顶部显示“编辑中”徽标，“批准”按钮隐藏；底部“保存/取消”。Markdown 摘要使用 **`el-input type="textarea" :autosize="{minRows: 10, maxRows: 40}"`**，渲染区仍复用现有 `renderPlanSummary()`。**设计决策 D2：不引入 Markdown 所见即所得编辑器**。理由：（a）CLAUDE.md 第 2 条要求“最小代码”；（b）Req 3.1 对摘要的要求是“0..50000 字符的 Markdown 文本”，纯 textarea 完全满足；（c）保存后刷新即可看到渲染效果，成本最低。
- **脏状态保护**（Req 9.5）：`draftPlan` 与 `currentPlan` 深比较得出 `isDirty`；`取消` 或抽屉 `beforeClose`、路由 `onBeforeRouteLeave` 在 `isDirty` 时用 `ElMessageBox.confirm` 二次确认。
- **批准对话框**（Req 9.6/9.7/9.8/9.9）：独立 `el-dialog`；`opinion` 用 `el-input type="textarea"`，`showWordLimit` + `maxlength=500`；`:disabled="loading"`；提交按钮在 `opinion.trim().length ∈ [1,500]` 且非 loading 时才可点；成功后关闭对话框、刷新详情、`ElMessage.success` 持续 ≥2s；失败保留输入（Req 9.9）。
- **审计轨迹入口**（Req 7.7）：详情抽屉底部增加一个 tab `审计记录`（或次级抽屉）——选择 **tab**：改动最小，复用现有 drawer。`onActivate` 时调用 `getPlanAudits(id)`，按时间倒序渲染为时间线组件 `el-timeline`，每条展开显示 opinion 与 changes。
- **入口可见性表**（Req 5/6/9）：

| 状态 ＼ 角色 | ADMIN/OPERATOR | VIEWER |
| --- | --- | --- |
| draft | 编辑 ✅ · 批准 ✅ · 执行 ❌ | 只读 |
| approved | 编辑 ✅ · 批准 ❌ · 执行 ✅ | 只读 |
| executing | 编辑 ❌ · 批准 ❌ · 执行 ❌ | 只读 |
| completed | 编辑 ❌ · 批准 ❌ · 执行 ❌ | 只读 |

### 4. 身份传递

完全复用现有机制：

- Java 侧：`FloodAiController` 的三条新路由均通过 `AiServiceClient` 调用；所有调用链经过 `userContext.getCurrentUser() → addUserHeaders()`（Req 8.1）。
- Python 侧：所有新路由第一行调用 `_get_user_from_request(http_request)`；若 `user_id` 为空或任一字段超过 255 → 400，`error_code=MISSING_IDENTITY`（Req 8.3）；若 `user_id` 在 `"user"` 表中不存在 → 400，`error_code=UNKNOWN_REVIEWER`（Req 8.4）。由于两服务共享同一 Postgres（README/docker-compose 已确认），直接 `SELECT 1 FROM "user" WHERE id::text = $1` 即可。

## Data Models

### 5.1 既有表的调整

在 `emergency_plan` 上新增一个列（通过 `ensure_plan_tables()` 的 `DO $$ BEGIN ALTER TABLE … ADD COLUMN IF NOT EXISTS … END $$` 迁移模式，与库中现有惯例一致）：

```sql
ALTER TABLE emergency_plan
  ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 0;
```

所有写入 `emergency_plan`、`emergency_action`、`resource_allocation`、`notification_record` 的路径（含 `save_emergency_plan`、`update_plan_status`、预案执行后台任务、新路径的编辑/批准）在同一事务内执行 `UPDATE emergency_plan SET version = version + 1 WHERE plan_id = $1`。写入点有限，受影响代码路径在 `database.py` 中集中可控。

### 5.2 新增表

**设计决策 D3：采用“父表 + 子表”而非单 JSON 列**。

- 父表 `plan_audit_record`：记录一次审核动作的元数据。
- 子表 `plan_audit_change`：记录字段级变更。
- 临时表 `plan_audit_draft`：编辑期间暂存差分条目，批准时聚合到 `plan_audit_change` 并清空。

理由：`Change_Log` 要求保留完整前后值（Req 7.3），对于 50000 字长 Markdown，两份完整值可能达 ~100KB；若全部塞到 `plan_audit_record.changes JSONB`，单行宽度会膨胀且难检索。拆两张表后，变更按字段路径检索、按审计记录聚合、长文本读写都更自然。

```sql
CREATE TABLE IF NOT EXISTS plan_audit_record (
    id                BIGSERIAL PRIMARY KEY,
    plan_id           VARCHAR(64) NOT NULL
                      REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
    action            VARCHAR(32) NOT NULL,        -- 'approve' | 'edit_after_approve'
    reviewer_user_id  VARCHAR(64) NOT NULL,
    reviewer_username VARCHAR(255) NOT NULL,
    reviewed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    opinion           TEXT,                         -- 仅 approve 非空；≤500 字符
    from_status       VARCHAR(32) NOT NULL,         -- 'draft' | 'approved'
    to_status         VARCHAR(32) NOT NULL,         -- 'approved' | 'approved'
    from_version      INT NOT NULL,
    to_version        INT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plan_audit_plan_time
    ON plan_audit_record(plan_id, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS plan_audit_change (
    id              BIGSERIAL PRIMARY KEY,
    audit_id        BIGINT NOT NULL
                    REFERENCES plan_audit_record(id) ON DELETE CASCADE,
    field_path      VARCHAR(255) NOT NULL,   -- e.g. 'summary', 'actions[a-001].priority'
    change_type     VARCHAR(16)  NOT NULL,   -- 'add' | 'delete' | 'modify'
    old_value       TEXT,                    -- 完整前值（Req 7.3），对 add 为 NULL
    new_value       TEXT,                    -- 完整后值，对 delete 为 NULL
    old_index       INT,                     -- Req 7.4：列表条目顺序变化时记录
    new_index       INT
);
CREATE INDEX IF NOT EXISTS idx_plan_audit_change_audit
    ON plan_audit_change(audit_id);

CREATE TABLE IF NOT EXISTS plan_audit_draft (
    id              BIGSERIAL PRIMARY KEY,
    plan_id         VARCHAR(64) NOT NULL
                    REFERENCES emergency_plan(plan_id) ON DELETE CASCADE,
    buffered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewer_user_id  VARCHAR(64) NOT NULL,
    reviewer_username VARCHAR(255) NOT NULL,
    field_path      VARCHAR(255) NOT NULL,
    change_type     VARCHAR(16)  NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    old_index       INT,
    new_index       INT
);
CREATE INDEX IF NOT EXISTS idx_plan_audit_draft_plan
    ON plan_audit_draft(plan_id, buffered_at);
```

### 5.3 审计记录的不可变性（Req 7.8）

两条约束：

1. **应用层：不提供任何 UPDATE/DELETE `plan_audit_record`/`plan_audit_change` 的代码路径**（含不在 Python 服务中暴露对应 HTTP 动词、不在 `DatabaseService` 上提供对应方法）。`ON DELETE CASCADE` 只在父预案行被删除时触发——这是数据清理预期，不构成“修改审计记录”。
2. **数据库层：使用触发器兜底**，拒绝 UPDATE，并拒绝直接 DELETE（级联删除来自 `emergency_plan` 时允许通过，以 `current_setting('plan_audit.cascade', true) = 'on'` 白名单开关实现），以防人为误操作：

```sql
CREATE OR REPLACE FUNCTION plan_audit_no_update()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'plan_audit_record is immutable';
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_plan_audit_record_immutable
BEFORE UPDATE ON plan_audit_record
FOR EACH ROW EXECUTE FUNCTION plan_audit_no_update();

-- plan_audit_change 同上
```

### 5.4 Change_Log 生成策略

**设计决策 D4：服务端差分 + 按编辑调用累计暂存 + 批准时汇总**（策略 B）。

流程：

1. **编辑调用（draft 状态）**：进入事务 → `SELECT ... FOR UPDATE` 取当前值 → 计算差分 → 写入 `plan_audit_draft` → 写入新值 → `version+=1` → 提交。一次编辑请求对应 N 条 draft 差分。
2. **批准调用**：进入事务 → 校验状态/版本/opinion → 聚合本预案 `plan_audit_draft` 中全部条目 → 写入 `plan_audit_record(action='approve')` + `plan_audit_change` → `DELETE FROM plan_audit_draft WHERE plan_id = $1` → `status='approved'` + `version+=1` → 提交。
3. **approved 状态下编辑（Req 6.5）**：进入事务 → 校验角色/版本 → 计算差分 → 直接写入 `plan_audit_record(action='edit_after_approve')` + `plan_audit_change` → 写入新值 → `version+=1` → 提交（不经 draft 暂存，因为没有后续的批准聚合点）。

为什么不是策略 A（客户端传 before/after）：

- 前端必须附带完整快照，带宽更大且可被伪造；
- 同一 Reviewer 连续两次编辑时，前端的 "before" 会快速过时；
- 服务端已经持有旧值，差分成本低。

字段路径约定：

- `summary`
- `actions[<action_id>].description`、`.priority`、`.assignee`、`.status`；新增时 `field_path='actions[<action_id>]'` + `change_type='add'`；删除同理。
- `resources[<resource_id>].type` 等；资源/通知主键使用自增 `id`。
- 仅顺序变化的条目：`change_type='modify'` + 仅填 `old_index`/`new_index`。

列表条目的增/删/改与顺序变化覆盖 Req 7.4。

### 5.5 DTO / API 数据结构（Java 侧）

Java 侧新增薄 DTO（放在 `com.waterinfo.platform.module.ai.dto`）：

- `PlanEditRequest`（对应 1.1 请求体，全部可选子结构 + `version` 必填）
- `PlanApproveRequest`：`{ int version; String opinion; }`
- `PlanApproveResponse`：`{ String planId; String status; int version; long auditRecordId; }`
- `PlanAuditRecord` / `PlanAuditChange` / `PlanAuditListResponse`
- `AiServiceClient` 对应三个方法：`updatePlan(id, request)`、`approvePlan(id, request)`、`listPlanAudits(id)`。

上述 DTO 纯透传、字段与 Python 响应对齐，Python 返回的 snake_case 由现有 Jackson 配置 + DTO 上的 `@JsonProperty` 处理（与 `FloodPlanResponse` 等现有 DTO 风格一致）。

## Correctness Properties


*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties are the bridge between the human-readable acceptance criteria above and machine-verifiable correctness guarantees below.*

PBT 适用性评估：本特性的核心是一组状态机 + 数据变换规则（状态闸门、角色授权、乐观锁、差分生成、审计不可变性）。这些都是在大输入空间上必须普遍成立的不变量，且可以用 mock 替代外部依赖以保证 100+ 轮迭代的成本合理。因此 PBT 适用。纯粹的 UI 时序细节（如 2 秒反馈、加载态禁用控件）归入例子测试。

以下 6 条性质是对 prework 产出的 ~18 条可属性化条目的合并结果；每条性质覆盖多条 EARS 验收条件。

### Property 1: 'draft' 是唯一映射到“草案”的状态标签

*For any* 字符串 `s`，前端的状态显示函数 `labelOf(s)` 返回 "草案" 当且仅当 `s === "draft"`；对其他任何状态值（包括 "approved"/"executing"/"completed"/空串/随机字符串），`labelOf(s) !== "草案"`。

**Validates: Requirements 1.1, 1.2, 9.1（状态只读展示）**

### Property 2: 角色 + 状态授权矩阵

*For any* 组合 `(role, status, action)`，其中 `role ∈ {未认证, VIEWER, OPERATOR, ADMIN}`、`status ∈ {draft, approved, executing, completed}`、`action ∈ {edit, approve, execute, readAudits, readPlan}`：调用对应的 Java 平台端点，当且仅当 `(role, status, action)` 属于下列 allow-table 时返回 2xx 并成功执行业务逻辑；否则返回 401（未认证）或 403（权限不足），且 `emergency_plan`/子表/`plan_audit_record` 字节级不变。

Allow-table（由 Req 2/5/6/7 推出）：

| action | 允许的 role | 允许的 status |
| --- | --- | --- |
| `readPlan` | ADMIN, OPERATOR, VIEWER | 全部 |
| `readAudits` | ADMIN, OPERATOR, VIEWER | 全部 |
| `edit` | ADMIN, OPERATOR | draft, approved |
| `approve` | ADMIN, OPERATOR | draft |
| `execute` | ADMIN, OPERATOR | draft, approved |

**Validates: Requirements 2.2, 2.5, 3.7, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.4, 6.6, 7.6, 9.2, 9.3**

### Property 3: 编辑内容的读后回放一致性

*For any* 预案 `P` 处于可编辑状态（draft 或 approved），以及任何通过字段级校验的编辑载荷 `patch`（对四个区块的子集做 upsert/delete），在当前 version 提交后通过 `GET /api/v1/plans/{id}` 读回的预案 `P'` 满足：

- `patch.summary` 若给出，则 `P'.summary == patch.summary`；否则 `P'.summary == P.summary`；
- 对每个被 `upsert` 的条目（行动/资源/通知），`P'` 中存在按业务键可匹配的条目且其字段值等于 `patch` 中给出的值；
- 对每个被 `delete` 的条目 id，`P'` 中不存在；
- 未在 `patch` 中出现的条目在 `P'` 中按原值原样保留；
- `P'.status == P.status`（编辑不改变状态，涵盖 Req 6.3 的 approved 保持不变）。

并且，对任何违反字段约束（summary 长度超限、required 字段缺失、priority 超范围、删除不存在的 id 等）的 `patch`，服务返回 422/404，并且数据库中该预案（及其子表）与提交前字节相同。

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6, 6.3**

### Property 4: 审核意见取值域

*For any* 字符串 `opinion`，对 draft 预案提交 `POST /api/v1/plans/{id}/approve` 请求，批准被服务接受当且仅当 `opinion.strip().length ∈ [1, 500]`；当 `opinion.strip().length == 0` 或 `> 500` 时，服务返回 422，预案状态保持 `draft`，且不生成任何审计记录。

**Validates: Requirements 4.2, 4.6, 4.7, 9.6**

### Property 5: 审核动作写入恰好一条且内容完整、不可更改的审计记录

*For any* 成功完成的审核动作 `a`，其中 `a ∈ {approve-from-draft, edit-after-approve}`，在该动作的事务提交后：

1. `plan_audit_record` 表对该预案新增行数恰好为 1，`action` 列取值对应 `a` 的类型；即使 `a == approve-from-draft` 且本次审核未发生任何内容修改，该记录依然存在且其关联 `plan_audit_change` 集合为空（覆盖 Req 7.1/7.2 的“空集合而非缺省”约束）。
2. 该审计记录的 `reviewer_user_id`、`reviewer_username` 字段按字节等于本次请求携带的 `X-User-Id`、`X-Username` 头，且二者均非空、长度 ≤ 255，且 `reviewer_user_id` 在 `user` 表中存在；否则请求在写入前被拒绝且无审计行被创建。
3. `reviewed_at` 为服务器 UTC 时间戳，精度至少到秒。
4. 对 approve：`opinion` 字段取值等于请求体中 `opinion.strip()`；对 edit-after-approve：`opinion` 为 NULL。
5. 关联的 `plan_audit_change` 集合构成审核前后预案在「摘要 + 行动列表 + 资源清单 + 通知列表」上的完整差分：
    - 对每个被修改的标量字段，存在恰好一条 `change_type='modify'` 条目，`old_value`、`new_value` 分别按字节等于修改前/后的完整字符串（无截断、无摘要，覆盖 Req 7.3）；
    - 对列表新增条目，存在一条 `change_type='add'`，`old_value=NULL`、`new_value` 为新条目的规范化序列化；
    - 对列表删除条目，存在一条 `change_type='delete'`，`old_value` 为删除前条目的规范化序列化、`new_value=NULL`；
    - 对仅发生顺序变化的列表条目，存在一条 `change_type='modify'` 条目，同时 `old_index != new_index`（覆盖 Req 7.4）。
6. 在审计行写入之后，对该审计行或其 change 子表的任何 UPDATE/DELETE 操作（应用层方法、直连 SQL、权限内的触发器规避）都被触发器拒绝，且该行的全部字段字节级保持不变（覆盖 Req 7.8）。
7. `GET /api/v1/plans/{id}/audits` 返回该预案的全部审计行，且按 `reviewed_at DESC` 严格递减排序；该预案无审计行时返回空数组而非错误（覆盖 Req 7.5）。

**Validates: Requirements 4.3, 4.4, 4.5, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5, 7.8, 8.2, 8.3, 8.4**

### Property 6: 乐观锁与初始状态不变式

*For any* 由 AI 持久化的新预案 `P`，其落库后 `P.status == "draft"` 且 `P.version == 0`（覆盖 Req 1.5）。

*For any* 并发或串行的两次编辑/批准请求 `r1 → r2`，两者都读到同一个 `version = v`：若 `r1` 先提交成功，则 `P.version` 变为 `v + 1`；`r2` 携带 `version = v` 再次提交时必然返回 409，且 `r2` 不产生任何内容变更、不产生任何审计或 draft 差分条目。

*For any* 成功通过内容编辑或批准路径提交的请求，提交前后 `P.version` 之差精确为 1。

**Validates: Requirements 1.5, 3.8**

## Error Handling

错误处理采取「**Python 侧为业务规则源、Java 侧透传**」的单点约定。Java `AiServiceClient` 已有 `WebClient` 4xx/5xx 上抛机制；新路由不需要额外翻译层。

### 错误码对齐

| HTTP | 语义 | 触发点（Req）|
| --- | --- | --- |
| 400 `MISSING_IDENTITY` | X-User-Id/X-Username 缺失或超长 | Req 8.3 |
| 400 `UNKNOWN_REVIEWER` | 审核人 id 在 `user` 表中查不到 | Req 8.4 |
| 400 `BAD_VERSION` | 请求体缺少 `version` | Req 3.8 |
| 401 `UNAUTHENTICATED` | 未登录 | Req 5.5 |
| 403 `FORBIDDEN_ROLE` | 角色不在 allowlist | Req 2.2, 5.3, 6.6 |
| 404 `PLAN_NOT_FOUND` / `ENTRY_NOT_FOUND` | 预案或子条目不存在 | Req 3.4 后半 |
| 409 `STATE_CONFLICT` | 当前状态不允许该动作 | Req 3.7, 4.5, 6.1 |
| 409 `VERSION_CONFLICT` | 乐观锁失败 | Req 3.8 |
| 422 `VALIDATION_FAILED` | 字段级校验失败（含 opinion 长度、summary 长度、优先级超出范围、必填缺失等） | Req 3.6, 4.6, 4.7 |
| 422 `AUDIT_IMMUTABLE` | 尝试修改审计记录（应用层） | Req 7.8 |
| 500 | 数据库/触发器异常 | — |

响应体形状（沿用 `ApiResponse`）：

```jsonc
{
  "code": 40901,
  "message": "预案已被他人更新，请刷新后重试",
  "data": {
    "errorCode": "VERSION_CONFLICT",
    "currentVersion": 7,
    "submittedVersion": 5,
    "fields": []                 // 422 时带字段路径与原因
  }
}
```

### 失败原子性

所有编辑/批准端点的事务边界即「整个请求」：任何 SQL 错误、触发器抛错、校验失败都会触发事务 `ROLLBACK`，不产生部分写入，满足 Req 3.6 / Req 3.8 / Req 7.8 的“保持原内容不变”。

### 前端错误处理（Req 9.9）

- 422/409 错误：错误提示使用 Element Plus `ElMessage.error`，展示 `data.message`；在审核对话框下展示的提示**必须保留**用户已填的 `opinion` 字段不被清空。
- 401：跳转登录（复用现有 `request.ts` 拦截器逻辑，不新增）。
- 403：停留在原视图，错误横幅提示。

### 日志与可观测性

- Python 侧在每个新端点入口处 `logger.info("[plan-review] action=%s plan=%s user=%s version=%s", ...)`；请求失败也记录。
- 不引入新的 APM/指标维度——超出本次 scope。

## Testing Strategy

双轨：单元/组件测试覆盖具体示例与 UI 时序；属性测试覆盖 P1–P6 六条普适性不变量。

### 测试分布

| 层 | 框架 | 关注点 |
| --- | --- | --- |
| Python 业务逻辑 + 数据访问 | `pytest` + `hypothesis`（项目已有 `.hypothesis/` 缓存，说明已安装） | P1（服务侧 label 无关，仅作幂等检查）、P2、P3、P4、P5、P6 |
| Java Web 层 | `@SpringBootTest` + `MockMvc`（或 `WebTestClient`）+ `WireMock` mock Python | P2 的 Java 端鉴权映射；DTO 透传回归 |
| 前端 | `vitest` + `@vue/test-utils` + `fast-check`（如未装则追加） | P1 的 UI label 映射；P2 的 UI 可见性矩阵；脏态/批准流程的 UI 例子测试 |
| 端到端 | 既有 smoke + 新的人工审核 smoke（一次完整 draft → edit → approve → read audit） | 1 条集成用例，不做属性化 |

### 属性测试实现要点

- **最少 100 轮**：所有 `@given` 默认 `settings(max_examples=100)`；涉及并发的 P6 用 `@hypothesis.strategies.composite` 模拟两线程序列（无需真正开线程，模拟 version 单调即可）。
- **Tag 注释**：每条属性测试在函数 docstring 顶部写一行 tag，格式：`Feature: plan-human-review, Property N: <property title>`，便于审计追溯。
- **生成器**：
    - 预案生成器基于现有 `save_emergency_plan` 字段类型，覆盖边界（summary 长度 0/1/50000，priority 1–5 边界，action/resource/notification 列表大小 0–10）。
    - opinion 生成器：覆盖纯空白、trim 后 1 字符、500 字符、501 字符、混合前后空白。
    - role 生成器：从 `{ANON, VIEWER, OPERATOR, ADMIN}` 枚举。
- **外部依赖用 mock**：`user` 表查询在 P5 中用固定的 in-memory seed；实际 Postgres 交互通过测试专用的 `testcontainers-python` 启动的临时库，与项目现有 DB 测试惯例一致（沿用 `test_db.py` 风格）。

### 单元/组件/集成测试（例子型）

仅列出属性测试无法覆盖的清单：

- 1.3 / 1.4：一次性契约测试——新建 draft 后 DB 字段和 JSON 字段都为字面量 `"draft"`。
- 2.1：集成测试——seed 四种状态各一条，`GET /plans` 返回集合非空且包含所有状态。
- 2.3 / 2.4：组件测试——`<PlanDetailDrawer>` 在空 actions/resources/notifications 时渲染占位；在 API 失败时渲染错误态。
- 3.5 / 9.7 / 9.8 / 9.9：组件测试——保存 / 批准加载态 / 成功反馈 ≥ 2s / 失败保留 opinion。
- 5.4：Java `@PreAuthorize` 单元测试——VIEWER 访问 `/plans/{id}/execute` 返回 403。
- 7.7：组件测试——approved/executing/completed 状态下详情抽屉显示“审计记录”入口。
- 8.1：Java 侧集成测试——`AiServiceClient.updatePlan()` 调用时 WireMock 捕获到 `X-User-Id`/`X-Username` 非空。
- 8.5：静态检查（grep）——`water-info-ai/app/**` 下不导入 `jwt`/`PyJWT`/`jose`。

### 不做属性测试的条目

- 所有 UI 计时条目（2 秒反馈、≥2s 成功提示、加载态禁用）—— UI 例子测试。
- `ON DELETE CASCADE` 行为 —— 数据库级 CTE 例子测试一条即可。
- 移除 `PATCH /api/v1/plans/{id}/status` 的回归 —— 一次性接口存在性测试。

### 验收自检

属性测试全部通过即视为 P1–P6 成立；再加上上述例子测试通过，即视为全部 EARS 验收条件被覆盖或显式标记为不可属性化（UI 计时/视觉）。
