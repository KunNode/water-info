# AI 指挥台完善设计文档

**日期**: 2026-03-02  
**状态**: 已批准，待实现

---

## 背景

当前 `src/views/ai/command/index.vue` 是一个单文件实现，存在以下不足：

1. 每次发送指令后对话内容被清空，不支持多轮对话历史
2. AI 回复为纯文本，无法渲染 Markdown 格式
3. 侧边栏缺少活跃告警展示和快捷指令入口
4. 所有逻辑内联在单文件，可维护性差

---

## 目标

- 支持多轮对话历史（用户/AI 气泡分离显示）
- AI 回复渲染 Markdown（marked + DOMPurify）
- 新增活跃告警面板（30s 轮询）
- 新增快捷指令芯片
- 重构为子组件架构，提升可维护性

---

## 文件结构

```
src/views/ai/command/
├── index.vue                  ← 主页面：状态中心 + 组合
└── components/
    ├── ChatPanel.vue          ← 对话历史列表 + 输入区
    ├── ChatMessage.vue        ← 单条消息气泡（user / assistant）
    ├── AgentTimeline.vue      ← 6个智能体执行进度
    ├── RiskPanel.vue          ← 风险等级圆圈展示
    ├── PlanStatus.vue         ← 预案生成进度
    ├── ActiveAlerts.vue       ← 活跃告警列表（自管理轮询）
    ├── QuickCommands.vue      ← 快捷指令芯片按钮
    └── SessionInfo.vue        ← 会话信息（ID、时间、交互数）
```

---

## 数据流设计

### 状态中心（index.vue）

```typescript
// 对话历史
interface ChatMessageItem {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}
const messages = ref<ChatMessageItem[]>([])

// SSE（唯一实例）
const { fullText, loading, error, start, stop, onStructuredEvent } = useSSE()

// 侧边栏状态
const agentStatus = reactive<Record<string, AgentStatusType>>({ ... })
const riskLevel = ref<string>('none')
const planInfo = ref<PlanInfo | null>(null)
const sessionId = ref('')
const startTime = ref('')
const queryCount = ref(0)
```

### 发送流程

1. 用户点击发送或快捷指令 → `sendQuery(text)` 触发
2. push `{ role: 'user', content: text }` 到 `messages`
3. push `{ role: 'assistant', content: '' }` 到 `messages`（占位）
4. 调用 `start(getStreamUrl(), { query, sessionId })`
5. `watch(fullText)` → 实时更新 `messages` 最后一条的 `content`
6. SSE 结束 → loading 变 false，对话完成

### Props / Emits

| 组件 | Props | Emits |
|------|-------|-------|
| ChatPanel | `messages`, `loading` | `send(query: string)` |
| ChatMessage | `message: ChatMessageItem`, `streaming: boolean` | — |
| QuickCommands | `disabled: boolean` | `send(query: string)` |
| AgentTimeline | `agentStatus` | — |
| RiskPanel | `riskLevel` | — |
| PlanStatus | `planInfo` | — |
| ActiveAlerts | —（自管理） | — |
| SessionInfo | `sessionId`, `startTime`, `queryCount` | — |

---

## 组件细节

### ChatMessage.vue

- **user 消息**：右对齐，背景 `rgba(59,130,246,0.2)`，蓝色左边框，纯文本显示
- **assistant 消息**：左对齐，背景 `rgba(255,255,255,0.05)`，用 `v-html` 渲染 `marked(content)`
- 流式输出中（`streaming=true`）：末尾附加闪烁光标 `|`
- 底部显示时间戳（`HH:mm:ss`）

```html
<!-- assistant 消息渲染 -->
<div v-html="renderedContent" class="markdown-body"></div>
```

```typescript
const renderedContent = computed(() =>
  DOMPurify.sanitize(marked(props.message.content) as string)
)
```

### QuickCommands.vue

4 个预设指令芯片：

| 指令文本 |
|---------|
| 分析当前水情 |
| 生成防洪应急预案 |
| 评估当前风险等级 |
| 调度应急资源 |

点击 → `emit('send', text)`

### ActiveAlerts.vue

- `onMounted`：调用 `getAlarms({ page: 1, size: 5, status: 'OPEN' })`
- `setInterval(refresh, 30000)` + `onUnmounted` 清理
- 显示：告警级别色块 + 站点名 + 指标类型 + 触发时间
- 空状态：绿色文字"暂无活跃告警 ✓"

告警级别颜色：
- CRITICAL → `#ef4444`
- HIGH → `#f97316`  
- MEDIUM → `#f59e0b`
- LOW → `#3b82f6`

---

## 依赖变更

需新增安装：

```bash
npm install marked dompurify
npm install -D @types/dompurify
```

---

## 布局不变

整体布局保持 `1fr 300px` 双栏，`position: fixed; inset: 0; z-index: 9999` 不变。侧边栏面板顺序：

1. 快捷指令（嵌入 ChatPanel 输入框上方，不在侧边栏）
2. 智能体进度
3. 风险等级
4. 预案状态
5. 活跃告警（新增）
6. 会话信息

---

## 验收标准

- [ ] 多轮对话历史正确保留，不会清空
- [ ] user/assistant 气泡样式区分明确
- [ ] Markdown 标题、列表、加粗、代码块正确渲染
- [ ] 快捷指令点击后自动填入并发送
- [ ] 活跃告警 30s 自动刷新，空状态正确显示
- [ ] `npm run build` 零 TS 错误
- [ ] 所有子组件有正确的 TypeScript 类型
