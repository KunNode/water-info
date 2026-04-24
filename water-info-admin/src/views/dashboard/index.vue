<template>
  <div class="page-container">
    <!-- Big Screen Entry -->
    <el-card shadow="hover" class="bigscreen-entry" :body-style="{ padding: '16px 24px' }">
      <div class="entry-content">
        <div class="entry-left">
          <el-icon size="32" color="#00d4ff"><Monitor /></el-icon>
          <div class="entry-text">
            <div class="entry-title">数据大屏</div>
            <div class="entry-desc">实时监控大屏，展示全系统运行状态</div>
          </div>
        </div>
        <el-button type="primary" size="large" @click="$router.push('/bigscreen')">
          <el-icon class="mr-2"><FullScreen /></el-icon>
          进入大屏
        </el-button>
      </div>
    </el-card>

    <!-- Stats cards -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6" v-for="card in statsCards" :key="card.title">
        <el-card shadow="hover" class="stat-card" :body-style="{ padding: '20px' }">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-title">{{ card.title }}</div>
              <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
            </div>
            <el-icon class="stat-icon" :style="{ color: card.color }">
              <component :is="card.icon" />
            </el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- Water level trend -->
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>水位趋势 (近24h)</span>
              <el-button text type="primary" @click="$router.push('/data/observation')">更多</el-button>
            </div>
          </template>
          <div ref="waterLevelChartRef" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- Recent alarms -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最新告警</span>
              <el-button text type="primary" @click="$router.push('/warning/alarm')">更多</el-button>
            </div>
          </template>
          <div class="alarm-list">
            <div v-for="alarm in recentAlarms" :key="alarm.id" class="alarm-item">
              <el-tag :type="alarmStatusMap[alarm.status]?.type as any" size="small" effect="dark">
                {{ alarmLevelMap[alarm.level]?.label }}
              </el-tag>
              <span class="alarm-station">{{ alarm.stationName }}</span>
              <span class="alarm-time">{{ formatDate(alarm.startAt, 'MM-DD HH:mm') }}</span>
            </div>
            <el-empty v-if="recentAlarms.length === 0" description="暂无告警" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- Rainfall chart -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>降雨量统计</span>
          </template>
          <div ref="rainfallChartRef" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- Station status -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>站点状态概览</span>
          </template>
          <div ref="stationPieRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { MapLocation, Cpu, Bell, DataLine, Monitor, FullScreen } from '@element-plus/icons-vue'
import { getAlarms } from '@/api/alarm'
import { getStations } from '@/api/station'
import { getSensors } from '@/api/sensor'
import { getObservations } from '@/api/observation'
import { formatDate, alarmLevelMap, alarmStatusMap } from '@/utils/format'
import type { Alarm } from '@/types'

// Icon components for stats cards
const iconComponents = { MapLocation, Cpu, Bell, DataLine }

const waterLevelChartRef = ref<HTMLElement>()
const rainfallChartRef = ref<HTMLElement>()
const stationPieRef = ref<HTMLElement>()
const recentAlarms = ref<Alarm[]>([])

let charts: echarts.ECharts[] = []

const statsCards = ref([
  { title: '监测站总数', value: '-', icon: MapLocation, color: '#409EFF' },
  { title: '在线传感器', value: '-', icon: Cpu, color: '#67C23A' },
  { title: '活跃告警', value: '-', icon: Bell, color: '#F56C6C' },
  { title: '今日数据量', value: '-', icon: DataLine, color: '#E6A23C' },
])

async function loadData() {
  try {
    // Load stations count
    const stationsRes = await getStations({ page: 1, size: 1 })
    if (stationsRes.data?.total !== undefined) {
      statsCards.value[0].value = String(stationsRes.data.total)
    }

    // Load sensors count (ONLINE status)
    const sensorsRes = await getSensors({ page: 1, size: 1, status: 'ONLINE' })
    if (sensorsRes.data?.total !== undefined) {
      statsCards.value[1].value = String(sensorsRes.data.total)
    }

    // Load alarms
    const alarmsRes = await getAlarms({ page: 1, size: 10, status: 'OPEN' })
    recentAlarms.value = alarmsRes.data?.records || []
    if (alarmsRes.data?.total !== undefined) {
      statsCards.value[2].value = String(alarmsRes.data.total)
    }

    // Load today's observation count
    const today = new Date()
    const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString()
    const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59).toISOString()
    const observationsRes = await getObservations({ page: 1, size: 1, start: startOfDay, end: endOfDay })
    if (observationsRes.data?.total !== undefined) {
      statsCards.value[3].value = String(observationsRes.data.total)
    }
  } catch {
    // Dashboard data is best-effort
  }
}

function initWaterLevelChart() {
  if (!waterLevelChartRef.value) return
  const chart = echarts.init(waterLevelChartRef.value)
  charts.push(chart)

  // Generate demo time-series data for last 24 hours
  const now = Date.now()
  const data = Array.from({ length: 24 }, (_, i) => {
    const time = new Date(now - (23 - i) * 3600000)
    return [time.toISOString(), (5 + Math.random() * 3).toFixed(2)]
  })

  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', name: '水位(m)', min: 4, max: 10 },
    series: [
      {
        name: '水位',
        type: 'line',
        data,
        smooth: true,
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2 },
        itemStyle: { color: '#409EFF' },
      },
    ],
  })
}

function initRainfallChart() {
  if (!rainfallChartRef.value) return
  const chart = echarts.init(rainfallChartRef.value)
  charts.push(chart)

  const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const data = days.map(() => Math.round(Math.random() * 80))

  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: days },
    yAxis: { type: 'value', name: '降雨量(mm)' },
    series: [
      {
        name: '降雨量',
        type: 'bar',
        data,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#409EFF' },
            { offset: 1, color: '#79bbff' },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
  })
}

function initStationPieChart() {
  if (!stationPieRef.value) return
  const chart = echarts.init(stationPieRef.value)
  charts.push(chart)

  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}: {c}' },
        data: [
          { value: 12, name: '水位站', itemStyle: { color: '#409EFF' } },
          { value: 8, name: '雨量站', itemStyle: { color: '#67C23A' } },
          { value: 5, name: '流量站', itemStyle: { color: '#E6A23C' } },
          { value: 3, name: '水库站', itemStyle: { color: '#F56C6C' } },
          { value: 2, name: '闸门站', itemStyle: { color: '#909399' } },
        ],
      },
    ],
  })
}

function handleResize() {
  charts.forEach((c) => c.resize())
}

onMounted(() => {
  loadData()
  initWaterLevelChart()
  initRainfallChart()
  initStationPieChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  charts.forEach((c) => c.dispose())
  charts = []
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped lang="scss">
.bigscreen-entry {
  margin-bottom: 16px;
  background: linear-gradient(135deg, rgba(0, 100, 150, 0.05) 0%, rgba(0, 212, 255, 0.05) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);

  .entry-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .entry-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .entry-text {
    .entry-title {
      font-size: 18px;
      font-weight: bold;
      color: #303133;
      margin-bottom: 4px;
    }

    .entry-desc {
      font-size: 13px;
      color: #909399;
    }
  }
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  .stat-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .stat-title {
    font-size: 14px;
    color: #909399;
    margin-bottom: 8px;
  }

  .stat-value {
    font-size: 28px;
    font-weight: 600;
  }

  .stat-icon {
    font-size: 48px;
    opacity: 0.6;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  height: 300px;
}

.alarm-list {
  max-height: 300px;
  overflow-y: auto;
}

.alarm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;

  &:last-child {
    border-bottom: none;
  }

  .alarm-station {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .alarm-time {
    color: #909399;
    font-size: 12px;
    flex-shrink: 0;
  }
}
</style>
