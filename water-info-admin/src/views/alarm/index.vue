<template>
  <div class="fm-alarm-page">
    <div class="fm-page-head">
      <h1>告警管理</h1>
      <span class="sub">// incident feed · ws live</span>
      <span class="sp" />
      <span class="fm-tag" :class="wsConnected ? 'fm-tag--ok' : 'fm-tag--danger'">
        <span class="fm-dot" :class="wsConnected ? 'ok' : 'danger'" />
        {{ wsConnected ? '实时连接' : '未连接' }}
      </span>
      <router-link to="/warning/threshold" class="fm-btn fm-btn--ghost">
        <el-icon><Setting /></el-icon>
        <span>阈值规则</span>
      </router-link>
    </div>

    <div class="fm-card fm-alarm-page__search">
      <el-form :model="queryParams" inline>
        <el-form-item label="告警等级">
          <el-select v-model="queryParams.level" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="(info, key) in alarmLevelMap" :key="key" :label="info.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="(info, key) in alarmStatusMap" :key="key" :label="info.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-card fm-alarm-page__table">
      <div class="fm-card__head">
        <span class="title">告警列表</span>
        <span class="mono">{{ total }} records</span>
        <span class="sp" />
        <span v-if="openCount > 0" class="fm-tag fm-tag--danger">{{ openCount }} open</span>
      </div>

      <el-table v-loading="loading" :data="tableData" stripe row-key="id" class="fm-alarm-table">
        <el-table-column prop="stationName" label="站点" min-width="140" />
        <el-table-column prop="metricType" label="指标" width="110">
          <template #default="{ row }">
            <span class="fm-tag">{{ metricTypeMap[row.metricType] || row.metricType }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="等级" width="96">
          <template #default="{ row }">
            <span class="fm-tag" :class="levelTagKind(row.level)">
              <span class="fm-dot" :class="levelDotKind(row.level)" />
              {{ alarmLevelMap[row.level]?.label }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="96">
          <template #default="{ row }">
            <span class="fm-tag" :class="statusTagKind(row.status)">{{ alarmStatusMap[row.status]?.label }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="告警信息" min-width="200" show-overflow-tooltip />
        <el-table-column prop="startAt" label="触发时间" width="170">
          <template #default="{ row }">
            <span class="mono-cell">{{ formatDate(row.startAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="acknowledgedByName" label="确认人" width="100" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'OPEN'"
              v-permission="['ADMIN', 'OPERATOR']"
              link
              type="warning"
              @click="handleAck(row)"
            >确认</el-button>
            <el-button
              v-if="row.status === 'ACK'"
              v-permission="['ADMIN', 'OPERATOR']"
              link
              type="success"
              @click="handleClose(row)"
            >关闭</el-button>
            <el-button link type="primary" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="fm-alarm-page__foot">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </div>

    <el-drawer v-model="drawerVisible" title="告警详情" size="460px">
      <template v-if="currentAlarm">
        <el-descriptions :column="1" border class="fm-alarm-detail">
          <el-descriptions-item label="站点">{{ currentAlarm.stationName }}</el-descriptions-item>
          <el-descriptions-item label="站点编码">
            <span class="mono-cell">{{ currentAlarm.stationCode }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="指标类型">
            {{ metricTypeMap[currentAlarm.metricType] || currentAlarm.metricType }}
          </el-descriptions-item>
          <el-descriptions-item label="等级">
            <span class="fm-tag" :class="levelTagKind(currentAlarm.level)">
              <span class="fm-dot" :class="levelDotKind(currentAlarm.level)" />
              {{ alarmLevelMap[currentAlarm.level]?.label }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <span class="fm-tag" :class="statusTagKind(currentAlarm.status)">{{ alarmStatusMap[currentAlarm.status]?.label }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="告警信息">{{ currentAlarm.message }}</el-descriptions-item>
          <el-descriptions-item label="触发时间">{{ formatDate(currentAlarm.startAt) }}</el-descriptions-item>
          <el-descriptions-item label="最后触发">{{ formatDate(currentAlarm.lastTriggerAt) }}</el-descriptions-item>
          <el-descriptions-item label="确认人">{{ currentAlarm.acknowledgedByName || '—' }}</el-descriptions-item>
          <el-descriptions-item label="确认时间">{{ currentAlarm.acknowledgedAt ? formatDate(currentAlarm.acknowledgedAt) : '—' }}</el-descriptions-item>
          <el-descriptions-item label="关闭人">{{ currentAlarm.closedByName || '—' }}</el-descriptions-item>
          <el-descriptions-item label="关闭时间">{{ currentAlarm.closedAt ? formatDate(currentAlarm.closedAt) : '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Setting } from '@element-plus/icons-vue'
import { getAlarms, ackAlarm, closeAlarm } from '@/api/alarm'
import { useWebSocket } from '@/composables/useWebSocket'
import {
  formatDate,
  alarmLevelMap,
  alarmStatusMap,
  metricTypeMap,
} from '@/utils/format'
import type { Alarm, AlarmLevel, AlarmStatus } from '@/types'

const loading = ref(false)
const tableData = ref<Alarm[]>([])
const total = ref(0)
const drawerVisible = ref(false)
const currentAlarm = ref<Alarm | null>(null)
const dateRange = ref<string[]>([])

const queryParams = reactive({
  page: 1,
  size: 20,
  level: '' as '' | AlarmLevel,
  status: '' as '' | AlarmStatus,
  start: '',
  end: '',
})

const { messages: wsMessages, connected: wsConnected, connect } = useWebSocket('/ws/alarms')

let lastMsgCount = 0
watch(wsMessages, (msgs) => {
  if (msgs.length > lastMsgCount) {
    ElMessage({ message: '收到新告警', type: 'warning', duration: 3000 })
    fetchData()
  }
  lastMsgCount = msgs.length
})

const openCount = computed(() => tableData.value.filter((a) => a.status === 'OPEN').length)

async function fetchData() {
  loading.value = true
  if (dateRange.value?.length === 2) {
    queryParams.start = dateRange.value[0]
    queryParams.end = dateRange.value[1]
  }
  try {
    const res = await getAlarms(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  queryParams.page = 1
  fetchData()
}
function handleReset() {
  queryParams.level = ''
  queryParams.status = ''
  dateRange.value = []
  queryParams.start = ''
  queryParams.end = ''
  handleSearch()
}

async function handleAck(row: Alarm) {
  await ElMessageBox.confirm('确认该告警？', '提示', { type: 'warning' })
  await ackAlarm(row.id)
  ElMessage.success('已确认')
  fetchData()
}

async function handleClose(row: Alarm) {
  await ElMessageBox.confirm('关闭该告警？', '提示', { type: 'warning' })
  await closeAlarm(row.id)
  ElMessage.success('已关闭')
  fetchData()
}

function showDetail(row: Alarm) {
  currentAlarm.value = row
  drawerVisible.value = true
}

// ── Tag / dot kind helpers ──────────────────────────
function levelTagKind(level: string): string {
  if (level === 'CRITICAL') return 'fm-tag--danger'
  if (level === 'HIGH') return 'fm-tag--warn'
  if (level === 'MEDIUM') return 'fm-tag--info'
  return ''
}
function levelDotKind(level: string): string {
  if (level === 'CRITICAL' || level === 'HIGH') return 'danger'
  if (level === 'MEDIUM') return 'warn'
  return 'off'
}
function statusTagKind(status: string): string {
  if (status === 'OPEN') return 'fm-tag--danger'
  if (status === 'ACK') return 'fm-tag--warn'
  return 'fm-tag--ok'
}

onMounted(() => {
  fetchData()
  connect()
})
</script>

<style scoped lang="scss">
.fm-alarm-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fm-alarm-page__search {
  padding: 16px 18px;

  :deep(.el-form) {
    margin: 0;
  }
  :deep(.el-form-item) {
    margin-bottom: 0;
    margin-right: 16px;
  }
}

.fm-alarm-page__foot {
  padding: 14px 16px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--fm-line);
}

.mono-cell {
  font-family: var(--fm-font-mono);
  font-size: 11.5px;
  color: var(--fm-fg-soft);
  letter-spacing: 0.04em;
}

/* Element table inside an fm-card: drop its own border so the card rules the frame */
.fm-alarm-table :deep(.el-table) {
  border: none;
  --el-table-border-color: var(--fm-line);
}
.fm-alarm-table :deep(.el-table__inner-wrapper::before) {
  background-color: var(--fm-line);
}

.fm-alarm-detail :deep(.el-descriptions__label) {
  background: var(--fm-bg-2);
  color: var(--fm-fg-mute);
  font-family: var(--fm-font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.fm-alarm-detail :deep(.el-descriptions__content) {
  color: var(--fm-fg);
}
</style>
