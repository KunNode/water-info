<script setup lang="ts">
interface Props {
  width?: number
  height?: number
  seeds?: number[]
  colors?: string[]
  glow?: boolean
  area?: boolean
  animate?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  width: 600,
  height: 180,
  seeds: () => [1],
  colors: () => ['var(--fm-brand-2)'],
  glow: true,
  area: true,
  animate: false,
})

function rand(seed: number, i: number): number {
  const x = Math.sin((seed + i) * 9.13) * 10000
  return x - Math.floor(x)
}

interface PathData {
  d: string
  areaD: string
  last: [number, number]
}

function buildPath(seed: number): PathData {
  const N = 50
  const pad = 12
  const pts = Array.from({ length: N }, (_, i) => {
    const x = pad + (i / (N - 1)) * (props.width - pad * 2)
    const y = pad + (0.15 + rand(seed, i) * 0.7) * (props.height - pad * 2)
    return [x, y] as [number, number]
  })
  const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const areaD = d + ` L ${props.width - pad},${props.height - pad} L ${pad},${props.height - pad} Z`
  return { d, areaD, last: pts[pts.length - 1] }
}
</script>

<template>
  <svg :width="'100%'" :height="height" :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none">
    <defs>
      <template v-for="(s, i) in seeds" :key="i">
        <linearGradient :id="`gla-${i}`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="colors[i] || colors[0]" stop-opacity="0.35"/>
          <stop offset="100%" :stop-color="colors[i] || colors[0]" stop-opacity="0"/>
        </linearGradient>
        <filter :id="`glg-${i}`" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2.5"/>
        </filter>
      </template>
    </defs>
    <line v-for="f in [0.25, 0.5, 0.75]" :key="f"
      :x1="12" :y1="height * f" :x2="width - 12" :y2="height * f"
      stroke="var(--fm-line)" stroke-dasharray="2 4" opacity="0.6"/>
    <template v-for="(s, i) in seeds" :key="`line-${i}`">
      <path v-if="area" :d="buildPath(s).areaD" :fill="`url(#gla-${i})`"/>
      <path v-if="glow" :d="buildPath(s).d" fill="none" :stroke="colors[i] || colors[0]"
        stroke-width="3" opacity="0.5" :filter="`url(#glg-${i})`"/>
      <path :d="buildPath(s).d" fill="none" :stroke="colors[i] || colors[0]"
        stroke-width="1.8" stroke-linejoin="round"/>
      <circle :cx="buildPath(s).last[0]" :cy="buildPath(s).last[1]" r="3" :stroke="colors[i] || colors[0]" fill="currentColor">
        <animate v-if="animate" attributeName="r" values="3;6;3" dur="1.8s" repeatCount="indefinite"/>
      </circle>
      <template v-if="animate">
        <circle :cx="buildPath(s).last[0]" :cy="buildPath(s).last[1]" r="8" fill="none" :stroke="colors[i] || colors[0]" opacity="0.4">
          <animate attributeName="r" values="3;14;3" dur="1.8s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="0.6;0;0.6" dur="1.8s" repeatCount="indefinite"/>
        </circle>
      </template>
    </template>
  </svg>
</template>
