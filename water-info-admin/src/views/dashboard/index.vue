<template>
  <div class="fm-dash">
    <div class="fm-page-head">
      <h1>指挥仪表盘</h1>
      <span class="sub">// overview · realtime · 翠屏湖流域</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--ok"><span class="fm-dot ok" />在线</span>
      <router-link to="/warning/alarm" class="fm-btn">
        <el-icon><Bell /></el-icon>
        <span>查看全部告警</span>
      </router-link>
      <router-link to="/bigscreen" class="fm-btn fm-btn--primary">
        <el-icon><Monitor /></el-icon>
        <span>进入大屏</span>
      </router-link>
    </div>

    <div class="fm-grid g-4 fm-dash__kpis">
      <div
        v-for="card in statsCards"
        :key="card.title"
        class="fm-card fm-kpi"
        :style="{ '--kpi-accent': card.color }"
      >
        <div class="label">
          <el-icon><component :is="card.icon" /></el-icon>
          <span>{{ card.title }}</span>
        </div>
        <div class="val">
          {{ card.value }}<span v-if="card.unit" class="u">{{ card.unit }}</span>
        </div>
        <div class="delta" :class="card.deltaDir === 'down' ? 'down' : 'up'">
          <span v-if="card.delta">{{ card.deltaDir === 'down' ? '▼' : '▲' }}</span>
          <span>{{ card.delta || '—' }}</span>
        </div>
        <div class="kpi-accent" />
      </div>
    </div>

    <div class="fm-grid g-12 fm-dash__row">
      <div class="fm-card" style="grid-column: span 8">
        <div class="fm-card__head">
          <span class="title">水位趋势 · 近 24h</span>
          <span class="mono">1 min 采样</span>
          <span class="sp" />
          <router-link to="/data/observation" class="fm-btn fm-btn--sm fm-btn--ghost">
            更多 <el-icon><ArrowRight /></el-icon>
          </router-link>
        </div>
        <div class="fm-card__body">
          <div ref="waterLevelChartRef" class="fm-dash__chart" />
        </div>
      </div>

      <div class="fm-card fm-dash__alerts" style="grid-column: span 4">
        <div class="fm-card__head">
          <span class="title">最新告警</span>
          <span class="mono">realtime</span>
          <span class="sp" />
          <span v-if="recentAlarms.length" class="fm-tag fm-tag--danger">
            {{ recentAlarms.length }} open
          </span>
        </div>
        <div class="fm-dash__alert-body">
          <div
            v-for="alarm in recentAlarms"
            :key="alarm.id"
            class="fm-dash__alert-row"
            :class="alertKind(alarm.level)"
          >
            <span class="time">{{ formatDate(alarm.startAt, 'MM-DD HH:mm') }}</span>
            <span class="stn">{{ stationCode(alarm.stationName) }}</span>
            <span class="msg">{{ alarm.stationName }}</span>
            <span class="fm-tag" :class="alertTagKind(alarm.level)">
              {{ alarmLevelMap[alarm.level]?.label || alarm.level }}
            </span>
          </div>
          <div v-if="recentAlarms.length === 0" class="fm-dash__alert-empty">
            <span class="fm-dot ok" />暂无活跃告警
          </div>
        </div>
      </div>
    </div>

    <div class="fm-grid g-12 fm-dash__row">
      <div class="fm-card" style="grid-column: span 6">
        <div class="fm-card__head">
          <span class="title">降雨量统计 · 近 7 天</span>
          <span class="mono">mm / day</span>
        </div>
        <div class="fm-card__body">
          <div ref="rainfallChartRef" class="fm-dash__chart" />
        </div>
      </div>
      <div class="fm-card" style="grid-column: span 6">
        <div class="fm-card__head">
          <span class="title">站点类型分布</span>
          <span class="mono">{{ totalStations }} stations</span>
        </div>
        <div class="fm-card__body">
          <div ref="stationPieRef" class="fm-dash__chart" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import {
  MapLocation,
  Cpu,
  Bell,
  DataLine,
  Monitor,
  ArrowRight,
} from '@element-plus/icons-vue'
import { getAlarms } from '@/api/alarm'
import { getStations } from '@/api/station'
import { getSensors } from '@/api/sensor'
import { getObservations } from '@/api/observation'
import { formatDate, alarmLevelMap, stationTypeMap } from '@/utils/format'
import type { Alarm } from '@/types'

interface StatsCard {
  title: string
  value: string
  unit?: string
  icon: unknown
  color: string
  delta?: string
  deltaDir?: 'up' | 'down'
}

const waterLevelChartRef = ref<HTMLElement>()
const rainfallChartRef = ref<HTMLElement>()
const stationPieRef = ref<HTMLElement>()
const recentAlarms = ref<Alarm[]>([])
const totalStations = ref(0)
let charts: echarts.ECharts[] = []

const statsCards = ref<StatsCard[]>([
  { title: '在线站点', value: '—', icon: MapLocation, color: '#49e1ff' },
  { title: '在线传感器', value: '—', icon: Cpu, color: '#2bd99f' },
  { title: '活跃告警', value: '—', icon: Bell, color: '#ff5a6a' },
  { title: '今日数据量', value: '—', icon: DataLine, color: '#ffb547' },
])

// ── FloodMind dark ECharts theme ──────────────────────
const FM = {
  fg: '#e8eef8',
  fgMute: '#6a7590',
  fgSoft: '#a9b3c6',
  line: '#1f2a3f',
  bg2: '#111a2c',
  brand: '#2f7bff',
  brand2: '#49e1ff',
  ok: '#2bd99f',
  warn: '#ffb547',
  danger: '#ff5a6a',
} as const

const baseAxisStyle = {
  axisLine: { lineStyle: { color: FM.line } },
  axisLabel: {
    color: FM.fgMute,
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: 10.5,
  },
  axisTick: { lineStyle: { color: FM.line } },
  splitLine: { lineStyle: { color: FM.line, type: 'dashed' } },
  nameTextStyle: { color: FM.fgMute, fontSize: 10.5 },
}

const baseTooltip = {
  backgroundColor: '#0b1220',
  borderColor: FM.line,
  borderWidth: 1,
  textStyle: { color: FM.fg, fontSize: 12 },
  extraCssText: 'box-shadow: 0 12px 30px -14px rgba(0,0,0,0.6); border-radius: 6px;',
}

// ── Data loading (unchanged semantics) ────────────────
async function loadData() {
  try {
    const [stationsRes, sensorsRes, alarmsRes] = await Promise.all([
      getStations({ page: 1, size: 1000 }),
      getSensors({ page: 1, size: 1, status: 'ONLINE' }),
      getAlarms({ page: 1, size: 10, status: 'OPEN' }),
    ])
    if (stationsRes.data?.total !== undefined) {
      statsCards.value[0].value = String(stationsRes.data.total)
      statsCards.value[0].unit = '/ 132'
      totalStations.value = stationsRes.data.total
    }
    if (sensorsRes.data?.total !== undefined) {
      statsCards.value[1].value = String(sensorsRes.data.total)
    }
    recentAlarms.value = alarmsRes.data?.records || []
    if (alarmsRes.data?.total !== undefined) {
      statsCards.value[2].value = String(alarmsRes.data.total)
      statsCards.value[2].delta = recentAlarms.value.length > 0 ? '近 1h' : '稳定'
      statsCards.value[2].deltaDir = recentAlarms.value.length > 5 ? 'down' : 'up'
    }

    const today = new Date()
    const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString()
    const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59).toISOString()
    const observationsRes = await getObservations({ page: 1, size: 1, start: startOfDay, end: endOfDay })
    if (observationsRes.data?.total !== undefined) {
      statsCards.value[3].value = String(observationsRes.data.total)
    }

    updateStationPieChart(stationsRes.data?.records || [])
    await Promise.all([
      updateWaterLevelChart(stationsRes.data?.records || []),
      updateRainfallChart(stationsRes.data?.records || []),
    ])
  } catch {
    // best effort
  }
}

// ── Water level chart ─────────────────────────────────
function initWaterLevelChart() {
  if (!waterLevelChartRef.value) return
  const chart = echarts.init(waterLevelChartRef.value)
  charts.push(chart)
  chart.setOption({
    tooltip: { trigger: 'axis', ...baseTooltip },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: [], ...baseAxisStyle },
    yAxis: { type: 'value', name: '水位 (m)', ...baseAxisStyle },
    series: [
      {
        name: '水位',
        type: 'line',
        data: [],
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: FM.brand2 },
        itemStyle: { color: FM.brand2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(73, 225, 255, 0.35)' },
            { offset: 1, color: 'rgba(73, 225, 255, 0.02)' },
          ]),
        },
      },
    ],
  })
}

async function updateWaterLevelChart(stations: any[]) {
  const chart = charts[0]
  if (!chart) return
  const station =
    stations.find((s) => s.code === 'ST_WL_CP_01') ||
    stations.find((s) => s.type === 'WATER_LEVEL')
  if (!station) {
    chart.setOption({ xAxis: { data: [] }, series: [{ data: [] }] })
    return
  }
  const now = new Date()
  const start = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString()
  const res = await getObservations({
    stationId: station.id,
    metricType: 'WATER_LEVEL',
    start,
    end: now.toISOString(),
    page: 1,
    size: 240,
  })
  const records = [...(res.data?.records || [])].reverse()
  const times = records.map((r) => formatDate(r.observedAt, 'HH:mm'))
  const values = records.map((r) => Number(Number(r.value).toFixed(2)))
  chart.setOption({ xAxis: { data: times }, series: [{ data: values }] })
}

// ── Rainfall chart ───────────────────────────────────
function initRainfallChart() {
  if (!rainfallChartRef.value) return
  const chart = echarts.init(rainfallChartRef.value)
  charts.push(chart)
  chart.setOption({
    tooltip: { trigger: 'axis', ...baseTooltip },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: [], ...baseAxisStyle },
    yAxis: { type: 'value', name: '降雨量 (mm)', ...baseAxisStyle },
    series: [
      {
        name: '降雨量',
        type: 'bar',
        data: [],
        barMaxWidth: 28,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: FM.brand2 },
            { offset: 1, color: FM.brand },
          ]),
          borderRadius: [4, 4, 0, 0],
          shadowColor: 'rgba(47, 123, 255, 0.45)',
          shadowBlur: 8,
        },
      },
    ],
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
  chart.setOption({
    xAxis: { data: dayLabels },
    series: [{ data: dayKeys.map((k) => Number(sums[k].toFixed(1))) }],
  })
}

// ── Station pie ──────────────────────────────────────
function initStationPieChart() {
  if (!stationPieRef.value) return
  const chart = echarts.init(stationPieRef.value)
  charts.push(chart)
  chart.setOption({
    tooltip: { trigger: 'item', ...baseTooltip },
    legend: {
      bottom: 0,
      textStyle: { color: FM.fgSoft, fontSize: 11 },
      itemGap: 14,
    },
    series: [
      {
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 6,
          borderColor: FM.bg2,
          borderWidth: 2,
        },
        label: {
          show: true,
          color: FM.fgSoft,
          fontSize: 11,
          fontFamily: 'JetBrains Mono, monospace',
          formatter: '{b}: {c}',
        },
        labelLine: { lineStyle: { color: FM.line } },
        data: [],
      },
    ],
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
    水位站: '#49e1ff',
    雨量站: '#2bd99f',
    流量站: '#ffb547',
    水库站: '#ff5a6a',
    闸门站: '#7aa2ff',
    泵站: '#8b5cf6',
  }
  chart.setOption({
    series: [
      {
        data: Object.entries(counts).map(([name, value]) => ({
          value,
          name,
          itemStyle: { color: colorMap[name] || FM.brand2 },
        })),
      },
    ],
  })
}

// ── Alarms presentation helpers ──────────────────────
function alertKind(level: string): string {
  if (level === 'CRITICAL' || level === 'HIGH') return 'crit'
  if (level === 'MEDIUM') return 'warn'
  return 'info'
}
function alertTagKind(level: string): string {
  if (level === 'CRITICAL' || level === 'HIGH') return 'fm-tag--danger'
  if (level === 'MEDIUM') return 'fm-tag--warn'
  return 'fm-tag--info'
}
function stationCode(name: string | undefined): string {
  if (!name) return '—'
  const m = name.match(/[A-Z]\d+/)
  return m ? m[0] : name.slice(0, 3).toUpperCase()
}

// ── Lifecycle ────────────────────────────────────────
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
.fm-dash {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fm-dash__kpis {
  margin-bottom: 0;
}

.fm-kpi {
  overflow: hidden;

  .label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10.5px;
  }
  .kpi-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--kpi-accent, var(--fm-brand-2));
    opacity: 0.8;
    box-shadow: 0 0 8px var(--kpi-accent, var(--fm-brand-2));
  }
}

.fm-dash__row {
  align-items: stretch;
}

.fm-dash__chart {
  height: 300px;
  width: 100%;
}

/* Alert stream */
.fm-dash__alerts {
  display: flex;
  flex-direction: column;
}

.fm-dash__alert-body {
  overflow-y: auto;
  max-height: 344px;
  padding: 4px 0;
}

.fm-dash__alert-row {
  display: grid;
  grid-template-columns: 80px 56px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 11px 16px;
  border-bottom: 1px solid var(--fm-line);
  font-size: 12.5px;
  cursor: pointer;
  transition: background 0.15s;

  &:last-child { border-bottom: none; }
  &:hover { background: var(--fm-bg-2); }

  &.crit { border-left: 2px solid var(--fm-danger); }
  &.warn { border-left: 2px solid var(--fm-warn); }
  &.info { border-left: 2px solid var(--fm-info); }

  .time {
    font-family: var(--fm-font-mono);
    font-size: 10.5px;
    color: var(--fm-fg-mute);
    letter-spacing: 0.04em;
  }
  .stn {
    font-family: var(--fm-font-mono);
    font-size: 11px;
    color: var(--fm-fg-soft);
    letter-spacing: 0.06em;
  }
  .msg {
    color: var(--fm-fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.fm-dash__alert-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  color: var(--fm-ok);
  font-size: 12.5px;
}

/* Link-as-button: keep router-link looking like a .fm-btn */
:deep(.fm-page-head .fm-btn),
:deep(.fm-card__head .fm-btn) {
  text-decoration: none;
  color: inherit;
}
</style>
