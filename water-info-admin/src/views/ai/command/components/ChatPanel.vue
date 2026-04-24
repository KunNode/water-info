<template>
  <section class="fm-card fm-chat">
    <div class="fm-card__head">
      <span class="title">指挥对话</span>
      <span class="mono">realtime · sse</span>
      <span class="sp" />
      <span v-if="loading" class="fm-tag fm-tag--warn">
        <span class="fm-dot warn" /> 流式生成中
      </span>
      <span v-else-if="messages.length > 0" class="fm-tag fm-tag--ok">
        <span class="fm-dot ok" /> 就绪
      </span>
    </div>

    <div ref="messagesRef" class="fm-chat__messages">
      <div v-if="messages.length === 0" class="fm-chat__empty">
        <el-icon class="icon"><ChatDotRound /></el-icon>
        <p>向指挥中心 AI 下达指令，调度多 Agent 协同分析水情并生成预案。</p>
      </div>
      <template v-else>
        <ChatMessage
          v-for="(msg, idx) in messages"
          :key="idx"
          :message="msg"
          :streaming="loading && idx === messages.length - 1 && msg.role === 'assistant'"
        />
      </template>
    </div>

    <QuickCommands :disabled="loading" @send="emit('send', $event)" />

    <div class="fm-chat__input">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="3"
        placeholder="向指挥中心 AI 下达指令… (Ctrl + Enter 发送)"
        :disabled="loading"
        resize="none"
        @keydown.ctrl.enter.prevent="handleSend"
      />
      <button
        type="button"
        class="fm-btn fm-btn--primary fm-chat__send"
        :disabled="loading || !inputText.trim()"
        @click="handleSend"
      >
        <el-icon><Position /></el-icon>
        <span>发送</span>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { ChatDotRound, Position } from '@element-plus/icons-vue'
import ChatMessage from './ChatMessage.vue'
import QuickCommands from './QuickCommands.vue'
import type { ChatMessageItem } from '@/stores/aiConversation'
import { useAiConversationStore } from '@/stores/aiConversation'

const store = useAiConversationStore()

const props = defineProps<{
  messages: ChatMessageItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  send: [query: string]
}>()

const inputText = ref(store.inputDraft)
const messagesRef = ref<HTMLElement | null>(null)

function handleSend() {
  const text = inputText.value.trim()
  if (!text || props.loading) return
  emit('send', text)
  inputText.value = ''
  store.setInputDraft('')
}

watch(inputText, (val) => {
  store.setInputDraft(val)
})

watch(
  () => props.messages,
  () => {
    nextTick(() => {
      if (messagesRef.value) {
        messagesRef.value.scrollTop = messagesRef.value.scrollHeight
      }
    })
  },
  { deep: true },
)
</script>

<style scoped lang="scss">
.fm-chat {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.fm-chat__messages {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px;
  min-height: 0;
  background: linear-gradient(
    180deg,
    rgba(47, 123, 255, 0.04) 0%,
    transparent 30%
  );
}

.fm-chat__empty {
  height: 100%;
  min-height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--fm-fg-mute);
  text-align: center;

  .icon {
    font-size: 48px;
    margin-bottom: 16px;
    color: var(--fm-brand-2);
    opacity: 0.5;
  }

  p {
    max-width: 320px;
    line-height: 1.6;
  }
}

.fm-chat__input {
  padding: 14px 16px;
  border-top: 1px solid var(--fm-line);
  display: flex;
  gap: 10px;
  align-items: stretch;
  background: var(--fm-bg-1);

  :deep(.el-textarea__inner) {
    background: var(--fm-bg-2);
    border-color: var(--fm-line-2);
    color: var(--fm-fg);
    font-family: var(--fm-font-sans);
    font-size: 13.5px;
    line-height: 1.6;
    box-shadow: none;

    &::placeholder {
      color: var(--fm-fg-mute);
    }
    &:hover,
    &:focus {
      border-color: var(--fm-brand);
      box-shadow: 0 0 0 3px var(--fm-line-glow);
    }
  }
}

.fm-chat__send {
  height: auto;
  padding: 0 18px;
  font-size: 13px;
  gap: 6px;

  &:disabled {
    filter: grayscale(0.4);
    opacity: 0.6;
    cursor: not-allowed;
  }
}
</style>
