<template>
  <section class="fm-card fm-chat">
    <div class="fm-card__head">
      <div class="fm-chat__heading">
        <span class="title">指挥对话</span>
        <span class="mono">realtime · sse</span>
      </div>
      <span class="sp" />
      <span class="fm-chat__count">{{ messages.length }} 条</span>
      <span v-if="loading" class="fm-tag fm-tag--warn">
        <span class="fm-dot warn" /> 流式生成中
      </span>
      <span v-else-if="messages.length > 0" class="fm-tag fm-tag--ok">
        <span class="fm-dot ok" /> 就绪
      </span>
    </div>

    <div ref="messagesRef" class="fm-chat__messages">
      <div v-if="messages.length === 0" class="fm-chat__empty">
        <div class="empty-mark">
          <el-icon><ChatDotRound /></el-icon>
        </div>
        <strong>等待指令</strong>
        <p>多智能体研判、证据命中与预案状态会在这里同步展开。</p>
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
        :rows="2"
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

.fm-chat__heading {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.fm-chat__count {
  color: var(--fm-fg-mute);
  font-family: var(--fm-font-mono);
  font-size: 10.5px;
  letter-spacing: 0.06em;
}

.fm-chat__messages {
  flex: 1;
  overflow-y: auto;
  padding: 22px 22px 18px;
  min-height: 0;
  background:
    linear-gradient(rgba(73, 225, 255, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(73, 225, 255, 0.018) 1px, transparent 1px),
    linear-gradient(180deg, rgba(47, 123, 255, 0.05) 0%, transparent 220px);
  background-size: 32px 32px, 32px 32px, auto;
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

  .empty-mark {
    width: 72px;
    height: 72px;
    border-radius: 22px;
    display: grid;
    place-items: center;
    margin-bottom: 18px;
    color: var(--fm-brand-2);
    background: rgba(73, 225, 255, 0.08);
    border: 1px solid rgba(73, 225, 255, 0.22);
    box-shadow: inset 0 0 24px rgba(73, 225, 255, 0.04);

    .el-icon {
      font-size: 34px;
    }
  }

  strong {
    color: var(--fm-fg);
    font-size: 18px;
    font-weight: 650;
  }

  p {
    max-width: 360px;
    margin: 8px 0 0;
    line-height: 1.6;
    text-wrap: pretty;
  }
}

.fm-chat__input {
  padding: 10px 12px;
  border-top: 1px solid var(--fm-line);
  display: flex;
  gap: 10px;
  align-items: stretch;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), transparent),
    var(--fm-bg-1);

  :deep(.el-textarea__inner) {
    background: var(--fm-bg-2);
    border-color: var(--fm-line-2);
    color: var(--fm-fg);
    font-family: var(--fm-font-sans);
    font-size: 14px;
    line-height: 1.6;
    box-shadow: none;
    min-height: 58px !important;
    border-radius: 8px;

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
  min-width: 80px;
  padding: 0 14px;
  font-size: 13px;
  gap: 6px;
  justify-content: center;

  &:disabled {
    filter: grayscale(0.4);
    opacity: 0.6;
    cursor: not-allowed;
  }
}
</style>
