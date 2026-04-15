import { type Ref, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import svgRaw from '@/assets/cuiping-lake.svg?raw'
import type { Station } from '@/types'
import { stationStatusMap, stationTypeMap } from '@/utils/format'

const STATION_POSITIONS: Record<string, [number, number]> = {
  ST_RAIN_CP_01: [220, 140],
  ST_RAIN_CP_02: [600, 160],
  ST_WL_CP_01: [400, 330],
  ST_WL_CP_02: [490, 290],
  ST_FLOW_CP_01: [440, 450],
  ST_RES_CP_01: [400, 305],
  ST_GATE_CP_01: [440, 490],
  ST_PUMP_CP_01: [560, 240],
}

const TYPE_COLORS: Record<string, string> = {
  RAIN_GAUGE: '#67C23A',
  WATER_LEVEL: '#409EFF',
  FLOW: '#E6A23C',
  RESERVOIR: '#F56C6C',
  GATE: '#909399',
  PUMP_STATION: '#8B5CF6',
}

const TYPE_SYMBOLS: Record<string, string> = {
  RAIN_GAUGE: 'circle',
  WATER_LEVEL: 'diamond',
  FLOW: 'triangle',
  RESERVOIR: 'rect',
  GATE: 'roundRect',
  PUMP_STATION: 'pin',
}

const UNAVAILABLE_COLOR = '#909399'

export interface StationMarker {
  station: Station
  latestValue?: number | null
  unit?: string
  hasAlarm?: boolean
  alarmLevel?: string
}

export function useLakeMap(containerRef: Ref<HTMLElement | undefined>) {
  let chart: echarts.ECharts | null = null

  function isUnavailable(status: Station['status']) {
    return status === 'INACTIVE' || status === 'MAINTENANCE'
  }

  function init() {
    if (!containerRef.value) return

    const svgDataUri = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgRaw)}`
    containerRef.value.style.backgroundImage = `url("${svgDataUri}")`
    containerRef.value.style.backgroundSize = '100% 100%'
    containerRef.value.style.backgroundRepeat = 'no-repeat'

    chart = echarts.init(containerRef.value)
    chart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 0, right: 0, top: 0, bottom: 0, containLabel: false },
      xAxis: { type: 'value', min: 0, max: 800, show: false },
      yAxis: { type: 'value', min: 0, max: 600, show: false, inverse: true },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(10, 26, 46, 0.9)',
        borderColor: 'rgba(0, 212, 255, 0.4)',
        textStyle: { color: '#fff', fontSize: 13 },
        formatter: (params: any) => {
          const d = params.data
          if (!d?.station) return ''
          const typeLabel = stationTypeMap[d.station.type] || d.station.type
          const statusLabel = stationStatusMap[d.station.status] || d.station.status
          let html = `<div style="font-weight:bold;margin-bottom:6px;color:#00d4ff">${d.station.name}</div>`
          html += `<div>类型：${typeLabel}</div>`
          html += `<div>编码：${d.station.code}</div>`
          html += `<div>状态：${statusLabel}</div>`
          if (d.latestValue != null) {
            html += `<div style="margin-top:4px;color:#00d4ff;font-size:15px;font-weight:bold">${d.latestValue} ${d.unit || ''}</div>`
          }
          if (d.hasAlarm) {
            html += '<div style="margin-top:4px;color:#F56C6C">存在活跃告警</div>'
          }
          return html
        },
      },
      series: [],
    })
  }

  function updateStations(markers: StationMarker[]) {
    if (!chart) return

    const normalData: any[] = []
    const alarmData: any[] = []

    for (const m of markers) {
      const pos = STATION_POSITIONS[m.station.code]
      if (!pos) continue

      const unavailable = isUnavailable(m.station.status)
      const color = unavailable ? UNAVAILABLE_COLOR : (TYPE_COLORS[m.station.type] || '#409EFF')
      const symbol = TYPE_SYMBOLS[m.station.type] || 'circle'

      const point = {
        value: [pos[0], pos[1]],
        station: m.station,
        latestValue: m.latestValue,
        unit: m.unit || '',
        hasAlarm: m.hasAlarm,
        itemStyle: {
          color,
          borderColor: unavailable ? 'rgba(255,255,255,0.65)' : '#fff',
          borderWidth: 1.5,
          opacity: unavailable ? 0.75 : 1,
        },
        symbol,
        symbolSize: unavailable ? 12 : 14,
      }

      if (m.hasAlarm) {
        alarmData.push({
          ...point,
          symbolSize: 18,
          itemStyle: { ...point.itemStyle, color: '#F56C6C' },
        })
      } else {
        normalData.push(point)
      }
    }

    chart.setOption(
      {
        series: [
          {
            name: '监测站点',
            type: 'scatter',
            data: normalData,
            z: 10,
            label: {
              show: true,
              formatter: (p: any) => p.data.station.name,
              position: 'bottom',
              color: 'rgba(255,255,255,0.7)',
              fontSize: 10,
              distance: 6,
            },
          },
          {
            name: '告警站点',
            type: 'effectScatter',
            data: alarmData,
            z: 20,
            rippleEffect: { brushType: 'stroke', scale: 4, period: 3 },
            label: {
              show: true,
              formatter: (p: any) => p.data.station.name,
              position: 'bottom',
              color: '#F56C6C',
              fontSize: 10,
              fontWeight: 'bold',
              distance: 6,
            },
          },
        ],
      },
      { replaceMerge: ['series'] },
    )
  }

  function resize() {
    chart?.resize()
  }

  function dispose() {
    chart?.dispose()
    chart = null
    if (containerRef.value) {
      containerRef.value.style.backgroundImage = ''
    }
  }

  onUnmounted(dispose)

  return { init, updateStations, resize, dispose }
}
