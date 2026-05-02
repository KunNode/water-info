<template>
  <div class="lake-stage">
    <svg
      class="lake-stage__scene"
      viewBox="0 0 1200 900"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <filter id="ls-glow"><feGaussianBlur stdDeviation="3" /></filter>
        <filter id="ls-soft-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" />
        </filter>
        <linearGradient id="ls-vignette" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="rgba(6,10,20,0.45)" />
          <stop offset="40%" stop-color="rgba(6,10,20,0)" />
          <stop offset="100%" stop-color="rgba(6,10,20,0.35)" />
        </linearGradient>
        <marker id="ls-flow-head" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M 0 0 L 12 6 L 0 12 L 3 6 Z" fill="rgba(140,235,255,0.95)" />
        </marker>

        <!-- Type icons (centred at origin) -->
        <symbol id="icon-water-level" viewBox="-9 -9 18 18">
          <path d="M -7 -2 Q -3.5 -6 0 -2 T 7 -2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          <path d="M -7 3 Q -3.5 -1 0 3 T 7 3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        </symbol>
        <symbol id="icon-rain-gauge" viewBox="-9 -9 18 18">
          <path d="M 0 -7 C -4.5 -2 -6 1 -6 3 A 6 6 0 1 0 6 3 C 6 1 4.5 -2 0 -7 Z" fill="currentColor" />
        </symbol>
        <symbol id="icon-flow" viewBox="-9 -9 18 18">
          <path d="M -6 -4 L 0 0 L -6 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M 0 -4 L 6 0 L 0 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
        </symbol>
        <symbol id="icon-reservoir" viewBox="-9 -9 18 18">
          <path d="M -6 5 L -4 -4 L 4 -4 L 6 5 Z" fill="currentColor" opacity="0.85" />
          <line x1="-6" y1="5" x2="6" y2="5" stroke="currentColor" stroke-width="1.4" />
          <line x1="-2" y1="-4" x2="-2" y2="5" stroke="rgba(6,10,20,0.6)" stroke-width="1" />
          <line x1="2" y1="-4" x2="2" y2="5" stroke="rgba(6,10,20,0.6)" stroke-width="1" />
        </symbol>
        <symbol id="icon-gate" viewBox="-9 -9 18 18">
          <rect x="-6" y="-5" width="12" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1.5" />
          <line x1="-6" y1="0" x2="6" y2="0" stroke="currentColor" stroke-width="1.4" />
          <line x1="-2.5" y1="-5" x2="-2.5" y2="5" stroke="currentColor" stroke-width="1.2" />
          <line x1="2.5" y1="-5" x2="2.5" y2="5" stroke="currentColor" stroke-width="1.2" />
        </symbol>
        <symbol id="icon-pump" viewBox="-9 -9 18 18">
          <circle r="6.5" fill="none" stroke="currentColor" stroke-width="1.5" />
          <text x="0" y="3.6" text-anchor="middle" font-size="10" font-weight="700" font-family="JetBrains Mono, monospace" fill="currentColor">P</text>
        </symbol>
        <symbol id="icon-station" viewBox="-9 -9 18 18">
          <circle r="3.5" fill="currentColor" />
        </symbol>
      </defs>

      <!-- Aerial photo of Cuiping Lake basin -->
      <image
        href="/image/backgrand.png"
        x="0" y="0"
        width="1200" height="900"
        preserveAspectRatio="xMidYMid slice"
      />
      <!-- Top/bottom vignette to keep top bar and legend readable -->
      <rect x="0" y="0" width="1200" height="900" fill="url(#ls-vignette)" />

      <!-- Flow arrows along the basin (upstream → dam → downstream) -->
      <g v-show="layers.flowArrows" class="lake-stage__flow">
        <path
          d="M 540 180 Q 520 300 540 420 Q 560 480 600 530"
          fill="none"
          stroke="rgba(140,235,255,0.85)"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-dasharray="10 16"
          marker-end="url(#ls-flow-head)"
          filter="url(#ls-soft-glow)"
        >
          <animate attributeName="stroke-dashoffset" from="0" to="-52" dur="2.2s" repeatCount="indefinite" />
        </path>
        <path
          d="M 600 540 Q 660 600 700 650"
          fill="none"
          stroke="rgba(140,235,255,0.85)"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-dasharray="10 16"
          marker-end="url(#ls-flow-head)"
          filter="url(#ls-soft-glow)"
        >
          <animate attributeName="stroke-dashoffset" from="0" to="-52" dur="2s" repeatCount="indefinite" />
        </path>
        <path
          d="M 720 680 Q 780 730 850 770"
          fill="none"
          stroke="rgba(140,235,255,0.95)"
          stroke-width="2.6"
          stroke-linecap="round"
          stroke-dasharray="10 16"
          marker-end="url(#ls-flow-head)"
          filter="url(#ls-soft-glow)"
        >
          <animate attributeName="stroke-dashoffset" from="0" to="-52" dur="1.7s" repeatCount="indefinite" />
        </path>
        <path
          d="M 920 360 Q 820 420 700 470"
          fill="none"
          stroke="rgba(140,235,255,0.65)"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-dasharray="8 14"
          marker-end="url(#ls-flow-head)"
          filter="url(#ls-soft-glow)"
        >
          <animate attributeName="stroke-dashoffset" from="0" to="-44" dur="2.6s" repeatCount="indefinite" />
        </path>
        <path
          d="M 280 480 Q 380 460 480 470"
          fill="none"
          stroke="rgba(140,235,255,0.55)"
          stroke-width="1.6"
          stroke-linecap="round"
          stroke-dasharray="8 14"
          marker-end="url(#ls-flow-head)"
          filter="url(#ls-soft-glow)"
        >
          <animate attributeName="stroke-dashoffset" from="0" to="-44" dur="2.8s" repeatCount="indefinite" />
        </path>
      </g>

      <!-- Station markers -->
      <g v-for="m in placedMarkers" :key="m.station.id" :transform="`translate(${m.x} ${m.y})`">
        <!-- Base ripple on water for critical stations -->
        <template v-if="m.severity === 'critical'">
          <circle r="22" fill="rgba(255,90,106,0.18)">
            <animate attributeName="r" values="14;30;14" dur="1.6s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.55;0.05;0.55" dur="1.6s" repeatCount="indefinite" />
          </circle>
          <circle r="14" fill="none" stroke="rgba(255,90,106,0.5)" stroke-width="1">
            <animate attributeName="r" values="8;20;8" dur="1.6s" begin="0.4s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.6;0;0.6" dur="1.6s" begin="0.4s" repeatCount="indefinite" />
          </circle>
        </template>

        <!-- Anchor dot at the station's geographical point -->
        <circle r="3.6" :fill="markerAccent(m)" />
        <circle r="6" fill="none" :stroke="markerAccent(m)" stroke-opacity="0.45" stroke-width="1" />

        <!-- Vertical connector to pin head -->
        <line
          x1="0"
          y1="-4"
          x2="0"
          y2="-30"
          :stroke="markerAccent(m)"
          stroke-width="1.4"
          stroke-dasharray="2 2"
          stroke-opacity="0.75"
        />

        <!-- Pin head with type icon -->
        <g :transform="`translate(0 ${m.severity === 'critical' ? -46 : -42})`">
          <circle
            :r="m.severity === 'critical' ? 16 : 13"
            fill="rgba(11,18,32,0.88)"
            :stroke="markerAccent(m)"
            stroke-width="1.6"
          />
          <use
            :href="`#icon-${typeIcon(m.station.type)}`"
            :width="m.severity === 'critical' ? 22 : 18"
            :height="m.severity === 'critical' ? 22 : 18"
            :x="m.severity === 'critical' ? -11 : -9"
            :y="m.severity === 'critical' ? -11 : -9"
            :style="{ color: markerAccent(m) }"
          />
        </g>

        <!-- Critical: stacked badge + station name + value -->
        <template v-if="m.severity === 'critical'">
          <!-- CRIT badge -->
          <g transform="translate(0 -76)">
            <rect x="-26" y="-10" width="52" height="18" rx="3"
                  fill="rgba(255,90,106,0.18)" stroke="#ff5a6a" stroke-width="1" />
            <text x="0" y="3.5" text-anchor="middle" fill="#ff5a6a"
                  font-size="11" font-weight="700" letter-spacing="2"
                  font-family="JetBrains Mono, monospace">CRIT</text>
          </g>
          <!-- Station name above badge -->
          <text x="0" y="-100" text-anchor="middle" fill="#ffffff"
                font-size="13" font-weight="700"
                stroke="rgba(6,10,20,0.85)" stroke-width="3" paint-order="stroke fill">
            {{ m.station.name }}
          </text>
          <!-- Value below pin -->
          <text v-if="m.latestValue != null" x="0" y="14" text-anchor="middle"
                fill="#ffffff" font-size="15" font-weight="700"
                font-family="JetBrains Mono, monospace"
                stroke="rgba(6,10,20,0.85)" stroke-width="3" paint-order="stroke fill">
            {{ formatValue(m.latestValue) }}<tspan font-size="11" fill="#a9b3c6">{{ ' ' + (m.unit ?? '') }}</tspan>
          </text>
        </template>

        <!-- High / medium: name to side, value below -->
        <template v-else-if="m.severity !== 'normal'">
          <text x="20" y="-46" :fill="severityColor(m.severity)"
                font-size="11" font-weight="700"
                font-family="JetBrains Mono, monospace"
                stroke="rgba(6,10,20,0.85)" stroke-width="3" paint-order="stroke fill">
            {{ severityLabel(m.severity) }}
          </text>
          <text x="20" y="-32" fill="#ffffff" font-size="12" font-weight="600"
                stroke="rgba(6,10,20,0.85)" stroke-width="3" paint-order="stroke fill">
            {{ m.station.name }}
          </text>
          <text v-if="m.latestValue != null" x="20" y="-18"
                fill="#dbe4f5" font-size="11" font-weight="700"
                font-family="JetBrains Mono, monospace"
                stroke="rgba(6,10,20,0.85)" stroke-width="3" paint-order="stroke fill">
            {{ formatValue(m.latestValue) }}<tspan font-size="9" fill="#8693af">{{ ' ' + (m.unit ?? '') }}</tspan>
          </text>
        </template>

        <!-- Normal: just the station name to the right of pin head -->
        <template v-else>
          <text x="20" y="-38" fill="#dbe4f5" font-size="11" font-weight="600"
                stroke="rgba(6,10,20,0.85)" stroke-width="3" paint-order="stroke fill">
            {{ m.station.name }}
          </text>
          <text v-if="m.latestValue != null" x="20" y="-24"
                fill="#a9b3c6" font-size="10"
                font-family="JetBrains Mono, monospace"
                stroke="rgba(6,10,20,0.85)" stroke-width="3" paint-order="stroke fill">
            {{ formatValue(m.latestValue) }}<tspan font-size="8">{{ ' ' + (m.unit ?? '') }}</tspan>
          </text>
        </template>
      </g>
    </svg>

    <!-- Legend / data layer panel -->
    <div class="lake-stage__legend">
      <div class="legend-block">
        <div class="legend-block__title">图例 <span>LEGEND</span></div>
        <div class="legend-grid">
          <div v-for="t in legendTypes" :key="t.key" class="legend-item">
            <span class="legend-item__icon" :style="{ color: t.color }">
              <svg viewBox="-9 -9 18 18" width="14" height="14">
                <use :href="`#icon-${t.icon}`" />
              </svg>
            </span>
            <span class="legend-item__name">{{ t.label }}</span>
          </div>
        </div>
      </div>
      <div class="legend-block">
        <div class="legend-block__title">数据图层 <span>LAYERS</span></div>
        <div class="legend-toggles">
          <label v-for="l in layerOptions" :key="l.key" class="legend-toggle">
            <input type="checkbox" v-model="layers[l.key]" />
            <span class="legend-toggle__box"></span>
            <span class="legend-toggle__name">{{ l.label }}</span>
          </label>
        </div>
      </div>
    </div>

    <div class="lake-stage__corner">
      CENTRAL · <b>CUIPING LAKE · AERIAL VIEW</b> · 实景底图
    </div>
    <div class="lake-stage__axes">
      <span>N ↑</span><span>SCALE 1 : 5,000</span><span>WGS84</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import type { StationMarker } from '@/composables/useLakeMap'
import type { Station } from '@/types'

const props = defineProps<{
  markers: StationMarker[]
}>()

// Placement in the 1200×900 viewBox aligned with public/image/backgrand.png.
// Coordinates correspond to recognisable features in the aerial photo.
const STATION_POSITIONS_3D: Record<string, [number, number]> = {
  ST_RAIN_CP_01: [220, 230],   // 北溪雨量站 — 西北山脊
  ST_RAIN_CP_02: [1010, 290],  // 南溪雨量站 — 东北山脊
  ST_RES_CP_01:  [240, 540],   // 水库站 — 西侧库湾
  ST_WL_CP_02:   [560, 250],   // 北岸水位站 — 入湖口
  ST_WL_CP_01:   [560, 460],   // 湖心水位站 — 湖中心
  ST_GATE_CP_01: [700, 660],   // 闸站 — 大坝闸门
  ST_FLOW_CP_01: [820, 740],   // 出湖流量站 — 大坝下游断面
  ST_PUMP_CP_01: [1020, 800],  // 城区泵站 — 东南前景
}

type Severity = 'critical' | 'high' | 'medium' | 'normal'

interface PlacedMarker extends StationMarker {
  x: number
  y: number
  severity: Severity
  unavailable: boolean
}

const TYPE_ICON: Record<Station['type'], string> = {
  WATER_LEVEL: 'water-level',
  RAIN_GAUGE: 'rain-gauge',
  FLOW: 'flow',
  RESERVOIR: 'reservoir',
  GATE: 'gate',
  PUMP_STATION: 'pump',
}

const TYPE_COLOR: Record<Station['type'], string> = {
  WATER_LEVEL: '#49e1ff',
  RAIN_GAUGE: '#7aa2ff',
  FLOW: '#2bd99f',
  RESERVOIR: '#ffb547',
  GATE: '#ff8da3',
  PUMP_STATION: '#c79bff',
}

function typeIcon(type: Station['type']): string {
  return TYPE_ICON[type] ?? 'station'
}

function severityFromAlarmLevel(level?: string): Severity {
  switch (level) {
    case 'CRITICAL':
      return 'critical'
    case 'HIGH':
      return 'high'
    case 'MEDIUM':
      return 'medium'
    default:
      return 'normal'
  }
}

function severityColor(s: Severity) {
  return s === 'critical' ? '#ff5a6a' : s === 'high' ? '#ffb547' : '#7aa2ff'
}

function severityLabel(s: Severity) {
  return s === 'critical' ? 'CRIT' : s === 'high' ? 'HIGH' : 'MED'
}

function markerAccent(m: PlacedMarker) {
  if (m.severity === 'critical') return '#ff5a6a'
  if (m.severity === 'high') return '#ffb547'
  if (m.severity === 'medium') return '#7aa2ff'
  if (m.unavailable) return '#6a7590'
  return TYPE_COLOR[m.station.type] ?? '#49e1ff'
}

function formatValue(v: number | null | undefined) {
  if (v == null) return '—'
  return v >= 100 ? Math.round(v).toString() : v.toFixed(2)
}

const placedMarkers = computed<PlacedMarker[]>(() => {
  return props.markers
    .map((m) => {
      const pos = STATION_POSITIONS_3D[m.station.code] ?? STATION_POSITIONS_3D[m.station.id]
      if (!pos) return null
      const severity: Severity = m.hasAlarm ? severityFromAlarmLevel(m.alarmLevel) : 'normal'
      return {
        ...m,
        x: pos[0],
        y: pos[1],
        severity,
        unavailable: m.station.status === 'INACTIVE' || m.station.status === 'MAINTENANCE',
      }
    })
    .filter((m): m is PlacedMarker => m !== null)
})

// === Legend / layer state ===

const legendTypes: { key: string; label: string; icon: string; color: string }[] = [
  { key: 'rain', label: '雨量站', icon: 'rain-gauge', color: TYPE_COLOR.RAIN_GAUGE },
  { key: 'wl', label: '水位站', icon: 'water-level', color: TYPE_COLOR.WATER_LEVEL },
  { key: 'flow', label: '流量站', icon: 'flow', color: TYPE_COLOR.FLOW },
  { key: 'res', label: '水库站', icon: 'reservoir', color: TYPE_COLOR.RESERVOIR },
  { key: 'gate', label: '闸门站', icon: 'gate', color: TYPE_COLOR.GATE },
  { key: 'pump', label: '泵站', icon: 'pump', color: TYPE_COLOR.PUMP_STATION },
]

type LayerKey = 'waterLevel' | 'flowArrows' | 'rainfall' | 'basin'

const layers = reactive<Record<LayerKey, boolean>>({
  waterLevel: true,
  flowArrows: true,
  rainfall: false,
  basin: false,
})

const layerOptions: { key: LayerKey; label: string }[] = [
  { key: 'waterLevel', label: '水位等值线' },
  { key: 'flowArrows', label: '流向箭头' },
  { key: 'rainfall', label: '降雨强度' },
  { key: 'basin', label: '流域边界' },
]
</script>

<style scoped lang="scss">
.lake-stage {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(73, 225, 255, 0.10);
  background: #060a14;
}

.lake-stage__scene {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.lake-stage__corner,
.lake-stage__axes {
  position: absolute;
  bottom: 12px;
  font-family: var(--fm-font-mono, 'JetBrains Mono', monospace);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--fm-fg-mute, #8693af);
  z-index: 4;
}

.lake-stage__corner {
  left: 14px;

  b {
    color: var(--fm-brand-2, #49e1ff);
    font-weight: 600;
  }
}

.lake-stage__axes {
  right: 14px;
  display: flex;
  gap: 14px;
}

/* ============== Legend / layer panel ============== */
.lake-stage__legend {
  position: absolute;
  left: 14px;
  bottom: 38px;
  display: flex;
  gap: 20px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(11, 18, 32, 0.66);
  border: 1px solid rgba(73, 225, 255, 0.18);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  z-index: 5;
  pointer-events: auto;
  font-family: var(--fm-font-mono, 'JetBrains Mono', monospace);
}

.legend-block__title {
  font-size: 10px;
  letter-spacing: 0.16em;
  color: #ffffff;
  font-weight: 600;
  margin-bottom: 8px;

  span {
    color: #6a7590;
    font-weight: 500;
    margin-left: 6px;
    letter-spacing: 0.18em;
  }
}

.legend-grid {
  display: grid;
  grid-template-columns: repeat(2, auto);
  column-gap: 16px;
  row-gap: 5px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #c1cbe0;

  &__icon {
    width: 16px;
    height: 16px;
    display: grid;
    place-items: center;
  }

  &__name {
    letter-spacing: 0.04em;
  }
}

.legend-toggles {
  display: grid;
  grid-template-columns: repeat(2, auto);
  column-gap: 16px;
  row-gap: 5px;
}

.legend-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #c1cbe0;
  cursor: pointer;
  user-select: none;

  input {
    display: none;
  }

  &__box {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    border: 1px solid rgba(73, 225, 255, 0.45);
    background: rgba(11, 18, 32, 0.6);
    display: grid;
    place-items: center;
    transition: background 0.15s ease, border-color 0.15s ease;

    &::after {
      content: '';
      width: 6px;
      height: 6px;
      border-radius: 1px;
      background: #49e1ff;
      transform: scale(0);
      transition: transform 0.15s ease;
    }
  }

  input:checked + &__box {
    border-color: #49e1ff;
    background: rgba(73, 225, 255, 0.18);

    &::after { transform: scale(1); }
  }
}
</style>
