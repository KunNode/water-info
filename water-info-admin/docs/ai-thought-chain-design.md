# AI 指挥对话思考链改造方案

## 1. 前端状态结构设计

核心类型已落在 `src/types/agentStream.ts`，并接入 `src/stores/aiConversation.ts`。

```ts
type AgentMessageStatus = 'thinking' | 'tool_running' | 'answering' | 'done' | 'error'

interface ChatMessageItem {
  id?: number | string
  role: 'user' | 'assistant' | 'thinking' | 'agent'
  content: string
  timestamp: Date
  status?: AgentMessageStatus
  reasoning?: ReasoningState
  answer?: AssistantAnswerState
  error?: string
}

interface ReasoningState {
  status: AgentMessageStatus
  title: string
  expanded: boolean
  startedAt: number
  endedAt?: number
  elapsedMs?: number
  steps: ReasoningStep[]
}

interface ReasoningStep {
  id: string
  kind: 'thought' | 'tool'
  title: string
  content: string
  status: 'pending' | 'running' | 'success' | 'error'
  startedAt: number
  endedAt?: number
  durationMs?: number
  tool?: {
    name: string
    displayName: string
    inputSummary?: string
    resultSummary?: string
  }
}

interface AssistantAnswerState {
  status: 'idle' | 'answering' | 'done' | 'error'
  content: string
  startedAt?: number
  endedAt?: number
  error?: string
}
```

同一条助手消息同时承载 `reasoning` 和 `answer/content`。思考链增量写入 `reasoning.steps[].content`，最终答案增量写入 `answer.content` 并同步到 `message.content`，状态流转为 `thinking -> tool_running -> answering -> done/error`。

## 2. SSE 事件协议设计

每条 SSE 推荐使用 `event: <type>` + `data: JSON`，JSON 内也保留 `type`，方便代理层丢失 event 名时恢复。

```txt
event: thought_delta
data: {"type":"thought_delta","id":"t1","delta":"正在分析上游来水..."}
```

事件示例与前端动作：

```json
{"type":"message_start","messageId":"msg_001","sessionId":"s_001"}
```
前端创建或绑定当前助手消息。

```json
{"type":"thought_start","id":"t1","title":"正在理解指挥意图","content":"需要先汇总实时水情。"}
```
新增 thought 节点，消息状态置为 `thinking`。

```json
{"type":"thought_delta","id":"t1","delta":" 同时核查未关闭告警。"}
```
通过 RAF buffer 追加到指定 thought 节点。

```json
{"type":"tool_start","id":"tool_1","toolName":"query_water_level","inputSummary":"查询重点站近 2 小时水位"}
```
新增 tool 节点，`toolName` 转译为“正在查询实时水情数据...”，不展示原始函数名和参数。

```json
{"type":"tool_delta","id":"tool_1","delta":"正在读取站点曲线..."}
```
追加工具执行过程摘要。

```json
{"type":"tool_result","id":"tool_1","summary":"2 个上游站点超过警戒线"}
```
写入工具结果摘要。

```json
{"type":"tool_end","id":"tool_1","status":"success","durationMs":1280}
```
工具节点置为 success，并显示耗时。

```json
{"type":"thought_end","id":"t1","durationMs":900}
```
思考节点置为 success。

```json
{"type":"answer_start"}
```
消息状态置为 `answering`。

```json
{"type":"answer_delta","delta":"当前建议按高风险响应处置："}
```
进入最终答案打字机队列。

```json
{"type":"answer_end","durationMs":2100}
```
等待打字机 buffer 清空后置为 done，思考面板标题变为“已思考（用时 x 秒）”。

```json
{"type":"error","message":"实时水情查询超时","recoverable":true}
```
新增错误/降级节点。`recoverable=true` 时不终止最终答案输出。

## 3. Element-Plus-X ThoughtChain 改造方案

评估结论：适合承载该 UI，但当前项目未安装 `vue-element-plus-x`，且仓库约定不新增依赖，所以本次实现了 `ThoughtChainPanel.vue` 作为无新增依赖版本。后续若允许新增依赖，可替换为 `ThoughtChain`。

官方文档显示 `ThoughtChain` 支持 `thinkingItems`、`loading/error/success` 状态、展开控制、Markdown、打字机配置和 `#icon` 插槽。映射方式：

```ts
const thinkingItems = computed(() => message.reasoning?.steps.map(step => ({
  id: step.id,
  title: step.title,
  thinkTitle: step.kind === 'tool' ? '工具执行' : '推理过程',
  thinkContent: step.tool?.resultSummary || step.content,
  status: step.status === 'running' ? 'loading' : step.status === 'error' ? 'error' : 'success',
  isCanExpand: true,
  isDefaultExpand: true,
  isMarkdown: step.isMarkdown,
})))
```

Vue 示例：

```vue
<script setup lang="ts">
import { ThoughtChain } from 'vue-element-plus-x'
import { computed } from 'vue'

const props = defineProps<{ message: ChatMessageItem }>()
const thinkingItems = computed(() => props.message.reasoning?.steps.map(mapStepToItem) ?? [])
</script>

<template>
  <ThoughtChain
    :thinking-items="thinkingItems"
    dot-size="small"
    max-width="900px"
    line-gradient
  >
    <template #icon="{ item }">
      <el-icon v-if="item.status === 'success'"><Check /></el-icon>
      <span v-else class="loading-dot" />
    </template>
  </ThoughtChain>
</template>
```

当前 `ThoughtChainPanel.vue` 自带 `#title`、`#step-icon`、`#step-content`、`#loading` 插槽，可按相同方式自定义标题、内容、状态图标和 loading 效果。若使用 Element-Plus-X，为贴近 DeepSeek 视觉，建议覆盖外层最大宽度、左侧竖线颜色、节点尺寸、标题字号、内容灰度、展开箭头、loading 动画和暗色主题变量。

## 4. 工具调用文案映射策略

映射函数在 `src/utils/agentToolCopy.ts`：

```ts
mapToolCallTitle('query_water_level') // 正在查询实时水情数据...
mapToolCallTitle('query_water_level', 'success') // 已获取实时水情数据
mapToolCallTitle('query_water_level', 'fallback') // 实时水情查询失败，正在尝试备用数据源
```

策略：
- 不显示 `toolName`、原始参数、token、手机号、邮箱、授权头等敏感字段；
- `inputSummary` 由后端提供时优先使用，否则只显示“已接收 xx 等查询条件”；
- `tool_result.summary` 优先，其次按数组长度、风险等级、状态、摘要字段生成短文案；
- 失败时显示友好降级提示，并允许后续 `answer_delta` 继续输出。

## 5. 流式渲染策略

`useAgentStream` 只负责解析 SSE。页面入口负责状态更新：
- 思考链 delta 进入 `reasoningBuffers`，用 `requestAnimationFrame` 合并写入；
- 最终答案 delta 进入 `answerBuffer`，每帧写入少量字符形成打字机效果；
- 思考链和最终答案状态互不覆盖；
- `answer_end` 只设置“buffer 清空后完成”，避免最后一段答案被截断；
- 兼容旧协议 `agent_message/trace_update`，旧 trace 也会转成自然语言思考节点。

## 6. 具体代码

已新增或接入：
- `src/composables/useAgentStream.ts`
- `src/views/ai/command/components/AgentMessage.vue`
- `src/views/ai/command/components/ThoughtChainPanel.vue`
- `src/types/agentStream.ts`
- `src/utils/agentToolCopy.ts`
- `src/mocks/agentThoughtChainSSE.ts`
- `src/views/ai/command/index.vue`
- `src/views/ai/command/components/ChatPanel.vue`
- `src/stores/aiConversation.ts`

本地 mock 可用：

```ts
import { mockAgentThoughtChainEvents, toMockSSELines } from '@/mocks/agentThoughtChainSSE'
```

## 7. 产品细节

当前实现：
- 生成中显示“思考中...”；
- 工具调用中显示“正在调用工具...”；
- 最终答案阶段显示“正在生成最终回答...”；
- 完成后显示“已思考（用时 x 秒）”；
- 默认展开，`ThoughtChainPanel` 支持 `autoCollapseDone`；
- 错误节点进入思考链，recoverable 错误不阻断最终答案；
- 展示的是可解释执行过程，不展示模型私有推理链；
- 工具名、原始参数和敏感字段不会直接暴露给用户。

