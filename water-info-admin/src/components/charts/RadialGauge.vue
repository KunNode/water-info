<script setup lang="ts">
interface Props {
  value?: number
  label?: string
  size?: number
  color?: string
}
withDefaults(defineProps<Props>(), {
  value: 62,
  label: 'RISK',
  size: 180,
  color: 'var(--fm-brand-2)',
})

const R = 0.38
const ARC_RATIO = 0.72
</script>

<template>
  <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`">
    <defs>
      <linearGradient :id="`rg-gr-${label}`" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#2f7bff"/>
        <stop offset="50%" stop-color="#49e1ff"/>
        <stop offset="100%" stop-color="#ffb547"/>
      </linearGradient>
      <filter :id="`rg-gl-${label}`">
        <feGaussianBlur stdDeviation="3"/>
      </filter>
    </defs>
    <circle :cx="size/2" :cy="size/2" :r="size*R" fill="none" stroke="var(--fm-line)"
      :stroke-width="size*0.05"
      :stroke-dasharray="`${2*Math.PI*size*R*ARC_RATIO} ${2*Math.PI*size*R}`"
      :transform="`rotate(126 ${size/2} ${size/2})`"
      stroke-linecap="round"/>
    <circle :cx="size/2" :cy="size/2" :r="size*R" fill="none"
      :stroke="`url(#rg-gr-${label})`"
      :stroke-width="size*0.05"
      :stroke-dasharray="`${2*Math.PI*size*R*ARC_RATIO*(value/100)} ${2*Math.PI*size*R}`"
      :transform="`rotate(126 ${size/2} ${size/2})`"
      stroke-linecap="round"
      :filter="`url(#rg-gl-${label})`" opacity="0.9"/>
    <circle :cx="size/2" :cy="size/2" :r="size*R" fill="none"
      :stroke="`url(#rg-gr-${label})`"
      :stroke-width="size*0.015"
      :stroke-dasharray="`${2*Math.PI*size*R*ARC_RATIO*(value/100)} ${2*Math.PI*size*R}`"
      :transform="`rotate(126 ${size/2} ${size/2})`"
      stroke-linecap="round"/>
    <line v-for="i in 28" :key="i"
      :x1="size/2 + Math.cos((126 + (i/27)*259)*Math.PI/180)*(size*R - size*0.07)"
      :y1="size/2 + Math.sin((126 + (i/27)*259)*Math.PI/180)*(size*R - size*0.07)"
      :x2="size/2 + Math.cos((126 + (i/27)*259)*Math.PI/180)*(size*R - size*0.1)"
      :y2="size/2 + Math.sin((126 + (i/27)*259)*Math.PI/180)*(size*R - size*0.1)"
      stroke="var(--fm-fg-dim)" stroke-width="1"
      :opacity="i/27 < value/100 ? 0.8 : 0.25"/>
    <text :x="size/2" :y="size/2 - 2" text-anchor="middle" :font-size="size*0.28" font-weight="600" fill="var(--fm-fg)">{{ value }}</text>
    <text :x="size/2" :y="size/2 + size*0.14" text-anchor="middle" :font-size="size*0.08" fill="var(--fm-fg-mute)" font-family="var(--fm-font-mono)" letter-spacing="0.14em">{{ label }}</text>
  </svg>
</template>
