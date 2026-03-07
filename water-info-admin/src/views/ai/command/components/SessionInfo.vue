<template>
  <div class="glass-panel sidebar-panel">
    <div class="panel-header">会话信息</div>
    <div class="session-info">
      <div class="info-row">
        <span class="label">Session ID</span>
        <span class="value">{{ sessionId ? sessionId.slice(0, 12) + '…' : '---' }}</span>
      </div>
      <div class="info-row">
        <span class="label">开始时间</span>
        <span class="value">{{ startTime || '---' }}</span>
      </div>
      <div class="info-row">
        <span class="label">交互次数</span>
        <span class="value accent">{{ queryCount }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  sessionId: string
  startTime: string
  queryCount: number
}>()
</script>

<style scoped>
.glass-panel {
  background: linear-gradient(135deg, rgba(0, 100, 150, 0.1) 0%, rgba(0, 50, 100, 0.05) 100%);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 8px;
  backdrop-filter: blur(4px);
}

.sidebar-panel {
  padding: 16px;
}

.panel-header {
  font-size: 14px;
  font-weight: 600;
  color: #00d4ff;
  margin-bottom: 14px;
  padding-left: 10px;
  position: relative;
}

.panel-header::before {
  content: '';
  position: absolute;
  left: 0;
  top: 2px;
  bottom: 2px;
  width: 3px;
  background: linear-gradient(180deg, #00d4ff, #0066cc);
  border-radius: 2px;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.label {
  color: rgba(255, 255, 255, 0.4);
}

.value {
  color: rgba(255, 255, 255, 0.75);
  font-family: 'Courier New', monospace;
}

.value.accent {
  color: #00d4ff;
  font-weight: 600;
}
</style>
