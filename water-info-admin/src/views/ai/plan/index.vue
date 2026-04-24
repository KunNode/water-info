<template>
  <div class="fm-admin-page plan-management">
    <div class="fm-page-head">
      <h1>应急预案</h1>
      <span class="sub">// AI generated plans · execution lifecycle</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--warn">{{ executingCount }} executing</span>
      <span class="fm-tag fm-tag--brand">{{ total }} plans</span>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">PLANS</div>
        <div class="value">{{ total }}</div>
        <div class="hint">预案库总数</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">EXECUTING</div>
        <div class="value">{{ executingCount }}</div>
        <div class="hint">执行中</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">APPROVED</div>
        <div class="value">{{ approvedCount }}</div>
        <div class="hint">已批准</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">ACTIONS</div>
        <div class="value">{{ actionCount }}</div>
        <div class="hint">当前页行动项</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :inline="true" :model="queryParams" class="filter-form" @submit.prevent="handleSearch">
        <el-form-item label="关键字">
          <el-input v-model="queryParams.keyword" placeholder="搜索摘要" clearable />
        </el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="queryParams.riskLevel" placeholder="全部" clearable style="width: 160px">
            <el-option label="极高风险" value="critical" />
            <el-option label="高风险" value="high" />
            <el-option label="中等风险" value="moderate" />
            <el-option label="低风险" value="low" />
            <el-option label="正常" value="none" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable style="width: 140px">
            <el-option label="草稿" value="draft" />
            <el-option label="已批准" value="approved" />
            <el-option label="执行中" value="executing" />
            <el-option label="已完成" value="completed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" @click="handleSearch">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">预案列表</span>
        <span class="mono">ranked · reviewed · executable</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="summary" label="摘要" min-width="280">
          <template #default="{ row }">
            <div class="summary-preview">
              <div class="summary-preview-title">{{ getSummaryTitle(row.summary) }}</div>
              <div class="summary-preview-text">{{ getSummaryExcerpt(row.summary) }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="riskLevel" label="风险等级" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getRiskTagType(row.riskLevel)" effect="dark">
              {{ getRiskLabel(row.riskLevel) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="130" align="center">
          <template #default="{ row }">
            <el-select
              v-model="row.status"
              size="small"
              style="width: 110px"
              @change="(val: string) => handleStatusChange(row, val)"
            >
              <el-option label="草稿" value="draft" />
              <el-option label="已批准" value="approved" />
              <el-option label="执行中" value="executing" />
              <el-option label="已完成" value="completed" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="行动数" width="90" align="center">
          <template #default="{ row }">
            {{ row.actions ? row.actions.length : 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180" align="center">
          <template #default="{ row }">
            {{ formatTime(row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">
              <el-icon><Document /></el-icon> 详情
            </el-button>
            <el-button 
              link 
              type="success" 
              size="small" 
              :disabled="row.status === 'completed' || row.status === 'executing'"
              @click="handleExecute(row)"
            >
              <el-icon><VideoPlay /></el-icon> 执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
      </div>
    </div>

    <!-- Detail Drawer -->
    <el-drawer v-model="drawerVisible" title="应急预案详情" size="50%" destroy-on-close>
      <div v-loading="detailLoading" v-if="currentPlan" class="plan-detail">
        <el-descriptions title="基本信息" :column="2" border class="mb-4">
          <el-descriptions-item label="预案 ID">{{ currentPlan.id }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentPlan.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="getRiskTagType(currentPlan.riskLevel)" effect="dark" size="small">
              {{ getRiskLabel(currentPlan.riskLevel) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-select
              v-model="currentPlan.status"
              size="small"
              style="width: 120px"
              @change="(val: string) => handleStatusChange(currentPlan!, val)"
            >
              <el-option label="草稿" value="draft" />
              <el-option label="已批准" value="approved" />
              <el-option label="执行中" value="executing" />
              <el-option label="已完成" value="completed" />
            </el-select>
          </el-descriptions-item>
        </el-descriptions>

        <section class="summary-panel mb-4">
          <div class="summary-panel-header">
            <div>
              <div class="summary-panel-eyebrow">AI 研判摘要</div>
              <div class="summary-panel-title">{{ getSummaryTitle(currentPlan.summary) }}</div>
            </div>
            <el-tag :type="getRiskTagType(currentPlan.riskLevel)" effect="plain" round>
              {{ getRiskLabel(currentPlan.riskLevel) }}
            </el-tag>
          </div>
          <div class="summary-panel-divider" />
          <div class="summary-markdown markdown-body" v-html="renderPlanSummary(currentPlan.summary)" />
        </section>

        <div class="section-title">应急行动列表 ({{ currentPlan.actions?.length || 0 }})</div>
        <el-table :data="currentPlan.actions || []" border size="small" class="mb-4">
          <el-table-column type="index" label="#" width="50" align="center" />
          <el-table-column prop="description" label="行动描述" />
          <el-table-column prop="priority" label="优先级" width="90" align="center" />
          <el-table-column prop="assignee" label="责任人" width="120" />
          <el-table-column prop="status" label="状态" width="100" align="center" />
        </el-table>

        <div class="section-title">资源清单 ({{ currentPlan.resources?.length || 0 }})</div>
        <el-table :data="currentPlan.resources || []" border size="small" class="mb-4">
          <el-table-column type="index" label="#" width="50" align="center" />
          <el-table-column prop="type" label="资源类型" width="120" />
          <el-table-column prop="name" label="资源名称" />
          <el-table-column prop="quantity" label="数量" width="100" align="center" />
          <el-table-column prop="location" label="位置" />
        </el-table>

        <div class="section-title">通知方案 ({{ currentPlan.notifications?.length || 0 }})</div>
        <el-table :data="currentPlan.notifications || []" border size="small" class="mb-4">
          <el-table-column type="index" label="#" width="50" align="center" />
          <el-table-column prop="channel" label="渠道" width="100" align="center" />
          <el-table-column prop="target" label="通知对象" width="140" />
          <el-table-column prop="message" label="通知内容" />
          <el-table-column prop="status" label="状态" width="100" align="center" />
        </el-table>
      </div>
      
      <template #footer>
        <div style="flex: auto">
          <el-button @click="drawerVisible = false">关闭</el-button>
          <el-button 
            type="success" 
            :loading="executing" 
            :disabled="!currentPlan || currentPlan.status === 'completed' || currentPlan.status === 'executing'"
            @click="executeCurrentPlan"
          >
            <el-icon><VideoPlay /></el-icon> 执行预案
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { Search, Document, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { getPlans, getPlan, executePlan, updatePlanStatus } from '@/api/flood'
import type { FloodPlan } from '@/types'

const loading = ref(false)
const tableData = ref<FloodPlan[]>([])
const total = ref(0)
const queryParams = reactive({
  page: 1,
  size: 10,
  keyword: '',
  riskLevel: '',
  status: ''
})

const drawerVisible = ref(false)
const detailLoading = ref(false)
const currentPlan = ref<FloodPlan | null>(null)
const executing = ref(false)

const executingCount = computed(() => tableData.value.filter((item) => item.status === 'executing').length)
const approvedCount = computed(() => tableData.value.filter((item) => item.status === 'approved').length)
const actionCount = computed(() => {
  return tableData.value.reduce((sum, item) => sum + (item.actions?.length || 0), 0)
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getPlans({ 
      page: queryParams.page, 
      size: queryParams.size
    })
    if (res && res.data) {
      let list = res.data.records || []
      
      // Frontend filtering since API doesn't support these natively in signature
      if (queryParams.keyword) {
        list = list.filter((item: FloodPlan) => item.summary && item.summary.includes(queryParams.keyword))
      }
      if (queryParams.riskLevel) {
        list = list.filter((item: FloodPlan) => item.riskLevel === queryParams.riskLevel)
      }
      if (queryParams.status) {
        list = list.filter((item: FloodPlan) => item.status === queryParams.status)
      }
      
      tableData.value = list
      total.value = res.data.total || 0
    }
  } catch (err: unknown) {
    if (err instanceof Error) {
      ElMessage.error(err.message || '获取预案列表失败')
    } else {
      ElMessage.error('获取预案列表失败')
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})

const handleSearch = () => {
  queryParams.page = 1
  fetchData()
}

const resetQuery = () => {
  queryParams.keyword = ''
  queryParams.riskLevel = ''
  queryParams.status = ''
  handleSearch()
}

const handleSizeChange = (val: number) => {
  queryParams.size = val
  fetchData()
}

const handleCurrentChange = (val: number) => {
  queryParams.page = val
  fetchData()
}

const openDetail = async (row: FloodPlan) => {
  drawerVisible.value = true
  detailLoading.value = true
  currentPlan.value = row // initial data
  
  try {
    const res = await getPlan(row.id)
    if (res && res.data) {
      currentPlan.value = res.data
    }
  } catch (err: unknown) {
    if (err instanceof Error) {
      ElMessage.error(err.message || '获取预案详情失败')
    } else {
      ElMessage.error('获取预案详情失败')
    }
  } finally {
    detailLoading.value = false
  }
}

const handleStatusChange = async (row: FloodPlan, newStatus: string) => {
  const prevStatus = row.status
  try {
    await updatePlanStatus(row.id, newStatus)
    ElMessage.success('状态已更新')
    if (currentPlan.value?.id === row.id) {
      currentPlan.value.status = newStatus as FloodPlan['status']
    }
  } catch {
    row.status = prevStatus
  }
}

const handleExecute = (row: FloodPlan) => {
  ElMessageBox.confirm(`确定要执行预案吗？该操作将分发行动任务并发送通知。`, '执行确认', {
    confirmButtonText: '确定执行',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await executePlan(row.id)
      ElMessage.success('预案执行已启动')
      fetchData()
    } catch (err: unknown) {
      if (err instanceof Error) {
        ElMessage.error(err.message || '执行预案失败')
      } else {
        ElMessage.error('执行预案失败')
      }
    }
  }).catch(() => {})
}

const executeCurrentPlan = async () => {
  if (!currentPlan.value) return
  executing.value = true
  try {
    await executePlan(currentPlan.value.id)
    ElMessage.success('预案执行已启动')
    currentPlan.value.status = 'executing'
    fetchData()
  } catch (err: unknown) {
    if (err instanceof Error) {
      ElMessage.error(err.message || '执行预案失败')
    } else {
      ElMessage.error('执行预案失败')
    }
  } finally {
    executing.value = false
  }
}

// Helpers
const stripMarkdown = (text = '') => {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[.*?\]\(.*?\)/g, ' ')
    .replace(/\[(.*?)\]\(.*?\)/g, '$1')
    .replace(/^>\s?/gm, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/(\*\*|__|\*|_|~~)/g, '')
    .replace(/\|/g, ' ')
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

const getSummaryTitle = (summary = '') => {
  const heading = summary.match(/^#\s+(.+)$/m)?.[1]?.trim()
  if (heading) return heading

  const plain = stripMarkdown(summary)
  if (!plain) return '暂无摘要'
  return plain.length > 26 ? `${plain.slice(0, 26)}...` : plain
}

const getSummaryExcerpt = (summary = '') => {
  const plain = stripMarkdown(summary)
  if (!plain) return '暂无摘要内容'

  const title = getSummaryTitle(summary)
  const normalized = plain.startsWith(title) ? plain.slice(title.length).trim() : plain
  const excerpt = normalized || plain
  return excerpt.length > 96 ? `${excerpt.slice(0, 96)}...` : excerpt
}

const renderPlanSummary = (summary = '') => {
  if (!summary) return '<p>暂无摘要内容</p>'

  const raw = marked.parse(summary, { async: false }) as string
  return DOMPurify.sanitize(raw, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'code', 'pre', 'blockquote',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'hr', 'a', 'span', 'div',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
  })
}

const formatTime = (timeStr?: string) => {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString()
}

const getRiskLabel = (level: string) => {
  const map: Record<string, string> = {
    critical: '极高风险',
    high: '高风险',
    moderate: '中等风险',
    low: '低风险',
    none: '正常'
  }
  return map[level] || level || '未知'
}

const getRiskTagType = (level: string): any => {
  const map: Record<string, string> = {
    critical: 'danger', 
    high: 'danger',
    moderate: 'warning',
    low: 'primary',
    none: 'info'
  }
  return map[level] || 'info'
}

</script>

<style scoped>
.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.summary-preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.summary-preview-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--fm-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.summary-preview-text {
  font-size: 12px;
  line-height: 1.6;
  color: var(--fm-fg-soft);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.plan-detail {
  padding: 0 16px;
}

.summary-panel {
  padding: 18px 20px;
  border-radius: var(--fm-radius);
  background:
    radial-gradient(circle at top right, rgba(73, 225, 255, 0.12), transparent 38%),
    var(--fm-grad-raised);
  border: 1px solid var(--fm-line);
  box-shadow: var(--fm-shadow-card);
}

.summary-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.summary-panel-eyebrow {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--fm-brand-2);
  margin-bottom: 6px;
}

.summary-panel-title {
  font-size: 22px;
  line-height: 1.35;
  font-weight: 700;
  color: var(--fm-fg);
}

.summary-panel-divider {
  height: 1px;
  margin: 14px 0 18px;
  background: var(--fm-grad-line);
}

.summary-markdown {
  font-size: 14px;
  line-height: 1.85;
  color: var(--fm-fg-soft);
}

.mb-4 {
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 24px 0 12px 0;
  color: var(--fm-fg);
  padding-left: 10px;
  position: relative;
}

.section-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 4px;
  background: var(--fm-grad-brand);
  border-radius: 2px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 18px 0 10px;
  line-height: 1.4;
  font-weight: 700;
  color: var(--fm-brand-2);
}

.markdown-body :deep(h1) {
  font-size: 24px;
  margin-top: 0;
}

.markdown-body :deep(h2) {
  font-size: 19px;
}

.markdown-body :deep(h3) {
  font-size: 16px;
}

.markdown-body :deep(h4) {
  font-size: 15px;
}

.markdown-body :deep(p) {
  margin: 8px 0;
  word-break: break-word;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 22px;
  margin: 10px 0;
}

.markdown-body :deep(li) {
  margin: 6px 0;
}

.markdown-body :deep(strong) {
  color: var(--fm-fg);
  font-weight: 700;
}

.markdown-body :deep(em) {
  color: var(--fm-brand-2);
  font-style: normal;
}

.markdown-body :deep(code) {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(47, 123, 255, 0.14);
  color: var(--fm-brand-2);
  font-size: 12px;
}

.markdown-body :deep(pre) {
  margin: 12px 0;
  padding: 14px 16px;
  overflow-x: auto;
  border-radius: 12px;
  background: var(--fm-bg-1);
  color: var(--fm-fg);
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-body :deep(blockquote) {
  margin: 14px 0;
  padding: 12px 14px;
  border-left: 4px solid var(--fm-warn);
  border-radius: 0 12px 12px 0;
  background: rgba(255, 181, 71, 0.08);
  color: var(--fm-fg-soft);
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid rgba(148, 163, 184, 0.35);
  margin: 16px 0;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
  overflow: hidden;
  border-radius: 12px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 10px 12px;
  border: 1px solid var(--fm-line);
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--fm-bg-2);
  color: var(--fm-brand-2);
  font-weight: 700;
}

@media (max-width: 900px) {
  .summary-panel-header {
    flex-direction: column;
  }

  .summary-panel-title {
    font-size: 18px;
  }
}
</style>
