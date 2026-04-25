<template>
  <div class="fm-quick">
    <span class="label">快捷指令</span>
    <div class="chips">
      <button
        v-for="(cmd, index) in commands"
        :key="cmd"
        class="chip"
        :disabled="disabled"
        @click="emit('send', cmd)"
      >
        <span class="chip-index">0{{ index + 1 }}</span>
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
  padding: 7px 12px;
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
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid var(--fm-line-2);
  background: rgba(255, 255, 255, 0.018);
  color: var(--fm-fg-soft);
  font-size: 12px;
  font-family: var(--fm-font-sans);
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;

  &:hover:not(:disabled) {
    background: rgba(73, 225, 255, 0.08);
    border-color: rgba(73, 225, 255, 0.42);
    color: var(--fm-fg);
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.chip-index {
  color: var(--fm-brand-2);
  font-family: var(--fm-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
}
</style>
