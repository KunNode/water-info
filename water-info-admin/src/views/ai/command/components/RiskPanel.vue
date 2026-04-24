<template>
  <div class="fm-card fm-risk">
    <div class="fm-card__head">
      <span class="title">风险等级</span>
      <span class="mono">live</span>
    </div>
    <div class="fm-card__body">
      <div
        class="risk-ring"
        :style="{
          '--ring': riskColor,
          '--ring-glow': riskLevel !== 'none' ? `${riskColor}66` : 'transparent',
        }"
      >
        <div class="risk-ring__inner">
          <div class="label">{{ riskLabel }}</div>
          <div class="sub">{{ riskSublabel }}</div>
        </div>
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

const riskInfo = computed(() => riskMap[props.riskLevel] ?? riskMap['none'])
const riskColor = computed(() => riskInfo.value.color)
const riskLabel = computed(() => riskInfo.value.label)
const riskSublabel = computed(() => riskInfo.value.sublabel)
</script>

<style scoped lang="scss">
.fm-risk .fm-card__body {
  display: flex;
  justify-content: center;
  padding: 20px 16px 22px;
}

.risk-ring {
  width: 118px;
  height: 118px;
  border-radius: 50%;
  border: 3px solid var(--ring);
  background: var(--fm-bg-1);
  display: grid;
  place-items: center;
  transition: all 0.4s ease;
  box-shadow: 0 0 24px -6px var(--ring-glow), inset 0 0 24px -10px var(--ring-glow);
  position: relative;
}

.risk-ring::before {
  content: "";
  position: absolute;
  inset: 6px;
  border-radius: 50%;
  border: 1px dashed var(--ring);
  opacity: 0.4;
}

.risk-ring__inner {
  text-align: center;
  color: var(--ring);

  .label {
    font-size: 18px;
    font-weight: 600;
    line-height: 1.2;
  }
  .sub {
    font-size: 11px;
    font-family: var(--fm-font-mono);
    opacity: 0.8;
    margin-top: 4px;
    letter-spacing: 0.04em;
  }
}
</style>
