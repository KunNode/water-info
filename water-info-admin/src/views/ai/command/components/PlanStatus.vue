<template>
  <div class="fm-card fm-plan">
    <div class="fm-card__head">
      <span class="title">预案状态</span>
      <span class="mono" v-if="planInfo">{{ planProgress }}%</span>
    </div>
    <div class="fm-card__body">
      <template v-if="planInfo">
        <div class="plan-summary">
          <span class="fm-tag plan-state" :class="statusTagKind">{{ statusLabel }}</span>
          <div class="plan-name">{{ planInfo.name }}</div>
        </div>

        <div class="fm-progress">
          <div class="bar" :class="progressBarKind" :style="{ width: planProgress + '%' }" />
        </div>

        <div class="plan-stats">
          <span class="steps">{{ planInfo.completed }} / {{ planInfo.total }} 步</span>
          <span class="fm-tag" :class="statusTagKind">{{ statusLabel }}</span>
        </div>
      </template>
      <div v-else class="empty-plan">
        <span class="empty-plan__line" />
        <strong>待生成</strong>
        <span>预案将在研判后写入这里</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface PlanInfo {
  name: string
  status: string
  total: number
  completed: number
  failed: number
}

const props = defineProps<{
  planInfo: PlanInfo | null
}>()

const planProgress = computed(() => {
  if (!props.planInfo || props.planInfo.total === 0) return 0
  if (props.planInfo.status === 'completed') return 100
  return Math.round((props.planInfo.completed / props.planInfo.total) * 100)
})

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    completed: '已完成',
    failed: '失败',
    running: '执行中',
  }
  return props.planInfo ? (map[props.planInfo.status] ?? props.planInfo.status) : ''
})

const statusTagKind = computed(() => {
  if (!props.planInfo) return ''
  if (props.planInfo.status === 'completed') return 'fm-tag--ok'
  if (props.planInfo.status === 'failed') return 'fm-tag--danger'
  return 'fm-tag--info'
})

const progressBarKind = computed(() => {
  if (!props.planInfo) return ''
  if (props.planInfo.status === 'failed') return 'danger'
  if (props.planInfo.status === 'completed') return ''
  return ''
})
</script>

<style scoped lang="scss">
.fm-plan .fm-card__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plan-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.plan-state {
  align-self: flex-start;
}

.plan-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--fm-fg);
  word-break: break-all;
  line-height: 1.5;
}

.plan-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--fm-fg-mute);
}

.steps {
  font-family: var(--fm-font-mono);
  letter-spacing: 0.04em;
}

.empty-plan {
  min-height: 88px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  padding: 14px;
  border: 1px dashed var(--fm-line-2);
  border-radius: 8px;
  color: var(--fm-fg-mute);
  font-size: 12px;
  background: rgba(255, 255, 255, 0.015);

  strong {
    color: var(--fm-fg);
    font-size: 16px;
    font-style: normal;
  }
}

.empty-plan__line {
  width: 42px;
  height: 2px;
  border-radius: 999px;
  background: var(--fm-brand-2);
  box-shadow: 0 0 10px var(--fm-brand-2);
}
</style>
