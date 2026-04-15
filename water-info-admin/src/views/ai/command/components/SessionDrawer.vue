<template>
  <div class="session-drawer" :class="{ open: modelValue }">
    <!-- Toggle handle -->
    <button class="drawer-toggle" @click="emit('update:modelValue', !modelValue)" :title="modelValue ? '收起会话列表' : '展开会话列表'">
      <el-icon><ChatLineRound /></el-icon>
      <span v-if="!modelValue" class="toggle-badge" v-show="conversations.length > 0">{{ conversations.length }}</span>
    </button>

    <!-- Panel -->
    <div class="drawer-panel" v-show="modelValue">
      <!-- Header -->
      <div class="panel-header">
        <span class="panel-title">会话记录</span>
        <el-button
          type="primary"
          size="small"
          class="new-btn"
          @click="handleNewSession"
        >
          <el-icon><Plus /></el-icon> 新会话
        </el-button>
      </div>

      <!-- Session list -->
      <div class="session-list" v-loading="loading" element-loading-background="rgba(0,0,0,0.5)">
        <div
          v-for="item in conversations"
          :key="item.session_id"
          class="session-item"
          :class="{ active: item.session_id === currentSessionId }"
          @click="handleSelect(item)"
        >
          <div class="item-title" :title="item.title">{{ item.title }}</div>
          <div class="item-meta">
            <span class="item-count">{{ item.message_count }} 条消息</span>
            <span class="item-time">{{ formatTime(item.updated_at) }}</span>
          </div>
          <div class="item-preview" v-if="item.last_message">
            {{ truncate(item.last_message, 40) }}
          </div>
          <el-button
            class="delete-btn"
            size="small"
            type="danger"
            link
            @click.stop="handleDelete(item)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
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
import { useAiConversationStore } from '@/stores/aiConversation'

const store = useAiConversationStore()

const props = defineProps<{
  modelValue: boolean       // drawer open/close
  currentSessionId: string | null  // currently active session (may be null for draft)
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
  // Don't create on server - emit signal for parent to start draft mode
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
    conversations.value = conversations.value.filter(c => c.session_id !== item.session_id)
    if (item.session_id === props.currentSessionId) {
      emit('new')  // signal parent to start fresh
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

// Refresh list when drawer opens
watch(() => props.modelValue, (open) => {
  if (open) fetchConversations()
})

onMounted(() => {
  if (props.modelValue) fetchConversations()
})

// Expose refresh so parent can call after a query completes
defineExpose({ refresh: fetchConversations })
</script>

<style scoped>
.session-drawer {
  position: relative;
  display: flex;
  align-items: stretch;
  z-index: 10;
}

.drawer-toggle {
  position: absolute;
  left: -36px;
  top: 50%;
  transform: translateY(-50%);
  width: 32px;
  height: 56px;
  background: rgba(0, 100, 150, 0.35);
  border: 1px solid rgba(0, 212, 255, 0.3);
  border-right: none;
  border-radius: 6px 0 0 6px;
  color: #00d4ff;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 18px;
  transition: background 0.2s;
}
.drawer-toggle:hover {
  background: rgba(0, 150, 200, 0.4);
}

.toggle-badge {
  font-size: 11px;
  line-height: 1;
  color: rgba(255,255,255,0.7);
}

.drawer-panel {
  width: 220px;
  background: rgba(5, 20, 40, 0.85);
  border-left: 1px solid rgba(0, 212, 255, 0.2);
  backdrop-filter: blur(6px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(0, 212, 255, 0.15);
  flex-shrink: 0;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255,255,255,0.8);
  letter-spacing: 0.5px;
}

.new-btn {
  background: rgba(0, 100, 200, 0.4);
  border-color: rgba(0, 212, 255, 0.4);
  color: #00d4ff;
  font-size: 12px;
  padding: 4px 10px;
}
.new-btn:hover {
  background: rgba(0, 150, 255, 0.5);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  min-height: 0;
}

.session-list::-webkit-scrollbar {
  width: 3px;
}
.session-list::-webkit-scrollbar-thumb {
  background: rgba(0, 212, 255, 0.3);
  border-radius: 3px;
}

.session-item {
  position: relative;
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  transition: background 0.15s;
}
.session-item:hover {
  background: rgba(0, 150, 200, 0.15);
}
.session-item.active {
  background: rgba(0, 212, 255, 0.12);
  border-left: 2px solid #00d4ff;
}

.item-title {
  font-size: 13px;
  color: rgba(255,255,255,0.85);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}

.item-meta {
  display: flex;
  gap: 6px;
  margin-top: 3px;
  font-size: 11px;
  color: rgba(255,255,255,0.4);
}

.item-preview {
  font-size: 11px;
  color: rgba(255,255,255,0.35);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 170px;
}

.delete-btn {
  position: absolute;
  top: 8px;
  right: 6px;
  opacity: 0;
  color: rgba(255, 80, 80, 0.7) !important;
  font-size: 13px;
  transition: opacity 0.15s;
}
.session-item:hover .delete-btn {
  opacity: 1;
}

.empty-hint {
  text-align: center;
  padding: 24px;
  font-size: 13px;
  color: rgba(255,255,255,0.3);
}
</style>
