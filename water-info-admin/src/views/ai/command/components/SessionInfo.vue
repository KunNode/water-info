<template>
  <div class="fm-card fm-session-info">
    <div class="fm-card__head">
      <span class="title">会话信息</span>
    </div>
    <div class="fm-card__body">
      <div class="row">
        <span class="k">Session ID</span>
        <span class="v mono">{{ sessionId ? sessionId.slice(0, 12) + '…' : '---' }}</span>
      </div>
      <div class="row">
        <span class="k">开始时间</span>
        <span class="v mono">{{ startTime || '---' }}</span>
      </div>
      <div class="row">
        <span class="k">交互次数</span>
        <span class="v v--accent mono">{{ queryCount }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  sessionId: string | null
  startTime: string
  queryCount: number
}>()
</script>

<style scoped lang="scss">
.fm-session-info .fm-card__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
}

.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  min-height: 38px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.018);
  border: 1px solid var(--fm-line);
}

.k {
  font-family: var(--fm-font-mono);
  color: var(--fm-fg-mute);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.v {
  color: var(--fm-fg-soft);
}

.v--accent {
  color: var(--fm-brand-2);
  font-weight: 600;
}

.mono {
  font-family: var(--fm-font-mono);
}
</style>
