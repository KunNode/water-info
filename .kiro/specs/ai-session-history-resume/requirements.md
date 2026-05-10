# Requirements Document

## Introduction

AI 指挥台（水情 AI Command Center）当前提供会话历史列表（SessionDrawer），但点击列表项不会产生任何效果：既不会加载历史消息，也不会导航到该会话，更不会提示错误。用户无法恢复之前的对话，也无法在历史会话基础上继续追问。

本特性要求打通"点击历史会话 → 还原前端消息（含推理链与工具调用轨迹）→ 基于完整历史继续对话（后端 AI 保留全量上下文）"的端到端链路，使用户能够在任一历史会话上无缝续聊，AI 能够记住先前提及的站点、风险结论、预案名称等实体信息。

涉及三端：
- 前端 `water-info-admin`（Vue 3 + Pinia）：`views/ai/command/index.vue`、`components/SessionDrawer.vue`、`stores/aiConversation.ts`、`api/flood.ts`
- 后端 `water-info-ai`（FastAPI + LangGraph）：`main.py` 的 `/api/v1/conversations/{id}/messages` 与 SSE `event_stream()`、`memory/service.py::load_context()`
- 数据库：`conversation_messages`、`conversation_snapshots` 两张表已存在，需在加载与续聊时被完整使用

## Glossary

- **AI_Command_Console**: 前端 AI 指挥台页面（`views/ai/command/index.vue`），用户在此与多智能体系统交互的主界面
- **Session_Drawer**: 前端会话历史抽屉组件（`components/SessionDrawer.vue`），展示历史会话列表
- **Conversation_Store**: 前端 Pinia 状态仓库（`stores/aiConversation.ts`），管理当前会话的消息列表、当前 `sessionId` 与加载状态
- **Messages_API**: 后端 REST 接口 `GET /api/v1/conversations/{session_id}/messages`，返回历史消息与快照
- **Stream_API**: 后端 SSE 接口 `POST /api/v1/flood/query/stream`，携带 `session_id` 以续聊
- **Memory_Service**: 后端 `app/memory/service.py` 中的 `load_context()`，负责从库中装载历史消息、快照、摘要并注入到智能体提示词
- **Message_Record**: 单条消息的持久化记录，字段包括 `role`、`content`、`reasoning`、`traces`、`created_at` 等
- **Reasoning_Chain**: 助手消息附带的思维链（reasoning 字段），前端以可折叠区域展示
- **Tool_Call_Trace**: 助手消息执行的工具调用轨迹（traces 字段），前端按工具名/参数/返回结果渲染
- **Snapshot**: `conversation_snapshots` 表中保存的结构化上下文快照（如已关注的站点、风险等级、预案 ID 等实体）
- **Conversation_Summary**: 后端维护的滚动摘要，用于长对话的压缩上下文
- **Loaded_Session**: 用户通过点击 Session_Drawer 中某一条历史会话后被激活为当前会话的会话

## Requirements

### Requirement 1：点击历史会话项必须能可靠加载会话

**User Story:** 作为 AI 指挥台用户，我希望点击会话历史抽屉中的任一会话条目即可切换到该会话，以便我能查看并继续之前的对话。

#### Acceptance Criteria

1. WHEN 用户在 Session_Drawer 中点击一条历史会话项，THE AI_Command_Console SHALL 将该条目对应的 `session_id` 设置为 Conversation_Store 的当前 `sessionId`
2. WHEN Conversation_Store 的当前 `sessionId` 被更新为历史会话 ID，THE Conversation_Store SHALL 调用 Messages_API 拉取该会话的历史消息
3. WHEN Messages_API 请求成功返回，THE Conversation_Store SHALL 用返回的消息列表替换当前消息列表，并标记当前会话为 Loaded_Session
4. WHEN 历史消息加载完成，THE AI_Command_Console SHALL 关闭 Session_Drawer 并将消息视图滚动至最新一条消息
5. WHILE Messages_API 请求进行中，THE AI_Command_Console SHALL 在消息视图区域展示加载中状态
6. THE Session_Drawer SHALL 对每条会话项提供可被键盘（Enter/Space）与鼠标点击触发的交互元素

### Requirement 2：加载后的前端必须完整还原历史消息内容

**User Story:** 作为 AI 指挥台用户，我希望加载历史会话后看到与当时完全一致的对话内容，包括 AI 的思维链和工具调用过程，以便我理解 AI 之前的推理依据。

#### Acceptance Criteria

1. WHEN Conversation_Store 处理 Messages_API 返回的 Message_Record，THE Conversation_Store SHALL 按 `created_at` 升序排列并保留每条消息的 `role`、`content`、`created_at` 字段
2. WHERE 某条 Message_Record 的 `role` 为 `assistant` 且包含非空 `reasoning` 字段，THE Conversation_Store SHALL 将其还原为该条消息的 Reasoning_Chain，并使前端以可折叠区域展示
3. WHERE 某条 Message_Record 包含非空 `traces` 字段，THE Conversation_Store SHALL 将其还原为该条消息的 Tool_Call_Trace 列表，并使前端按每次工具调用的名称、参数、返回结果渲染
4. WHEN 历史消息在前端渲染完成，THE AI_Command_Console SHALL 展示与原会话相同的消息顺序、文本内容、Reasoning_Chain 与 Tool_Call_Trace
5. IF 某条 Message_Record 的 `reasoning` 或 `traces` 字段缺失或为空，THEN THE AI_Command_Console SHALL 仅省略对应的可折叠区域，并正常展示该消息的其余内容

### Requirement 3：在已加载会话上继续对话时，后端 AI 必须携带完整历史上下文

**User Story:** 作为 AI 指挥台用户，我希望在加载历史会话后直接追问，AI 能记住之前提到的站点、风险结论与预案名称，以便我不需要重复提供背景信息。

#### Acceptance Criteria

1. WHEN 用户在 Loaded_Session 中发送新消息，THE AI_Command_Console SHALL 在调用 Stream_API 时携带该 Loaded_Session 的 `session_id`
2. WHEN Stream_API 收到带有已存在 `session_id` 的请求，THE Memory_Service SHALL 从 `conversation_messages` 表加载该会话的全部历史 Message_Record
3. WHEN Memory_Service 加载历史上下文，THE Memory_Service SHALL 同时加载 `conversation_snapshots` 表中该会话的最新 Snapshot 与 Conversation_Summary
4. WHEN 多智能体工作流接收到新请求，THE Memory_Service SHALL 将历史 Message_Record、Snapshot、Conversation_Summary 注入到每个参与本次请求的智能体（含 Supervisor 与 Conversation_Assistant）的提示词上下文
5. WHEN AI 在 Loaded_Session 中生成新回复，THE AI_Command_Console SHALL 能够在不重复提供背景的情况下引用历史会话中提及的站点名称、风险等级结论、预案名称等实体
6. WHEN 新的用户消息与 AI 回复生成完成，THE Memory_Service SHALL 将新消息以与原会话相同的字段结构（`role`、`content`、`reasoning`、`traces`）追加写入 `conversation_messages` 表，且 `session_id` 与 Loaded_Session 一致

### Requirement 4：会话加载失败时必须优雅降级

**User Story:** 作为 AI 指挥台用户，当某个历史会话无法加载时，我希望得到明确提示而不是静默失败，以便我知晓问题并能继续使用产品。

#### Acceptance Criteria

1. IF Messages_API 返回非 2xx 状态码或网络请求失败，THEN THE AI_Command_Console SHALL 展示一条包含失败原因的错误提示
2. IF 会话加载失败，THEN THE Conversation_Store SHALL 保留用户切换会话之前的消息列表与 `sessionId`，不得清空当前视图
3. IF Messages_API 返回的消息列表为空数组，THEN THE AI_Command_Console SHALL 展示空会话状态（不报错），并允许用户在该会话 ID 下继续发起新对话
4. IF 后端在加载历史上下文过程中读取 `conversation_messages` 或 `conversation_snapshots` 失败，THEN THE Memory_Service SHALL 记录错误日志并向 Stream_API 返回可被前端识别的错误事件
5. WHEN AI_Command_Console 收到错误事件，THE AI_Command_Console SHALL 停止当前的流式渲染并提示用户重试
