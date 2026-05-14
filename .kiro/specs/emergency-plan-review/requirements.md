# Requirements Document

## Introduction

本需求聚焦应急预案的「人工审核」闭环，补齐当前只能改 status、不能改内容的能力空白。AI 生成的 `draft` 状态预案视为「草案」，需要由 `ADMIN`/`OPERATOR` 角色的值班人员在 UI 上对预案的摘要、行动项、资源清单、通知方案进行逐条审查与修订，再以显式审核动作转入 `approved`。本次同时引入审核留痕（含 AI 原稿快照与审核后快照）、驳回语义与并发修改保护。

已存在、本次不再重复设计的基础：

- 预案状态枚举 `draft` / `approved` / `executing` / `completed`；AI 生成默认 `draft`
- `GET /api/v1/plans`、`GET /api/v1/plans/{id}`、`POST /api/v1/plans/{id}/execute`、`PATCH /api/v1/plans/{id}/status`
- 前端 `src/views/ai/plan/index.vue` 的列表 / 详情 / 状态下拉 / 执行按钮
- 角色权限：`ADMIN` / `OPERATOR` 可写，`VIEWER` 只读

## Assumptions (需用户确认后固化)

以下假设在首版写入需求，若不符合期望请在评审阶段反馈，将整体调整：

1. **可编辑字段范围**：摘要 markdown 全文；每条 action 的 `description` / `priority` / `assignee`；每条 resource 的 `type` / `name` / `quantity` / `location`；每条 notification 的 `channel` / `target` / `message`。运行态字段 action.status、notification.status **不纳入审核编辑**（留给执行阶段）。
2. **action / resource / notification 的增删**：允许在审核中新增、删除整条记录，而非仅原地修改现有条目。
3. **驳回语义**：不新增 `rejected` 状态枚举；驳回视为「停留在 `draft` 并写一条驳回留痕（含必填驳回意见）」，预案可被继续编辑或再次提交审核。
4. **留痕粒度**：保留一份 AI 原稿快照（首次生成时固化）与审核通过时的终稿快照；中间编辑过程不做多版本历史，仅覆盖当前 `draft` 内容。
5. **审核意见**：审核通过时选填，驳回时必填。
6. **批量审核**：本期不在范围内，审核逐条进行。
7. **并发控制**：采用基于 `updatedAt`（或版本号）的乐观锁；后写者若检测到基线过期需拒绝并提示刷新。
8. **可编辑的状态窗口**：仅 `draft` 允许内容编辑；`approved` / `executing` / `completed` 的预案内容只读。

## Glossary

- **Emergency_Plan**：应急预案聚合根，包含 summary、actions、resources、notifications 四段内容与状态字段
- **Plan_Draft**：`status = draft` 的 Emergency_Plan，对应 UI 术语「草案」
- **Plan_Review_Service**：后端预案审核能力（目前物理上位于 water-info-ai，由 water-info-platform 反向代理），提供编辑、审核通过、驳回三类写操作
- **Plan_Editor**：前端 `water-info-admin` 中承载审核编辑的界面组件
- **Plan_Review_Record**：审核留痕记录，包含审核人、审核时间、审核决定、审核意见、AI 原稿快照、审核后快照
- **Reviewer**：具备 `ADMIN` 或 `OPERATOR` 角色、执行审核动作的后台用户
- **AI_Original_Snapshot**：预案首次生成时的内容快照，不随人工编辑改变
- **Approved_Snapshot**：审核通过瞬间的内容快照
- **Baseline_Version**：客户端读取预案时拿到的 `updatedAt` 或版本号，用于提交时的乐观锁比对

## Requirements

### Requirement 1: 草案术语与审核入口

**User Story:** 作为值班 Operator，我想在预案列表与详情里一眼识别出哪些是待审核草案，并进入人工审核界面，以便优先处理未审核的 AI 产出。

#### Acceptance Criteria

1. WHERE 预案的 `status` 取值为 `draft`, THE Plan_Editor SHALL 在列表与详情中以「草案」文案替代当前「草稿」显示。
2. WHERE 当前登录用户角色为 `ADMIN` 或 `OPERATOR` 且预案 `status` 为 `draft`, THE Plan_Editor SHALL 在该预案的操作列与详情页显示「人工审核」入口按钮。
3. WHERE 当前登录用户角色为 `VIEWER`, THE Plan_Editor SHALL 隐藏「人工审核」入口按钮。
4. WHEN Reviewer 点击某条草案的「人工审核」入口, THE Plan_Editor SHALL 打开可编辑的审核视图并加载该预案当前 `draft` 全量内容。

### Requirement 2: 摘要与结构化条目的编辑能力

**User Story:** 作为审核人，我想在审核过程中直接修订 AI 草案的摘要文字与行动项/资源/通知清单，以便在批准前纠正偏差。

#### Acceptance Criteria

1. WHILE 预案处于 `draft` 状态, THE Plan_Review_Service SHALL 接受对 `summary` 全文、`actions` 列表、`resources` 列表、`notifications` 列表的整体替换式更新。
2. WHEN Reviewer 提交内容更新, THE Plan_Review_Service SHALL 允许对 action 的 `description` / `priority` / `assignee` 字段修改，且不接受对 action.status 的修改。
3. WHEN Reviewer 提交内容更新, THE Plan_Review_Service SHALL 允许对 resource 的 `type` / `name` / `quantity` / `location` 字段修改。
4. WHEN Reviewer 提交内容更新, THE Plan_Review_Service SHALL 允许对 notification 的 `channel` / `target` / `message` 字段修改，且不接受对 notification.status 的修改。
5. WHEN Reviewer 在列表中新增或删除整条 action / resource / notification, THE Plan_Review_Service SHALL 持久化新增与删除结果并返回更新后的列表。
6. IF 更新请求中 `quantity` 为非正整数或 `priority` / `channel` 不在已定义枚举中, THEN THE Plan_Review_Service SHALL 拒绝请求并返回字段级校验错误。
7. IF 更新请求中 `actions` / `resources` / `notifications` 均为空数组且 `summary` 去除 Markdown 后为空, THEN THE Plan_Review_Service SHALL 拒绝请求并返回「预案内容不能整体为空」错误。

### Requirement 3: 审核状态窗口约束

**User Story:** 作为合规负责人，我不希望已批准或执行中的预案被任意编辑，以保证执行上下文稳定可追溯。

#### Acceptance Criteria

1. WHILE 预案 `status` 为 `approved` 或 `executing` 或 `completed`, THE Plan_Review_Service SHALL 拒绝对 `summary` / `actions` / `resources` / `notifications` 的任何修改请求。
2. IF 对非 `draft` 状态的预案发起内容编辑请求, THEN THE Plan_Review_Service SHALL 返回 HTTP 409 并附带当前实际状态。
3. WHILE 预案 `status` 不为 `draft`, THE Plan_Editor SHALL 以只读方式渲染内容，并隐藏保存与审核按钮。

### Requirement 4: 审核通过动作

**User Story:** 作为审核人，我想在确认草案无误后一次性把「最新编辑内容」与「状态转为已批准」原子落库，以免出现内容未保存就已批准的错位。

#### Acceptance Criteria

1. WHEN Reviewer 触发审核通过动作, THE Plan_Review_Service SHALL 在单个事务中完成内容更新与 `status` 从 `draft` 置为 `approved`。
2. WHEN 审核通过事务提交, THE Plan_Review_Service SHALL 写入一条 Plan_Review_Record，记录审核人 ID 与姓名、审核时间（UTC）、决定为 `approved`、审核意见（可为空）、Approved_Snapshot。
3. WHERE Reviewer 在提交时填写了审核意见, THE Plan_Review_Service SHALL 将该意见原文保存于 Plan_Review_Record.`comment`。
4. IF 审核通过事务中任一步骤失败, THEN THE Plan_Review_Service SHALL 回滚内容更新与状态变更，并返回失败原因。
5. WHEN 审核通过成功, THE Plan_Editor SHALL 刷新详情视图，展示新状态 `approved` 并禁用后续编辑控件。

### Requirement 5: 驳回动作

**User Story:** 作为审核人，当草案与现场研判不符时我希望驳回并留下原因，让后续编辑者看到驳回依据再修订。

#### Acceptance Criteria

1. WHEN Reviewer 触发驳回动作, THE Plan_Review_Service SHALL 保持预案 `status` 为 `draft`，不做状态迁移。
2. WHEN Reviewer 触发驳回动作, THE Plan_Review_Service SHALL 写入一条 Plan_Review_Record，决定为 `rejected`，记录审核人、审核时间、驳回意见。
3. IF 驳回请求中审核意见为空或仅含空白字符, THEN THE Plan_Review_Service SHALL 拒绝请求并返回「驳回必须填写意见」错误。
4. WHEN 驳回写入成功, THE Plan_Editor SHALL 在该预案的审核历史区域展示最新一条驳回记录（审核人 / 时间 / 意见）。
5. WHERE 预案存在未解决的驳回记录, THE Plan_Editor SHALL 在审核视图顶部显示最近一次驳回意见。

### Requirement 6: 审核留痕与快照

**User Story:** 作为合规与复盘人员，我想查看每份预案的 AI 原稿、审核后终稿以及历次审核动作，以便事后追溯修改轨迹。

#### Acceptance Criteria

1. WHEN AI 生成预案并落库, THE Plan_Review_Service SHALL 基于此时的 `summary` / `actions` / `resources` / `notifications` 固化一份 AI_Original_Snapshot，此快照后续不随人工编辑更新。
2. WHEN 审核通过完成, THE Plan_Review_Service SHALL 将事务提交瞬间的内容快照作为 Approved_Snapshot 存入该预案的 Plan_Review_Record。
3. THE Plan_Review_Service SHALL 对同一预案按时间倒序维护全部 Plan_Review_Record（含通过与驳回）。
4. WHEN Reviewer 在详情页请求查看审核记录, THE Plan_Editor SHALL 展示该预案的 AI_Original_Snapshot、最新 Approved_Snapshot（若有）、全部审核动作时间线。

### Requirement 7: 并发编辑保护

**User Story:** 作为多人值守场景下的审核人，我不希望自己的修改被另一位同时打开同一草案的同事覆盖。

#### Acceptance Criteria

1. WHEN Plan_Editor 加载草案用于审核, THE Plan_Review_Service SHALL 在响应中返回当前 Baseline_Version（`updatedAt` 或版本号字段）。
2. WHEN Reviewer 提交内容更新 / 审核通过 / 驳回请求, THE Plan_Editor SHALL 在请求体中携带加载时的 Baseline_Version。
3. IF 请求携带的 Baseline_Version 与库中当前值不一致, THEN THE Plan_Review_Service SHALL 拒绝写入并返回 HTTP 409 「预案已被他人修改，请刷新后重试」。
4. WHEN 写操作成功, THE Plan_Review_Service SHALL 递增 Baseline_Version 并在响应中返回新值。

### Requirement 8: 审核权限

**User Story:** 作为系统管理员，我希望审核相关接口严格遵守既有角色模型，避免越权。

#### Acceptance Criteria

1. WHERE 调用方角色为 `ADMIN` 或 `OPERATOR`, THE Plan_Review_Service SHALL 允许内容编辑、审核通过、驳回三类写操作。
2. IF 调用方角色为 `VIEWER` 或未认证, THEN THE Plan_Review_Service SHALL 拒绝上述三类写操作并返回 HTTP 403。
3. THE Plan_Review_Service SHALL 将请求者的用户 ID 与角色作为审核留痕来源，不接受客户端自行传入的审核人身份字段。
