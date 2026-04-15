<template>
  <div class="map-page">
    <div class="map-toolbar">
      <el-select v-model="filterType" placeholder="站点类型" clearable size="small" style="width: 140px">
        <el-option v-for="(label, key) in stationTypeMap" :key="key" :label="label" :value="key" />
      </el-select>
      <el-tag size="small" effect="plain" style="margin-left: 12px">共 {{ filteredStations.length }} 个站点</el-tag>
      <div class="legend">
        <span class="legend-item"><i class="dot" style="background: #67c23a"></i>正常</span>
        <span class="legend-item"><i class="dot" style="background: #f56c6c"></i>告警</span>
        <span class="legend-item"><i class="dot" style="background: #909399"></i>离线/维护</span>
      </div>
    </div>
    <div ref="mapRef" class="map-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { getStations } from '@/api/station'
import { getAlarms } from '@/api/alarm'
import { getLatestObservations, type LatestObservationBatchItem } from '@/api/observation'
import { stationTypeMap } from '@/utils/format'
import { useLakeMap, type StationMarker } from '@/composables/useLakeMap'
import type { Station, MetricType } from '@/types'

const mapRef = ref<HTMLElement>()
const stations = ref<Station[]>([])
const filterType = ref('')
const { init, updateStations, resize, dispose } = useLakeMap(mapRef)

const filteredStations = computed(() => {
  if (!filterType.value) return stations.value
  return stations.value.filter((s) => s.type === filterType.value)
})

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

async function refreshMap() {
  try {
    const alarmsRes = await getAlarms({ page: 1, size: 50, status: 'OPEN' })
    const alarmStationIds = new Set((alarmsRes.data?.records || []).map((a) => a.stationId))
    const markers: StationMarker[] = []
    const observationItems: LatestObservationBatchItem[] = filteredStations.value.flatMap((station) => {
      const metric = stationMetricType[station.type]
      return metric ? [{ stationId: station.id, metricType: metric }] : []
    })
    const latestObservationMap = new Map<string, number>()

    if (observationItems.length > 0) {
      const latestRes = await getLatestObservations(observationItems)
      ;(latestRes.data || []).forEach((observation) => {
        latestObservationMap.set(
          buildObservationKey(observation.stationId, observation.metricType),
          observation.value,
        )
      })
    }

    filteredStations.value.forEach((station) => {
      const metric = stationMetricType[station.type]
      if (!metric) {
        markers.push({ station, hasAlarm: alarmStationIds.has(station.id) })
        return
      }

      markers.push({
        station,
        latestValue: latestObservationMap.get(buildObservationKey(station.id, metric)) ?? null,
        unit: metricUnits[metric],
        hasAlarm: alarmStationIds.has(station.id),
      })
    })

    updateStations(markers)
  } catch {
    updateStations([])
  }
}

async function loadStations() {
  try {
    const res = await getStations({ page: 1, size: 1000 })
    stations.value = res.data?.records || []
    await refreshMap()
  } catch {
    stations.value = []
    updateStations([])
  }
}

watch(filterType, () => {
  refreshMap()
})

function handleResize() {
  resize()
}

onMounted(() => {
  init()
  loadStations()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  dispose()
})
</script>

<style scoped lang="scss">
.map-page {
  height: calc(100vh - 84px);
  display: flex;
  flex-direction: column;
}
.map-toolbar {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  z-index: 5;
}
.legend {
  display: flex;
  gap: 16px;
  margin-left: auto;
  font-size: 13px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.map-container {
  flex: 1;
  z-index: 0;
}
</style>
