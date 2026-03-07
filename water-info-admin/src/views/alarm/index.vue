<template>
  <div class="page-container">
    <div class="search-bar">
      <el-form :model="queryParams" inline>
        <el-form-item label="告警等级">
          <el-select v-model="queryParams.level" placeholder="全部" clearable>
            <el-option v-for="(info, key) in alarmLevelMap" :key="key" :label="info.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option v-for="(info, key) in alarmStatusMap" :key="key" :label="info.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker v-model="dateRange" type="datetimerange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="table-card">
      <div class="table-header">
        <span class="table-title">告警列表</span>
        <el-tag v-if="wsConnected" type="success" size="small" effect="plain">实时连接</el-tag>
        <el-tag v-else type="danger" size="small" effect="plain">未连接</el-tag>
      </div>
      <el-table v-loading="loading" :data="tableData" border stripe row-key="id">
        <el-table-column prop="stationName" label="站点" min-width="140" />
        <el-table-column prop="metricType" label="指标" width="90" />
        <el-table-column prop="level" label="等级" width="80">
          <template #default="{ row }">
            <el-tag :color="alarmLevelMap[row.level]?.color" effect="dark" size="small" style="border: none; color: #fff">
              {{ alarmLevelMap[row.level]?.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="alarmStatusMap[row.status]?.type as any" size="small">
              {{ alarmStatusMap[row.status]?.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="告警信息" min-width="200" show-overflow-tooltip />
        <el-table-column prop="startAt" label="触发时间" width="170">
          <template #default="{ row }">{{ formatDate(row.startAt) }}</template>
        </el-table-column>
        <el-table-column prop="acknowledgedByName" label="确认人" width="100" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'OPEN'" v-permission="['ADMIN', 'OPERATOR']" link type="warning" @click="handleAck(row)">确认</el-button>
            <el-button v-if="row.status === 'ACK'" v-permission="['ADMIN', 'OPERATOR']" link type="success" @click="handleClose(row)">关闭</el-button>
            <el-button link type="primary" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </div>

    <!-- Detail drawer -->
    <el-drawer v-model="drawerVisible" title="告警详情" size="450px">
      <template v-if="currentAlarm">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="站点">{{ currentAlarm.stationName }}</el-descriptions-item>
          <el-descriptions-item label="站点编码">{{ currentAlarm.stationCode }}</el-descriptions-item>
          <el-descriptions-item label="指标类型">{{ currentAlarm.metricType }}</el-descriptions-item>
          <el-descriptions-item label="等级">
            <el-tag :color="alarmLevelMap[currentAlarm.level]?.color" effect="dark" size="small" style="border: none; color: #fff">
              {{ alarmLevelMap[currentAlarm.level]?.label }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="alarmStatusMap[currentAlarm.status]?.type as any" size="small">
              {{ alarmStatusMap[currentAlarm.status]?.label }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="告警信息">{{ currentAlarm.message }}</el-descriptions-item>
          <el-descriptions-item label="触发时间">{{ formatDate(currentAlarm.startAt) }}</el-descriptions-item>
          <el-descriptions-item label="最后触发">{{ formatDate(currentAlarm.lastTriggerAt) }}</el-descriptions-item>
          <el-descriptions-item label="确认人">{{ currentAlarm.acknowledgedByName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="确认时间">{{ currentAlarm.acknowledgedAt ? formatDate(currentAlarm.acknowledgedAt) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="关闭人">{{ currentAlarm.closedByName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关闭时间">{{ currentAlarm.closedAt ? formatDate(currentAlarm.closedAt) : '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { getAlarms, ackAlarm, closeAlarm } from '@/api/alarm'
import { useWebSocket } from '@/composables/useWebSocket'
import { formatDate, alarmLevelMap, alarmStatusMap } from '@/utils/format'
import type { Alarm, AlarmLevel, AlarmStatus } from '@/types'

const loading = ref(false)
const tableData = ref<Alarm[]>([])
const total = ref(0)
const drawerVisible = ref(false)
const currentAlarm = ref<Alarm | null>(null)
const dateRange = ref<string[]>([])

const queryParams = reactive({ page: 1, size: 20, level: '' as '' | AlarmLevel, status: '' as '' | AlarmStatus, start: '', end: '' })

// WebSocket for real-time alarms
const { messages: wsMessages, connected: wsConnected, connect } = useWebSocket('/ws/alarms')

// Watch message length for new messages - more efficient than deep watch
let lastMsgCount = 0
watch(wsMessages, (msgs) => {
  if (msgs.length > lastMsgCount) {
    ElMessage({ message: '收到新告警', type: 'warning', duration: 3000 })
    fetchData()
  }
  lastMsgCount = msgs.length
})

async function fetchData() {
  loading.value = true
  if (dateRange.value?.length === 2) { queryParams.start = dateRange.value[0]; queryParams.end = dateRange.value[1] }
  try {
    const res = await getAlarms(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

function handleSearch() { queryParams.page = 1; fetchData() }
function handleReset() { queryParams.level = ''; queryParams.status = ''; dateRange.value = []; queryParams.start = ''; queryParams.end = ''; handleSearch() }

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

function showDetail(row: Alarm) { currentAlarm.value = row; drawerVisible.value = true }

onMounted(() => { fetchData(); connect() })
</script>

<style scoped>
.table-title { font-size: 16px; font-weight: 600; }
.table-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
</style>
