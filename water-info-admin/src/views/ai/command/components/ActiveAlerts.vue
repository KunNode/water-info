<template>
  <div class="glass-panel sidebar-panel">
    <div class="panel-header">
      活跃告警
      <span class="badge" v-if="alarms.length > 0">{{ alarms.length }}</span>
    </div>
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中…</span>
    </div>
    <div v-else-if="alarms.length === 0" class="empty-state">
      <span class="ok-dot">●</span> 暂无活跃告警
    </div>
    <div v-else class="alarm-list">
      <div v-for="alarm in alarms" :key="alarm.id" class="alarm-item">
        <div class="alarm-level-dot" :style="{ background: levelColor(alarm.level) }"></div>
        <div class="alarm-body">
          <div class="alarm-station">{{ alarm.stationName }}</div>
          <div class="alarm-meta">{{ alarm.metricType }} · {{ formatTime(alarm.startAt) }}</div>
        </div>
        <div class="alarm-level-tag" :style="{ color: levelColor(alarm.level) }">
          {{ alarm.level }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { getAlarms } from '@/api/alarm'
import type { Alarm } from '@/types'

const alarms = ref<Alarm[]>([])
const loading = ref(false)

const levelColorMap: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#f59e0b',
  LOW: '#3b82f6',
}

function levelColor(level: string): string {
  return levelColorMap[level] ?? '#6b7280'
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

async function refresh() {
  try {
    loading.value = true
    const res = await getAlarms({ page: 1, size: 5, status: 'OPEN' })
    alarms.value = res.data?.records ?? []
  } catch {
    // silently fail — non-critical
  } finally {
    loading.value = false
  }
}

let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
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
  display: flex;
  align-items: center;
  gap: 8px;
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

.badge {
  background: #ef4444;
  color: #fff;
  font-size: 11px;
  font-weight: bold;
  border-radius: 10px;
  padding: 1px 6px;
  line-height: 1.4;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
  padding: 8px 0;
}

.is-loading {
  animation: rotate 1.5s linear infinite;
}

@keyframes rotate {
  100% { transform: rotate(360deg); }
}

.empty-state {
  font-size: 13px;
  color: #10b981;
  padding: 8px 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.ok-dot {
  font-size: 10px;
}

.alarm-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alarm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.alarm-level-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.alarm-body {
  flex: 1;
  min-width: 0;
}

.alarm-station {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alarm-meta {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 2px;
}

.alarm-level-tag {
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
</style>
