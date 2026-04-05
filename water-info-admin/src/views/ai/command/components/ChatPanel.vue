<template>
  <section class="chat-panel glass-panel">
    <!-- Messages area -->
    <div class="messages" ref="messagesRef">
      <div v-if="messages.length === 0" class="empty-state">
        <el-icon class="empty-icon"><ChatDotRound /></el-icon>
        <p>向AI提问，分析当前水情并生成防洪应急预案</p>
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

    <!-- Quick commands -->
    <QuickCommands :disabled="loading" @send="emit('send', $event)" />

    <!-- Input area -->
    <div class="input-area">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="3"
        placeholder="请输入指令 (按 Ctrl + Enter 发送)..."
        :disabled="loading"
        @keydown.ctrl.enter.prevent="handleSend"
        class="command-input"
      />
      <el-button
        type="primary"
        :loading="loading"
        @click="handleSend"
        class="send-btn"
      >
        发送 <el-icon class="el-icon--right"><Position /></el-icon>
      </el-button>
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

// Use store's inputDraft for persistence
const inputText = ref(store.inputDraft)
const messagesRef = ref<HTMLElement | null>(null)

function handleSend() {
  const text = inputText.value.trim()
  if (!text || props.loading) return
  emit('send', text)
  inputText.value = ''
  store.setInputDraft('')
}

// Sync inputText with store draft on change
watch(inputText, (val) => {
  store.setInputDraft(val)
})

// Auto-scroll to bottom when messages change or content updates
watch(
  () => props.messages,
  () => {
    nextTick(() => {
      if (messagesRef.value) {
        messagesRef.value.scrollTop = messagesRef.value.scrollHeight
      }
    })
  },
  { deep: true }
)
</script>

<style scoped>
.chat-panel {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  min-height: 0;
}

.messages::-webkit-scrollbar {
  width: 4px;
}
.messages::-webkit-scrollbar-thumb {
  background: rgba(0, 212, 255, 0.3);
  border-radius: 4px;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.3);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  color: rgba(0, 212, 255, 0.3);
}

.input-area {
  padding: 16px;
  border-top: 1px solid rgba(0, 212, 255, 0.15);
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-shrink: 0;
}

.command-input :deep(.el-textarea__inner) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.3);
  color: #fff;
  border-radius: 6px;
  box-shadow: none;
}
.command-input :deep(.el-textarea__inner:focus) {
  border-color: #00d4ff;
}

.send-btn {
  height: 74px;
  background: #0066cc;
  border: none;
  font-weight: bold;
  flex-shrink: 0;
}
.send-btn:hover {
  background: #0088ff;
}
</style>
