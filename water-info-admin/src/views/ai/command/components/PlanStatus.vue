<template>
  <div class="fm-card fm-plan">
    <div class="fm-card__head">
      <span class="title">预案状态</span>
      <span class="mono" v-if="planInfo">{{ planProgress }}%</span>
    </div>
    <div class="fm-card__body">
      <template v-if="planInfo">
        <div class="plan-name">{{ planInfo.name }}</div>

        <div class="fm-progress">
          <div class="bar" :class="progressBarKind" :style="{ width: planProgress + '%' }" />
        </div>

        <div class="plan-stats">
          <span class="steps">{{ planInfo.completed }} / {{ planInfo.total }} 步</span>
          <span class="fm-tag" :class="statusTagKind">{{ statusLabel }}</span>
        </div>
      </template>
      <div v-else class="empty-plan">等待 AI 生成预案…</div>
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
  gap: 10px;
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
  color: var(--fm-fg-mute);
  text-align: center;
  padding: 14px 0;
  font-size: 13px;
  font-style: italic;
}
</style>
