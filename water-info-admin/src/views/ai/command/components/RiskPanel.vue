<template>
  <div class="fm-card fm-risk">
    <div class="fm-card__head">
      <button class="tab" :class="{ active: activeTab === 'risk' }" @click="activeTab = 'risk'">风险等级</button>
      <button class="tab" :class="{ active: activeTab === 'scan' }" @click="activeTab = 'scan'">AI 巡检</button>
      <span class="sp" />
      <span class="mono">{{ scanConnected ? 'live' : 'offline' }}</span>
    </div>
    <div v-if="activeTab === 'risk'" class="fm-card__body">
      <div class="risk-summary" :style="{ '--risk-color': riskColor }">
        <div>
          <div class="risk-summary__label">{{ riskLabel }}</div>
          <div class="risk-summary__sub">{{ riskSublabel }}</div>
        </div>
        <span class="risk-summary__pulse" />
      </div>
      <div class="risk-meter">
        <span
          v-for="level in riskOrder"
          :key="level"
          :class="{ on: levelActive(level) }"
          :style="{ '--level-color': riskMap[level].color }"
        />
      </div>
      <div class="risk-scale">
        <span>正常</span>
        <span>I 级</span>
      </div>
    </div>
    <div v-else class="fm-card__body">
      <div v-if="latestAssessment" class="scan-summary" :style="{ '--risk-color': assessmentColor }">
        <div class="scan-summary__head">
          <span class="level">{{ assessmentLabel }}</span>
          <span class="fm-tag" :class="latestAssessment.source === 'EVENT' ? 'fm-tag--danger' : 'fm-tag--info'">
            {{ latestAssessment.source }}
          </span>
        </div>
        <div class="summary">{{ latestAssessment.summary }}</div>
        <div v-if="latestAssessment.planExcerpt" class="plan">{{ latestAssessment.planExcerpt }}</div>
        <div class="time">{{ assessmentTime }}</div>
      </div>
      <div v-else class="scan-empty">
        <span class="fm-dot ok" />
        <span>等待 AI 巡检结果</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { getAiAssessments } from '@/api/aiAssessment'
import { useWebSocket } from '@/composables/useWebSocket'
import type { AiAssessment } from '@/types'

const props = defineProps<{
  riskLevel: string
}>()

const riskMap: Record<string, { label: string; sublabel: string; color: string }> = {
  none:     { label: '正常',   sublabel: '无需响应',  color: '#6a7590' },
  low:      { label: '低风险', sublabel: 'IV 级响应', color: '#7aa2ff' },
  moderate: { label: '中风险', sublabel: 'III 级响应', color: '#ffb547' },
  high:     { label: '高风险', sublabel: 'II 级响应',  color: '#ff5a6a' },
  critical: { label: '极高危', sublabel: 'I 级响应',   color: '#ff8a96' },
}
const riskOrder = ['none', 'low', 'moderate', 'high', 'critical']
const activeTab = ref<'risk' | 'scan'>('risk')
const latestAssessment = ref<AiAssessment | null>(null)
const { messages: scanMessages, connected: scanConnected, connect: connectScan } = useWebSocket('/ws/ai-assessments')

const riskInfo = computed(() => riskMap[props.riskLevel] ?? riskMap['none'])
const riskColor = computed(() => riskInfo.value.color)
const riskLabel = computed(() => riskInfo.value.label)
const riskSublabel = computed(() => riskInfo.value.sublabel)
const assessmentLevel = computed(() => (latestAssessment.value?.level || 'none').toLowerCase())
const assessmentColor = computed(() => riskMap[assessmentLevel.value]?.color ?? riskMap.none.color)
const assessmentLabel = computed(() => riskMap[assessmentLevel.value]?.label ?? latestAssessment.value?.level ?? '研判')
const assessmentTime = computed(() => {
  if (!latestAssessment.value?.assessedAt) return ''
  const d = new Date(latestAssessment.value.assessedAt)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${min}`
})

function levelActive(level: string) {
  const current = riskOrder.indexOf(props.riskLevel)
  const target = riskOrder.indexOf(level)
  return target <= Math.max(current, 0)
}

watch(scanMessages, (items) => {
  const last = items[items.length - 1]
  if (last?.type === 'AI_ASSESSMENT' && last.data) {
    latestAssessment.value = last.data as AiAssessment
  }
}, { deep: true })

onMounted(async () => {
  connectScan()
  try {
    const res = await getAiAssessments({ limit: 1 })
    latestAssessment.value = res.data?.[0] ?? null
  } catch {
    // non-critical panel
  }
})
</script>

<style scoped lang="scss">
.fm-risk .fm-card__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 15px 16px 16px;
}

.tab {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--fm-fg-mute);
  font-size: 12px;
  font-weight: 600;
  padding: 0;
  cursor: pointer;

  &.active {
    color: var(--fm-fg);
  }
}

.risk-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 74px;
  padding: 13px 14px;
  border-radius: 8px;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--risk-color) 16%, transparent), transparent 62%),
    var(--fm-bg-2);
  border: 1px solid color-mix(in srgb, var(--risk-color) 38%, var(--fm-line));
}

.risk-summary__label {
  color: var(--risk-color);
  font-size: 22px;
  font-weight: 700;
  line-height: 1.1;
}

.risk-summary__sub {
  margin-top: 5px;
  color: var(--fm-fg-soft);
  font-family: var(--fm-font-mono);
  font-size: 11px;
  letter-spacing: 0.04em;
}

.risk-summary__pulse {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--risk-color);
  box-shadow: 0 0 18px -4px var(--risk-color), inset 0 0 18px -10px var(--risk-color);
  position: relative;

  &::after {
    content: "";
    position: absolute;
    inset: 10px;
    border-radius: 50%;
    background: var(--risk-color);
  }
}

.risk-meter {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;

  span {
    height: 8px;
    border-radius: 999px;
    background: var(--fm-bg-3);
    border: 1px solid var(--fm-line);
  }

  span.on {
    background: var(--level-color);
    border-color: var(--level-color);
    box-shadow: 0 0 12px -5px var(--level-color);
  }
}

.risk-scale {
  display: flex;
  justify-content: space-between;
  color: var(--fm-fg-mute);
  font-family: var(--fm-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
}

.scan-summary {
  min-height: 142px;
  padding: 13px 14px;
  border-radius: 8px;
  background: var(--fm-bg-2);
  border: 1px solid color-mix(in srgb, var(--risk-color) 34%, var(--fm-line));
}

.scan-summary__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  .level {
    color: var(--risk-color);
    font-size: 16px;
    font-weight: 700;
  }
}

.summary,
.plan {
  color: var(--fm-fg);
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.plan {
  margin-top: 8px;
  color: var(--fm-fg-soft);
  -webkit-line-clamp: 2;
}

.time {
  margin-top: 10px;
  color: var(--fm-fg-mute);
  font-family: var(--fm-font-mono);
  font-size: 10px;
}

.scan-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 142px;
  color: var(--fm-fg-mute);
  font-size: 12px;
}
</style>
