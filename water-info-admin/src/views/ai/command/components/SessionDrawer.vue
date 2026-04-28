<template>
  <div class="fm-session-drawer" :class="{ open: modelValue }">
    <button
      type="button"
      class="fm-session-drawer__handle"
      :title="modelValue ? '收起会话列表' : '展开会话列表'"
      @click="emit('update:modelValue', !modelValue)"
    >
      <el-icon><ChatLineRound /></el-icon>
      <span v-if="!modelValue && conversations.length > 0" class="count">
        {{ conversations.length }}
      </span>
    </button>

    <div v-show="modelValue" class="fm-session-drawer__panel">
      <div class="panel-head">
        <span class="title">会话记录</span>
        <span class="sp" />
        <button
          type="button"
          class="fm-btn fm-btn--primary fm-btn--sm"
          @click="handleNewSession"
        >
          <el-icon><Plus /></el-icon>新会话
        </button>
      </div>

      <div v-loading="loading" class="panel-list">
        <div
          v-for="item in conversations"
          :key="item.session_id"
          class="session-row"
          :class="{ active: item.session_id === currentSessionId }"
          @click="handleSelect(item)"
        >
          <div class="row-title" :title="item.title">{{ item.title }}</div>
          <div class="row-meta">
            <span class="count">{{ item.message_count }} 条</span>
            <span class="time">{{ formatTime(item.updated_at) }}</span>
          </div>
          <div v-if="item.last_message" class="row-preview">
            {{ truncate(item.last_message, 48) }}
          </div>
          <button
            type="button"
            class="row-del"
            title="删除会话"
            @click.stop="handleDelete(item)"
          >
            <el-icon><Delete /></el-icon>
          </button>
        </div>

        <div v-if="!loading && conversations.length === 0" class="empty-hint">
          暂无会话记录
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { Plus, Delete, ChatLineRound } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { listConversations, deleteConversation } from '@/api/flood'
import type { ConversationItem } from '@/types'

const props = defineProps<{
  modelValue: boolean
  currentSessionId: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'select': [sessionId: string]
  'new': [sessionId?: string]
}>()

const conversations = ref<ConversationItem[]>([])
const loading = ref(false)

async function fetchConversations() {
  loading.value = true
  try {
    const res = await listConversations({ limit: 50 })
    conversations.value = res.data ?? []
  } catch {
    // silently fail — not critical
  } finally {
    loading.value = false
  }
}

function handleNewSession() {
  emit('new')
}

function handleSelect(item: ConversationItem) {
  if (item.session_id === props.currentSessionId) return
  emit('select', item.session_id)
}

async function handleDelete(item: ConversationItem) {
  try {
    await ElMessageBox.confirm(`删除会话「${item.title}」？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteConversation(item.session_id)
    conversations.value = conversations.value.filter((c) => c.session_id !== item.session_id)
    if (item.session_id === props.currentSessionId) {
      emit('new')
    }
    ElMessage.success('已删除')
  } catch {
    // cancelled or error — ignore
  }
}

function formatTime(ts: string | null | undefined): string {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function truncate(str: string, len: number): string {
  return str.length > len ? str.slice(0, len) + '…' : str
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) fetchConversations()
  },
)

onMounted(() => {
  if (props.modelValue) fetchConversations()
})

defineExpose({ refresh: fetchConversations })
</script>

<style scoped lang="scss">
.fm-session-drawer {
  position: fixed;
  top: calc(var(--fm-topbar-h) + var(--fm-tags-h) + 90px);
  right: 0;
  z-index: 30;
  display: flex;
  align-items: stretch;
  pointer-events: none;

  > * {
    pointer-events: auto;
  }
}

.fm-session-drawer__handle {
  position: absolute;
  left: -32px;
  top: 0;
  width: 32px;
  height: 64px;
  background: var(--fm-grad-panel);
  border: 1px solid var(--fm-line-2);
  border-right: none;
  border-radius: 8px 0 0 8px;
  color: var(--fm-brand-2);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 18px;
  transition: all 0.2s;

  &:hover {
    background: var(--fm-bg-3);
    box-shadow: 0 0 0 1px var(--fm-brand-2);
  }

  .count {
    font-size: 10px;
    font-family: var(--fm-font-mono);
    color: var(--fm-fg-mute);
    line-height: 1;
  }
}

.fm-session-drawer__panel {
  width: 300px;
  background: var(--fm-grad-panel);
  border-left: 1px solid var(--fm-line);
  border-top: 1px solid var(--fm-line);
  border-bottom: 1px solid var(--fm-line);
  border-radius: var(--fm-radius) 0 0 var(--fm-radius);
  box-shadow: var(--fm-shadow-pop);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-height: calc(100vh - var(--fm-topbar-h) - var(--fm-tags-h) - 120px);
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--fm-line);

  .title {
    font-size: 13px;
    font-weight: 600;
    color: var(--fm-fg);
    letter-spacing: 0.04em;
  }
  .sp {
    flex: 1;
  }
}

.panel-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
  min-height: 100px;
}

.session-row {
  position: relative;
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid var(--fm-line);
  transition: background 0.15s;

  &:hover {
    background: var(--fm-bg-2);
  }

  &.active {
    background: linear-gradient(90deg, rgba(47, 123, 255, 0.15), transparent 70%);
    border-left: 2px solid var(--fm-brand-2);
  }

  &:hover .row-del {
    opacity: 1;
  }
}

.row-title {
  font-size: 13px;
  color: var(--fm-fg);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.row-meta {
  display: flex;
  gap: 8px;
  margin-top: 3px;
  font-size: 10.5px;
  font-family: var(--fm-font-mono);
  color: var(--fm-fg-mute);
  letter-spacing: 0.04em;
}

.row-preview {
  font-size: 11px;
  color: var(--fm-fg-mute);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 250px;
  font-style: italic;
}

.row-del {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--fm-danger);
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.15s;

  &:hover {
    background: rgba(255, 90, 106, 0.15);
  }
}

.empty-hint {
  text-align: center;
  padding: 28px 16px;
  font-size: 12.5px;
  color: var(--fm-fg-mute);
}
</style>
