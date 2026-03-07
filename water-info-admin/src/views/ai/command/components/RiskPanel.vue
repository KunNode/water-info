<template>
  <div class="glass-panel sidebar-panel">
    <div class="panel-header">风险等级</div>
    <div class="risk-display">
      <div
        class="risk-circle"
        :style="{
          borderColor: riskColor,
          color: riskColor,
          boxShadow: riskLevel !== 'none' ? `0 0 20px ${riskColor}40` : 'none',
        }"
      >
        <div class="risk-label">{{ riskLabel }}</div>
        <div class="risk-sublabel">{{ riskSublabel }}</div>
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
  none:     { label: '正常',   sublabel: '无需响应',   color: '#6b7280' },
  low:      { label: '低风险', sublabel: 'IV级响应',   color: '#3b82f6' },
  moderate: { label: '中风险', sublabel: 'III级响应',  color: '#f59e0b' },
  high:     { label: '高风险', sublabel: 'II级响应',   color: '#ef4444' },
  critical: { label: '极高危', sublabel: 'I级响应',    color: '#7c3aed' },
}

const riskInfo = computed(() => riskMap[props.riskLevel] ?? riskMap['none'])
const riskColor = computed(() => riskInfo.value.color)
const riskLabel = computed(() => riskInfo.value.label)
const riskSublabel = computed(() => riskInfo.value.sublabel)
</script>

<style scoped>
.glass-panel {
  background: linear-gradient(135deg, rgba(0, 100, 150, 0.1) 0%, rgba(0, 50, 100, 0.05) 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.sidebar-panel {
  padding: 16px;
}

.panel-header {
  font-size: 14px;
  font-weight: 600;
  color: #00d4ff;
  margin-bottom: 14px;
  padding-left: 10px;
  position: relative;
}

.panel-header::before {
  content: '';
  position: absolute;
  left: 0;
  top: 2px;
  bottom: 2px;
  width: 3px;
  background: linear-gradient(180deg, #00d4ff, #0066cc);
  border-radius: 2px;
}

.risk-display {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

.risk-circle {
  width: 110px;
  height: 110px;
  border-radius: 50%;
  border: 3px solid;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.2);
  transition: all 0.4s ease;
}

.risk-label {
  font-size: 18px;
  font-weight: bold;
  line-height: 1.2;
}

.risk-sublabel {
  font-size: 11px;
  opacity: 0.7;
  margin-top: 4px;
}
</style>
