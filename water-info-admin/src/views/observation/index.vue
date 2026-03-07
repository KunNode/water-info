<template>
  <div class="page-container">
    <div class="search-bar">
      <el-form :model="queryParams" inline>
        <el-form-item label="站点">
          <el-input v-model="queryParams.stationId" placeholder="站点ID" clearable />
        </el-form-item>
        <el-form-item label="指标类型">
          <el-select v-model="queryParams.metricType" placeholder="全部" clearable>
            <el-option v-for="(label, key) in metricTypeMap" :key="key" :label="label" :value="key" />
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
    <el-card shadow="hover" style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span>数据趋势</span>
          <el-radio-group v-model="chartType" size="small">
            <el-radio-button value="line">折线图</el-radio-button>
            <el-radio-button value="bar">柱状图</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <div ref="chartRef" class="chart-container"></div>
    </el-card>

    <!-- Table -->
    <div class="table-card">
      <div class="table-header">
        <span class="table-title">观测数据</span>
      </div>
      <el-table v-loading="loading" :data="tableData" border stripe>
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
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getObservations } from '@/api/observation'
import { formatDate, formatNumber, metricTypeMap } from '@/utils/format'
import type { Observation, MetricType } from '@/types'

const loading = ref(false)
const tableData = ref<Observation[]>([])
const total = ref(0)
const chartRef = ref<HTMLElement>()
const chartType = ref('line')
const dateRange = ref<string[]>([])
let chart: echarts.ECharts | null = null

const queryParams = reactive({ page: 1, size: 20, stationId: '', metricType: '' as '' | MetricType, start: '', end: '' })

// Memoize chart data - only recomputed when tableData changes
const chartData = computed(() => tableData.value.map((o) => [o.observedAt, o.value]))

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
    updateChart()
  } finally {
    loading.value = false
  }
}

function updateChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)

  // Use memoized computed data instead of mapping on every render
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'time' },
    yAxis: { type: 'value' },
    series: [{ type: chartType.value, data: chartData.value, smooth: true, areaStyle: chartType.value === 'line' ? { opacity: 0.1 } : undefined }],
  }, true)
}

watch(chartType, updateChart)

function handleSearch() { queryParams.page = 1; fetchData() }
function handleReset() { queryParams.stationId = ''; queryParams.metricType = ''; dateRange.value = []; queryParams.start = ''; queryParams.end = ''; handleSearch() }

function handleResize() { chart?.resize() }

onMounted(() => { fetchData(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { chart?.dispose(); window.removeEventListener('resize', handleResize) })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.chart-container { height: 300px; }
.table-title { font-size: 16px; font-weight: 600; }
</style>
