<template>
  <div class="bs" ref="screenRef">
    <!-- ============== Top bar ============== -->
    <header class="bs-topbar">
      <div class="bs-brand">
        <div class="bs-brand__mark">F</div>
        <div>
          <div class="bs-brand__name">FloodMind <span>翠屏湖防洪指挥中心</span></div>
          <div class="bs-brand__sub">REAL-TIME · 24H · CUIPING LAKE BASIN</div>
        </div>
      </div>

      <div class="alarm-river" :class="{ 'is-empty': recentAlarms.length === 0 }">
        <div class="alarm-river__label">
          <template v-if="recentAlarms.length">LIVE ALERTS</template>
          <template v-else>ALL CLEAR</template>
        </div>
        <div v-if="recentAlarms.length" class="alarm-river__track">
          <span
            v-for="(alarm, i) in alarmRiverItems"
            :key="`${alarm.id}-${i}`"
            class="alarm-river__item"
          >
            <span class="lvl" :class="alarm.level.toLowerCase()">{{ alarmLevelMap[alarm.level]?.label || alarm.level }}</span>
            <b>{{ alarm.stationName }}</b>
            {{ metricTypeMap[alarm.metricType] || alarm.metricType }} · {{ formatAlarmAge(alarm.startAt) }}
          </span>
        </div>
        <div v-else class="alarm-river__empty">系统运行正常</div>
      </div>

      <div class="bs-topbar__right">
        <div class="bs-clock">
          {{ currentTime }}
          <small>{{ currentDate }} · {{ currentWeek }}</small>
        </div>
        <button class="bs-iconbtn" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏'">
          <el-icon><Crop v-if="isFullscreen" /><FullScreen v-else /></el-icon>
        </button>
        <button class="bs-iconbtn" @click="goBack" title="返回">
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </header>

    <!-- ============== Body ============== -->
    <div class="bs-body">
      <!-- ========= LEFT ========= -->
      <div class="bs-col">
        <!-- KPIs -->
        <section class="card">
          <div class="card__head">
            <div class="card__title">Overview <span class="card__chs">流域综览</span></div>
            <div class="card__meta">LIVE</div>
          </div>
          <div class="kpi-grid">
            <div class="kpi">
              <div class="kpi__label">Stations</div>
              <div class="kpi__value">{{ stats.stationTotal }} <small>处</small></div>
              <div class="kpi__delta up">↑ 在线 {{ onlineStationPct }}%</div>
              <svg class="kpi__spark" viewBox="0 0 100 18" preserveAspectRatio="none">
                <polyline points="0,12 14,10 28,11 42,8 56,9 70,7 84,8 100,5" fill="none" stroke="#49e1ff" stroke-width="1.4" />
              </svg>
            </div>
            <div class="kpi">
              <div class="kpi__label">Sensors</div>
              <div class="kpi__value">{{ stats.sensorTotal }} <small>个</small></div>
              <div class="kpi__delta up">在线传感器</div>
              <svg class="kpi__spark" viewBox="0 0 100 18" preserveAspectRatio="none">
                <polyline points="0,8 14,9 28,7 42,8 56,6 70,7 84,5 100,4" fill="none" stroke="#2bd99f" stroke-width="1.4" />
              </svg>
            </div>
            <div class="kpi" :class="{ 'kpi--alarm': stats.alarmTotal > 0 }">
              <div class="kpi__label">Active Alerts</div>
              <div class="kpi__value">{{ stats.alarmTotal }} <small>条</small></div>
              <div class="kpi__delta" :class="stats.alarmTotal > 0 ? 'down' : 'up'">
                {{ stats.alarmTotal > 0 ? '↑ 待处置' : '✓ 暂无告警' }}
              </div>
              <svg class="kpi__spark" viewBox="0 0 100 18" preserveAspectRatio="none">
                <polyline
                  :points="stats.alarmTotal > 0 ? '0,15 14,14 28,13 42,12 56,9 70,7 84,4 100,2' : '0,16 100,16'"
                  fill="none"
                  :stroke="stats.alarmTotal > 0 ? '#ff5a6a' : '#2bd99f'"
                  stroke-width="1.4"
                />
              </svg>
            </div>
            <div class="kpi">
              <div class="kpi__label">Records · 24h</div>
              <div class="kpi__value">{{ formatRecordCount(stats.obsToday) }}</div>
              <div class="kpi__delta up">↑ 数据接入正常</div>
              <svg class="kpi__spark" viewBox="0 0 100 18" preserveAspectRatio="none">
                <polyline points="0,10 14,9 28,11 42,8 56,9 70,7 84,8 100,7" fill="none" stroke="#7aa2ff" stroke-width="1.4" />
              </svg>
            </div>
          </div>
        </section>

        <!-- 站点类型分布 -->
        <section class="card">
          <div class="card__head">
            <div class="card__title">Composition <span class="card__chs">站点类型分布</span></div>
            <div class="card__meta">N={{ stats.stationTotal }}</div>
          </div>
          <div ref="pieChartRef" class="chart-box chart-box--pie" />
        </section>

        <!-- 水位趋势 -->
        <section class="card">
          <div class="card__head">
            <div class="card__title">Water Level <span class="card__chs">水位趋势 · 24h</span></div>
            <div class="card__meta">{{ stats.maxWaterStation || '—' }}</div>
          </div>
          <div ref="waterLevelChartRef" class="chart-box" />
        </section>
      </div>

      <!-- ========= CENTER ========= -->
      <div class="bs-col bs-col--center">
        <LakeStage :markers="lakeMarkers" />

        <div class="floating-strips">
          <div class="strip" :class="{ 'strip--crit': stats.maxWaterLevel >= 4.5 }">
            <div>
              <div class="strip__label">Max Water</div>
              <div class="strip__value">{{ stats.maxWaterLevel }}<small>m</small></div>
            </div>
            <div class="strip__site">{{ stats.maxWaterStation || '—' }}</div>
          </div>
          <div class="strip">
            <div>
              <div class="strip__label">Max Rainfall</div>
              <div class="strip__value">{{ stats.maxRainfall }}<small>mm</small></div>
            </div>
            <div class="strip__site">{{ stats.maxRainStation || '—' }}</div>
          </div>
          <div class="strip">
            <div>
              <div class="strip__label">Max Flow</div>
              <div class="strip__value">{{ stats.maxFlow }}<small>m³/s</small></div>
            </div>
            <div class="strip__site">{{ stats.maxFlowStation || '—' }}</div>
          </div>
        </div>
      </div>

      <!-- ========= RIGHT ========= -->
      <div class="bs-col">
        <!-- 实时告警 -->
        <section class="card">
          <div class="card__head">
            <div class="card__title">Active Alerts <span class="card__chs">实时告警</span></div>
            <div class="card__meta">{{ recentAlarms.length }} OPEN</div>
          </div>
          <div class="alarm-list">
            <div
              v-for="(alarm, i) in recentAlarms"
              :key="alarm.id"
              class="alarm"
              :class="[severityClass(alarm.level), { 'alarm--new': i === 0 && alarm.level === 'CRITICAL' }]"
            >
              <div class="alarm__lvl">{{ severityShort(alarm.level) }}</div>
              <div>
                <div class="alarm__site">{{ alarm.stationName }}</div>
                <div class="alarm__metric">
                  {{ metricTypeMap[alarm.metricType] || alarm.metricType }}
                  <span v-if="alarm.message"> · {{ alarm.message }}</span>
                </div>
              </div>
              <div class="alarm__time">{{ formatAlarmTime(alarm.startAt) }}</div>
            </div>
            <div v-if="recentAlarms.length === 0" class="empty-tip">暂无告警</div>
          </div>
        </section>

        <!-- AI 综合研判 -->
        <section class="card">
          <div class="card__head">
            <div class="card__title">AI Assessment <span class="card__chs">AI 综合研判</span></div>
            <div class="card__meta">{{ aiAssessment ? aiAssessment.timeLabel : '待机' }}</div>
          </div>
          <div class="ai" v-if="aiAssessment">
            <div class="ai__head">
              <span class="ai__badge">{{ aiAssessment.source }}</span>
              <span class="ai__time">{{ aiAssessment.trigger }}</span>
            </div>
            <div class="ai__risk-row">
              <span class="ai__risk-label">Risk</span>
              <span class="ai__risk-value" :style="{ color: aiAssessment.color }">{{ aiAssessment.risk }}</span>
              <span class="ai__risk-trend" :style="{ color: aiAssessment.color }">↑ {{ aiAssessment.trend }}</span>
            </div>
            <div class="ai__body">{{ aiAssessment.summary }}</div>
          </div>
          <div v-else class="empty-tip">流域态势平稳，无需特别研判</div>
        </section>

        <!-- 7日降雨 -->
        <section class="card">
          <div class="card__head">
            <div class="card__title">Rainfall · 7d <span class="card__chs">7日累积降雨</span></div>
            <div class="card__meta">mm</div>
          </div>
          <div ref="rainfallChartRef" class="chart-box chart-box--small" />
        </section>

        <!-- 站点排名 -->
        <section class="card">
          <div class="card__head">
            <div class="card__title">Top Stations <span class="card__chs">站点数据排名</span></div>
            <div class="card__meta">实时</div>
          </div>
          <div class="rank-list">
            <div
              v-for="(item, idx) in stationRankings"
              :key="item.name + idx"
              class="rank"
              :class="{ 'rank--top': idx < 3 }"
            >
              <div class="rank__num">{{ idx + 1 }}</div>
              <div class="rank__name">{{ item.name }}</div>
              <div class="rank__bar"><div class="rank__fill" :style="{ width: item.percent + '%' }" /></div>
              <div class="rank__val">{{ item.value }}</div>
            </div>
            <div v-if="stationRankings.length === 0" class="empty-tip">暂无数据</div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { FullScreen, Crop, Close } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getStations } from '@/api/station'
import { getSensors } from '@/api/sensor'
import { getAlarms } from '@/api/alarm'
import { getLatestObservations, getObservations, type LatestObservationBatchItem } from '@/api/observation'
import { alarmLevelMap, metricTypeMap, stationTypeMap } from '@/utils/format'
import type { Alarm, Station, MetricType } from '@/types'
import type { StationMarker } from '@/composables/useLakeMap'
import LakeStage from './components/LakeStage.vue'

const router = useRouter()
const screenRef = ref<HTMLElement>()
const isFullscreen = ref(false)

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    screenRef.value?.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

function goBack() {
  router.push('/dashboard')
}

const currentDate = ref('')
const currentTime = ref('')
const currentWeek = ref('')
const weekDays = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function updateTime() {
  const d = new Date()
  currentDate.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  currentTime.value = `${pad(d.getHours())} : ${pad(d.getMinutes())} : ${pad(d.getSeconds())}`
  currentWeek.value = weekDays[d.getDay()]
}

const stats = ref({
  stationTotal: 0,
  sensorTotal: 0,
  alarmTotal: 0,
  obsToday: 0,
  maxWaterLevel: 0,
  maxWaterStation: '',
  maxRainfall: 0,
  maxRainStation: '',
  maxFlow: 0,
  maxFlowStation: '',
})

const recentAlarms = ref<Alarm[]>([])
const stationRankings = ref<{ name: string; value: number; percent: number }[]>([])
const lakeMarkers = ref<StationMarker[]>([])

const pieChartRef = ref<HTMLElement>()
const waterLevelChartRef = ref<HTMLElement>()
const rainfallChartRef = ref<HTMLElement>()
let pieChart: echarts.ECharts | null = null
let waterLevelChart: echarts.ECharts | null = null
let rainfallChart: echarts.ECharts | null = null

// === Helpers ===

function formatAlarmTime(dateStr: string) {
  const d = new Date(dateStr)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatAlarmAge(dateStr: string) {
  const diffMin = Math.max(0, Math.round((Date.now() - new Date(dateStr).getTime()) / 60_000))
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const h = Math.floor(diffMin / 60)
  return `${h} 小时前`
}

function formatRecordCount(n: number) {
  if (n >= 10_000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function severityClass(level: string) {
  return level === 'CRITICAL' ? 'alarm--crit' : level === 'HIGH' ? 'alarm--high' : 'alarm--med'
}

function severityShort(level: string) {
  return level === 'CRITICAL' ? 'CRIT' : level === 'HIGH' ? 'HIGH' : level === 'MEDIUM' ? 'MED' : 'LOW'
}

const onlineStationPct = computed(() => {
  if (!stats.value.stationTotal) return 0
  // Assume all currently fetched stations are online; refine when sensor health rolls in.
  return 100
})

// Loop the alarm list once for seamless marquee scroll.
const alarmRiverItems = computed<Alarm[]>(() => [...recentAlarms.value, ...recentAlarms.value])

// Placeholder AI assessment — derives a quick read from the highest-severity OPEN alarm
// until the ai-assessment WebSocket / REST endpoint lands.
const aiAssessment = computed(() => {
  const order: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
  const sorted = [...recentAlarms.value].sort((a, b) => (order[a.level] ?? 9) - (order[b.level] ?? 9))
  const top = sorted[0]
  if (!top) return null

  const isCritical = top.level === 'CRITICAL'
  const isHigh = top.level === 'HIGH'
  return {
    source: isCritical || isHigh ? 'EVENT TRIGGERED' : 'PERIODIC',
    risk: isCritical ? 'HIGH' : isHigh ? 'MEDIUM' : 'LOW',
    color: isCritical ? '#ff5a6a' : isHigh ? '#ffb547' : '#7aa2ff',
    trend: isCritical ? '上升中' : isHigh ? '关注' : '平稳',
    trigger: `由${top.stationName} ${severityShort(top.level)} 触发`,
    timeLabel: `${severityShort(top.level)} · ${formatAlarmAge(top.startAt)}`,
    summary: isCritical
      ? `${top.stationName} 已超警戒，建议立即启动 III 级响应；上下游联动监测，加密巡查与会商。`
      : isHigh
        ? `${top.stationName} 接近警戒值，建议加强观测频次并复核上游输入。`
        : '当前态势平稳，按计划巡检即可。',
  }
})

// === ECharts ===

const ECHARTS_TYPE_COLORS: Record<string, string> = {
  水位站: '#2f7bff',
  雨量站: '#49e1ff',
  流量站: '#2bd99f',
  水库站: '#ffb547',
  闸门站: '#ff5a6a',
  泵站: '#7aa2ff',
}

function initPieChart() {
  if (!pieChartRef.value) return
  pieChart = echarts.init(pieChartRef.value)
  pieChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(11, 18, 32, 0.92)',
      borderColor: 'rgba(73,225,255,0.25)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: 8,
      top: 'center',
      icon: 'roundRect',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: '#a9b3c6', fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['58%', '82%'],
        center: ['32%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 4, borderColor: '#0b1220', borderWidth: 2 },
        label: { show: false },
        data: [],
      },
    ],
  })
}

function initWaterLevelChart() {
  if (!waterLevelChartRef.value) return
  waterLevelChart = echarts.init(waterLevelChartRef.value)
  waterLevelChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(11, 18, 32, 0.92)',
      borderColor: 'rgba(73,225,255,0.25)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
      formatter: '{b}<br/>水位 {c} m',
    },
    grid: { left: 38, right: 14, top: 14, bottom: 24 },
    xAxis: {
      type: 'category',
      data: [],
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(73,225,255,0.18)' } },
      axisTick: { show: false },
      axisLabel: { color: '#6a7590', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      axisLabel: { color: '#6a7590', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
    },
    series: [
      {
        type: 'line',
        data: [],
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        lineStyle: { color: '#49e1ff', width: 1.6 },
        itemStyle: { color: '#49e1ff', borderColor: '#0b1220', borderWidth: 2 },
        emphasis: { focus: 'series' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(73, 225, 255, 0.45)' },
            { offset: 1, color: 'rgba(73, 225, 255, 0)' },
          ]),
        },
      },
    ],
  })
}

function initRainfallChart() {
  if (!rainfallChartRef.value) return
  rainfallChart = echarts.init(rainfallChartRef.value)
  rainfallChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(11, 18, 32, 0.92)',
      borderColor: 'rgba(73,225,255,0.25)',
      textStyle: { color: '#e8eef8', fontSize: 12 },
      formatter: '{b}<br/>降雨 {c} mm',
    },
    grid: { left: 32, right: 12, top: 18, bottom: 22 },
    xAxis: {
      type: 'category',
      data: [],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#6a7590', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
      axisLabel: { color: '#6a7590', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
    },
    series: [
      {
        type: 'bar',
        data: [],
        barWidth: '54%',
        itemStyle: {
          color: 'rgba(47, 123, 255, 0.7)',
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
  })
}

// === Data loading ===

const stationMetricType: Partial<Record<Station['type'], MetricType>> = {
  WATER_LEVEL: 'WATER_LEVEL',
  RAIN_GAUGE: 'RAINFALL',
  FLOW: 'FLOW',
  RESERVOIR: 'WATER_LEVEL',
  GATE: 'WATER_LEVEL',
  PUMP_STATION: 'FLOW',
}

const metricUnits: Record<MetricType, string> = {
  WATER_LEVEL: 'm',
  RAINFALL: 'mm',
  FLOW: 'm³/s',
}

function buildObservationKey(stationId: string, metricType: MetricType) {
  return `${stationId}:${metricType}`
}

async function fetchLatestObservationMap(stations: Station[]) {
  const items: LatestObservationBatchItem[] = stations.flatMap((station) => {
    const metric = stationMetricType[station.type]
    return metric ? [{ stationId: station.id, metricType: metric }] : []
  })
  if (items.length === 0) return new Map<string, { value: number; metricType: MetricType }>()
  const res = await getLatestObservations(items)
  return new Map(
    (res.data || []).map((o) => [
      buildObservationKey(o.stationId, o.metricType),
      { value: o.value, metricType: o.metricType },
    ]),
  )
}

let allStations: Station[] = []

async function loadData() {
  try {
    const [stationsRes, sensorsRes, alarmsRes] = await Promise.all([
      getStations({ page: 1, size: 100 }),
      getSensors({ page: 1, size: 1, status: 'ONLINE' }),
      getAlarms({ page: 1, size: 10, status: 'OPEN' }),
    ])

    allStations = stationsRes.data?.records || []
    stats.value.stationTotal = stationsRes.data?.total || 0
    stats.value.sensorTotal = sensorsRes.data?.total || 0
    stats.value.alarmTotal = alarmsRes.data?.total || 0
    recentAlarms.value = (alarmsRes.data?.records || []).slice(0, 6)

    const today = new Date()
    const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString()
    const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59).toISOString()
    const obsRes = await getObservations({ page: 1, size: 1, start: startOfDay, end: endOfDay })
    stats.value.obsToday = obsRes.data?.total || 0

    const openAlarmsByStation = new Map<string, Alarm>()
    recentAlarms.value
      .filter((a) => a.status === 'OPEN')
      .forEach((a) => {
        const cur = openAlarmsByStation.get(a.stationId)
        if (!cur || severityRank(a.level) < severityRank(cur.level)) {
          openAlarmsByStation.set(a.stationId, a)
        }
      })

    const latestObservationMap = await fetchLatestObservationMap(allStations)
    const markers: StationMarker[] = []
    const latestValues: { station: Station; value: number; metric: MetricType; unit: string }[] = []

    allStations.forEach((station) => {
      const metric = stationMetricType[station.type]
      const alarm = openAlarmsByStation.get(station.id)

      if (!metric) {
        markers.push({ station, hasAlarm: !!alarm, alarmLevel: alarm?.level })
        return
      }

      const latest = latestObservationMap.get(buildObservationKey(station.id, metric))
      const value = latest?.value ?? null
      const unit = metricUnits[metric]

      markers.push({
        station,
        latestValue: value,
        unit,
        hasAlarm: !!alarm,
        alarmLevel: alarm?.level,
      })

      if (value != null) {
        latestValues.push({ station, value, metric, unit })
      }
    })

    lakeMarkers.value = markers

    const wl = latestValues.filter((o) => o.metric === 'WATER_LEVEL')
    const rain = latestValues.filter((o) => o.metric === 'RAINFALL')
    const flow = latestValues.filter((o) => o.metric === 'FLOW')

    if (wl.length) {
      const max = wl.reduce((a, b) => (a.value > b.value ? a : b))
      stats.value.maxWaterLevel = Number(max.value.toFixed(2))
      stats.value.maxWaterStation = max.station.name
    }
    if (rain.length) {
      const max = rain.reduce((a, b) => (a.value > b.value ? a : b))
      stats.value.maxRainfall = Number(max.value.toFixed(1))
      stats.value.maxRainStation = max.station.name
    }
    if (flow.length) {
      const max = flow.reduce((a, b) => (a.value > b.value ? a : b))
      stats.value.maxFlow = Number(max.value.toFixed(1))
      stats.value.maxFlowStation = max.station.name
    }

    updatePieChart()
    const sorted = [...latestValues].sort((a, b) => b.value - a.value).slice(0, 5)
    const maxVal = sorted[0]?.value || 1
    stationRankings.value = sorted.map((o) => ({
      name: o.station.name,
      value: Number(o.value.toFixed(2)),
      percent: Math.round((o.value / maxVal) * 100),
    }))

    await Promise.all([loadWaterLevelTrend(), loadRainfallTrend()])
  } catch (e) {
    console.error('Failed to load bigscreen data:', e)
  }
}

function severityRank(level: string) {
  return level === 'CRITICAL' ? 0 : level === 'HIGH' ? 1 : level === 'MEDIUM' ? 2 : 3
}

function updatePieChart() {
  if (!pieChart) return
  const counts: Record<string, number> = {}
  allStations.forEach((s) => {
    const label = stationTypeMap[s.type] || s.type
    counts[label] = (counts[label] || 0) + 1
  })
  pieChart.setOption({
    series: [
      {
        data: Object.entries(counts).map(([name, value]) => ({
          name,
          value,
          itemStyle: { color: ECHARTS_TYPE_COLORS[name] || '#2f7bff' },
        })),
      },
    ],
  })
}

async function loadWaterLevelTrend() {
  const wlStation =
    allStations.find((s) => s.code === 'ST_WL_CP_01') || allStations.find((s) => s.type === 'WATER_LEVEL')
  if (!wlStation || !waterLevelChart) return
  const now = new Date()
  const start = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString()
  try {
    const res = await getObservations({
      stationId: wlStation.id,
      metricType: 'WATER_LEVEL',
      start,
      end: now.toISOString(),
      page: 1,
      size: 200,
    })
    const records = [...(res.data?.records || [])].reverse()
    const times = records.map((r) => {
      const d = new Date(r.observedAt)
      return `${pad(d.getHours())}:${pad(d.getMinutes())}`
    })
    const values = records.map((r) => Number(Number(r.value).toFixed(2)))
    waterLevelChart.setOption({ xAxis: { data: times }, series: [{ data: values }] })
  } catch (e) {
    console.error('Failed to load water level trend:', e)
  }
}

async function loadRainfallTrend() {
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
  try {
    const rainStations = allStations.filter((s) => s.type === 'RAIN_GAUGE')
    if (!rainfallChart || rainStations.length === 0) return
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
    const dailySum: Record<string, number> = {}
    dayKeys.forEach((k) => (dailySum[k] = 0))
    responses.forEach((res) => {
      ;(res.data?.records || []).forEach((r) => {
        const day = r.observedAt.split('T')[0]
        if (day in dailySum) dailySum[day] += r.value
      })
    })
    const data = dayKeys.map((k) => Number(dailySum[k].toFixed(1)))
    const lastIdx = data.length - 1
    const dataItems = data.map((value, idx) =>
      idx === lastIdx
        ? {
            value,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#49e1ff' },
                { offset: 1, color: '#2f7bff' },
              ]),
              borderRadius: [4, 4, 0, 0],
              shadowBlur: 12,
              shadowColor: 'rgba(73, 225, 255, 0.5)',
            },
          }
        : { value },
    )
    rainfallChart.setOption({ xAxis: { data: dayLabels }, series: [{ data: dataItems }] })
  } catch (e) {
    console.error('Failed to load rainfall trend:', e)
  }
}

function handleResize() {
  pieChart?.resize()
  waterLevelChart?.resize()
  rainfallChart?.resize()
}

let timeTimer: ReturnType<typeof setInterval> | null = null
let dataTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  updateTime()
  timeTimer = setInterval(updateTime, 1000)
  initPieChart()
  initWaterLevelChart()
  initRainfallChart()
  loadData()
  dataTimer = setInterval(loadData, 30000)
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
})
</script>

<style scoped lang="scss">
/* Local tokens — bigscreen lives in dark cinematic mode regardless of admin theme */
.bs {
  --bs-glass: linear-gradient(180deg, rgba(23, 35, 56, 0.55) 0%, rgba(11, 18, 32, 0.35) 100%);
  --bs-line: rgba(73, 225, 255, 0.10);
  --bs-line-2: rgba(73, 225, 255, 0.18);
  --bs-display-mono: 'JetBrains Mono', 'SFMono-Regular', 'Menlo', ui-monospace, monospace;

  width: 100vw;
  height: 100vh;
  display: grid;
  grid-template-rows: 64px 1fr;
  background: #060a14;
  background-image:
    radial-gradient(1400px 800px at 12% 6%, rgba(47, 123, 255, 0.16), transparent 55%),
    radial-gradient(1100px 700px at 92% 98%, rgba(73, 225, 255, 0.08), transparent 55%),
    radial-gradient(900px 600px at 60% 50%, rgba(47, 123, 255, 0.05), transparent 60%);
  color: #ffffff;
  overflow: hidden;
  font-feature-settings: 'tnum' 1;

  &::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      radial-gradient(1.4px 1.4px at 10% 30%, rgba(73, 225, 255, 0.4), transparent 50%),
      radial-gradient(1.2px 1.2px at 30% 60%, rgba(47, 123, 255, 0.35), transparent 50%),
      radial-gradient(1px 1px at 55% 20%, rgba(255, 255, 255, 0.5), transparent 50%),
      radial-gradient(1.4px 1.4px at 78% 75%, rgba(73, 225, 255, 0.3), transparent 50%),
      radial-gradient(1.2px 1.2px at 88% 35%, rgba(255, 255, 255, 0.4), transparent 50%),
      radial-gradient(1px 1px at 22% 85%, rgba(73, 225, 255, 0.4), transparent 50%);
    background-size: 600px 400px;
    animation: bs-drift 60s linear infinite;
    pointer-events: none;
    opacity: 0.7;
  }
}

@keyframes bs-drift {
  0% { transform: translate(0, 0); }
  100% { transform: translate(60px, -40px); }
}

/* ============== Top bar ============== */
.bs-topbar {
  display: grid;
  grid-template-columns: 360px 1fr 320px;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  border-bottom: 1px solid var(--bs-line);
  background: linear-gradient(180deg, rgba(11, 18, 32, 0.7) 0%, rgba(6, 10, 20, 0.2) 100%);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  z-index: 10;
}

.bs-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bs-brand__mark {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: linear-gradient(135deg, #2f7bff 0%, #49e1ff 100%);
  display: grid;
  place-items: center;
  color: white;
  font-weight: 700;
  font-size: 17px;
  font-family: var(--bs-display-mono);
  box-shadow: 0 0 0 1px rgba(73, 225, 255, 0.3), 0 8px 24px -8px rgba(47, 123, 255, 0.6);
  position: relative;
  overflow: hidden;

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 30% 25%, rgba(255, 255, 255, 0.45), transparent 50%);
  }
}

.bs-brand__name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.04em;

  span {
    color: #8693af;
    font-weight: 400;
    margin-left: 6px;
  }
}

.bs-brand__sub {
  font-size: 10px;
  color: #8693af;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-family: var(--bs-display-mono);
  margin-top: 2px;
}

.alarm-river {
  height: 36px;
  border-radius: 10px;
  background: var(--bs-glass);
  border: 1px solid var(--bs-line);
  overflow: hidden;
  display: flex;
  align-items: center;

  &.is-empty .alarm-river__label {
    color: #2bd99f;
    background: rgba(43, 217, 159, 0.06);
    &::before { background: #2bd99f; box-shadow: 0 0 8px #2bd99f; animation: none; }
  }
}

.alarm-river__label {
  flex: 0 0 auto;
  padding: 0 12px 0 14px;
  font-size: 10px;
  color: #ff5a6a;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-family: var(--bs-display-mono);
  font-weight: 600;
  border-right: 1px solid var(--bs-line);
  height: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 90, 106, 0.06);

  &::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #ff5a6a;
    box-shadow: 0 0 8px #ff5a6a;
    animation: bs-pulse 1.4s ease-in-out infinite;
  }
}

@keyframes bs-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}

.alarm-river__track {
  flex: 1;
  display: flex;
  gap: 28px;
  padding-left: 14px;
  white-space: nowrap;
  animation: bs-scroll 30s linear infinite;
}

.alarm-river__empty {
  flex: 1;
  padding-left: 14px;
  font-size: 12px;
  color: #8693af;
  font-family: var(--bs-display-mono);
  letter-spacing: 0.05em;
}

@keyframes bs-scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

.alarm-river__item {
  font-size: 12px;
  color: #c1cbe0;
  display: inline-flex;
  align-items: center;
  gap: 8px;

  b {
    color: #ffffff;
    font-weight: 600;
  }

  .lvl {
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 3px;
    letter-spacing: 0.1em;
    font-family: var(--bs-display-mono);
    font-weight: 700;

    &.critical { background: rgba(255, 90, 106, 0.15); color: #ff5a6a; }
    &.high     { background: rgba(255, 181, 71, 0.15); color: #ffb547; }
    &.medium   { background: rgba(122, 162, 255, 0.18); color: #7aa2ff; }
    &.low      { background: rgba(144, 163, 174, 0.16); color: #909399; }
  }
}

.bs-topbar__right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
}

.bs-clock {
  font-family: var(--bs-display-mono);
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #ffffff;
  text-shadow: 0 0 16px rgba(73, 225, 255, 0.25);
  text-align: right;

  small {
    display: block;
    font-size: 10px;
    color: #8693af;
    letter-spacing: 0.18em;
    font-weight: 400;
    margin-top: 2px;
  }
}

.bs-iconbtn {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--bs-glass);
  border: 1px solid var(--bs-line);
  color: #c1cbe0;
  cursor: pointer;
  font: inherit;

  &:hover {
    color: #49e1ff;
    border-color: var(--bs-line-2);
  }
}

/* ============== Body ============== */
.bs-body {
  display: grid;
  grid-template-columns: 340px 1fr 340px;
  gap: 14px;
  padding: 14px 18px 18px;
  overflow: hidden;
  min-height: 0;
}

.bs-col {
  display: grid;
  grid-template-rows: auto 1fr 1fr;
  gap: 12px;
  min-height: 0;

  &--center {
    grid-template-rows: 1fr;
    position: relative;
    min-width: 0;
  }
}

.bs-col:nth-child(3) {
  grid-template-rows: auto auto auto auto;
}

/* ============== Glass card ============== */
.card {
  background: var(--bs-glass);
  border: 1px solid var(--bs-line);
  border-radius: 12px;
  padding: 12px 14px;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.04) 0%, transparent 30%);
    pointer-events: none;
  }

  &::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, #49e1ff, transparent);
    opacity: 0.3;
  }
}

.card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  flex: 0 0 auto;
}

.card__title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #c1cbe0;
  display: flex;
  align-items: center;
  gap: 8px;

  &::before {
    content: '';
    width: 3px;
    height: 12px;
    background: linear-gradient(180deg, #49e1ff, #2f7bff);
    border-radius: 2px;
    box-shadow: 0 0 6px #49e1ff;
  }
}

.card__chs {
  color: #ffffff;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: none;
  font-size: 13px;
}

.card__meta {
  font-size: 10px;
  color: #8693af;
  font-family: var(--bs-display-mono);
  letter-spacing: 0.1em;
}

/* ============== KPI ============== */
.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.kpi {
  padding: 12px 12px 10px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(47, 123, 255, 0.08) 0%, rgba(11, 18, 32, 0.4) 100%);
  border: 1px solid var(--bs-line);
  position: relative;
  overflow: hidden;

  &__label {
    font-size: 10px;
    color: #8693af;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-family: var(--bs-display-mono);
  }

  &__value {
    font-family: var(--bs-display-mono);
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #ffffff;
    margin-top: 4px;
    line-height: 1.1;
    text-shadow: 0 0 14px rgba(73, 225, 255, 0.18);

    small {
      font-size: 12px;
      color: #8693af;
      margin-left: 4px;
      font-weight: 400;
    }
  }

  &__delta {
    font-size: 10px;
    margin-top: 2px;
    font-family: var(--bs-display-mono);
    letter-spacing: 0.04em;

    &.up { color: #2bd99f; }
    &.down { color: #ff5a6a; }
    &.warn { color: #ffb547; }
  }

  &__spark {
    margin-top: 6px;
    height: 18px;
    width: 100%;
  }

  &--alarm {
    background: linear-gradient(180deg, rgba(255, 90, 106, 0.10) 0%, rgba(11, 18, 32, 0.4) 100%);
    border-color: rgba(255, 90, 106, 0.22);

    .kpi__value { text-shadow: 0 0 14px rgba(255, 90, 106, 0.35); }
  }
}

/* ============== Charts ============== */
.chart-box {
  flex: 1;
  min-height: 130px;
  width: 100%;

  &--pie { min-height: 152px; }
  &--small { min-height: 100px; }
}

/* ============== Center stage ============== */
.bs-col--center {
  display: grid;
}

.floating-strips {
  position: absolute;
  top: 14px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 12px;
  z-index: 4;
  pointer-events: none;
}

.strip {
  padding: 9px 16px;
  border-radius: 999px;
  background: rgba(11, 18, 32, 0.6);
  border: 1px solid var(--bs-line-2);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  display: flex;
  align-items: center;
  gap: 10px;

  &__label {
    font-size: 10px;
    color: #8693af;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-family: var(--bs-display-mono);
  }

  &__value {
    font-family: var(--bs-display-mono);
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;

    small {
      color: #8693af;
      font-size: 10px;
      font-weight: 400;
      margin-left: 2px;
    }
  }

  &__site {
    font-size: 10px;
    color: #8693af;
    border-left: 1px solid var(--bs-line-2);
    padding-left: 10px;
  }

  &--crit {
    border-color: rgba(255, 90, 106, 0.4);
    box-shadow: 0 0 24px -4px rgba(255, 90, 106, 0.5);

    .strip__value { color: #ff5a6a; }
  }
}

/* ============== Alarm list ============== */
.alarm-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
}

.alarm {
  display: grid;
  grid-template-columns: 56px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 9px 10px;
  background: linear-gradient(180deg, rgba(23, 35, 56, 0.5), rgba(11, 18, 32, 0.3));
  border: 1px solid var(--bs-line);
  border-left-width: 2px;
  border-radius: 8px;
  position: relative;
  flex-shrink: 0;

  &--crit { border-left-color: #ff5a6a; }
  &--high { border-left-color: #ffb547; }
  &--med  { border-left-color: #7aa2ff; }

  &--new::before {
    content: '';
    position: absolute;
    inset: -1px;
    border-radius: 8px;
    box-shadow: 0 0 0 0 rgba(255, 90, 106, 0.7);
    animation: bs-ripple 1.6s ease-out 1;
    pointer-events: none;
  }

  &__lvl {
    font-family: var(--bs-display-mono);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.14em;
    padding: 3px 6px;
    border-radius: 4px;
    text-align: center;
  }

  &--crit .alarm__lvl { background: rgba(255, 90, 106, 0.16); color: #ff5a6a; }
  &--high .alarm__lvl { background: rgba(255, 181, 71, 0.16); color: #ffb547; }
  &--med .alarm__lvl  { background: rgba(122, 162, 255, 0.16); color: #7aa2ff; }

  &__site {
    font-size: 12px;
    font-weight: 600;
    color: #ffffff;
  }

  &__metric {
    font-size: 11px;
    color: #8693af;
    font-family: var(--bs-display-mono);
    margin-top: 1px;
  }

  &__time {
    font-size: 11px;
    color: #8693af;
    font-family: var(--bs-display-mono);
  }
}

@keyframes bs-ripple {
  0% { box-shadow: 0 0 0 0 rgba(255, 90, 106, 0.7); }
  100% { box-shadow: 0 0 0 18px rgba(255, 90, 106, 0); }
}

/* ============== AI Assessment ============== */
.ai {
  padding: 14px 14px;
  background: linear-gradient(180deg, rgba(47, 123, 255, 0.08), rgba(11, 18, 32, 0.4));
  border: 1px solid rgba(73, 225, 255, 0.18);
  border-radius: 10px;

  &__head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  &__badge {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: #49e1ff;
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(73, 225, 255, 0.12);
    font-family: var(--bs-display-mono);
  }

  &__time {
    font-size: 10px;
    color: #8693af;
    font-family: var(--bs-display-mono);
  }

  &__risk-row {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 8px;
  }

  &__risk-label {
    font-size: 10px;
    color: #8693af;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-family: var(--bs-display-mono);
  }

  &__risk-value {
    font-family: var(--bs-display-mono);
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  &__risk-trend {
    font-size: 10px;
    font-family: var(--bs-display-mono);
  }

  &__body {
    font-size: 12px;
    color: #c1cbe0;
    line-height: 1.7;
  }
}

/* ============== Ranking ============== */
.rank-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.rank {
  display: grid;
  grid-template-columns: 22px 1fr 90px 60px;
  align-items: center;
  gap: 10px;
  font-size: 12px;

  &__num {
    width: 20px;
    height: 20px;
    display: grid;
    place-items: center;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.05);
    color: #8693af;
    font-family: var(--bs-display-mono);
    font-size: 11px;
    font-weight: 600;
  }

  &--top &__num {
    background: linear-gradient(135deg, #2f7bff 0%, #49e1ff 100%);
    color: white;
    box-shadow: 0 0 10px rgba(73, 225, 255, 0.5);
  }

  &__name {
    color: #c1cbe0;
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__bar {
    height: 4px;
    border-radius: 2px;
    background: rgba(255, 255, 255, 0.06);
    overflow: hidden;
  }

  &__fill {
    height: 100%;
    background: linear-gradient(90deg, #2f7bff, #49e1ff);
    border-radius: 2px;
    box-shadow: 0 0 8px rgba(73, 225, 255, 0.4);
    transition: width 0.5s ease;
  }

  &__val {
    text-align: right;
    font-family: var(--bs-display-mono);
    font-size: 12px;
    font-weight: 600;
    color: #ffffff;
  }
}

.empty-tip {
  text-align: center;
  color: #4f5d78;
  padding: 18px 0;
  font-size: 12px;
}

::-webkit-scrollbar {
  width: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(73, 225, 255, 0.3);
  border-radius: 2px;
}
</style>
