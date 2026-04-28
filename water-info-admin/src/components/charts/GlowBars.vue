<script setup lang="ts">
interface Props {
  width?: number
  height?: number
  seed?: number
  bars?: number
  color?: string
}
withDefaults(defineProps<Props>(), {
  width: 320,
  height: 120,
  seed: 3,
  bars: 18,
  color: 'var(--fm-brand)',
})

function rand(seed: number, i: number): number {
  const x = Math.sin((seed + i) * 9.13) * 10000
  return x - Math.floor(x)
}
</script>

<template>
  <svg :width="'100%'" :height="height" :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none">
    <defs>
      <linearGradient id="glbar-bg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity="1"/>
        <stop offset="100%" :stop-color="color" stop-opacity="0.25"/>
      </linearGradient>
    </defs>
    <line x1="0" :y1="height-1" :x2="width" :y2="height-1" stroke="var(--fm-line)" opacity="0.6"/>
    <g v-for="i in bars" :key="i">
      <rect :x="(i - 1) * (width / (bars * 1.4)) + (width / (bars * 1.4)) * 0.2"
        :y="height - (0.15 + rand(seed, i - 1) * 0.8) * (height - 8)"
        :width="width / (bars * 1.4) * 0.7"
        :height="(0.15 + rand(seed, i - 1) * 0.8) * (height - 8)"
        fill="url(#glbar-bg)" rx="2"/>
      <rect :x="(i - 1) * (width / (bars * 1.4)) + (width / (bars * 1.4)) * 0.2"
        :y="height - (0.15 + rand(seed, i - 1) * 0.8) * (height - 8) - 2"
        :width="width / (bars * 1.4) * 0.7" height="2" :fill="color" opacity="0.9"/>
    </g>
  </svg>
</template>
