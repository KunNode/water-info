<template>
  <div class="glass-panel sidebar-panel">
    <div class="panel-header">预案状态</div>
    <div v-if="planInfo" class="plan-info">
      <div class="plan-name">{{ planInfo.name }}</div>
      <el-progress
        :percentage="planProgress"
        :status="planInfo.status === 'completed' ? 'success' : undefined"
        :color="planInfo.status === 'failed' ? '#ef4444' : '#3b82f6'"
        :stroke-width="6"
      />
      <div class="plan-stats">
        <span>{{ planInfo.completed }} / {{ planInfo.total }} 步</span>
        <el-tag
          size="small"
          :type="planInfo.status === 'completed' ? 'success' : planInfo.status === 'failed' ? 'danger' : 'info'"
        >
          {{ statusLabel }}
        </el-tag>
      </div>
    </div>
    <div v-else class="empty-plan">等待 AI 生成预案…</div>
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

.plan-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.plan-name {
  font-size: 13px;
  font-weight: 500;
  color: #fff;
  word-break: break-all;
  line-height: 1.4;
}

.plan-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.empty-plan {
  color: rgba(255, 255, 255, 0.3);
  text-align: center;
  padding: 16px 0;
  font-size: 13px;
}

/* Override el-progress colors for dark bg */
:deep(.el-progress-bar__outer) {
  background: rgba(255, 255, 255, 0.1);
}
</style>
