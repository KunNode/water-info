<template>
  <div class="page-container">
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

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6" v-for="card in statsCards" :key="card.title">
        <el-card shadow="hover" class="stat-card" :body-style="{ padding: '20px' }">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-title">{{ card.title }}</div>
              <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
            </div>
            <el-icon class="stat-icon" :style="{ color: card.color }"><component :is="card.icon" /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
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
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>降雨量统计</span></template>
          <div ref="rainfallChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span>站点状态概览</span></template>
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
import { formatDate, alarmLevelMap, alarmStatusMap, stationTypeMap } from '@/utils/format'
import type { Alarm } from '@/types'

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
    const [stationsRes, sensorsRes, alarmsRes] = await Promise.all([
      getStations({ page: 1, size: 1000 }),
      getSensors({ page: 1, size: 1, status: 'ONLINE' }),
      getAlarms({ page: 1, size: 10, status: 'OPEN' }),
    ])
    if (stationsRes.data?.total !== undefined) {
      statsCards.value[0].value = String(stationsRes.data.total)
    }
    if (sensorsRes.data?.total !== undefined) {
      statsCards.value[1].value = String(sensorsRes.data.total)
    }
    recentAlarms.value = alarmsRes.data?.records || []
    if (alarmsRes.data?.total !== undefined) {
      statsCards.value[2].value = String(alarmsRes.data.total)
    }

    const today = new Date()
    const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString()
    const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59).toISOString()
    const observationsRes = await getObservations({ page: 1, size: 1, start: startOfDay, end: endOfDay })
    if (observationsRes.data?.total !== undefined) {
      statsCards.value[3].value = String(observationsRes.data.total)
    }

    updateStationPieChart(stationsRes.data?.records || [])
    await Promise.all([updateWaterLevelChart(stationsRes.data?.records || []), updateRainfallChart(stationsRes.data?.records || [])])
  } catch {
    // best effort
  }
}

function initWaterLevelChart() {
  if (!waterLevelChartRef.value) return
  const chart = echarts.init(waterLevelChartRef.value)
  charts.push(chart)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: [] },
    yAxis: { type: 'value', name: '水位(m)' },
    series: [{ name: '水位', type: 'line', data: [], smooth: true, areaStyle: { opacity: 0.15 }, lineStyle: { width: 2 }, itemStyle: { color: '#409EFF' } }],
  })
}

async function updateWaterLevelChart(stations: any[]) {
  const chart = charts[0]
  if (!chart) return
  const station = stations.find((s) => s.code === 'ST_WL_CP_01') || stations.find((s) => s.type === 'WATER_LEVEL')
  if (!station) {
    chart.setOption({ xAxis: { data: [] }, series: [{ data: [] }] })
    return
  }
  const now = new Date()
  const start = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString()
  const res = await getObservations({ stationId: station.id, metricType: 'WATER_LEVEL', start, end: now.toISOString(), page: 1, size: 240 })
  const records = [...(res.data?.records || [])].reverse()
  const times = records.map((r) => formatDate(r.observedAt, 'HH:mm'))
  const values = records.map((r) => Number(Number(r.value).toFixed(2)))
  chart.setOption({ xAxis: { data: times }, series: [{ data: values }] })
}

function initRainfallChart() {
  if (!rainfallChartRef.value) return
  const chart = echarts.init(rainfallChartRef.value)
  charts.push(chart)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: [] },
    yAxis: { type: 'value', name: '降雨量(mm)' },
    series: [{
      name: '降雨量',
      type: 'bar',
      data: [],
      itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#409EFF' }, { offset: 1, color: '#79bbff' }]), borderRadius: [4, 4, 0, 0] },
    }],
  })
}

async function updateRainfallChart(stations: any[]) {
  const chart = charts[1]
  if (!chart) return
  const rainStations = stations.filter((s) => s.type === 'RAIN_GAUGE')
  if (!rainStations.length) {
    chart.setOption({ xAxis: { data: [] }, series: [{ data: [] }] })
    return
  }
  const now = new Date()
  const start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
  const dayLabels: string[] = []
  const dayKeys: string[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    dayLabels.push(`${d.getMonth() + 1}/${d.getDate()}`)
    dayKeys.push(d.toISOString().split('T')[0])
  }
  const responses = await Promise.all(
    rainStations.map((s) =>
      getObservations({
        stationId: s.id,
        metricType: 'RAINFALL',
        start: start.toISOString(),
        end: now.toISOString(),
        page: 1,
        size: 500,
      }),
    ),
  )
  const sums: Record<string, number> = {}
  dayKeys.forEach((k) => {
    sums[k] = 0
  })
  responses.forEach((res) => {
    ;(res.data?.records || []).forEach((r) => {
      const day = r.observedAt.split('T')[0]
      if (day in sums) sums[day] += r.value
    })
  })
  chart.setOption({ xAxis: { data: dayLabels }, series: [{ data: dayKeys.map((k) => Number(sums[k].toFixed(1))) }] })
}

function initStationPieChart() {
  if (!stationPieRef.value) return
  const chart = echarts.init(stationPieRef.value)
  charts.push(chart)
  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{ type: 'pie', radius: ['40%', '70%'], avoidLabelOverlap: false, itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 }, label: { show: true, formatter: '{b}: {c}' }, data: [] }],
  })
}

function updateStationPieChart(stations: any[]) {
  const chart = charts[2]
  if (!chart) return
  const counts: Record<string, number> = {}
  stations.forEach((s) => {
    const name = stationTypeMap[s.type] || s.type
    counts[name] = (counts[name] || 0) + 1
  })
  const colorMap: Record<string, string> = {
    水位站: '#409EFF',
    雨量站: '#67C23A',
    流量站: '#E6A23C',
    水库站: '#F56C6C',
    闸门站: '#909399',
    泵站: '#8B5CF6',
  }
  chart.setOption({
    series: [{
      data: Object.entries(counts).map(([name, value]) => ({
        value,
        name,
        itemStyle: { color: colorMap[name] || '#409EFF' },
      })),
    }],
  })
}

function handleResize() {
  charts.forEach((c) => c.resize())
}

onMounted(() => {
  initWaterLevelChart()
  initRainfallChart()
  initStationPieChart()
  loadData()
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
