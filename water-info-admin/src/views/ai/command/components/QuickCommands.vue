<template>
  <div class="quick-commands">
    <span class="label">快捷指令：</span>
    <div class="chips">
      <button
        v-for="cmd in commands"
        :key="cmd"
        class="chip"
        :disabled="disabled"
        @click="emit('send', cmd)"
      >
        {{ cmd }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  disabled: boolean
}>()

const emit = defineEmits<{
  send: [query: string]
}>()

const commands = [
  '分析当前水情',
  '生成防洪应急预案',
  '评估当前风险等级',
  '调度应急资源',
]
</script>

<style scoped>
.quick-commands {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid rgba(0, 212, 255, 0.1);
  flex-wrap: wrap;
}

.label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  white-space: nowrap;
  flex-shrink: 0;
}

.chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.chip {
  padding: 4px 12px;
  border-radius: 20px;
  border: 1px solid rgba(0, 212, 255, 0.3);
  background: rgba(0, 212, 255, 0.06);
  color: rgba(0, 212, 255, 0.85);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.chip:hover:not(:disabled) {
  background: rgba(0, 212, 255, 0.15);
  border-color: #00d4ff;
  color: #fff;
}

.chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
