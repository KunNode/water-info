<template>
  <div class="fm-msg" :class="message.role">
    <template v-if="message.role === 'user'">
      <div class="fm-msg__bubble">
        <div class="user-text">{{ message.content }}</div>
      </div>
      <div class="time">{{ formattedTime }}</div>
    </template>

    <template v-else-if="message.role === 'assistant'">
      <ThoughtChainPanel
        v-if="message.reasoning"
        :reasoning="message.reasoning"
        :auto-collapse-done="autoCollapseThought"
      />
      <ExecutionTrace v-else :message="message" />

      <div v-if="message.content || streaming || message.error" class="fm-msg__bubble">
        <div v-if="message.content" class="markdown" v-html="renderedContent" />
        <div v-else-if="message.error" class="fm-msg__error">{{ message.error }}</div>
        <div v-else class="fm-msg__answering">正在整理最终回答...</div>
        <span v-if="streaming" class="caret">|</span>
      </div>
      <div class="time">{{ formattedTime }}</div>
    </template>

    <template v-else-if="message.role === 'agent'">
      <div class="fm-msg__bubble fm-msg__bubble--agent">
        <div class="agent-head">
          <span class="agent-dot" />
          <span class="agent-label">{{ agentLabel }}</span>
          <span v-if="message.agentStatus === 'done'" class="agent-badge">已完成</span>
          <span v-else class="agent-typing">
            <span class="td" /><span class="td" /><span class="td" />
          </span>
        </div>
        <div class="markdown" v-html="renderedContent" />
      </div>
      <div class="time">{{ formattedTime }}</div>
    </template>

    <template v-else>
      <div class="fm-msg__thinking">
        <span class="dot" /><span class="dot" /><span class="dot" />
        <span class="label">{{ message.content }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ChatMessageItem } from '@/stores/aiConversation'
import ExecutionTrace from './ExecutionTrace.vue'
import ThoughtChainPanel from './ThoughtChainPanel.vue'

const props = defineProps<{
  message: ChatMessageItem
  streaming?: boolean
  autoCollapseThought?: boolean
}>()

const renderedContent = computed(() => {
  if (!props.message.content) return ''
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

const AGENT_LABELS: Record<string, string> = {
  data_analyst: '数据研判',
  risk_assessor: '风险评估',
  plan_generator: '预案生成',
  knowledge_retriever: '知识检索',
  resource_dispatcher: '资源调度',
  notification: '通知编排',
  execution_monitor: '执行监测',
  final_response: '综合结论',
}

const agentLabel = computed(() => AGENT_LABELS[props.message.agent ?? ''] ?? '智能体')
</script>

<style scoped lang="scss">
.fm-msg {
  display: flex;
  flex-direction: column;
  margin-bottom: 18px;

  &.user { align-items: flex-end; }
  &.assistant,
  &.agent,
  &.thinking { align-items: flex-start; }
}

.fm-msg.user .fm-msg__bubble {
  max-width: 76%;
  padding: 11px 14px;
  border-radius: 12px 12px 3px 12px;
  background: linear-gradient(135deg, #2563d6 0%, #2f7bff 58%, #49e1ff 100%);
  color: #fff;
  font-size: 13.5px;
  line-height: 1.6;
  box-shadow: 0 14px 26px -16px rgba(47, 123, 255, 0.75);
}

.fm-msg.assistant .fm-msg__bubble,
.fm-msg.agent .fm-msg__bubble {
  max-width: 82%;
  padding: 12px 15px;
  border-radius: 12px 12px 12px 3px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.025), transparent),
    var(--fm-bg-2);
  border: 1px solid var(--fm-line);
  color: var(--fm-fg);
  font-size: 13.5px;
  line-height: 1.7;
}

.user-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.markdown {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--fm-fg);
  min-width: 0;
}

.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4) {
  color: var(--fm-brand-2);
  margin: 12px 0 6px;
  font-weight: 600;
  line-height: 1.4;
}

.markdown :deep(h1) { font-size: 17px; }
.markdown :deep(h2) { font-size: 15.5px; }
.markdown :deep(h3) { font-size: 14.5px; }
.markdown :deep(h4) { font-size: 13.5px; }

.markdown :deep(p) {
  margin: 6px 0;
  word-break: break-word;
}

.markdown :deep(ul),
.markdown :deep(ol) {
  padding-left: 20px;
  margin: 6px 0;
}

.markdown :deep(li) { margin: 3px 0; }
.markdown :deep(strong) { color: var(--fm-fg); font-weight: 600; }
.markdown :deep(em) { color: var(--fm-brand-2); }

.markdown :deep(code) {
  background: var(--fm-bg-3);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--fm-font-mono);
  font-size: 12.5px;
  color: var(--fm-brand-2);
}

.markdown :deep(pre) {
  background: var(--fm-bg-1);
  border: 1px solid var(--fm-line);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown :deep(pre code) {
  background: transparent;
  padding: 0;
  color: var(--fm-fg-soft);
}

.markdown :deep(blockquote) {
  border-left: 3px solid var(--fm-brand);
  padding-left: 12px;
  margin: 6px 0;
  color: var(--fm-fg-mute);
}

.markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12.5px;
}

.markdown :deep(th),
.markdown :deep(td) {
  border: 1px solid var(--fm-line);
  padding: 6px 10px;
  text-align: left;
}

.markdown :deep(th) {
  background: var(--fm-bg-3);
  color: var(--fm-brand-2);
  font-family: var(--fm-font-mono);
  font-size: 11px;
}

.fm-msg__answering,
.fm-msg__error {
  color: var(--fm-fg-mute);
  font-size: 13px;
}

.fm-msg__error {
  color: var(--fm-danger);
}

.caret {
  display: inline-block;
  width: 2px;
  color: var(--fm-brand-2);
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}

.time {
  font-size: 10.5px;
  color: var(--fm-fg-dim);
  margin-top: 5px;
  font-family: var(--fm-font-mono);
  letter-spacing: 0.04em;
}

.agent-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.agent-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--fm-brand-2);
  box-shadow: 0 0 12px var(--fm-brand-2);
  flex-shrink: 0;
}

.agent-label {
  font-size: 11px;
  color: var(--fm-brand-2);
}

.agent-badge {
  margin-left: auto;
  color: var(--fm-fg-mute);
  font-size: 10.5px;
}

.agent-typing {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
}

.td,
.fm-msg__thinking .dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--fm-brand-2);
  animation: typing-pulse 1.2s ease-in-out infinite;
}

.td:nth-child(2),
.fm-msg__thinking .dot:nth-child(2) { animation-delay: 0.2s; }
.td:nth-child(3),
.fm-msg__thinking .dot:nth-child(3) { animation-delay: 0.4s; }

.fm-msg__thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  background: var(--fm-bg-2);
  border: 1px dashed rgba(73, 225, 255, 0.3);
  border-radius: 10px;
  max-width: 240px;
}

.fm-msg__thinking .label {
  font-size: 12.5px;
  color: var(--fm-fg-mute);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes typing-pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(1); }
  40% { opacity: 1; transform: scale(1.25); }
}

@media (max-width: 760px) {
  .fm-msg.user .fm-msg__bubble,
  .fm-msg.assistant .fm-msg__bubble,
  .fm-msg.agent .fm-msg__bubble {
    max-width: 94%;
  }
}
</style>

