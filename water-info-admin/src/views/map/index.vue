<template>
  <div class="fm-map-page">
    <div class="fm-page-head">
      <h1>流域地图</h1>
      <span class="sub">// realtime map · station markers · alarm layer</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ filteredStations.length }} stations</span>
    </div>

    <div class="fm-map-shell">
      <div class="fm-map-side fm-card">
        <div class="fm-card__head">
          <span class="title">图层控制</span>
          <span class="mono">layers</span>
        </div>
        <div class="fm-card__body">
          <span class="fm-label-sm">站点类型</span>
          <el-select v-model="filterType" placeholder="全部站点" clearable style="width: 100%">
            <el-option v-for="(label, key) in stationTypeMap" :key="key" :label="label" :value="key" />
          </el-select>

          <div class="fm-divider" />

          <div class="fm-map-layer on"><span class="fm-switch on" />水系基础</div>
          <div class="fm-map-layer on"><span class="fm-switch on" />站点标记</div>
          <div class="fm-map-layer on"><span class="fm-switch on" />实时告警</div>
          <div class="fm-map-layer"><span class="fm-switch" />雨量热力</div>

          <div class="fm-divider" />

          <span class="fm-label-sm">状态图例</span>
          <div class="legend">
            <span class="legend-item"><i class="fm-dot ok" />正常</span>
            <span class="legend-item"><i class="fm-dot danger" />告警</span>
            <span class="legend-item"><i class="fm-dot off" />离线/维护</span>
          </div>
        </div>
      </div>

      <div class="fm-map-main fm-card">
        <div class="fm-map-floating">
          <span class="fm-chip">30.88N 114.34E</span>
          <span class="fm-chip">zoom 11</span>
          <span class="fm-chip"><span class="ind" />live</span>
        </div>
        <div ref="mapRef" class="map-container"></div>
      </div>
    </div>
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
.fm-map-page {
  min-height: calc(100vh - var(--fm-topbar-h) - var(--fm-tags-h) - 44px);
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 16px;
}
.fm-map-shell {
  min-height: 640px;
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
}
.fm-map-side {
  overflow: hidden;
}
.fm-map-layer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--fm-radius-sm);
  color: var(--fm-fg-soft);
  font-size: 12.5px;
}
.fm-map-layer.on {
  background: rgba(73, 225, 255, 0.08);
  color: var(--fm-fg);
}
.legend {
  display: grid;
  gap: 10px;
  font-size: 12.5px;
  color: var(--fm-fg-soft);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.fm-map-main {
  position: relative;
  overflow: hidden;
  min-height: 640px;
}
.fm-map-floating {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  gap: 8px;
  z-index: 5;
}
.map-container {
  width: 100%;
  height: 100%;
  min-height: 640px;
  z-index: 0;
}
@media (max-width: 1100px) {
  .fm-map-shell {
    grid-template-columns: 1fr;
  }
  .fm-map-main,
  .map-container {
    min-height: 520px;
  }
}
</style>
