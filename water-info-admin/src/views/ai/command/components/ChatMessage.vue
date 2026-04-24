<template>
  <div class="fm-msg" :class="message.role">
    <!-- Thinking placeholder -->
    <template v-if="message.role === 'thinking'">
      <div class="fm-msg__thinking">
        <span class="dot" /><span class="dot" /><span class="dot" />
        <span class="label">{{ message.content }}</span>
      </div>
    </template>

    <!-- Agent bubble -->
    <template v-else-if="message.role === 'agent'">
      <div class="fm-msg__agent" :style="{ '--agent-color': agentColor }">
        <div class="agent-head">
          <span class="agent-dot" />
          <span class="agent-label">{{ agentLabel }}</span>
          <span v-if="message.agentStatus === 'done'" class="agent-badge">已完成</span>
          <span v-else class="agent-typing">
            <span class="td" /><span class="td" /><span class="td" />
          </span>
        </div>
        <div class="markdown" v-html="renderedContent" />
        <span v-if="message.agentStatus !== 'done'" class="caret">|</span>
      </div>
      <div class="time">{{ formattedTime }}</div>
    </template>

    <!-- User / assistant bubble -->
    <template v-else-if="message.role === 'user' || message.role === 'assistant'">
      <div class="fm-msg__bubble">
        <div v-if="message.role === 'assistant'" class="markdown" v-html="renderedContent" />
        <div v-else class="user-text">{{ message.content }}</div>
        <span v-if="streaming && message.role === 'assistant'" class="caret">|</span>
      </div>
      <div class="time">{{ formattedTime }}</div>
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

const AGENT_META: Record<string, { label: string; color: string }> = {
  data_analyst:        { label: 'DATA',     color: '#49e1ff' },
  risk_assessor:       { label: 'RISK',     color: '#ffb547' },
  plan_generator:      { label: 'PLAN',     color: '#2bd99f' },
  knowledge_retriever: { label: 'KNOW',     color: '#7aa2ff' },
  resource_dispatcher: { label: 'DISPATCH', color: '#8b5cf6' },
  notification:        { label: 'NOTIFY',   color: '#ff5a6a' },
  execution_monitor:   { label: 'MONITOR',  color: '#a9b3c6' },
  final_response:      { label: 'SUMMARY',  color: '#49e1ff' },
}

const agentMeta = computed(
  () => AGENT_META[props.message.agent ?? ''] ?? { label: (props.message.agent ?? 'AI').toUpperCase(), color: '#49e1ff' },
)
const agentLabel = computed(() => agentMeta.value.label)
const agentColor = computed(() => agentMeta.value.color)
</script>

<style scoped lang="scss">
.fm-msg {
  display: flex;
  flex-direction: column;
  margin-bottom: 16px;

  &.user { align-items: flex-end; }
  &.assistant,
  &.agent { align-items: flex-start; }
}

/* ── User bubble (brand gradient) ── */
.fm-msg.user .fm-msg__bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 14px 14px 2px 14px;
  background: var(--fm-grad-brand);
  color: #fff;
  font-size: 13.5px;
  line-height: 1.6;
  box-shadow: 0 8px 20px -8px rgba(47, 123, 255, 0.5);
}

/* ── Assistant bubble ── */
.fm-msg.assistant .fm-msg__bubble {
  max-width: 88%;
  padding: 10px 14px;
  border-radius: 14px 14px 14px 2px;
  background: var(--fm-bg-2);
  border: 1px solid var(--fm-line);
  color: var(--fm-fg);
  font-size: 13.5px;
  line-height: 1.7;
}

.user-text {
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── Agent bubble (color-coded left border) ── */
.fm-msg__agent {
  max-width: 90%;
  padding: 10px 14px;
  border-radius: 0 10px 10px 0;
  border-left: 3px solid var(--agent-color);
  background: var(--fm-bg-2);
  border-top: 1px solid var(--fm-line);
  border-right: 1px solid var(--fm-line);
  border-bottom: 1px solid var(--fm-line);
  position: relative;
}

.agent-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.agent-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--agent-color);
  box-shadow: 0 0 6px var(--agent-color);
  flex-shrink: 0;
}

.agent-label {
  font-size: 10.5px;
  font-family: var(--fm-font-mono);
  font-weight: 600;
  color: var(--agent-color);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.agent-badge {
  font-size: 10px;
  font-family: var(--fm-font-mono);
  color: var(--fm-fg-mute);
  background: var(--fm-bg-3);
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: auto;
  letter-spacing: 0.04em;
}

.agent-typing {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
}

.td {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--fm-fg-soft);
  animation: typing-pulse 1.2s ease-in-out infinite;
}
.td:nth-child(2) { animation-delay: 0.2s; }
.td:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(1); }
  40% { opacity: 1; transform: scale(1.3); }
}

/* ── Markdown styling ── */
.markdown {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--fm-fg);
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

.markdown :deep(hr) {
  border: none;
  border-top: 1px solid var(--fm-line);
  margin: 10px 0;
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
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ── Caret ── */
.caret {
  display: inline-block;
  width: 2px;
  color: var(--fm-brand-2);
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ── Time ── */
.time {
  font-size: 10.5px;
  color: var(--fm-fg-dim);
  margin-top: 4px;
  font-family: var(--fm-font-mono);
  letter-spacing: 0.04em;
}

/* ── Thinking ── */
.fm-msg__thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--fm-bg-2);
  border: 1px dashed rgba(73, 225, 255, 0.3);
  border-radius: 8px;
  max-width: 240px;
}

.fm-msg__thinking .label {
  font-size: 12.5px;
  color: var(--fm-fg-mute);
  font-style: italic;
}

.fm-msg__thinking .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--fm-brand-2);
  animation: thinking-pulse 1.4s ease-in-out infinite;
  flex-shrink: 0;
  box-shadow: 0 0 6px var(--fm-brand-2);
}
.fm-msg__thinking .dot:nth-child(2) { animation-delay: 0.2s; }
.fm-msg__thinking .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes thinking-pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.9); }
  40% { opacity: 1; transform: scale(1.1); }
}
</style>
