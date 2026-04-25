<template>
  <div class="fm-card fm-risk">
    <div class="fm-card__head">
      <span class="title">风险等级</span>
      <span class="mono">live</span>
    </div>
    <div class="fm-card__body">
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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

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

const riskInfo = computed(() => riskMap[props.riskLevel] ?? riskMap['none'])
const riskColor = computed(() => riskInfo.value.color)
const riskLabel = computed(() => riskInfo.value.label)
const riskSublabel = computed(() => riskInfo.value.sublabel)

function levelActive(level: string) {
  const current = riskOrder.indexOf(props.riskLevel)
  const target = riskOrder.indexOf(level)
  return target <= Math.max(current, 0)
}
</script>

<style scoped lang="scss">
.fm-risk .fm-card__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 15px 16px 16px;
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
</style>
