<template>
  <div class="map-page">
    <div class="map-toolbar">
      <el-select v-model="filterType" placeholder="站点类型" clearable size="small" style="width: 140px" @change="updateMarkers">
        <el-option v-for="(label, key) in stationTypeMap" :key="key" :label="label" :value="key" />
      </el-select>
      <el-tag size="small" effect="plain" style="margin-left: 12px">
        共 {{ filteredStations.length }} 个站点
      </el-tag>
      <div class="legend">
        <span class="legend-item"><i class="dot" style="background: #67C23A"></i>正常</span>
        <span class="legend-item"><i class="dot" style="background: #F56C6C"></i>告警</span>
        <span class="legend-item"><i class="dot" style="background: #909399"></i>离线</span>
      </div>
    </div>
    <div ref="mapRef" class="map-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { getStations } from '@/api/station'
import { stationTypeMap } from '@/utils/format'
import type { Station } from '@/types'

const mapRef = ref<HTMLElement>()
const stations = ref<Station[]>([])
const filterType = ref('')
let map: L.Map | null = null
let markerGroup: L.LayerGroup | null = null

const filteredStations = computed(() => {
  if (!filterType.value) return stations.value
  return stations.value.filter((s) => s.type === filterType.value)
})

function getMarkerColor(status: string): string {
  if (status === 'ACTIVE') return '#67C23A'
  if (status === 'MAINTENANCE') return '#E6A23C'
  return '#909399'
}

function createCircleIcon(color: string) {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.3)"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

function updateMarkers() {
  if (!map || !markerGroup) return
  markerGroup.clearLayers()

  filteredStations.value.forEach((station) => {
    if (!station.lat || !station.lon) return

    const color = getMarkerColor(station.status)
    const marker = L.marker([station.lat, station.lon], { icon: createCircleIcon(color) })

    marker.bindPopup(`
      <div style="min-width:180px">
        <h4 style="margin:0 0 8px">${station.name}</h4>
        <p style="margin:2px 0;font-size:13px">编码：${station.code}</p>
        <p style="margin:2px 0;font-size:13px">类型：${stationTypeMap[station.type] || station.type}</p>
        <p style="margin:2px 0;font-size:13px">流域：${station.riverBasin || '-'}</p>
        <p style="margin:2px 0;font-size:13px">行政区：${station.adminRegion || '-'}</p>
        <p style="margin:2px 0;font-size:13px">高程：${station.elevation || '-'} m</p>
        <p style="margin:2px 0;font-size:13px">状态：<span style="color:${color};font-weight:600">${station.status === 'ACTIVE' ? '正常' : station.status === 'MAINTENANCE' ? '维护中' : '离线'}</span></p>
      </div>
    `)

    markerGroup!.addLayer(marker)
  })

  // Fit bounds if stations exist
  if (filteredStations.value.length > 0) {
    const validStations = filteredStations.value.filter((s) => s.lat && s.lon)
    if (validStations.length > 0) {
      const bounds = L.latLngBounds(validStations.map((s) => [s.lat, s.lon] as [number, number]))
      map.fitBounds(bounds, { padding: [50, 50] })
    }
  }
}

async function loadStations() {
  try {
    const res = await getStations({ page: 1, size: 1000 })
    stations.value = res.data?.records || []
    updateMarkers()
  } catch {
    // Fallback: show empty map
  }
}

function initMap() {
  if (!mapRef.value) return

  map = L.map(mapRef.value, {
    center: [30.5, 114.3], // Default: Wuhan area
    zoom: 8,
    zoomControl: true,
  })

  // Use OpenStreetMap tiles
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18,
  }).addTo(map)

  markerGroup = L.layerGroup().addTo(map)
}

watch(filterType, updateMarkers)

onMounted(() => {
  initMap()
  loadStations()
})

onUnmounted(() => {
  map?.remove()
  map = null
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
  z-index: 500;
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

// Fix leaflet icon default paths
:deep(.custom-marker) {
  background: transparent;
  border: none;
}
</style>
