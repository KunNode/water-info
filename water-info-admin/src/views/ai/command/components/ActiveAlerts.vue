<template>
  <div class="fm-card fm-alerts">
    <div class="fm-card__head">
      <span class="title">活跃告警</span>
      <span class="sp" />
      <span v-if="alarms.length > 0" class="fm-tag fm-tag--danger">{{ alarms.length }}</span>
      <span v-else class="fm-tag fm-tag--ok">0</span>
    </div>
    <div class="fm-card__body">
      <div v-if="loading" class="state">
        <el-icon class="spin"><Loading /></el-icon>
        <span>加载中…</span>
      </div>
      <div v-else-if="alarms.length === 0" class="state state--ok">
        <span class="fm-dot ok" /> 暂无活跃告警
      </div>
      <div v-else class="alarm-list">
        <div v-for="alarm in alarms" :key="alarm.id" class="alarm-item">
          <span class="fm-dot" :class="levelDot(alarm.level)" />
          <div class="body">
            <div class="station">{{ alarm.stationName }}</div>
            <div class="meta">{{ alarm.metricType }} · {{ formatTime(alarm.startAt) }}</div>
          </div>
          <span class="level" :class="levelTag(alarm.level)">{{ alarm.level }}</span>
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

function levelDot(level: string): string {
  if (level === 'CRITICAL' || level === 'HIGH') return 'danger'
  if (level === 'MEDIUM') return 'warn'
  return 'ok'
}

function levelTag(level: string): string {
  if (level === 'CRITICAL' || level === 'HIGH') return 'fm-tag fm-tag--danger'
  if (level === 'MEDIUM') return 'fm-tag fm-tag--warn'
  return 'fm-tag fm-tag--info'
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

<style scoped lang="scss">
.state {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--fm-fg-mute);
  padding: 6px 0;

  &--ok {
    color: var(--fm-ok);
  }
}

.spin {
  animation: spin 1.5s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.alarm-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alarm-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--fm-bg-2);
  border-radius: var(--fm-radius-sm);
  border: 1px solid var(--fm-line);

  .body {
    flex: 1;
    min-width: 0;
  }

  .station {
    font-size: 12.5px;
    color: var(--fm-fg);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .meta {
    font-size: 10.5px;
    font-family: var(--fm-font-mono);
    color: var(--fm-fg-mute);
    margin-top: 2px;
  }

  .level {
    font-size: 10px;
    padding: 1px 6px;
    flex-shrink: 0;
  }
}
</style>
