<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>观测数据</h1>
      <span class="sub">// timeseries · query · export</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} records</span>
      <span class="fm-tag">5 min avg</span>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">TOTAL</div>
        <div class="value">{{ total }}</div>
        <div class="hint">查询结果总量</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">PAGE</div>
        <div class="value">{{ tableData.length }}</div>
        <div class="hint">当前页记录</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">MAX</div>
        <div class="value">{{ maxValue }}</div>
        <div class="hint">趋势峰值</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">GOOD</div>
        <div class="value">{{ goodCount }}</div>
        <div class="hint">趋势中 GOOD 标记</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="站点">
          <el-select :model-value="queryParams.stationId" placeholder="请选择站点" clearable filterable style="min-width: 200px" @update:model-value="selectStation">
            <el-option v-for="s in stationList" :key="s.id" :label="`${s.name}（${s.code}）`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- Chart area -->
    <div class="fm-card">
      <div class="fm-card__head">
          <span class="title">数据趋势</span>
          <span class="mono" v-if="canShowChart">{{ metricLabel }}{{ metricUnit ? ` / ${metricUnit}` : '' }}</span>
          <span class="mono" v-else>请先选择站点</span>
          <span class="sp" />
          <el-radio-group v-model="chartType" size="small" :disabled="!canShowChart">
            <el-radio-button value="line">折线图</el-radio-button>
            <el-radio-button value="bar">柱状图</el-radio-button>
          </el-radio-group>
      </div>
      <div class="fm-card__body">
        <div v-if="canShowChart" ref="chartRef" class="chart-container"></div>
        <div v-else class="chart-placeholder">请选择站点以查看数据趋势</div>
      </div>
    </div>

    <!-- Table -->
    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">观测数据</span>
        <span class="mono">{{ queryParams.metricType || 'ALL METRICS' }}</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="stationName" label="站点" min-width="150" />
        <el-table-column prop="metricType" label="指标类型" width="100">
          <template #default="{ row }">{{ metricTypeMap[row.metricType] || row.metricType }}</template>
        </el-table-column>
        <el-table-column prop="value" label="数值" width="100">
          <template #default="{ row }">{{ formatNumber(row.value) }}</template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="qualityFlag" label="质量标志" width="100">
          <template #default="{ row }">
            <el-tag :type="row.qualityFlag === 'GOOD' ? 'success' : row.qualityFlag === 'SUSPECT' ? 'danger' : 'warning'" size="small">
              {{ row.qualityFlag }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="observedAt" label="观测时间" width="170">
          <template #default="{ row }">{{ formatDate(row.observedAt) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="数据来源" width="120" />
      </el-table>
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="fetchData"
        @current-change="fetchData"
      />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getObservations } from '@/api/observation'
import { getStations } from '@/api/station'
import { formatDate, formatApiDateTime, formatNumber, metricTypeMap } from '@/utils/format'
import type { Observation, MetricType, Station } from '@/types'

const loading = ref(false)
const tableData = ref<Observation[]>([])
const total = ref(0)
const chartRef = ref<HTMLElement>()
const chartType = ref('line')
let chart: echarts.ECharts | null = null

const queryParams = reactive({ page: 1, size: 20, stationId: '', metricType: '' as '' | MetricType, start: '', end: '' })
const dateRange = ref<string[]>([])

function initDefaultDateRange() {
  const end = new Date()
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000)
  dateRange.value = [formatApiDateTime(start), formatApiDateTime(end)]
}

const stationTypeToMetric: Record<string, MetricType> = {
  WATER_LEVEL: 'WATER_LEVEL',
  RAIN_GAUGE: 'RAINFALL',
  FLOW: 'FLOW',
  RESERVOIR: 'RESERVOIR_LEVEL',
  GATE: 'GATE_OPENING',
  PUMP_STATION: 'PUMP_POWER',
}

const stationList = ref<Station[]>([])
async function loadStations() {
  try {
    const res = await getStations({ page: 1, size: 200, status: 'ACTIVE' } as any)
    stationList.value = res.data?.records || []
    if (!queryParams.stationId && stationList.value.length > 0) {
      selectStation(stationList.value[0].id)
    }
  } catch { /* ignore */ }
}

function selectStation(stationId: string) {
  queryParams.stationId = stationId
  const station = stationList.value.find((s) => s.id === stationId)
  queryParams.metricType = station ? (stationTypeToMetric[station.type] || 'WATER_LEVEL') : ''
}

// Chart-specific data, independent from pagination
const chartRawData = ref<Observation[]>([])
const chartLoading = ref(false)

const metricUnitMap: Record<MetricType, string> = {
  WATER_LEVEL: 'm',
  RAINFALL: 'mm',
  FLOW: 'm³/s',
  RESERVOIR_LEVEL: 'm',
  GATE_OPENING: '%',
  PUMP_POWER: 'kW',
}

const canShowChart = computed(() => !!queryParams.stationId)
const metricUnit = computed(() => queryParams.metricType ? metricUnitMap[queryParams.metricType] || '' : '')
const metricLabel = computed(() => queryParams.metricType ? (metricTypeMap[queryParams.metricType] || queryParams.metricType) : '')

const chartData = computed(() =>
  chartRawData.value.map((o) => [o.observedAt, o.value]).sort((a, b) => String(a[0]).localeCompare(String(b[0])))
)
const maxValue = computed(() => {
  const values = chartRawData.value.map((item) => Number(item.value)).filter(Number.isFinite)
  if (values.length === 0) return '—'
  return formatNumber(Math.max(...values))
})
const goodCount = computed(() => chartRawData.value.filter((item) => item.qualityFlag === 'GOOD').length)

async function fetchData() {
  loading.value = true
  if (dateRange.value?.length === 2) {
    queryParams.start = dateRange.value[0]
    queryParams.end = dateRange.value[1]
  }
  try {
    const res = await getObservations(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function fetchChartData() {
  if (!canShowChart.value) {
    chartRawData.value = []
    updateChart()
    return
  }
  chartLoading.value = true
  if (dateRange.value?.length === 2) {
    queryParams.start = dateRange.value[0]
    queryParams.end = dateRange.value[1]
  }
  try {
    const res = await getObservations({
      page: 1,
      size: 500,
      stationId: queryParams.stationId,
      metricType: queryParams.metricType,
      start: queryParams.start,
      end: queryParams.end,
    } as any)
    chartRawData.value = (res.data?.records || []).sort(
      (a: Observation, b: Observation) => a.observedAt.localeCompare(b.observedAt)
    )
    updateChart()
  } finally {
    chartLoading.value = false
  }
}

function updateChart() {
  if (!chartRef.value) {
    chart?.dispose()
    chart = null
    return
  }
  // Re-init if container was recreated (v-if toggle)
  if (chart && chart.getDom() !== chartRef.value) {
    chart.dispose()
    chart = null
  }
  if (!chart) chart = echarts.init(chartRef.value)

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0b1220',
      borderColor: '#1f2a3f',
      textStyle: { color: '#e8eef8' },
    },
    grid: { left: 50, right: 20, top: 24, bottom: 34 },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: '#1f2a3f' } },
      axisLabel: { color: '#6a7590', fontFamily: 'JetBrains Mono, monospace' },
      splitLine: { lineStyle: { color: '#1f2a3f', type: 'dashed' } },
    },
    yAxis: {
      type: 'value',
      name: metricLabel.value ? `${metricLabel.value}${metricUnit.value ? ` (${metricUnit.value})` : ''}` : '',
      nameTextStyle: { color: '#6a7590', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      axisLine: { lineStyle: { color: '#1f2a3f' } },
      axisLabel: { color: '#6a7590', fontFamily: 'JetBrains Mono, monospace' },
      splitLine: { lineStyle: { color: '#1f2a3f', type: 'dashed' } },
    },
    series: [{
      type: chartType.value,
      data: chartData.value,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      itemStyle: { color: '#49e1ff' },
      lineStyle: { color: '#49e1ff', width: 2 },
      areaStyle: chartType.value === 'line'
        ? { color: 'rgba(73, 225, 255, 0.14)' }
        : undefined,
    }],
  }, true)
}

watch(chartType, updateChart)

function handleSearch() { queryParams.page = 1; fetchData(); fetchChartData() }
function handleReset() {
  queryParams.page = 1
  initDefaultDateRange()
  selectStation(stationList.value.length > 0 ? stationList.value[0].id : '')
  handleSearch()
}

watch(() => queryParams.stationId, () => {
  if (canShowChart.value) fetchChartData()
  else { chartRawData.value = []; updateChart() }
})

function handleResize() { chart?.resize() }

onMounted(async () => {
  initDefaultDateRange()
  await loadStations()
  fetchData()
  // fetchChartData triggered by watcher after loadStations sets default stationId
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => { chart?.dispose(); window.removeEventListener('resize', handleResize) })
</script>

<style scoped>
.chart-container { height: 300px; }
.chart-placeholder {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6a7590;
  font-size: 14px;
}
</style>
