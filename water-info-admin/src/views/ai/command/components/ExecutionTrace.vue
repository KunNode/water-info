<template>
  <div v-if="message.traces?.length" class="fm-trace">
    <button class="fm-trace__toggle" @click="expanded = !expanded">
      <el-icon class="fm-trace__mark"><Operation /></el-icon>
      <span>已执行</span>
      <span class="fm-trace__time">（{{ durationLabel }}）</span>
      <el-icon class="fm-trace__arrow" :class="{ 'is-expanded': expanded }">
        <ArrowDown />
      </el-icon>
    </button>
    <Transition name="fm-trace-slide">
      <div v-show="expanded" class="fm-trace__timeline">
        <div
          v-for="(trace, idx) in message.traces"
          :key="idx"
          class="fm-trace__step"
          :class="[`fm-trace__step--${trace.status}`, `fm-trace__phase--${trace.phase}`]"
        >
          <div class="fm-trace__body">
            <div class="fm-trace__title">{{ trace.title }}</div>
            <div v-if="trace.detail" class="fm-trace__detail">{{ trace.detail }}</div>
            <div v-if="trace.tool_name" class="fm-trace__tool">
              <span>调用工具</span>
              <code>{{ trace.tool_name }}</code>
              <span v-if="trace.metadata?.duration_ms != null" class="fm-trace__duration">
                {{ trace.metadata.duration_ms }}ms
              </span>
            </div>
            <div v-if="traceSummary(trace)" class="fm-trace__summary">
              {{ traceSummary(trace) }}
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowDown, Operation } from '@element-plus/icons-vue'
import type { ChatMessageItem, ExecutionTrace } from '@/stores/aiConversation'

const props = defineProps<{
  message: ChatMessageItem
}>()

const expanded = ref(true)

const durationLabel = computed(() => {
  const traces = props.message.traces ?? []
  const totalMs = traces.reduce((sum, trace) => {
    const duration = trace.metadata?.duration_ms
    return sum + (typeof duration === 'number' ? duration : 0)
  }, 0)

  if (totalMs > 0) return `用时 ${formatSeconds(totalMs)} 秒`
  return `${traces.length} 步`
})

function formatSeconds(ms: number) {
  return Math.max(1, Math.round(ms / 1000))
}

function traceSummary(trace: ExecutionTrace) {
  const input = trace.metadata?.input_summary
  const output = trace.metadata?.output_summary
  const parts = []
  if (typeof input === 'string' && input.trim()) parts.push(`输入：${input.trim()}`)
  if (typeof output === 'string' && output.trim()) parts.push(`输出：${output.trim()}`)
  return parts.join('；')
}
</script>

<style scoped lang="scss">
.fm-trace {
  margin: 10px 0 4px;
  max-width: min(900px, 92%);
}

.fm-trace__toggle {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 4px 2px;
  border: 0;
  background: transparent;
  color: var(--fm-fg-soft);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    color: var(--fm-brand-2);
  }
}

.fm-trace__mark {
  color: #6288ff;
  font-size: 16px;
}

.fm-trace__arrow {
  transition: transform 0.2s;
  font-size: 13px;

  &.is-expanded {
    transform: rotate(180deg);
  }
}

.fm-trace__time {
  color: var(--fm-fg-dim);
  font-variant-numeric: tabular-nums;
}

/* ── Timeline ── */
.fm-trace__timeline {
  margin-top: 8px;
  margin-left: 11px;
  padding: 0 0 2px 20px;
  border-left: 1px solid var(--fm-line-2);
}

.fm-trace__step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 0 0 16px 0;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: -25px;
    top: 6px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--fm-fg-dim);
  }
}

.fm-trace__phase--data_query::before { background: #49e1ff; }
.fm-trace__phase--tool_call::before { background: #2bd99f; }
.fm-trace__phase--risk_assessment::before { background: #ffb547; }
.fm-trace__phase--final_response::before { background: #7aa2ff; }
.fm-trace__step--failed::before { background: #ff5a6a !important; }

.fm-trace__body {
  min-width: 0;
  flex: 1;
}

.fm-trace__title {
  font-size: 13px;
  color: var(--fm-fg-soft);
  line-height: 1.7;
}

.fm-trace__detail {
  font-size: 12.5px;
  color: var(--fm-fg-mute);
  margin-top: 5px;
  line-height: 1.7;
}

.fm-trace__tool {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 6px;
  color: var(--fm-fg-mute);
  font-size: 12px;

  code {
    font-size: 11px;
    background: var(--fm-bg-3);
    padding: 1px 6px;
    border-radius: 4px;
    color: var(--fm-brand-2);
    font-family: var(--fm-font-mono);
  }
}

.fm-trace__summary {
  margin-top: 6px;
  color: var(--fm-fg-mute);
  font-size: 12.5px;
  line-height: 1.7;
}

.fm-trace__duration {
  font-size: 10.5px;
  color: var(--fm-fg-dim);
  font-family: var(--fm-font-mono);
}

/* ── Transition ── */
.fm-trace-slide-enter-active,
.fm-trace-slide-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.fm-trace-slide-enter-from,
.fm-trace-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.fm-trace-slide-enter-to,
.fm-trace-slide-leave-from {
  opacity: 1;
  max-height: 1000px;
}
</style>
