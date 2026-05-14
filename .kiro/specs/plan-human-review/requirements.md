# Requirements Document

## Introduction

本特性在智慧水利防汛应急管理系统的应急预案（以下称“预案”）模块中，新增**人工审核**流程。由 AI 生成的预案进入系统后以“草案”形式存在，审核人员（ADMIN 或 OPERATOR 角色）可在审核过程中修改预案的任意内容（摘要、应急行动、资源清单、通知方案），填写审核意见后，将预案从草案状态推进至已批准状态，以便后续执行。整个审核过程必须留存完整的审计痕迹。

本特性不引入新的状态（如“已驳回”），也不改变现有生命周期 draft → approved → executing → completed；仅在 draft → approved 的跃迁上附加一次“人工审核”动作，并将前端对 draft 状态的展示文案由“草稿”调整为“草案”。

## Glossary

- **Plan**: 应急预案，即 `emergency_plan` 及其关联的 `emergency_action`、`resource_allocation`、`notification_record` 记录构成的完整业务对象。
- **Draft_Plan**: 处于 `draft` 状态的预案，前端显示文案为“草案”，由 AI 生成的预案默认进入该状态。
- **Reviewer**: 对预案执行人工审核操作的用户，须具备 ADMIN 或 OPERATOR 角色。
- **Review_Action**: 人工审核动作，包括“编辑预案内容”和“批准预案（draft → approved）”。
- **Review_Opinion**: 审核人员在批准预案时填写的自由文本意见。
- **Change_Log**: 单次审核期间，对预案内容所作的字段级修改记录，包含被修改的字段路径、修改前值与修改后值。
- **Audit_Record**: 一次完整审核动作（批准）所产生的审计记录，至少包含审核人 ID、审核人用户名、审核时间、审核意见以及本次审核的变更日志。
- **Plan_Service**: 位于 `water-info-ai`（FastAPI，端口 8100）的预案后端服务，拥有 `emergency_plan` 及其关联表。
- **Platform_Service**: 位于 `water-info-platform`（Spring Boot，端口 8080）的业务平台服务，负责认证、鉴权，并代理前端调用至 Plan_Service。
- **Admin_Console**: `water-info-admin` Vue 3 管理端，预案管理页面位于 `src/views/ai/plan/index.vue`。
- **Role_ADMIN**: 系统管理员角色。
- **Role_OPERATOR**: 业务操作员角色。
- **Role_VIEWER**: 只读查看者角色。

## Requirements

### Requirement 1: 草案术语与展示

**User Story:** 作为管理端使用者，我希望 AI 生成的预案在界面上被称为“草案”，以便与审核后的预案明确区分。

#### Acceptance Criteria

1. WHERE 预案的状态字段值等于字符串字面量 `draft`（小写、精确匹配），THE Admin_Console SHALL 在预案列表页、预案详情页、状态筛选器选项、状态标签徽标，以及任何面向最终用户展示该状态的位置，将该状态的展示文案渲染为中文“草案”（两个汉字，不含前后缀、不含其他修饰词）。
2. IF 预案的状态字段值不等于字符串字面量 `draft`，THEN THE Admin_Console SHALL NOT 将该预案的状态展示文案渲染为“草案”。
3. THE Plan_Service SHALL 在数据库与领域模型中保留字符串字面量 `draft`（小写）作为该状态的底层存储值，不新增、不替换、不重命名现有状态枚举，且不引入额外状态值。
4. THE Platform_Service SHALL 在对外 API 的请求与响应负载中保留字符串字面量 `draft`（小写）作为该状态的传输值，不新增、不替换、不重命名现有状态枚举，且不引入额外状态值。
5. WHEN AI 完成一份新预案的生成并首次持久化，THE Plan_Service SHALL 将该预案的状态字段初始化为字符串字面量 `draft`，且在初始化失败时保留原有数据不落库并向调用方返回指示初始化失败的错误响应。

### Requirement 2: 查看草案

**User Story:** 作为 Reviewer 或 Role_VIEWER，我希望能够查看草案的完整内容，以便进行审核或只读了解。

#### Acceptance Criteria

1. WHEN 已登录用户（持有 Role_ADMIN、Role_OPERATOR 或 Role_VIEWER 之一）请求预案列表时，THE Platform_Service SHALL 在 2 秒内返回包含 `draft`、`approved`、`executing`、`completed` 全部状态的预案条目，且每个条目包含预案标识、标题、当前状态、最后更新时间。
2. IF 未登录用户或不具备 Role_ADMIN、Role_OPERATOR、Role_VIEWER 任一角色的用户请求预案列表或详情，THEN THE Platform_Service SHALL 拒绝该请求并返回表示“未授权”的错误响应，且不返回任何预案数据。
3. WHEN 已登录用户打开一份预案的详情视图时，THE Admin_Console SHALL 在同一视图中完整展示该预案的以下四个区块：摘要（以 Markdown 渲染）、应急行动列表、资源清单、通知方案；任一区块若无数据，THE Admin_Console SHALL 以明确的空状态提示替代该区块内容。
4. IF 预案详情加载失败（例如预案不存在或服务不可达），THEN THE Admin_Console SHALL 在详情视图中展示错误提示并保留用户返回列表的入口，且不展示任何部分加载的数据。
5. WHERE 用户仅具备 Role_VIEWER 角色，THE Admin_Console SHALL 在列表与详情视图中隐藏或以禁用状态呈现所有编辑与批准入口，仅保留查看与返回能力。

### Requirement 3: 编辑预案内容

**User Story:** 作为 Reviewer，我希望在审核过程中能够修改预案的任意内容，以便在批准前修正 AI 生成结果中的不准确或不完整之处。

#### Acceptance Criteria

1. WHILE 预案处于 `draft` 状态且当前用户具有 ADMIN 或 OPERATOR 角色，THE Admin_Console SHALL 向该 Reviewer 提供对以下字段的编辑入口：摘要（Markdown 文本，长度 0 至 50000 字符）、应急行动列表中每条的 description、priority、assignee、status 字段、资源清单中每条的 type、name、quantity、location 字段、通知方案中每条的 channel、target、message、status 字段。
2. WHILE 预案处于 `draft` 状态，THE Plan_Service SHALL 对来自具有 ADMIN 或 OPERATOR 角色的 Reviewer 的字段级修改请求在必填字段、字段类型与取值范围校验通过后，将更新后的内容持久化。
3. WHEN Reviewer 在编辑中新增一条应急行动、资源项或通知项时，THE Plan_Service SHALL 对该条目进行必填字段校验后作为该预案的新记录持久化，其中应急行动必填 description 与 priority，资源项必填 type、name 与 quantity，通知项必填 channel 与 target。
4. WHEN Reviewer 在编辑中删除一条已有的应急行动、资源项或通知项时，THE Plan_Service SHALL 将该条目从该预案中移除且不影响预案其它条目；IF 指定条目在该预案中不存在，THEN THE Plan_Service SHALL 拒绝该请求并返回指示条目不存在的错误信息。
5. WHEN Reviewer 提交的编辑内容通过保存操作写入成功时，THE Admin_Console SHALL 在 2 秒内向该 Reviewer 展示保存成功的反馈并刷新详情视图以呈现最新内容。
6. IF Reviewer 提交的编辑请求中存在必填字段缺失、字段类型不符或字段长度/数值超出规定范围的情况，THEN THE Plan_Service SHALL 拒绝该请求、保持预案原有内容不变，并返回可定位到具体字段的错误信息。
7. IF Reviewer 对处于非 `draft` 状态的预案提交编辑请求，THEN THE Plan_Service SHALL 拒绝该请求、保持预案内容不变，并返回指示当前状态不允许编辑的错误信息。
8. IF 多位 Reviewer 对同一预案并发提交编辑请求，且某一请求所基于的预案内容已被先前另一请求更新，THEN THE Plan_Service SHALL 拒绝该过期请求、保持已成功写入的内容不变，并返回指示内容已被他人更新、需刷新后重试的错误信息。

### Requirement 4: 批准草案（draft → approved）

**User Story:** 作为 Reviewer，我希望在检查并在必要时修改草案内容后，以“批准”动作将预案推进到已批准状态，以便后续执行。

#### Acceptance Criteria

1. WHILE 预案处于 `draft` 状态，THE Admin_Console SHALL 向 Reviewer 展示一个可点击的“批准”操作入口。
2. WHEN Reviewer 触发批准操作时，THE Admin_Console SHALL 展示 Review_Opinion 输入框，并在 Review_Opinion 为空或仅包含空白字符时禁用提交按钮。
3. WHEN Reviewer 提交带有 Review_Opinion（去除首尾空白后长度在 1 到 500 字符之间）的批准请求时，THE Plan_Service SHALL 将该预案的状态由 `draft` 更新为 `approved`。
4. WHEN 一次批准请求成功完成时，THE Plan_Service SHALL 为该次审核创建一条 Audit_Record（见 Requirement 7），并向 Admin_Console 返回更新后的预案状态。
5. IF 当前预案状态不是 `draft`，THEN THE Plan_Service SHALL 拒绝批准请求、保持原状态不变，并返回指明“状态不匹配”的错误响应。
6. IF Reviewer 提交批准请求时 Review_Opinion 为空或去除首尾空白后长度为 0，THEN THE Plan_Service SHALL 拒绝该请求、保持预案状态不变，并返回指明“审核意见必填”的错误响应。
7. IF Reviewer 提交批准请求时 Review_Opinion 去除首尾空白后长度超过 500 字符，THEN THE Plan_Service SHALL 拒绝该请求、保持预案状态不变，并返回指明“审核意见超出最大长度（500 字符）”的错误响应。

### Requirement 5: 角色权限

**User Story:** 作为系统管理员，我希望审核能力按照既有角色模型被精确限定，以保证只有合适的人能修改或批准预案。

#### Acceptance Criteria

1. WHEN 已认证用户携带 Role_ADMIN 或 Role_OPERATOR 角色调用预案编辑接口（涵盖创建、更新、删除预案草稿以及提交送审操作），THE Platform_Service SHALL 允许该请求继续执行对应的业务逻辑。
2. WHEN 已认证用户携带 Role_ADMIN 或 Role_OPERATOR 角色调用预案批准接口，THE Platform_Service SHALL 允许该请求继续执行对应的业务逻辑。
3. IF 已认证用户仅具备 Role_VIEWER 角色并调用预案编辑接口或预案批准接口，THEN THE Platform_Service SHALL 拒绝该请求、返回指示权限不足的错误响应，并保持预案及审核状态数据不发生任何变更。
4. THE Platform_Service SHALL 保持现有预案执行接口（`POST /api/v1/plans/{id}/execute`）仅对 Role_ADMIN 和 Role_OPERATOR 开放的既有授权策略不变。
5. IF 请求在未通过认证的情况下访问预案编辑接口或预案批准接口，THEN THE Platform_Service SHALL 拒绝该请求、返回指示未认证的错误响应，并保持预案及审核状态数据不发生任何变更。

### Requirement 6: 执行前的可编辑性闸门

**User Story:** 作为 Reviewer，我希望预案一旦进入执行阶段就不能再被改动，以避免执行期间内容漂移带来的混乱。

#### Acceptance Criteria

1. WHILE 预案处于 `executing` 或 `completed` 状态，THE Plan_Service SHALL 拒绝任何对该预案摘要、应急行动、资源清单、通知方案字段的编辑请求，保持原字段值不变，并向调用方返回标识“预案处于执行或已完成状态、不可编辑”的错误响应。
2. WHILE 预案处于 `executing` 或 `completed` 状态，THE Admin_Console SHALL 将该预案的编辑入口与批准入口呈现为不可操作状态（隐藏或以禁用样式展示且不可点击）。
3. WHEN Reviewer 在预案处于 `approved` 状态时提交对摘要、应急行动、资源清单或通知方案字段的编辑请求，THE Plan_Service SHALL 保存更新后的字段值并保持预案状态为 `approved`。
4. WHILE 预案处于 `approved` 状态，THE Admin_Console SHALL 仅向 Reviewer 角色暴露对摘要、应急行动、资源清单、通知方案的编辑入口，并对其他角色隐藏该入口。
5. WHEN Plan_Service 成功完成对 `approved` 状态预案的字段编辑，THE Plan_Service SHALL 记录一条包含编辑人、编辑时间、被修改字段范围的修改日志条目，并将其纳入该预案的审计轨迹中供查询。
6. IF 非 Reviewer 角色通过任何入口尝试编辑 `approved` 状态预案的受保护字段（摘要、应急行动、资源清单、通知方案），THEN THE Plan_Service SHALL 拒绝该请求并返回标识“无编辑权限”的错误响应，同时保持原字段值不变。

### Requirement 7: 审计记录

**User Story:** 作为系统管理员或事后追溯者，我希望每一次人工批准都留下完整的审计痕迹，以便回溯谁在什么时候基于什么意见、做了哪些修改后批准了预案。

#### Acceptance Criteria

1. WHEN Plan_Service 完成一次草案批准时（无论本次审核是否对预案内容进行了修改），THE Plan_Service SHALL 为该次审核持久化恰好一条 Audit_Record。
2. THE Audit_Record SHALL 包含以下字段：审核人用户 ID、审核人用户名、审核时间（以服务器 UTC 时间戳表示，精度至少到秒）、Review_Opinion、以及本次审核期间对预案所做的 Change_Log；IF 本次审核未对预案进行任何修改，THEN THE Plan_Service SHALL 将 Change_Log 持久化为一个空集合而非缺省字段或空值。
3. THE Change_Log SHALL 以字段路径为粒度，为每一处被修改的字段记录修改前值与修改后值；对于 Markdown 文本或其他长文本字段，THE Change_Log SHALL 记录完整的修改前字符串与修改后字符串，而不得以摘要、差分片段或截断文本替代。
4. WHERE Change_Log 针对的是列表类字段（含应急行动、资源项、通知项），THE Change_Log SHALL 对列表中新增的条目标记为“新增”动作、对列表中删除的条目标记为“删除”动作，并对列表中已有条目仅发生顺序变化的情况标记为“修改”动作并同时记录该条目的修改前索引与修改后索引。
5. WHEN Reviewer 请求查看某份预案的审计记录时，THE Plan_Service SHALL 按审核时间倒序返回该预案的全部 Audit_Record；IF 该预案尚无任何 Audit_Record，THEN THE Plan_Service SHALL 返回空集合而非错误响应。
6. WHERE 已认证用户具备 Role_ADMIN、Role_OPERATOR 或 Role_VIEWER，THE Platform_Service SHALL 允许该用户调用审计记录查询接口；IF 请求方未认证或不具备上述任一角色，THEN THE Platform_Service SHALL 拒绝该请求并返回表示权限不足的错误响应。
7. WHEN Reviewer 打开一份已批准、执行中或已完成的预案详情时，THE Admin_Console SHALL 提供查看该预案历史审计记录的入口。
8. IF 任何调用方尝试修改或删除已持久化的 Audit_Record，THEN THE Plan_Service SHALL 拒绝该操作、保留原 Audit_Record 内容与字段完全不变，并返回表示审计记录不可变更的错误响应。

### Requirement 8: 身份信息在 Platform_Service 与 Plan_Service 之间的传递

**User Story:** 作为系统架构师，我希望在由 Platform_Service 代理到 Plan_Service 的审核请求中，真实审核人的身份信息可以被可靠地传递，以便 Plan_Service 能够记录准确的审计信息。

#### Acceptance Criteria

1. WHEN Platform_Service 将预案编辑或批准请求代理到 Plan_Service 时，THE Platform_Service SHALL 在代理请求中附带当前已认证用户的用户 ID 与用户名，其中用户 ID 与用户名均为非空字符串且长度不超过 255 个字符。
2. WHEN Plan_Service 接收到预案编辑或批准请求时，THE Plan_Service SHALL 仅使用 Platform_Service 代理请求中附带的用户 ID 与用户名作为 Audit_Record 审核人字段的唯一来源。
3. IF Plan_Service 接收到的预案编辑或批准请求未附带用户 ID 或用户名，或其中任一字段为空字符串，或任一字段长度超过 255 个字符，THEN THE Plan_Service SHALL 拒绝该请求，不创建或更新任何 Audit_Record，并返回指示身份信息缺失或无效的错误响应。
4. IF Plan_Service 接收到的代理请求中附带的用户 ID 不对应任一已存在的系统用户，THEN THE Plan_Service SHALL 拒绝该请求，不创建或更新任何 Audit_Record，并返回指示审核人身份无法识别的错误响应。
5. THE Plan_Service SHALL 不直接解析或依赖 Platform_Service 的 JWT、前端凭证或任何非代理请求附带字段来确定审核人身份。

### Requirement 9: 前端审核交互

**User Story:** 作为 Reviewer，我希望前端界面提供清晰的“审核/编辑/批准”入口，而不是通过可直接改写状态值的下拉框来处理状态变更，以防止误操作。

#### Acceptance Criteria

1. THE Admin_Console SHALL 在预案列表行操作区与详情视图中移除允许直接改写预案状态值的下拉选择控件，并以只读文本形式展示当前预案状态。
2. WHILE 预案处于 `draft` 状态且当前用户为 Reviewer，THE Admin_Console SHALL 在该预案的详情视图中提供“编辑”和“批准”两个显式操作入口。
3. WHILE 预案处于 `approved` 状态且当前用户为 Reviewer，THE Admin_Console SHALL 在该预案的详情视图中仅提供“编辑”操作入口，且不展示“批准”入口。
4. WHEN Reviewer 触发“编辑”操作时，THE Admin_Console SHALL 将摘要、应急行动、资源清单、通知方案切换为可编辑表单，提供“保存”和“取消”入口，并在编辑模式期间隐藏或禁用“批准”入口。
5. WHILE 编辑表单处于已修改未保存状态，IF Reviewer 触发“取消”操作或离开当前详情视图，THEN THE Admin_Console SHALL 弹出二次确认提示告知存在未保存修改，并在 Reviewer 未确认放弃前保留编辑内容不做丢弃。
6. WHEN Reviewer 触发“批准”操作时，THE Admin_Console SHALL 弹出确认表单强制填写 Review_Opinion，对输入执行前后空白裁剪，并要求裁剪后长度在 1 至 500 个字符之间；在输入不满足该校验前，确认提交按钮 SHALL 保持禁用状态。
7. WHILE 批准请求处于已提交未返回结果的进行中状态，THE Admin_Console SHALL 禁用确认表单中的全部提交控件以阻止重复提交。
8. WHEN 批准接口返回成功响应时，THE Admin_Console SHALL 更新该预案在当前视图中的状态展示，并向 Reviewer 展示批准成功的反馈，且该成功反馈 SHALL 至少持续可见 2 秒。
9. IF 批准接口返回失败响应，THEN THE Admin_Console SHALL 保持该预案状态展示不变，向 Reviewer 展示携带失败原因的错误提示，并保留 Reviewer 已填写的 Review_Opinion 输入内容不被清空。
