<template>
  <div class="big-screen" ref="screenRef">
    <!-- Header -->
    <div class="screen-header">
      <div class="header-left">
        <div class="date-time">{{ currentDate }}</div>
        <div class="week-day">{{ currentWeek }}</div>
      </div>
      <div class="header-center">
        <h1 class="title">智慧水利监控平台</h1>
        <div class="subtitle">Smart Water Management System</div>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <el-button
            type="primary"
            text
            :icon="isFullscreen ? Crop : FullScreen"
            @click="toggleFullscreen"
            class="fullscreen-btn"
          >
            {{ isFullscreen ? '退出全屏' : '全屏' }}
          </el-button>
          <el-button
            type="info"
            text
            icon="Close"
            @click="goBack"
            class="close-btn"
          >
            返回
          </el-button>
        </div>
        <div class="time">{{ currentTime }}</div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="screen-body">
      <!-- Left Panel -->
      <div class="left-panel">
        <!-- Station Stats -->
        <div class="panel-box">
          <div class="panel-title">
            <span class="title-icon"></span>
            <span>站点统计</span>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-num">{{ stats.stationTotal }}</div>
              <div class="stat-label">监测站点</div>
            </div>
            <div class="stat-item">
              <div class="stat-num">{{ stats.sensorTotal }}</div>
              <div class="stat-label">在线传感器</div>
            </div>
            <div class="stat-item">
              <div class="stat-num">{{ stats.alarmTotal }}</div>
              <div class="stat-label">活跃告警</div>
            </div>
            <div class="stat-item">
              <div class="stat-num">{{ stats.obsToday }}</div>
              <div class="stat-label">今日数据</div>
            </div>
          </div>
        </div>

        <!-- Station Type Distribution -->
        <div class="panel-box">
          <div class="panel-title">
            <span class="title-icon"></span>
            <span>站点类型分布</span>
          </div>
          <div ref="pieChartRef" class="chart-box"></div>
        </div>

        <!-- Water Level Trend -->
        <div class="panel-box">
          <div class="panel-title">
            <span class="title-icon"></span>
            <span>水位趋势 (24h)</span>
          </div>
          <div ref="waterLevelChartRef" class="chart-box"></div>
        </div>
      </div>

      <!-- Center Panel (Map) -->
      <div class="center-panel">
        <div class="map-container" ref="mapRef"></div>

        <!-- Floating Stats -->
        <div class="floating-stats">
          <div class="float-item">
            <div class="float-label">最高水位</div>
            <div class="float-value">{{ stats.maxWaterLevel }}m</div>
            <div class="float-station">{{ stats.maxWaterStation }}</div>
          </div>
          <div class="float-item">
            <div class="float-label">最大雨量</div>
            <div class="float-value">{{ stats.maxRainfall }}mm</div>
            <div class="float-station">{{ stats.maxRainStation }}</div>
          </div>
          <div class="float-item">
            <div class="float-label">最大流量</div>
            <div class="float-value">{{ stats.maxFlow }}m³/s</div>
            <div class="float-station">{{ stats.maxFlowStation }}</div>
          </div>
        </div>
      </div>

      <!-- Right Panel -->
      <div class="right-panel">
        <!-- Real-time Alarms -->
        <div class="panel-box">
          <div class="panel-title">
            <span class="title-icon"></span>
            <span>实时告警</span>
          </div>
          <div class="alarm-list">
            <div v-for="alarm in recentAlarms" :key="alarm.id" class="alarm-item" :class="alarm.level">
              <div class="alarm-level">{{ alarmLevelMap[alarm.level]?.label }}</div>
              <div class="alarm-info">
                <div class="alarm-station">{{ alarm.stationName }}</div>
                <div class="alarm-type">{{ alarm.metricType }}</div>
              </div>
              <div class="alarm-time">{{ formatTime(alarm.startAt) }}</div>
            </div>
            <div v-if="recentAlarms.length === 0" class="no-data">暂无告警</div>
          </div>
        </div>

        <!-- Rainfall Stats -->
        <div class="panel-box">
          <div class="panel-title">
            <span class="title-icon"></span>
            <span>降雨量统计</span>
          </div>
          <div ref="rainfallChartRef" class="chart-box"></div>
        </div>

        <!-- Station Rankings -->
        <div class="panel-box">
          <div class="panel-title">
            <span class="title-icon"></span>
            <span>站点数据排名</span>
          </div>
          <div class="rank-list">
            <div v-for="(item, index) in stationRankings" :key="index" class="rank-item">
              <div class="rank-num" :class="{ top: index < 3 }">{{ index + 1 }}</div>
              <div class="rank-name">{{ item.name }}</div>
              <div class="rank-bar">
                <div class="rank-fill" :style="{ width: item.percent + '%' }"></div>
              </div>
              <div class="rank-value">{{ item.value }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { FullScreen, Crop, Close } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { getStations } from '@/api/station'
import { getSensors } from '@/api/sensor'
import { getAlarms } from '@/api/alarm'
import { getObservations } from '@/api/observation'
import { alarmLevelMap } from '@/utils/format'
import type { Alarm } from '@/types'

const router = useRouter()
const screenRef = ref<HTMLElement>()
const isFullscreen = ref(false)

// Fullscreen toggle
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    screenRef.value?.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

// Listen for fullscreen change
function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

// Go back to dashboard
function goBack() {
  router.push('/dashboard')
}

// Time
const currentDate = ref('')
const currentTime = ref('')
const currentWeek = ref('')
const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

function updateTime() {
  const now = new Date()
  currentDate.value = `${now.getFullYear()}年${String(now.getMonth() + 1).padStart(2, '0')}月${String(now.getDate()).padStart(2, '0')}日`
  currentTime.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  currentWeek.value = weekDays[now.getDay()]
}

// Stats
const stats = ref({
  stationTotal: 0,
  sensorTotal: 0,
  alarmTotal: 0,
  obsToday: 0,
  maxWaterLevel: 0,
  maxWaterStation: '-',
  maxRainfall: 0,
  maxRainStation: '-',
  maxFlow: 0,
  maxFlowStation: '-'
})

const recentAlarms = ref<Alarm[]>([])
const stationRankings = ref<{ name: string; value: number; percent: number }[]>([])

// Charts
const pieChartRef = ref<HTMLElement>()
const waterLevelChartRef = ref<HTMLElement>()
const rainfallChartRef = ref<HTMLElement>()
const mapRef = ref<HTMLElement>()
let pieChart: echarts.ECharts | null = null
let waterLevelChart: echarts.ECharts | null = null
let rainfallChart: echarts.ECharts | null = null
let map: L.Map | null = null

// Format time for alarm list
function formatTime(dateStr: string) {
  const date = new Date(dateStr)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

// Load data
async function loadStats() {
  try {
    // Station count
    const stationsRes = await getStations({ page: 1, size: 1 })
    stats.value.stationTotal = stationsRes.data?.total || 0

    // Sensor count
    const sensorsRes = await getSensors({ page: 1, size: 1, status: 'ONLINE' })
    stats.value.sensorTotal = sensorsRes.data?.total || 0

    // Alarm count
    const alarmsRes = await getAlarms({ page: 1, size: 1, status: undefined })
    stats.value.alarmTotal = alarmsRes.data?.total || 0

    // Today's observations
    const today = new Date()
    const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString()
    const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59).toISOString()
    const obsRes = await getObservations({ page: 1, size: 1, start: startOfDay, end: endOfDay })
    stats.value.obsToday = obsRes.data?.total || 0

    // Recent alarms (show up to 6)
    const recentRes = await getAlarms({ page: 1, size: 6 })
    recentAlarms.value = recentRes.data?.records || []
  } catch (e) {
    console.error('Failed to load stats:', e)
  }
}

// Init pie chart
function initPieChart() {
  if (!pieChartRef.value) return
  pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: '#fff' }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 5, borderColor: '#0a1a2e', borderWidth: 2 },
      label: { show: false },
      data: [
        { value: 15, name: '水位站', itemStyle: { color: '#409EFF' } },
        { value: 12, name: '雨量站', itemStyle: { color: '#67C23A' } },
        { value: 8, name: '流量站', itemStyle: { color: '#E6A23C' } },
        { value: 5, name: '水库站', itemStyle: { color: '#F56C6C' } },
        { value: 3, name: '闸门站', itemStyle: { color: '#909399' } }
      ]
    }]
  })
}

// Init water level chart
function initWaterLevelChart() {
  if (!waterLevelChartRef.value) return
  waterLevelChart = echarts.init(waterLevelChartRef.value)

  const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)
  const data = hours.map((_, i) => {
    const base = 2.5
    const wave = Math.sin(i / 4) * 1.2
    const random = (Math.random() - 0.5) * 0.3
    return (base + wave + random).toFixed(2)
  })

  waterLevelChart.setOption({
    tooltip: { trigger: 'axis', formatter: '{b}<br/>水位: {c}m' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: hours,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.3)' } },
      axisLabel: { color: 'rgba(255,255,255,0.6)', fontSize: 10, interval: 3 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.3)' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      axisLabel: { color: 'rgba(255,255,255,0.6)', fontSize: 10 }
    },
    series: [{
      type: 'line',
      data,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#00d4ff', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(0,212,255,0.3)' },
          { offset: 1, color: 'rgba(0,212,255,0.05)' }
        ])
      }
    }]
  })
}

// Init rainfall chart
function initRainfallChart() {
  if (!rainfallChartRef.value) return
  rainfallChart = echarts.init(rainfallChartRef.value)

  const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const data = [45, 32, 58, 25, 48, 72, 38]

  rainfallChart.setOption({
    tooltip: { trigger: 'axis', formatter: '{b}<br/>降雨量: {c}mm' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: days,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.3)' } },
      axisLabel: { color: 'rgba(255,255,255,0.6)', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.3)' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      axisLabel: { color: 'rgba(255,255,255,0.6)', fontSize: 10 }
    },
    series: [{
      type: 'bar',
      data,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#00d4ff' },
          { offset: 1, color: '#0066cc' }
        ]),
        borderRadius: [4, 4, 0, 0]
      }
    }]
  })
}

// Init map
async function initMap() {
  if (!mapRef.value) return

  map = L.map(mapRef.value, {
    zoomControl: false,
    attributionControl: false
  }).setView([31.23, 121.47], 10)

  // Dark themed tiles
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19
  }).addTo(map)

  // Load stations and add markers
  try {
    const res = await getStations({ page: 1, size: 100 })
    const stations = res.data?.records || []

    // Update rankings
    stationRankings.value = stations.slice(0, 5).map((s: any, i: number) => ({
      name: s.name,
      value: Math.floor(Math.random() * 500) + 100,
      percent: 100 - i * 15
    }))

    // Add markers
    const stationTypeColors: Record<string, string> = {
      'RAIN_GAUGE': '#67C23A',
      'WATER_LEVEL': '#409EFF',
      'FLOW': '#E6A23C',
      'RESERVOIR': '#F56C6C',
      'GATE': '#909399',
      'PUMP_STATION': '#8B5CF6'
    }

    stations.forEach((s: any) => {
      if (s.lat && s.lon) {
        const color = stationTypeColors[s.type] || '#409EFF'
        const marker = L.circleMarker([s.lat, s.lon], {
          radius: 8,
          fillColor: color,
          color: '#fff',
          weight: 2,
          opacity: 1,
          fillOpacity: 0.8
        }).addTo(map!)

        marker.bindPopup(`<b>${s.name}</b><br>类型: ${s.type}<br>状态: ${s.status}`)
      }
    })
  } catch (e) {
    console.error('Failed to load map data:', e)
  }
}

// Handle resize
function handleResize() {
  pieChart?.resize()
  waterLevelChart?.resize()
  rainfallChart?.resize()
  map?.invalidateSize()
}

// Auto refresh
let timeTimer: ReturnType<typeof setInterval> | null = null
let dataTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  updateTime()
  timeTimer = setInterval(updateTime, 1000)

  loadStats()
  initPieChart()
  initWaterLevelChart()
  initRainfallChart()
  initMap()

  // Refresh data every 30 seconds
  dataTimer = setInterval(loadStats, 30000)

  window.addEventListener('resize', handleResize)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  if (timeTimer) clearInterval(timeTimer)
  if (dataTimer) clearInterval(dataTimer)
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  pieChart?.dispose()
  waterLevelChart?.dispose()
  rainfallChart?.dispose()
  map?.remove()
})
</script>

<style scoped lang="scss">
.big-screen {
  width: 100vw;
  height: 100vh;
  background: linear-gradient(135deg, #0a1a2e 0%, #162b45 50%, #0d1f33 100%);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

// Header
.screen-header {
  height: 80px;
  background: linear-gradient(180deg, rgba(0,212,255,0.1) 0%, transparent 100%);
  border-bottom: 1px solid rgba(0,212,255,0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
  position: relative;
}

.header-left, .header-right {
  color: rgba(255,255,255,0.8);
  font-size: 14px;
}

.date-time {
  font-size: 16px;
  margin-bottom: 4px;
}

.week-day {
  color: rgba(255,255,255,0.5);
}

.header-center {
  text-align: center;
}

.title {
  font-size: 32px;
  font-weight: bold;
  color: #fff;
  margin: 0;
  text-shadow: 0 0 20px rgba(0,212,255,0.5);
  letter-spacing: 8px;
}

.subtitle {
  font-size: 12px;
  color: rgba(0,212,255,0.6);
  margin-top: 4px;
  letter-spacing: 4px;
}

.time {
  font-size: 24px;
  font-weight: bold;
  color: #00d4ff;
  font-family: 'Courier New', monospace;
}

.header-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  justify-content: flex-end;
}

.fullscreen-btn,
.close-btn {
  color: rgba(255, 255, 255, 0.8) !important;
  font-size: 13px;

  &:hover {
    color: #00d4ff !important;
  }
}

// Body
.screen-body {
  flex: 1;
  display: flex;
  padding: 16px;
  gap: 16px;
  overflow: hidden;
}

// Panels
.left-panel, .right-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.center-panel {
  flex: 1;
  position: relative;
}

// Panel Box
.panel-box {
  background: linear-gradient(135deg, rgba(0,100,150,0.1) 0%, rgba(0,50,100,0.05) 100%);
  border: 1px solid rgba(0,212,255,0.15);
  border-radius: 8px;
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: bold;
  color: #fff;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0,212,255,0.2);
}

.title-icon {
  width: 4px;
  height: 16px;
  background: linear-gradient(180deg, #00d4ff, #0066cc);
  border-radius: 2px;
}

// Stats Grid
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: rgba(0,212,255,0.05);
  border-radius: 8px;
  border: 1px solid rgba(0,212,255,0.1);
}

.stat-num {
  font-size: 28px;
  font-weight: bold;
  color: #00d4ff;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: rgba(255,255,255,0.6);
}

// Chart Box
.chart-box {
  flex: 1;
  min-height: 0;
}

// Map
.map-container {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(0,212,255,0.2);
}

// Floating Stats
.floating-stats {
  position: absolute;
  bottom: 20px;
  left: 20px;
  right: 20px;
  display: flex;
  justify-content: space-around;
  gap: 16px;
}

.float-item {
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0,212,255,0.3);
  border-radius: 8px;
  padding: 16px 24px;
  text-align: center;
  min-width: 120px;
}

.float-label {
  font-size: 12px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 4px;
}

.float-value {
  font-size: 24px;
  font-weight: bold;
  color: #00d4ff;
  margin-bottom: 4px;
}

.float-station {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
}

// Alarm List
.alarm-list {
  flex: 1;
  overflow-y: auto;
}

.alarm-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
  border-left: 3px solid;
}

.alarm-item.CRITICAL {
  border-left-color: #f56c6c;
  background: rgba(245,108,108,0.1);
}

.alarm-item.WARNING {
  border-left-color: #e6a23c;
  background: rgba(230,162,60,0.1);
}

.alarm-item.INFO {
  border-left-color: #409eff;
  background: rgba(64,158,255,0.1);
}

.alarm-level {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  color: #fff;
  background: rgba(255,255,255,0.2);
}

.alarm-info {
  flex: 1;
}

.alarm-station {
  font-size: 14px;
  color: #fff;
  margin-bottom: 2px;
}

.alarm-type {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
}

.alarm-time {
  font-size: 12px;
  color: rgba(255,255,255,0.4);
}

.no-data {
  text-align: center;
  color: rgba(255,255,255,0.4);
  padding: 40px 0;
}

// Rankings
.rank-list {
  flex: 1;
  overflow-y: auto;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.rank-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

.rank-num.top {
  background: linear-gradient(135deg, #00d4ff, #0066cc);
  color: #fff;
}

.rank-name {
  width: 80px;
  font-size: 13px;
  color: rgba(255,255,255,0.8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-bar {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
  overflow: hidden;
}

.rank-fill {
  height: 100%;
  background: linear-gradient(90deg, #00d4ff, #0066cc);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.rank-value {
  width: 50px;
  text-align: right;
  font-size: 13px;
  color: #00d4ff;
}

// Scrollbar
::-webkit-scrollbar {
  width: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(0,212,255,0.3);
  border-radius: 2px;
}
</style>
