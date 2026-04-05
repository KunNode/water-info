# AI 对话后端持久化迁移 Task

**日期**: 2026-04-05  
**状态**: 待实现  
**优先级**: P0  
**范围**: `water-info-admin` / `water-info-platform` / `water-info-ai`

---

## 背景

当前 AI 对话能力已经处于“半后端化”状态：

- AI 服务已具备 `conversation_session` / `conversation_message` 表及基础 CRUD。
- 前端会话列表、会话创建、删除、切换历史已走后端接口。
- 但页面主状态仍由前端页面和 `localStorage` 驱动，存在本地缓存与数据库两套事实源。

当前主要问题：

1. 页面刷新后优先恢复本地缓存，而不是以后端为准。
2. 会话未按用户隔离，无法实现真正的“我的会话列表”。
3. assistant 消息只在流结束后落库，中断后可能丢失回复。
4. 右侧风险、预案、智能体状态无法从后端完整恢复。
5. 现有消息结构过于简单，不利于后续 AI 记忆系统扩展。

---

## 目标

- 将 AI 对话切换为“后端数据库为唯一事实源”。
- 前端交互流程接近 ChatGPT 网页端：
  - 新对话草稿态
  - 首条消息发送时创建会话
  - 左侧会话列表
  - 点击会话恢复完整历史
  - 刷新页面后可从服务端恢复
- 为后续记忆系统预留结构化存储能力。

---

## 核心决策

### 1. 会话创建时机

采用“首条消息发送时创建会话”，不再点击“新会话”立即落库，避免产生大量空会话。

### 2. 单一事实源

后端数据库为唯一事实源，前端仅保留以下临时状态：

- 当前输入框草稿
- 当前打开的会话 ID
- 抽屉开关状态
- 正在进行中的流式渲染临时状态

不再把完整消息列表、风险状态、预案状态写入 `localStorage`。

### 3. 消息存储策略

- `user` / `assistant` 作为正式对话消息持久化。
- `thinking` 不入库。
- `agent_message` 不直接混入主聊天消息表，优先进入 `snapshot` 或 `metadata`，避免污染用户主对话历史。

### 4. 用户隔离

由 Spring Boot 平台从当前登录用户上下文读取身份，并在调用 AI 服务时透传用户信息给 AI 服务。AI 服务所有会话查询必须按 `user_id` 过滤。

---

## 范围

### 本次必须完成

- 会话和消息按用户隔离
- 服务端完整恢复会话历史
- 流式 assistant 消息稳定落库
- 前端移除整页 `localStorage` 会话缓存
- 前端状态改为以后端接口为准
- 会话详情接口返回消息 + 会话快照

### 本次不做

- 向量数据库和语义检索
- 长期知识库召回
- 多模态附件上传
- 完整的 Agent Trace 可视化后台

---

## 数据模型任务

### Task 1: 扩展会话表

- [ ] 为 `conversation_session` 增加 `user_id`
- [ ] 增加 `username`
- [ ] 增加 `status`，建议值：`draft` / `active` / `archived` / `deleted`
- [ ] 增加 `last_message_at`
- [ ] 增加 `last_message_preview`
- [ ] 增加 `title_source`，建议值：`manual` / `auto_first_query` / `auto_summary`
- [ ] 为 `(user_id, updated_at desc)` 建索引

建议字段：

```sql
ALTER TABLE conversation_session
  ADD COLUMN IF NOT EXISTS user_id VARCHAR(64) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS username VARCHAR(64) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_message_preview TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS title_source VARCHAR(32) NOT NULL DEFAULT 'auto_first_query';
```

### Task 2: 扩展消息表

- [ ] 为 `conversation_message` 增加 `message_type`
- [ ] 增加 `status`，建议值：`streaming` / `completed` / `failed`
- [ ] 增加 `metadata JSONB`
- [ ] 保留 `role` 字段，兼容 `user` / `assistant` 语义
- [ ] 为 `(session_id, id)` 建稳定分页索引

建议字段：

```sql
ALTER TABLE conversation_message
  ADD COLUMN IF NOT EXISTS message_type VARCHAR(32) NOT NULL DEFAULT 'chat',
  ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'completed',
  ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
```

### Task 3: 新增会话快照表

- [ ] 新增 `conversation_snapshot`
- [ ] 每轮会话结束后更新最新业务快照
- [ ] 快照保存最近一次：
  - `risk_level`
  - `plan_info`
  - `agent_status_summary`
  - `query_count`

建议字段：

```sql
CREATE TABLE IF NOT EXISTS conversation_snapshot (
  session_id VARCHAR(128) PRIMARY KEY REFERENCES conversation_session(session_id) ON DELETE CASCADE,
  risk_level VARCHAR(32) NOT NULL DEFAULT 'none',
  plan_info JSONB NOT NULL DEFAULT '{}'::jsonb,
  agent_status_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  query_count INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Task 4: 为记忆系统预留表

- [ ] 新增 `conversation_summary`
- [ ] 新增 `memory_item`
- [ ] 本期先完成表结构和写入接口占位，不要求完整召回逻辑

---

## 平台透传任务

### Task 5: 平台读取当前用户并透传到 AI 服务

- [ ] 在平台层从 `SecurityContext` 获取当前登录用户
- [ ] 将 `user_id` / `username` 透传给 AI 服务
- [ ] 建议使用请求头：
  - `X-User-Id`
  - `X-Username`
- [ ] AI 服务收到请求后校验并写入会话

建议涉及文件：

- `water-info-platform/src/main/java/com/waterinfo/platform/module/ai/controller/FloodAiController.java`
- `water-info-platform/src/main/java/com/waterinfo/platform/module/ai/client/AiServiceClient.java`
- 可新增 `AiRequestContext` 或类似辅助类，避免 controller 内直接拼 header

验收标准：

- 同一数据库中不同用户只能看到自己的会话列表
- 使用 A 用户创建的会话，B 用户无法查询或删除

---

## AI 服务任务

### Task 6: 重构会话写入逻辑

- [ ] `flood/query` 和 `flood/query/stream` 支持接收平台透传的用户信息
- [ ] 当请求未携带 `session_id` 时，首条消息发送时创建新会话
- [ ] 写入 user message 后，立即更新 `last_message_*`
- [ ] 流式回复开始前创建 assistant 占位消息，状态 `streaming`
- [ ] 流结束后将 assistant 消息更新为最终内容，并标记 `completed`
- [ ] 异常中断时将 assistant 消息标记为 `failed`

### Task 7: 补齐会话接口

- [ ] 保留现有接口兼容前端
- [ ] 新增 `GET /api/v1/conversations/{session_id}` 返回：
  - `session`
  - `snapshot`
  - `latest_plan_summary`
- [ ] 将 `GET /api/v1/conversations/{session_id}/messages` 改为支持分页
- [ ] 增加 `limit`、`before_id` 或 cursor 参数
- [ ] 所有接口按 `user_id` 校验权限

建议返回结构：

```json
{
  "session": {
    "session_id": "xxx",
    "title": "当前汛情分析",
    "status": "active",
    "created_at": "2026-04-05T10:00:00Z",
    "updated_at": "2026-04-05T10:05:00Z"
  },
  "snapshot": {
    "risk_level": "high",
    "plan_info": {},
    "agent_status_summary": {},
    "query_count": 3
  }
}
```

### Task 8: 会话标题优化

- [ ] 默认标题仍可用首条 query 截断兜底
- [ ] 预留异步标题生成能力
- [ ] 当用户手动重命名后，不再被自动覆盖

### Task 9: 记忆系统占位写入

- [ ] 每轮对话完成后异步生成摘要
- [ ] 将摘要写入 `conversation_summary`
- [ ] 将关键事实、决策、待办写入 `memory_item`
- [ ] LangGraph 上下文读取逻辑先保留“最近窗口 + 摘要”模式

建议涉及文件：

- `water-info-ai/app/database.py`
- `water-info-ai/app/main.py`
- `water-info-ai/app/models.py`
- `water-info-ai/app/services/session.py`

---

## 前端任务

### Task 10: 建立 AI 会话状态中心

- [ ] 将 `index.vue` 中的会话主状态抽离到独立 store 或 composable
- [ ] 推荐新增：
  - `water-info-admin/src/stores/aiConversation.ts`
  - 或 `water-info-admin/src/composables/useAiConversation.ts`
- [ ] `SessionDrawer` 不再持有自己的主数据源，只负责展示和触发事件

### Task 11: 移除整页 localStorage 缓存

- [ ] 删除 `water_ai_command_page_cache_v1` 相关逻辑
- [ ] 不再本地持久化完整 `messages`
- [ ] 不再本地持久化 `riskLevel` / `planInfo` / `agentStatus`
- [ ] 仅保留：
  - 当前会话 ID
  - 输入草稿
  - 抽屉开关状态

### Task 12: 路由与会话恢复

- [ ] 路由改为支持 `/ai/command/:sessionId?`
- [ ] 页面加载时：
  - 先取会话列表
  - 若 URL 有 `sessionId`，加载该会话详情
  - 若无 `sessionId`，进入草稿态新会话
- [ ] 点击历史会话时从后端恢复：
  - 主消息区
  - 风险状态
  - 预案状态
  - 查询次数

### Task 13: 新会话与发送流程

- [ ] 点击“新会话”时仅清空当前视图，不立即调用创建接口
- [ ] 首条消息发送时，如果当前没有 `sessionId`，由后端创建并通过流返回
- [ ] 收到 `session_init` 后更新当前路由
- [ ] 发送过程中可做乐观渲染，但结束后以后端结果为准

### Task 14: 适配新的会话详情接口

- [ ] 从详情接口恢复 `messages`
- [ ] 从详情接口恢复 `snapshot`
- [ ] 支持历史消息分页加载
- [ ] 为后续“向上滚动加载历史”预留 UI 结构

建议涉及文件：

- `water-info-admin/src/views/ai/command/index.vue`
- `water-info-admin/src/views/ai/command/components/SessionDrawer.vue`
- `water-info-admin/src/api/flood.ts`
- `water-info-admin/src/composables/useSSE.ts`
- `water-info-admin/src/router/index.ts`

---

## 测试任务

### Task 15: 后端测试

- [ ] AI 服务补充：
  - 会话按用户隔离测试
  - 消息流式写入测试
  - 中断失败标记测试
  - 会话详情接口测试
- [ ] 平台补充：
  - 已登录用户上下文透传测试
  - 越权访问会话测试

### Task 16: 前端测试

- [ ] 刷新页面后从服务端恢复会话
- [ ] 新会话草稿态不落库
- [ ] 首条消息发送后生成新会话
- [ ] 切换会话时侧栏状态正确恢复
- [ ] 删除会话后 UI 与后端同步

---

## 实施顺序

### Phase 1: 后端打底

- [ ] 数据库 schema 变更
- [ ] 平台透传用户身份
- [ ] AI 服务按用户隔离查询

### Phase 2: 会话详情与流式持久化

- [ ] assistant 占位消息
- [ ] 流式更新
- [ ] 快照持久化
- [ ] 新会话首条消息创建

### Phase 3: 前端切换为服务端真值

- [ ] 移除本地完整缓存
- [ ] 增加 store/composable
- [ ] 路由会话化
- [ ] 详情恢复

### Phase 4: 记忆能力预埋

- [ ] 会话摘要
- [ ] memory item
- [ ] 上下文读取切换到“最近窗口 + 摘要”

---

## 验收标准

- [ ] 登录用户只能看到自己的 AI 会话
- [ ] 页面刷新后能从后端完整恢复当前会话
- [ ] 新会话在未发送消息前不会落库
- [ ] 流式中断后数据库中可看到 assistant 失败或未完成状态
- [ ] 会话详情可恢复主消息区和右侧业务快照
- [ ] 删除、重命名、续聊流程稳定
- [ ] 前后端接口兼容现有鉴权体系
- [ ] 为后续记忆系统预留可扩展表结构和接口

---

## 建议拆分为 3 个开发 PR

### PR 1: 后端基础能力

- 平台透传用户
- AI 服务 schema 变更
- 会话按用户隔离
- 会话详情接口

### PR 2: 流式持久化与快照

- assistant 占位消息
- streaming/completed/failed 状态机
- snapshot 持久化

### PR 3: 前端适配

- store/composable 抽离
- 路由会话化
- 移除整页 localStorage
- 新会话草稿态

---

## 备注

如果后续要把 AI 记忆系统继续做深，可以在本任务完成后新增第二期任务，单独处理：

- memory item 检索策略
- 摘要压缩策略
- 多 Agent trace 持久化
- 长期知识库召回
