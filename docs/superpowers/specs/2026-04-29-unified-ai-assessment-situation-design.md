# 统一 AI 研判态势事实源设计

## 背景

当前系统已经具备 AI 风险巡检、AI 研判持久化、`/api/v1/ai-assessments` 查询接口和 `/ws/ai-assessments` 推送通道。前端也已经在 AI 指挥台局部消费 AI 研判，在大屏中展示 AI Assessment 区域。

现有问题是前端页面之间存在风险态势口径分裂：

1. 大屏的 AI Assessment 目前会从 `recentAlarms` 临时推导风险等级和建议文案。
2. AI 指挥台的风险状态来自会话流式事件、局部 RiskPanel 最新研判和页面状态，容易和大屏不同步。
3. WebSocket 消息可加速刷新，但页面刷新、断线重连、多页面并存时仍需要回到持久化数据。

本设计的目标是让前端各页面对同一份数据得到一致的信息，避免“大屏显示高风险，而 AI 指挥台显示正常”的不一致。

## 目标

1. 以平台侧持久化的最新 AI 研判记录作为当前 AI 风险态势的权威来源。
2. 前端建立统一态势事实源，所有页面读取同一个规范化态势状态。
3. WebSocket 作为刷新加速通道，而不是唯一真相来源。
4. 明确定义无研判、研判过期、网络失败和断线时的降级展示。
5. 保持第一阶段范围可控：前端统一状态与后端 WebSocket 契约增强，不重建完整态势领域模型。

## 非目标

1. 不在第一阶段新增完整 `/situation/current` 聚合接口。
2. 不改变 AI 风险模型本身的判断逻辑。
3. 不要求重构 AI 指挥台会话流式分析流程。
4. 不把告警列表临时推导结果伪装成 AI 研判。

## 核心原则

持久化研判记录是权威来源。AI 服务完成事件触发或定时巡检后，应写入平台侧 `ai_assessment` 表。前端每次进入大屏、AI 指挥台或展示风险态势时，都读取最新持久化 AI 研判记录。

WebSocket 的职责是通知前端“有新研判可用”并加速刷新。即使 WebSocket 携带完整 payload，页面刷新、断线重连和多页面同步仍以 REST 查询到的最新持久化记录为最终恢复路径。

页面可以有不同视觉表达，但不能各自独立计算当前 AI 风险等级。有有效 AI 研判时，大屏和 AI 指挥台展示同一条 `id / level / assessedAt / source / summary`。

## 前端设计

### 统一态势 Store

新增前端统一态势事实源，例如 `useSituationStore`。该 Store 负责：

1. `ensureFresh()`：页面进入或需要展示态势时读取最新持久化 AI 研判。
2. `connectAssessmentStream()`：连接 `/ws/ai-assessments`，接收新研判通知。
3. `refreshLatestAssessment()`：通过 `/api/v1/ai-assessments?limit=1` 回补最新记录。
4. 规范化风险等级，将后端大写或小写等级统一为前端风险枚举。
5. 维护连接状态、同步状态、最后成功同步时间和错误原因。
6. 计算研判是否过期，并输出统一降级状态。

建议 Store 输出状态：

```ts
type SituationFreshness = 'fresh' | 'stale' | 'none' | 'offline'
type SituationConnection = 'connecting' | 'connected' | 'reconnecting' | 'disconnected'

interface SituationState {
  latestAssessment: AiAssessment | null
  canonicalRiskLevel: 'none' | 'low' | 'moderate' | 'high' | 'critical'
  freshness: SituationFreshness
  connection: SituationConnection
  lastSyncedAt: string | null
  lastError: string | null
  isLoading: boolean
}
```

### 大屏接入

`water-info-admin/src/views/bigscreen/index.vue` 不再从 `recentAlarms` 推导 AI Assessment。它改为读取统一态势 Store：

1. 有 `fresh` AI 研判时，显示统一风险等级、来源、研判时间、摘要和预案摘录。
2. `stale` 时，继续显示最后一次研判，但标注“研判已过期/仅供参考”。
3. `offline` 时，显示同步失败或离线标识；如有缓存记录，标注缓存来源。
4. `none` 时，显示“暂无 AI 研判”。如展示告警态势，只标注为“告警辅助”，不得命名为 AI 研判。

### AI 指挥台接入

AI 指挥台保留会话内流式过程态，用于表达“当前对话正在分析中”。但页面顶部风险态势和 RiskPanel 的最终风险展示读取统一态势 Store。

`store.riskLevel` 可继续作为会话流式事件中的过程态或当前回答上下文，但不能覆盖统一态势 Store 中的最新持久化研判。RiskPanel 应明确区分：

1. 当前会话分析中：来自 SSE 的过程状态。
2. 当前系统态势：来自最新持久化 AI 研判。

第一阶段优先保证“大屏和 AI 指挥台最终展示的系统态势一致”。

## 后端设计

### 持久化约束

平台侧现有 `AiAssessmentService.upsert` 已在写入后广播 WebSocket。第一阶段保留该模型，但需要确认写入成功后再广播。前端以写入后的最新记录为准。

### WebSocket 契约增强

`/ws/ai-assessments` 建议统一事件格式：

```json
{
  "type": "AI_ASSESSMENT_UPDATED",
  "data": {
    "id": "assessment-id",
    "stationId": "station-id",
    "stationName": "站点名称",
    "metricType": "WATER_LEVEL",
    "level": "HIGH",
    "summary": "研判摘要",
    "planExcerpt": "预案摘录",
    "source": "EVENT",
    "assessedAt": "2026-04-29T10:30:00"
  },
  "timestamp": 1777420000000
}
```

同时补充轻量连接事件：

1. `PONG`：响应前端 ping，支持连接健康判断。
2. `ERROR`：后端可发送可恢复错误信息。
3. 连接关闭后由前端 Store 进入 `reconnecting` 或 `disconnected`。

如果后端暂时只广播完整 payload，前端可以直接应用 payload；如果未来改为只广播 `id` 或 `assessedAt`，前端收到后调用 `refreshLatestAssessment()`。

## 同步流程

页面挂载时：

1. 页面调用 `situationStore.ensureFresh()`。
2. Store 通过 REST 获取最新持久化 AI 研判。
3. Store 规范化风险等级和新鲜度。
4. 页面响应式读取统一状态并展示。

实时更新时：

1. AI 服务完成巡检并写入平台持久化记录。
2. 平台写入成功后广播 `AI_ASSESSMENT_UPDATED`。
3. Store 收到消息后应用完整 payload 或重新拉取最新记录。
4. 大屏和 AI 指挥台同时从 Store 更新展示。

断线恢复时：

1. Store 标记连接为 `reconnecting`。
2. 重连成功后立即调用 `refreshLatestAssessment()`。
3. 如果 REST 成功，以最新持久化记录覆盖本地缓存。
4. 如果 REST 失败，保留已有记录并标记 `offline`。

## 降级规则

`fresh`：最新持久化 AI 研判在有效期内。所有页面显示同一条研判。

`stale`：有持久化研判，但超过有效期。继续显示最后一次研判，并标注“研判已过期/仅供参考”。

`offline`：REST 或 WebSocket 失败。如本地已有上次成功记录，可显示缓存并标注离线；没有缓存则显示无法获取研判。

`none`：数据库无 AI 研判记录。页面显示“暂无 AI 研判”。告警态势可以辅助展示，但必须标注“告警辅助”，不能作为 AI 风险结论。

第一阶段建议默认新鲜度阈值为 30 分钟，可在 Store 中集中配置。后续如业务确认不同来源有不同有效期，可再扩展为配置项。

## 测试与验收

1. 当最新持久化 AI 研判为 `HIGH` 时，刷新大屏和 AI 指挥台，两处均显示 `HIGH`，且 `id / assessedAt / source` 一致。
2. WebSocket 断开时，页面仍能通过 REST 恢复最新持久化研判。
3. 新 AI 研判写入并广播后，大屏和 AI 指挥台均更新到同一条记录。
4. 数据库没有 AI 研判时，页面显示“暂无 AI 研判”，不得从告警中伪造 AI 风险。
5. 研判超过有效期时，两处均显示相同过期状态。
6. REST 获取失败且本地有旧记录时，页面显示旧记录和离线标识。
7. 前端构建通过，关键页面可正常打开。

## 风险与对策

1. 风险：现有 AI 指挥台会话风险与系统态势风险并存，用户可能混淆。  
   对策：文案和组件命名区分“当前会话分析”与“当前系统态势”。

2. 风险：WebSocket payload 与 REST 字段不一致。  
   对策：前端 Store 统一 normalize；后端广播使用与 `AiAssessmentVO` 对齐的字段。

3. 风险：过期阈值业务含义未定。  
   对策：第一阶段使用集中常量，默认 30 分钟，并在 UI 中表达“研判时间”。

4. 风险：只做前端统一 Store 仍可能遗漏非接入页面。  
   对策：第一阶段明确接入大屏和 AI 指挥台；后续地图、告警页如展示 AI 态势，也必须读取同一 Store。

## 实施边界

第一阶段建议改动范围：

1. `water-info-admin/src/stores/`：新增统一态势 Store。
2. `water-info-admin/src/composables/useWebSocket.ts`：增强连接状态、重连状态和心跳支持，或新增专用可靠 WebSocket composable。
3. `water-info-admin/src/views/bigscreen/index.vue`：AI Assessment 区域改读统一态势 Store。
4. `water-info-admin/src/views/ai/command/components/RiskPanel.vue`：系统态势改读统一态势 Store。
5. `water-info-platform/src/main/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandler.java`：统一事件类型并补轻量心跳/错误事件。
6. `water-info-platform/src/main/java/com/waterinfo/platform/module/aiassessment/service/AiAssessmentService.java`：确保广播字段与 VO 一致。

本设计不进入实现阶段，下一步应基于该 spec 编写实施计划。
