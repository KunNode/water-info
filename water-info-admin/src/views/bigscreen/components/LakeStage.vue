<template>
  <div class="lake-stage">
    <div class="lake-stage__sky" />
    <div class="lake-stage__rain" />

    <svg
      class="lake-stage__scene"
      viewBox="0 0 880 800"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="ls-terrain1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#1f2d45" />
          <stop offset="100%" stop-color="#0b1220" />
        </linearGradient>
        <linearGradient id="ls-terrain2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#162133" />
          <stop offset="100%" stop-color="#070b16" />
        </linearGradient>
        <linearGradient id="ls-lake" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#3a8ad6" stop-opacity="0.85" />
          <stop offset="50%" stop-color="#1d6bc7" stop-opacity="0.78" />
          <stop offset="100%" stop-color="#0a3b99" stop-opacity="0.55" />
        </linearGradient>
        <radialGradient id="ls-lake-hl" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stop-color="#49e1ff" stop-opacity="0.45" />
          <stop offset="100%" stop-color="#49e1ff" stop-opacity="0" />
        </radialGradient>
        <filter id="ls-glow"><feGaussianBlur stdDeviation="3" /></filter>
      </defs>

      <path
        d="M 0 420 L 80 380 L 160 360 L 240 340 L 340 320 L 440 310 L 540 300 L 640 310 L 740 320 L 820 340 L 880 360 L 880 800 L 0 800 Z"
        fill="url(#ls-terrain2)"
        opacity="0.7"
      />
      <path
        d="M 0 480 L 70 460 L 140 430 L 210 420 L 280 410 L 360 405 L 440 400 L 520 405 L 600 410 L 680 425 L 760 445 L 880 470 L 880 800 L 0 800 Z"
        fill="url(#ls-terrain1)"
      />
      <path
        d="M 0 560 L 80 540 L 160 530 L 240 520 L 320 525 L 400 520 L 480 515 L 560 520 L 640 525 L 720 540 L 800 555 L 880 570 L 880 800 L 0 800 Z"
        fill="#1f2d45"
      />

      <ellipse cx="440" cy="600" rx="320" ry="68" fill="url(#ls-lake-hl)" opacity="0.6" />
      <ellipse cx="440" cy="610" rx="290" ry="56" fill="url(#ls-lake)" />
      <ellipse cx="440" cy="600" rx="200" ry="28" fill="none" stroke="rgba(73,225,255,0.35)" stroke-width="0.8" />
      <ellipse cx="440" cy="608" rx="240" ry="38" fill="none" stroke="rgba(73,225,255,0.25)" stroke-width="0.8" />
      <ellipse cx="440" cy="616" rx="270" ry="48" fill="none" stroke="rgba(73,225,255,0.18)" stroke-width="0.8" />

      <g opacity="0.4">
        <polygon points="0,600 100,580 80,800 0,800" fill="#0b1426" />
        <polygon points="100,580 220,565 200,800 80,800" fill="#0e1a32" />
        <polygon points="660,560 780,580 800,800 700,800" fill="#0b1426" />
        <polygon points="780,580 880,610 880,800 800,800" fill="#091020" />
      </g>

      <g opacity="0.85">
        <circle cx="640" cy="320" r="2" fill="#49e1ff" filter="url(#ls-glow)">
          <animate attributeName="cy" values="320;380;460;540;610" dur="2.8s" repeatCount="indefinite" />
          <animate attributeName="cx" values="640;600;540;480;460" dur="2.8s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;1;1;0.6;0" dur="2.8s" repeatCount="indefinite" />
        </circle>
        <circle cx="680" cy="300" r="1.6" fill="#49e1ff" filter="url(#ls-glow)">
          <animate attributeName="cy" values="300;370;450;540;610" dur="3.4s" begin="0.5s" repeatCount="indefinite" />
          <animate attributeName="cx" values="680;640;560;500;480" dur="3.4s" begin="0.5s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;1;1;0.6;0" dur="3.4s" begin="0.5s" repeatCount="indefinite" />
        </circle>
        <circle cx="600" cy="350" r="1.4" fill="#49e1ff" filter="url(#ls-glow)">
          <animate attributeName="cy" values="350;400;480;560;620" dur="3.0s" begin="1s" repeatCount="indefinite" />
          <animate attributeName="cx" values="600;560;520;480;460" dur="3.0s" begin="1s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;1;1;0.6;0" dur="3.0s" begin="1s" repeatCount="indefinite" />
        </circle>
        <circle cx="720" cy="280" r="1.8" fill="#49e1ff" filter="url(#ls-glow)">
          <animate attributeName="cy" values="280;360;450;550;620" dur="3.2s" begin="1.6s" repeatCount="indefinite" />
          <animate attributeName="cx" values="720;680;600;520;490" dur="3.2s" begin="1.6s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;1;1;0.6;0" dur="3.2s" begin="1.6s" repeatCount="indefinite" />
        </circle>
        <circle cx="560" cy="380" r="1.2" fill="#7aa2ff" filter="url(#ls-glow)">
          <animate attributeName="cy" values="380;430;500;570;620" dur="2.6s" begin="0.3s" repeatCount="indefinite" />
          <animate attributeName="cx" values="560;530;500;470;460" dur="2.6s" begin="0.3s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0;1;1;0.6;0" dur="2.6s" begin="0.3s" repeatCount="indefinite" />
        </circle>
      </g>

      <g v-for="m in placedMarkers" :key="m.station.id" :transform="`translate(${m.x} ${m.y})`">
        <template v-if="m.severity === 'critical'">
          <circle r="22" :fill="`rgba(255,90,106,0.18)`">
            <animate attributeName="r" values="14;28;14" dur="1.6s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.5;0.1;0.5" dur="1.6s" repeatCount="indefinite" />
          </circle>
          <circle r="6" fill="#ff5a6a" filter="url(#ls-glow)" />
          <circle r="3" fill="#fff" />
        </template>
        <template v-else-if="m.severity === 'high'">
          <circle r="14" fill="rgba(255,181,71,0.18)">
            <animate attributeName="r" values="10;20;10" dur="2s" repeatCount="indefinite" />
          </circle>
          <circle r="5" fill="#ffb547" filter="url(#ls-glow)" />
        </template>
        <template v-else-if="m.severity === 'medium'">
          <circle r="12" fill="rgba(122,162,255,0.16)" />
          <circle r="4" fill="#7aa2ff" filter="url(#ls-glow)" />
        </template>
        <template v-else>
          <circle r="3.5" :fill="m.unavailable ? '#6a7590' : '#2bd99f'" />
        </template>

        <g v-if="m.severity !== 'normal'" :transform="m.severity === 'critical' ? 'translate(0 -52)' : 'translate(14 0)'">
          <text
            v-if="m.severity === 'critical'"
            text-anchor="middle"
            :fill="severityColor(m.severity)"
            font-family="var(--fm-font-mono)"
            font-size="10"
            font-weight="700"
            letter-spacing="1"
          >
            {{ severityLabel(m.severity) }} · {{ m.station.name }}
          </text>
          <text
            v-else
            x="0"
            y="-2"
            :fill="severityColor(m.severity)"
            font-family="var(--fm-font-mono)"
            font-size="10"
            font-weight="700"
          >
            {{ m.station.name }}
          </text>
          <text
            v-if="m.latestValue != null"
            :x="m.severity === 'critical' ? 0 : 0"
            :y="m.severity === 'critical' ? -38 : 12"
            :text-anchor="m.severity === 'critical' ? 'middle' : 'start'"
            fill="#ffffff"
            font-family="var(--fm-font-mono)"
            font-size="11"
            font-weight="700"
          >
            {{ formatValue(m.latestValue) }}<tspan font-size="9" fill="#8693af">{{ ' ' + (m.unit ?? '') }}</tspan>
          </text>
        </g>
        <text
          v-else
          x="8"
          y="3"
          fill="#8693af"
          font-family="var(--fm-font-mono)"
          font-size="9"
        >
          {{ m.station.name }}
        </text>
      </g>
    </svg>

    <div class="lake-stage__corner">
      CENTRAL · <b>THREE.JS · FLUID PARTICLE FIELD</b> · 占位中
    </div>
    <div class="lake-stage__axes">
      <span>N ↑</span><span>SCALE 1 : 5,000</span><span>WGS84</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StationMarker } from '@/composables/useLakeMap'

const props = defineProps<{
  markers: StationMarker[]
}>()

// Placement in the new 880×800 fluid scene viewBox.
// When the real Three.js scene replaces this, these stay as the source of truth
// for label overlay positioning.
const STATION_POSITIONS_3D: Record<string, [number, number]> = {
  ST_RAIN_CP_01: [220, 240],
  ST_RAIN_CP_02: [680, 200],
  ST_WL_CP_01: [420, 600],
  ST_WL_CP_02: [510, 580],
  ST_FLOW_CP_01: [540, 700],
  ST_RES_CP_01: [400, 590],
  ST_GATE_CP_01: [620, 670],
  ST_PUMP_CP_01: [320, 200],
}

type Severity = 'critical' | 'high' | 'medium' | 'normal'

interface PlacedMarker extends StationMarker {
  x: number
  y: number
  severity: Severity
  unavailable: boolean
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
</script>

<style scoped lang="scss">
.lake-stage {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(73, 225, 255, 0.10);
  background: radial-gradient(120% 90% at 50% 50%, rgba(47, 123, 255, 0.10) 0%, rgba(6, 10, 20, 0) 60%);
}

.lake-stage__sky {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(80% 60% at 50% 100%, rgba(47, 123, 255, 0.22), transparent 60%),
    radial-gradient(40% 40% at 30% 110%, rgba(73, 225, 255, 0.18), transparent 60%);
  pointer-events: none;
}

.lake-stage__rain {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(170deg, transparent 49.6%, rgba(73, 225, 255, 0.18) 49.7%, rgba(73, 225, 255, 0.18) 50.0%, transparent 50.1%);
  background-size: 5px 80px;
  opacity: 0.35;
  animation: ls-rain 1.4s linear infinite;
  pointer-events: none;
}

@keyframes ls-rain {
  0% { background-position: 0 0; }
  100% { background-position: 30px 80px; }
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
  font-family: var(--fm-font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--fm-fg-mute);
  z-index: 4;
}

.lake-stage__corner {
  left: 14px;

  b {
    color: var(--fm-brand-2);
    font-weight: 600;
  }
}

.lake-stage__axes {
  right: 14px;
  display: flex;
  gap: 14px;
}
</style>
