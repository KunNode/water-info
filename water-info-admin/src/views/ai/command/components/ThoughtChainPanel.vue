<template>
  <div v-if="reasoning" class="fm-thought" :class="[`is-${reasoning.status}`, { 'is-collapsed': !localExpanded }]">
    <button type="button" class="fm-thought__head" @click="toggle">
      <slot name="title" :reasoning="reasoning" :expanded="localExpanded">
        <span class="fm-thought__status">
          <slot name="loading" :reasoning="reasoning">
            <span v-if="isRunning" class="fm-thought__spinner" />
          </slot>
          <span>{{ title }}</span>
        </span>
      </slot>
      <el-icon class="fm-thought__arrow" :class="{ 'is-expanded': localExpanded }">
        <ArrowDown />
      </el-icon>
    </button>

    <Transition name="fm-thought-slide">
      <div v-show="localExpanded" class="fm-thought__body">
        <div v-if="reasoning.steps.length === 0" class="fm-thought__empty">
          正在理解问题并组织可解释执行过程...
        </div>

        <div
          v-for="step in reasoning.steps"
          :key="step.id"
          class="fm-thought__step"
          :class="[`is-${step.status}`, `is-${step.kind}`]"
        >
          <div class="fm-thought__node">
            <slot name="step-icon" :step="step">
              <el-icon v-if="step.status === 'success'"><Check /></el-icon>
              <el-icon v-else-if="step.status === 'error'"><Warning /></el-icon>
              <span v-else class="fm-thought__dot" />
            </slot>
          </div>
          <div class="fm-thought__step-body">
            <div class="fm-thought__step-title">
              {{ step.title }}
              <span v-if="step.durationMs != null" class="fm-thought__duration">
                {{ formatSeconds(step.durationMs) }}s
              </span>
            </div>
            <slot name="step-content" :step="step">
              <div v-if="step.content" class="fm-thought__content" v-html="renderMarkdown(step.content)" />
              <div v-if="step.tool?.resultSummary" class="fm-thought__summary">
                {{ step.tool.resultSummary }}
              </div>
              <div v-if="step.status === 'running' && !step.content" class="fm-thought__muted">
                正在等待结果...
              </div>
            </slot>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ArrowDown, Check, Warning } from '@element-plus/icons-vue'
import type { ReasoningState } from '@/types/agentStream'

const props = defineProps<{
  reasoning?: ReasoningState
  autoCollapseDone?: boolean
}>()

const localExpanded = ref(props.reasoning?.expanded ?? true)
const collapsedAfterDone = ref(false)

const isRunning = computed(() =>
  props.reasoning?.status === 'thinking' ||
  props.reasoning?.status === 'tool_running' ||
  props.reasoning?.status === 'answering',
)

const title = computed(() => {
  const reasoning = props.reasoning
  if (!reasoning) return ''
  if (reasoning.status === 'done') return reasoning.title
  if (reasoning.status === 'tool_running') return '正在调用工具...'
  if (reasoning.status === 'answering') return '正在生成最终回答...'
  if (reasoning.status === 'error') return '分析过程遇到问题'
  return '思考中...'
})

watch(
  () => props.reasoning?.expanded,
  (expanded) => {
    if (expanded != null) localExpanded.value = expanded
  },
)

watch(
  () => props.reasoning?.status,
  (status) => {
    if (status === 'done' && props.autoCollapseDone && !collapsedAfterDone.value) {
      localExpanded.value = false
      collapsedAfterDone.value = true
    }
  },
)

function toggle() {
  localExpanded.value = !localExpanded.value
  if (props.reasoning) props.reasoning.expanded = localExpanded.value
}

function renderMarkdown(content: string) {
  const raw = marked.parse(content, { async: false }) as string
  return DOMPurify.sanitize(raw, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'ul', 'ol', 'li', 'span'],
    ALLOWED_ATTR: ['class'],
  })
}

function formatSeconds(ms: number) {
  return Math.max(1, Math.ceil(ms / 1000))
}
</script>

<style scoped lang="scss">
.fm-thought {
  width: min(900px, 92%);
  margin: 2px 0 8px;
  color: var(--fm-fg-soft);
}

.fm-thought__head {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  padding: 4px 2px;
  border: 0;
  background: transparent;
  color: var(--fm-fg-soft);
  font-size: 13px;
  cursor: pointer;
  line-height: 1.6;

  &:hover {
    color: var(--fm-brand-2);
  }
}

.fm-thought__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.fm-thought__spinner {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(106, 117, 144, 0.35);
  border-top-color: var(--fm-brand-2);
  animation: fm-thought-spin 0.9s linear infinite;
  flex-shrink: 0;
}

.fm-thought__arrow {
  font-size: 13px;
  color: var(--fm-fg-dim);
  transition: transform 0.2s;
  flex-shrink: 0;

  &.is-expanded {
    transform: rotate(180deg);
  }
}

.fm-thought__body {
  margin-top: 8px;
  margin-left: 9px;
  padding: 0 0 2px 18px;
  border-left: 1px solid rgba(106, 117, 144, 0.36);
}

.fm-thought__empty {
  padding: 0 0 14px;
  color: var(--fm-fg-mute);
  font-size: 12.5px;
  line-height: 1.7;
}

.fm-thought__step {
  display: grid;
  grid-template-columns: 0 1fr;
  column-gap: 16px;
  position: relative;
  padding: 0 0 15px;
}

.fm-thought__node {
  position: relative;
  left: -23px;
  top: 4px;
  width: 9px;
  height: 9px;
  display: grid;
  place-items: center;
  color: var(--fm-brand-2);
  z-index: 1;

  .el-icon {
    width: 15px;
    height: 15px;
    padding: 2px;
    border-radius: 50%;
    background: var(--fm-bg-2);
    font-size: 11px;
  }
}

.fm-thought__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--fm-fg-dim);
  box-shadow: 0 0 0 3px var(--fm-bg-2);
}

.fm-thought__step.is-running .fm-thought__dot {
  background: var(--fm-brand-2);
  animation: fm-thought-pulse 1.2s ease-in-out infinite;
}

.fm-thought__step.is-tool .fm-thought__dot {
  background: #2bd99f;
}

.fm-thought__step.is-error .fm-thought__node {
  color: var(--fm-danger);
}

.fm-thought__step-body {
  min-width: 0;
}

.fm-thought__step-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--fm-fg-soft);
  font-size: 13px;
  line-height: 1.7;
}

.fm-thought__duration {
  color: var(--fm-fg-dim);
  font-family: var(--fm-font-mono);
  font-size: 10.5px;
}

.fm-thought__content,
.fm-thought__summary,
.fm-thought__muted {
  margin-top: 4px;
  color: var(--fm-fg-mute);
  font-size: 12.5px;
  line-height: 1.75;
  word-break: break-word;
}

.fm-thought__content :deep(p) {
  margin: 0 0 4px;
}

.fm-thought__summary {
  padding-left: 10px;
  border-left: 2px solid rgba(106, 117, 144, 0.32);
}

.fm-thought-slide-enter-active,
.fm-thought-slide-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.fm-thought-slide-enter-from,
.fm-thought-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.fm-thought-slide-enter-to,
.fm-thought-slide-leave-from {
  opacity: 1;
  max-height: 900px;
}

@keyframes fm-thought-spin {
  to { transform: rotate(360deg); }
}

@keyframes fm-thought-pulse {
  0%, 100% { opacity: 0.55; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.2); }
}
</style>

