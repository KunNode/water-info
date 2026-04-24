<template>
  <div class="fm-card fm-agent-timeline">
    <div class="fm-card__head">
      <span class="title">智能体流水线</span>
      <span class="mono">agents · {{ activeCount }}/{{ agentList.length }}</span>
    </div>
    <div class="fm-card__body">
      <div v-for="agent in agentList" :key="agent.key" class="agent-row">
        <div class="status" :class="statusClass(agent.key)">
          <el-icon v-if="agentStatus[agent.key] === 'done'"><Select /></el-icon>
          <el-icon v-else-if="agentStatus[agent.key] === 'failed'"><Close /></el-icon>
          <el-icon v-else-if="agentStatus[agent.key] === 'active'" class="spin"><Loading /></el-icon>
          <span v-else class="pending" />
        </div>
        <div class="meta">
          <div class="code">{{ agent.code }}</div>
          <div class="name" :class="{ active: agentStatus[agent.key] === 'active' }">{{ agent.name }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Select, Close, Loading } from '@element-plus/icons-vue'

const props = defineProps<{
  agentStatus: Record<string, string>
}>()

const agentList = [
  { key: 'supervisor',          code: 'A-01', name: '调度器' },
  { key: 'data_analyst',        code: 'A-02', name: '数据分析' },
  { key: 'risk_assessor',       code: 'A-03', name: '风险评估' },
  { key: 'plan_generator',      code: 'A-04', name: '预案生成' },
  { key: 'resource_dispatcher', code: 'A-05', name: '资源调度' },
  { key: 'notification',        code: 'A-06', name: '通知预警' },
]

const activeCount = computed(() =>
  agentList.filter((a) => {
    const s = props.agentStatus[a.key]
    return s === 'active' || s === 'done'
  }).length,
)

function statusClass(key: string): string {
  return props.agentStatus[key] || 'pending'
}
</script>

<style scoped lang="scss">
.fm-agent-timeline .fm-card__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.agent-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  flex-shrink: 0;
  border: 1px solid var(--fm-line);
  background: var(--fm-bg-2);
  color: var(--fm-fg-mute);

  &.active {
    background: rgba(255, 181, 71, 0.15);
    border-color: rgba(255, 181, 71, 0.5);
    color: var(--fm-warn);
    box-shadow: 0 0 12px -2px rgba(255, 181, 71, 0.5);
  }
  &.done {
    background: rgba(43, 217, 159, 0.15);
    border-color: rgba(43, 217, 159, 0.4);
    color: var(--fm-ok);
  }
  &.failed {
    background: rgba(255, 90, 106, 0.15);
    border-color: rgba(255, 90, 106, 0.4);
    color: var(--fm-danger);
  }
}

.pending {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--fm-fg-dim);
}

.spin {
  animation: spin 1.5s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.meta {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;

  .code {
    font-family: var(--fm-font-mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    color: var(--fm-fg-mute);
  }
  .name {
    font-size: 13px;
    color: var(--fm-fg-soft);
    transition: color 0.2s;

    &.active {
      color: var(--fm-fg);
      font-weight: 500;
    }
  }
}
</style>
