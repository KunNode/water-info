<template>
  <div class="knowledge-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">知识库管理</h2>
        <p class="page-subtitle">上传制度、手册、预案模板和资料文档，供 AI 检索引用。</p>
      </div>
    </div>

    <div class="stats-grid">
      <el-card shadow="never">
        <div class="stat-label">文档数</div>
        <div class="stat-value">{{ stats.document_count }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="stat-label">已就绪文档</div>
        <div class="stat-value">{{ stats.ready_document_count }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="stat-label">Chunk 数</div>
        <div class="stat-value">{{ stats.chunk_count }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="stat-label">近期成功率</div>
        <div class="stat-value">{{ formatRate(stats.job_success_rate) }}</div>
      </el-card>
    </div>

    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar-row">
        <el-input
          v-model="filters.q"
          placeholder="搜索标题或来源"
          clearable
          style="max-width: 320px"
          @keyup.enter="fetchDocuments"
        />
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 160px">
          <el-option label="待处理" value="pending" />
          <el-option label="处理中" value="processing" />
          <el-option label="已就绪" value="ready" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button type="primary" @click="fetchDocuments">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <el-upload
          v-if="canWrite"
          :show-file-list="false"
          :http-request="handleUpload"
          accept=".md,.markdown,.txt,.pdf,.docx"
        >
          <el-button type="success">上传文档</el-button>
        </el-upload>
      </div>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table :data="documents" v-loading="loading" border stripe>
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="mime" label="类型" width="180" />
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="Chunk" width="90" align="center" />
        <el-table-column prop="embedding_model" label="Embedding" min-width="150" />
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="canWrite" link type="primary" @click="handleReindex(row)">重建</el-button>
            <el-button v-if="canWrite" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>检索调试</span>
          <el-tag type="info">ADMIN / OPERATOR</el-tag>
        </div>
      </template>
      <div class="search-row">
        <el-input
          v-model="debugQuery"
          type="textarea"
          :rows="3"
          placeholder="输入你希望 AI 检索的问题，例如：III 级响应下现场处置流程是什么？"
        />
        <div class="search-actions">
          <el-button type="primary" :loading="searching" @click="handleSearch">执行检索</el-button>
        </div>
      </div>

      <div v-if="searchResults.length" class="result-list">
        <div v-for="item in searchResults" :key="item.chunk_id" class="result-card">
          <div class="result-header">
            <div class="result-title">{{ item.document_title }}</div>
            <el-tag type="success">score {{ item.score.toFixed(3) }}</el-tag>
          </div>
          <div class="result-meta">
            {{ item.heading_path?.length ? item.heading_path.join(' / ') : '正文' }}
            <span v-if="item.source_uri"> · {{ item.source_uri }}</span>
          </div>
          <div class="result-content">{{ item.content }}</div>
        </div>
      </div>
      <el-empty v-else description="暂无检索结果" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import type { UploadRequestOptions } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { deleteKnowledgeDocument, getKnowledgeStats, listKnowledgeDocuments, reindexKnowledgeDocument, searchKnowledge, uploadKnowledgeDocument } from '@/api/knowledge'
import { useUserStore } from '@/stores/user'
import type { KnowledgeDocument, KnowledgeSearchHit, KnowledgeStats } from '@/types'

const userStore = useUserStore()
const canWrite = computed(() => userStore.hasRole('ADMIN'))

const loading = ref(false)
const searching = ref(false)
const documents = ref<KnowledgeDocument[]>([])
const searchResults = ref<KnowledgeSearchHit[]>([])
const debugQuery = ref('')

const stats = reactive<KnowledgeStats>({
  document_count: 0,
  ready_document_count: 0,
  chunk_count: 0,
  job_success_rate: 0,
  model_distribution: {},
})

const filters = reactive({
  q: '',
  status: '',
})

function formatTime(value?: string | null) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function formatRate(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function statusLabel(status: string) {
  return (
    {
      pending: '待处理',
      processing: '处理中',
      ready: '已就绪',
      failed: '失败',
      deleted: '已删除',
    }[status] || status
  )
}

function statusTagType(status: string) {
  return (
    {
      pending: 'info',
      processing: 'warning',
      ready: 'success',
      failed: 'danger',
      deleted: 'info',
    }[status] || 'info'
  ) as 'success' | 'info' | 'warning' | 'danger'
}

async function fetchStats() {
  const res = await getKnowledgeStats()
  Object.assign(stats, res.data)
}

async function fetchDocuments() {
  loading.value = true
  try {
    const res = await listKnowledgeDocuments({
      q: filters.q || undefined,
      status: filters.status || undefined,
      limit: 100,
      offset: 0,
    })
    documents.value = res.data ?? []
  } catch (error: any) {
    ElMessage.error(error?.message || '获取知识文档失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.q = ''
  filters.status = ''
  fetchDocuments()
}

async function handleUpload(options: UploadRequestOptions) {
  try {
    const file = options.file as File
    await uploadKnowledgeDocument(file)
    ElMessage.success('文档已提交，正在后台索引')
    await Promise.all([fetchDocuments(), fetchStats()])
    options.onSuccess?.({})
  } catch (error: any) {
    ElMessage.error(error?.message || '上传失败')
    options.onError?.(error)
  }
}

async function handleDelete(row: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm(`确定删除《${row.title}》吗？`, '删除确认', { type: 'warning' })
    await deleteKnowledgeDocument(row.id)
    ElMessage.success('文档已删除')
    await Promise.all([fetchDocuments(), fetchStats()])
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '删除失败')
    }
  }
}

async function handleReindex(row: KnowledgeDocument) {
  try {
    await reindexKnowledgeDocument(row.id)
    ElMessage.success('已触发重建')
    await Promise.all([fetchDocuments(), fetchStats()])
  } catch (error: any) {
    ElMessage.error(error?.message || '重建失败')
  }
}

async function handleSearch() {
  if (!debugQuery.value.trim()) {
    ElMessage.warning('请输入检索问题')
    return
  }
  searching.value = true
  try {
    const res = await searchKnowledge({ query: debugQuery.value, topK: 8 })
    searchResults.value = res.data ?? []
  } catch (error: any) {
    ElMessage.error(error?.message || '检索失败')
  } finally {
    searching.value = false
  }
}

onMounted(async () => {
  await Promise.all([fetchDocuments(), fetchStats()])
})
</script>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.page-subtitle {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.stat-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 700;
}

.toolbar-row,
.search-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.search-row {
  align-items: flex-start;
}

.search-actions {
  display: flex;
  align-items: center;
  min-width: 120px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 14px;
  background: var(--el-fill-color-blank);
}

.result-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.result-title {
  font-weight: 600;
}

.result-meta {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.result-content {
  margin-top: 10px;
  white-space: pre-wrap;
  line-height: 1.7;
}

@media (max-width: 960px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
