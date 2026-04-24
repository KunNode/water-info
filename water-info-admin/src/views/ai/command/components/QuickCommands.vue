<template>
  <div class="fm-quick">
    <span class="label">快捷指令</span>
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

<style scoped lang="scss">
.fm-quick {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-top: 1px solid var(--fm-line);
  flex-wrap: wrap;
  background: var(--fm-bg-1);
}

.label {
  font-size: 10.5px;
  font-family: var(--fm-font-mono);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--fm-fg-mute);
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
  border-radius: 14px;
  border: 1px solid var(--fm-line-2);
  background: var(--fm-bg-2);
  color: var(--fm-fg-soft);
  font-size: 12px;
  font-family: var(--fm-font-sans);
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;

  &:hover:not(:disabled) {
    background: rgba(47, 123, 255, 0.12);
    border-color: var(--fm-brand);
    color: var(--fm-fg);
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}
</style>
