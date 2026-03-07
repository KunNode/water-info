<template>
  <div class="glass-panel sidebar-panel">
    <div class="panel-header">智能体进度</div>
    <div class="agent-timeline">
      <div v-for="agent in agentList" :key="agent.key" class="agent-item">
        <div class="agent-status-icon" :class="agentStatus[agent.key] || 'pending'">
          <el-icon v-if="agentStatus[agent.key] === 'done'"><Select /></el-icon>
          <el-icon v-else-if="agentStatus[agent.key] === 'failed'"><Close /></el-icon>
          <el-icon v-else-if="agentStatus[agent.key] === 'active'" class="is-loading"><Loading /></el-icon>
          <span v-else class="pending-dot"></span>
        </div>
        <div class="agent-name" :class="{ active: agentStatus[agent.key] === 'active' }">
          {{ agent.name }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Select, Close, Loading } from '@element-plus/icons-vue'

defineProps<{
  agentStatus: Record<string, string>
}>()

const agentList = [
  { key: 'supervisor', name: '调度器' },
  { key: 'data_analyst', name: '数据分析' },
  { key: 'risk_assessor', name: '风险评估' },
  { key: 'plan_generator', name: '预案生成' },
  { key: 'resource_dispatcher', name: '资源调度' },
  { key: 'notification', name: '通知预警' },
]
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

.agent-timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-status-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.agent-status-icon.pending {
  background: rgba(255, 255, 255, 0.08);
}

.pending-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
}

.agent-status-icon.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.agent-status-icon.done {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.agent-status-icon.failed {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.is-loading {
  animation: rotate 1.5s linear infinite;
}

@keyframes rotate {
  100% { transform: rotate(360deg); }
}

.agent-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  transition: color 0.2s;
}

.agent-name.active {
  color: #fff;
  font-weight: 500;
}
</style>
