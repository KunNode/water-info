<template>
  <div class="chat-message" :class="message.role">
    <!-- Thinking / analyzing placeholder -->
    <template v-if="message.role === 'thinking'">
      <div class="thinking-bubble">
        <span class="thinking-dot" /><span class="thinking-dot" /><span class="thinking-dot" />
        <span class="thinking-label">{{ message.content }}</span>
      </div>
    </template>

    <!-- Agent 分体气泡 -->
    <template v-else-if="message.role === 'agent'">
      <div class="agent-bubble" :style="{ '--agent-color': agentColor }">
        <div class="agent-bubble-header">
          <span class="agent-dot" />
          <span class="agent-label">{{ agentLabel }}</span>
          <span v-if="message.agentStatus === 'done'" class="agent-done-badge">已完成</span>
          <span v-else class="agent-typing-badge">
            <span class="typing-dot" /><span class="typing-dot" /><span class="typing-dot" />
          </span>
        </div>
        <div class="markdown-body agent-content" v-html="renderedContent" />
        <span v-if="message.agentStatus !== 'done'" class="cursor-blink">|</span>
      </div>
      <div class="timestamp">{{ formattedTime }}</div>
    </template>

    <!-- User / assistant 气泡（原有逻辑） -->
    <template v-else-if="message.role === 'user' || message.role === 'assistant'">
      <div class="bubble">
        <div
          v-if="message.role === 'assistant'"
          class="markdown-body"
          v-html="renderedContent"
        />
        <div v-else class="user-text">{{ message.content }}</div>
        <span v-if="streaming && message.role === 'assistant'" class="cursor-blink">|</span>
      </div>
      <div class="timestamp">{{ formattedTime }}</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ChatMessageItem } from '@/stores/aiConversation'

const props = defineProps<{
  message: ChatMessageItem
  streaming?: boolean
}>()

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  // marked v5+ synchronous API; cast needed because overloads include Promise variant
  const raw = marked.parse(props.message.content, { async: false }) as string
  return DOMPurify.sanitize(raw, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'code', 'pre', 'blockquote',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'hr', 'a', 'span', 'div',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
  })
})

const formattedTime = computed(() => {
  const d = props.message.timestamp
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
})

// 智能体颜色与显示名映射
const AGENT_META: Record<string, { label: string; color: string }> = {
  data_analyst:        { label: '数据分析',  color: '#00d4ff' },
  risk_assessor:       { label: '风险评估',  color: '#f59e0b' },
  plan_generator:      { label: '预案生成',  color: '#10b981' },
  resource_dispatcher: { label: '资源调度',  color: '#8b5cf6' },
  notification:        { label: '通知预警',  color: '#ef4444' },
  execution_monitor:   { label: '执行监控',  color: '#6b7280' },
  final_response:      { label: '综合报告',  color: '#00d4ff' },
}

const agentMeta = computed(() => AGENT_META[props.message.agent ?? ''] ?? { label: props.message.agent ?? 'AI', color: '#00d4ff' })
const agentLabel = computed(() => agentMeta.value.label)
const agentColor = computed(() => agentMeta.value.color)
</script>

<style scoped>
.chat-message {
  display: flex;
  flex-direction: column;
  margin-bottom: 16px;
}

.chat-message.user {
  align-items: flex-end;
}

.chat-message.assistant,
.chat-message.agent {
  align-items: flex-start;
}

/* ── Agent 分体气泡 ── */
.agent-bubble {
  max-width: 90%;
  border-left: 3px solid var(--agent-color, #00d4ff);
  background: rgba(255, 255, 255, 0.04);
  border-radius: 0 10px 10px 0;
  padding: 10px 14px 10px 14px;
  position: relative;
}

.agent-bubble-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.agent-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--agent-color, #00d4ff);
  flex-shrink: 0;
}

.agent-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--agent-color, #00d4ff);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.agent-done-badge {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: auto;
}

.agent-typing-badge {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
}

.typing-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  animation: typing-pulse 1.2s ease-in-out infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(1); }
  40% { opacity: 1; transform: scale(1.2); }
}

.agent-content {
  font-size: 13.5px;
  line-height: 1.75;
  color: rgba(255, 255, 255, 0.85);
}

/* ── User / assistant 气泡（原有样式） ── */
.bubble {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  position: relative;
}

.chat-message.user .bubble {
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.4);
  border-bottom-right-radius: 4px;
  color: rgba(255, 255, 255, 0.95);
}

.chat-message.assistant .bubble {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-bottom-left-radius: 4px;
  color: rgba(255, 255, 255, 0.9);
}

.user-text {
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── Markdown 样式（共用） ── */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  color: #00d4ff;
  margin: 12px 0 6px;
  font-weight: 600;
  line-height: 1.4;
}
.markdown-body :deep(h1) { font-size: 18px; }
.markdown-body :deep(h2) { font-size: 16px; }
.markdown-body :deep(h3) { font-size: 15px; }
.markdown-body :deep(h4) { font-size: 14px; }

.markdown-body :deep(p) {
  margin: 6px 0;
  word-break: break-word;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 6px 0;
}

.markdown-body :deep(li) {
  margin: 3px 0;
}

.markdown-body :deep(strong) {
  color: #fff;
  font-weight: 600;
}

.markdown-body :deep(em) {
  color: rgba(0, 212, 255, 0.8);
}

.markdown-body :deep(code) {
  background: rgba(0, 0, 0, 0.4);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #00d4ff;
}

.markdown-body :deep(pre) {
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: rgba(255, 255, 255, 0.85);
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid rgba(0, 212, 255, 0.4);
  padding-left: 12px;
  margin: 6px 0;
  color: rgba(255, 255, 255, 0.6);
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  margin: 10px 0;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: 6px 10px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: rgba(0, 212, 255, 0.1);
  color: #00d4ff;
}

.cursor-blink {
  display: inline-block;
  width: 2px;
  color: #00d4ff;
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.timestamp {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.3);
  margin-top: 4px;
  font-family: 'Courier New', monospace;
}

/* ── Thinking / analyzing placeholder ── */
.thinking-bubble {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed rgba(0, 212, 255, 0.25);
  border-radius: 8px;
  max-width: 220px;
}

.thinking-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
  font-style: italic;
}

.thinking-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(0, 212, 255, 0.5);
  animation: thinking-pulse 1.4s ease-in-out infinite;
  flex-shrink: 0;
}
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes thinking-pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.9); }
  40% { opacity: 1; transform: scale(1.1); }
}
</style>
