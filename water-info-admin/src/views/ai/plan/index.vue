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
            <el-option label="草案" value="draft" />
            <el-option label="已批准" value="approved" />
            <el-option label="执行中" value="executing" />
            <el-option label="已完成" value="completed" />
            <el-option label="执行失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
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
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
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
              v-if="isReviewer"
              link
              type="success"
              size="small"
              :disabled="!['approved', 'failed', 'cancelled'].includes(row.status)"
              @click="handleExecute(row)"
            >
              <el-icon><VideoPlay /></el-icon> {{ ['failed', 'cancelled'].includes(row.status) ? '重新执行' : '执行' }}
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
    <el-drawer v-model="drawerVisible" title="应急预案详情" size="50%" destroy-on-close :before-close="handleDrawerClose">
      <div v-loading="detailLoading" v-if="currentPlan" class="plan-detail">
        <div class="detail-header-bar mb-4">
          <el-tag v-if="editMode" type="warning">编辑中</el-tag>
          <el-button v-if="canEditCurrentPlan && !editMode" size="small" @click="enterEditMode">编辑</el-button>
          <el-button v-if="canApproveCurrentPlan && !editMode" size="small" type="success" @click="openApprovalDialog">
            批准
          </el-button>
        </div>

        <el-tabs v-model="detailTab" @tab-change="handleDetailTabChange">
          <el-tab-pane label="详情" name="detail">
        <el-descriptions title="基本信息" :column="2" border class="mb-4">
          <el-descriptions-item label="预案 ID">{{ currentPlan.id }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentPlan.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="getRiskTagType(currentPlan.riskLevel)" effect="dark" size="small">
              {{ getRiskLabel(currentPlan.riskLevel) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(currentPlan.status)" size="small">
              {{ statusLabel(currentPlan.status) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <!-- View Mode: read-only summary -->
        <template v-if="!editMode">
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

          <div class="section-title">
            应急行动列表 ({{ displayActions.length }})
            <span v-if="isExecutingCurrentPlan" style="font-size: 12px; color: #e6a23c; margin-left: 8px">执行中 · 每 3 秒刷新</span>
          </div>
          <el-table :data="displayActions" border size="small" class="mb-4" empty-text="暂无应急行动">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="description" label="行动描述" />
            <el-table-column prop="priority" label="优先级" width="90" align="center" />
            <el-table-column prop="responsible_dept" label="责任部门" width="120" />
            <el-table-column label="状态" width="140" align="center">
              <template #default="{ row }">
                <el-select
                  v-if="isExecutingCurrentPlan"
                  :model-value="row.status"
                  size="small"
                  style="width: 120px"
                  @change="(val: string) => handleActionStatusChange(row.action_id, val)"
                >
                  <el-option label="待执行" value="pending" />
                  <el-option label="执行中" value="in_progress" />
                  <el-option label="已完成" value="completed" />
                  <el-option label="已失败" value="failed" />
                </el-select>
                <el-tag v-else :type="actionStatusTagType(row.status)" size="small">
                  {{ actionStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div class="section-title">资源清单 ({{ currentPlan.resources?.length || 0 }})</div>
          <el-table :data="currentPlan.resources || []" border size="small" class="mb-4" empty-text="暂无资源项">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="type" label="资源类型" width="120" />
            <el-table-column prop="name" label="资源名称" />
            <el-table-column prop="quantity" label="数量" width="100" align="center" />
            <el-table-column prop="location" label="位置" />
          </el-table>

          <div class="section-title">通知方案 ({{ currentPlan.notifications?.length || 0 }})</div>
          <el-table :data="currentPlan.notifications || []" border size="small" class="mb-4" empty-text="暂无通知方案">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="channel" label="渠道" width="100" align="center" />
            <el-table-column prop="target" label="通知对象" width="140" />
            <el-table-column prop="message" label="通知内容" />
            <el-table-column prop="status" label="状态" width="100" align="center" />
          </el-table>
        </template>

        <!-- Edit Mode: editable forms -->
        <template v-if="editMode && draftPlan">
          <div class="section-title">摘要 (Markdown)</div>
          <el-input
            v-model="draftPlan.summary"
            type="textarea"
            :autosize="{ minRows: 10, maxRows: 40 }"
            placeholder="请输入预案摘要（支持 Markdown）"
            class="mb-4"
          />

          <div class="section-title">
            应急行动列表 ({{ draftPlan.actions?.length || 0 }})
            <el-button size="small" type="primary" class="section-add-btn" @click="addAction">新增行</el-button>
          </div>
          <el-table :data="draftPlan.actions || []" border size="small" class="mb-4" empty-text="暂无应急行动">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column label="行动描述" min-width="180">
              <template #default="{ row }">
                <el-input v-model="row.description" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="100" align="center">
              <template #default="{ row }">
                <el-input v-model="row.priority" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="责任人" width="120">
              <template #default="{ row }">
                <el-input v-model="row.assignee" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-input v-model="row.status" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70" align="center">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="removeAction($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="section-title">
            资源清单 ({{ draftPlan.resources?.length || 0 }})
            <el-button size="small" type="primary" class="section-add-btn" @click="addResource">新增行</el-button>
          </div>
          <el-table :data="draftPlan.resources || []" border size="small" class="mb-4" empty-text="暂无资源项">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column label="资源类型" width="120">
              <template #default="{ row }">
                <el-input v-model="row.type" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="资源名称" min-width="140">
              <template #default="{ row }">
                <el-input v-model="row.name" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="数量" width="100" align="center">
              <template #default="{ row }">
                <el-input-number v-model="row.quantity" size="small" :min="0" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="位置" min-width="140">
              <template #default="{ row }">
                <el-input v-model="row.location" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70" align="center">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="removeResource($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="section-title">
            通知方案 ({{ draftPlan.notifications?.length || 0 }})
            <el-button size="small" type="primary" class="section-add-btn" @click="addNotification">新增行</el-button>
          </div>
          <el-table :data="draftPlan.notifications || []" border size="small" class="mb-4" empty-text="暂无通知方案">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column label="渠道" width="100" align="center">
              <template #default="{ row }">
                <el-input v-model="row.channel" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="通知对象" width="140">
              <template #default="{ row }">
                <el-input v-model="row.target" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="通知内容" min-width="180">
              <template #default="{ row }">
                <el-input v-model="row.message" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-input v-model="row.status" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70" align="center">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="removeNotification($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
          </el-tab-pane>
          <el-tab-pane v-if="showAuditTab" label="审计记录" name="audits">
            <div v-loading="auditLoading" class="audit-panel">
              <el-empty v-if="!auditLoading && auditRecords.length === 0" description="暂无审计记录" />
              <el-timeline v-else>
                <el-timeline-item
                  v-for="record in auditRecords"
                  :key="record.id"
                  :timestamp="formatTime(record.reviewedAt)"
                  placement="top"
                >
                  <div class="audit-record">
                    <div class="audit-record__head">
                      <strong>{{ formatAuditAction(record.action) }}</strong>
                      <span>{{ record.reviewerUsername }}</span>
                    </div>
                    <p v-if="record.opinion" class="audit-opinion">{{ record.opinion }}</p>
                    <el-table :data="record.changes || []" size="small" border empty-text="无内容修改">
                      <el-table-column prop="fieldPath" label="字段" min-width="150" />
                      <el-table-column prop="changeType" label="类型" width="90" />
                      <el-table-column label="修改前" min-width="160">
                        <template #default="{ row }">{{ formatChangeValue(row.oldValue) }}</template>
                      </el-table-column>
                      <el-table-column label="修改后" min-width="160">
                        <template #default="{ row }">{{ formatChangeValue(row.newValue) }}</template>
                      </el-table-column>
                    </el-table>
                  </div>
                </el-timeline-item>
              </el-timeline>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      
      <template #footer>
        <div style="flex: auto">
          <template v-if="editMode">
            <el-button @click="cancelEdit">取消</el-button>
            <el-button type="primary" :loading="saving" :disabled="saving" @click="handleSave">保存</el-button>
          </template>
          <template v-else>
            <el-button @click="drawerVisible = false">关闭</el-button>
            <el-button
              v-if="canCancelCurrentPlan"
              type="danger"
              @click="cancelCurrentPlan"
            >
              <el-icon><VideoPause /></el-icon> 取消执行
            </el-button>
            <el-button
              v-if="canExecuteCurrentPlan"
              type="success"
              :loading="executing"
              :disabled="executing"
              @click="executeCurrentPlan"
            >
              <el-icon><VideoPlay /></el-icon>
              {{ currentPlan?.status === 'approved' ? '执行预案' : '重新执行' }}
            </el-button>
          </template>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="approvalDialogVisible" title="批准草案" width="520px" :close-on-click-modal="!approvalLoading">
      <el-form label-position="top">
        <el-form-item label="审核意见" required>
          <el-input
            v-model="approvalOpinion"
            type="textarea"
            :maxlength="500"
            show-word-limit
            :rows="5"
            :disabled="approvalLoading"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="approvalLoading" @click="approvalDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="approvalLoading"
          :disabled="!opinionValid || approvalLoading"
          @click="handleApprove"
        >
          确认批准
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Search, Document, VideoPlay, VideoPause } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  getPlans, getPlan, executePlan, updatePlan, approvePlan, getPlanAudits,
  getPlanProgress, updateActionStatus, cancelPlan,
} from '@/api/flood'
import { useUserStore } from '@/stores/user'
import type { FloodPlan, PlanAuditRecord, PlanEditRequest, ActionProgress } from '@/types'
import { statusLabel } from './statusLabel'

const userStore = useUserStore()
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
const saving = ref(false)
const detailTab = ref('detail')
const auditLoading = ref(false)
const auditLoaded = ref(false)
const auditRecords = ref<PlanAuditRecord[]>([])
const approvalDialogVisible = ref(false)
const approvalOpinion = ref('')
const approvalLoading = ref(false)

// Edit mode state
const editMode = ref(false)
const draftPlan = ref<FloodPlan | null>(null)
const isDirty = computed(() => {
  if (!editMode.value || !draftPlan.value || !currentPlan.value) return false
  return JSON.stringify(draftPlan.value) !== JSON.stringify(currentPlan.value)
})

// Execution progress polling
const progressData = ref<ActionProgress[]>([])
const progressLoading = ref(false)
let progressTimer: ReturnType<typeof setInterval> | null = null

const startProgressPolling = (planId: string) => {
  stopProgressPolling()
  const poll = async () => {
    try {
      const res = await getPlanProgress(planId)
      if (res && res.data) {
        progressData.value = res.data.actions || []
        // Stop polling if plan reached a terminal state
        const ps = res.data.plan_status
        if (ps === 'completed' || ps === 'failed' || ps === 'cancelled') {
          stopProgressPolling()
          if (currentPlan.value) {
            currentPlan.value.status = ps as FloodPlan['status']
          }
          fetchData()
        }
      }
    } catch {
      // ignore polling errors
    }
  }
  poll()
  progressTimer = setInterval(poll, 3000)
}

const stopProgressPolling = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

onBeforeUnmount(() => stopProgressPolling())

const executingCount = computed(() => tableData.value.filter((item) => item.status === 'executing').length)
const approvedCount = computed(() => tableData.value.filter((item) => item.status === 'approved').length)
const actionCount = computed(() => {
  return tableData.value.reduce((sum, item) => sum + (item.actions?.length || 0), 0)
})
const isReviewer = computed(() => userStore.roles.some((role) => role === 'ADMIN' || role === 'OPERATOR'))
const canEditCurrentPlan = computed(() => {
  return !!currentPlan.value && isReviewer.value && ['draft', 'approved'].includes(currentPlan.value.status)
})
const canApproveCurrentPlan = computed(() => {
  return !!currentPlan.value && isReviewer.value && currentPlan.value.status === 'draft'
})
const canExecuteCurrentPlan = computed(() => {
  return !!currentPlan.value && isReviewer.value
    && ['approved', 'failed', 'cancelled'].includes(currentPlan.value.status)
})
const canCancelCurrentPlan = computed(() => {
  return !!currentPlan.value && isReviewer.value && currentPlan.value.status === 'executing'
})
const isExecutingCurrentPlan = computed(() => {
  return !!currentPlan.value && currentPlan.value.status === 'executing'
})
const showAuditTab = computed(() => {
  return !!currentPlan.value && ['approved', 'executing', 'completed', 'failed', 'cancelled'].includes(currentPlan.value.status)
})
const opinionValid = computed(() => {
  const len = approvalOpinion.value.trim().length
  return len >= 1 && len <= 500
})

// Actions displayed in the detail table: use live progress data when executing, otherwise plan actions
const displayActions = computed(() => {
  if (progressData.value.length > 0) {
    return progressData.value
  }
  return currentPlan.value?.actions || []
})

const actionStatusTagType = (status: string): 'info' | 'warning' | 'success' | 'danger' => {
  const map: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const actionStatusLabel = (status: string): string => {
  const map: Record<string, string> = {
    pending: '待执行',
    in_progress: '执行中',
    completed: '已完成',
    failed: '已失败',
  }
  return map[status] || status || '未知'
}

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
  editMode.value = false
  draftPlan.value = null
  detailTab.value = 'detail'
  auditLoaded.value = false
  auditRecords.value = []
  progressData.value = []
  stopProgressPolling()

  try {
    const res = await getPlan(row.id)
    if (res && res.data) {
      currentPlan.value = res.data
      // Start progress polling if plan is executing
      if (res.data.status === 'executing') {
        startProgressPolling(res.data.id)
      }
    }
  } catch (err: unknown) {
    currentPlan.value = null
    if (err instanceof Error) {
      ElMessage.error(err.message || '获取预案详情失败')
    } else {
      ElMessage.error('获取预案详情失败')
    }
  } finally {
    detailLoading.value = false
  }
}

// Edit mode functions
const enterEditMode = () => {
  if (!canEditCurrentPlan.value || !currentPlan.value) return
  draftPlan.value = JSON.parse(JSON.stringify(currentPlan.value))
  editMode.value = true
  detailTab.value = 'detail'
}

const cancelEdit = async () => {
  if (isDirty.value) {
    try {
      await ElMessageBox.confirm('存在未保存修改，确认放弃？')
    } catch {
      return
    }
  }
  editMode.value = false
  draftPlan.value = null
}

const handleDrawerClose = async (done: () => void) => {
  if (editMode.value && isDirty.value) {
    try {
      await ElMessageBox.confirm('存在未保存修改，确认放弃？')
    } catch {
      return
    }
  }
  editMode.value = false
  draftPlan.value = null
  stopProgressPolling()
  progressData.value = []
  done()
}

const handleDetailTabChange = (name: string | number) => {
  if (name === 'audits') {
    loadAudits()
  }
}

onBeforeRouteLeave(async () => {
  if (editMode.value && isDirty.value) {
    try {
      await ElMessageBox.confirm('存在未保存修改，确认放弃？')
    } catch {
      return false
    }
  }
  return true
})

const addAction = () => {
  if (!draftPlan.value) return
  if (!draftPlan.value.actions) draftPlan.value.actions = []
  draftPlan.value.actions.push({ id: '', description: '', priority: '3', assignee: '', status: 'pending' })
}

const removeAction = (index: number) => {
  if (!draftPlan.value?.actions) return
  draftPlan.value.actions.splice(index, 1)
}

const addResource = () => {
  if (!draftPlan.value) return
  if (!draftPlan.value.resources) draftPlan.value.resources = []
  draftPlan.value.resources.push({ type: '', name: '', quantity: 0, location: '' })
}

const removeResource = (index: number) => {
  if (!draftPlan.value?.resources) return
  draftPlan.value.resources.splice(index, 1)
}

const addNotification = () => {
  if (!draftPlan.value) return
  if (!draftPlan.value.notifications) draftPlan.value.notifications = []
  draftPlan.value.notifications.push({ channel: '', target: '', message: '', status: 'pending' })
}

const removeNotification = (index: number) => {
  if (!draftPlan.value?.notifications) return
  draftPlan.value.notifications.splice(index, 1)
}

const handleSave = async () => {
  if (!currentPlan.value || !draftPlan.value) return
  saving.value = true
  try {
    const payload: PlanEditRequest = { version: currentPlan.value.version }

    // Diff summary
    if (draftPlan.value.summary !== currentPlan.value.summary) {
      payload.summary = draftPlan.value.summary
    }

    // Diff actions
    const oldActions = currentPlan.value.actions || []
    const newActions = draftPlan.value.actions || []
    const newActionIds = new Set(newActions.map((a) => a.id).filter(Boolean))
    const actionsUpsert = newActions
      .filter((a) => {
        if (!a.id) return true // new item
        const old = oldActions.find((o) => o.id === a.id)
        if (!old) return true
        return (
          a.description !== old.description ||
          a.priority !== old.priority ||
          a.assignee !== old.assignee ||
          a.status !== old.status
        )
      })
      .map((a) => ({
        actionId: a.id || null,
        description: a.description,
        priority: Number(a.priority) || 0,
        assignee: a.assignee,
        status: a.status,
      }))
    const actionsDelete = oldActions.filter((a) => a.id && !newActionIds.has(a.id)).map((a) => a.id)
    if (actionsUpsert.length || actionsDelete.length) {
      payload.actions = {
        upsert: actionsUpsert.length ? actionsUpsert : undefined,
        delete: actionsDelete.length ? actionsDelete : undefined,
      }
    }

    // Diff resources
    const oldResources = currentPlan.value.resources || []
    const newResources = draftPlan.value.resources || []
    const newResourceIds = new Set(newResources.map((r) => (r as any).id).filter(Boolean))
    const resourcesUpsert = newResources
      .filter((r) => {
        const rid = (r as any).id
        if (!rid) return true // new item
        const old = oldResources.find((o) => (o as any).id === rid)
        if (!old) return true
        return r.type !== old.type || r.name !== old.name || r.quantity !== old.quantity || r.location !== old.location
      })
      .map((r) => ({
        resourceId: (r as any).id ? Number((r as any).id) : 0,
        type: r.type,
        name: r.name,
        quantity: r.quantity,
        location: r.location,
      }))
    const resourcesDelete = oldResources
      .filter((r) => (r as any).id && !newResourceIds.has((r as any).id))
      .map((r) => Number((r as any).id))
    if (resourcesUpsert.length || resourcesDelete.length) {
      payload.resources = {
        upsert: resourcesUpsert.length ? resourcesUpsert : undefined,
        delete: resourcesDelete.length ? resourcesDelete : undefined,
      }
    }

    // Diff notifications
    const oldNotifications = currentPlan.value.notifications || []
    const newNotifications = draftPlan.value.notifications || []
    const newNotifIds = new Set(newNotifications.map((n) => (n as any).id).filter(Boolean))
    const notificationsUpsert = newNotifications
      .filter((n) => {
        const nid = (n as any).id
        if (!nid) return true // new item
        const old = oldNotifications.find((o) => (o as any).id === nid)
        if (!old) return true
        return (
          n.channel !== old.channel || n.target !== old.target || n.message !== old.message || n.status !== old.status
        )
      })
      .map((n) => ({
        notificationId: (n as any).id ? Number((n as any).id) : 0,
        channel: n.channel,
        target: n.target,
        message: n.message,
        status: n.status,
      }))
    const notificationsDelete = oldNotifications
      .filter((n) => (n as any).id && !newNotifIds.has((n as any).id))
      .map((n) => Number((n as any).id))
    if (notificationsUpsert.length || notificationsDelete.length) {
      payload.notifications = {
        upsert: notificationsUpsert.length ? notificationsUpsert : undefined,
        delete: notificationsDelete.length ? notificationsDelete : undefined,
      }
    }

    const res = await updatePlan(currentPlan.value.id, payload)
    if (res && res.data) {
      currentPlan.value = res.data
      draftPlan.value = JSON.parse(JSON.stringify(res.data))
      ElMessage.success({ message: '保存成功', duration: 2000 })
      editMode.value = false
      draftPlan.value = null
    }
  } catch (err: unknown) {
    if (err instanceof Error) {
      ElMessage.error(err.message || '保存失败')
    } else {
      ElMessage.error('保存失败')
    }
  } finally {
    saving.value = false
  }
}

const openApprovalDialog = () => {
  if (!canApproveCurrentPlan.value) return
  approvalDialogVisible.value = true
  approvalOpinion.value = ''
}

const handleApprove = async () => {
  if (!currentPlan.value || !opinionValid.value) return
  approvalLoading.value = true
  try {
    const res = await approvePlan(currentPlan.value.id, {
      version: currentPlan.value.version,
      opinion: approvalOpinion.value.trim(),
    })
    if (res?.data) {
      currentPlan.value.status = 'approved'
      currentPlan.value.version = res.data.version
      approvalDialogVisible.value = false
      approvalOpinion.value = ''
      auditLoaded.value = false
      ElMessage.success({ message: '批准成功', duration: 2000 })
      const detail = await getPlan(currentPlan.value.id)
      if (detail?.data) currentPlan.value = detail.data
      fetchData()
    }
  } catch (err: unknown) {
    if (err instanceof Error) {
      ElMessage.error(err.message || '批准失败')
    } else {
      ElMessage.error('批准失败')
    }
  } finally {
    approvalLoading.value = false
  }
}

const loadAudits = async () => {
  if (!currentPlan.value || auditLoaded.value || auditLoading.value) return
  auditLoading.value = true
  try {
    const res = await getPlanAudits(currentPlan.value.id)
    auditRecords.value = res.data.records || []
    auditLoaded.value = true
  } catch (err: unknown) {
    if (err instanceof Error) {
      ElMessage.error(err.message || '获取审计记录失败')
    } else {
      ElMessage.error('获取审计记录失败')
    }
  } finally {
    auditLoading.value = false
  }
}



const handleExecute = (row: FloodPlan) => {
  if (!isReviewer.value || !['approved', 'failed', 'cancelled'].includes(row.status)) return
  const msg = row.status === 'approved'
    ? '确定要执行预案吗？该操作将分发行动任务并发送通知。'
    : '确定要重新执行预案吗？将重置所有行动状态并重新执行。'
  ElMessageBox.confirm(msg, '执行确认', {
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
  if (!canExecuteCurrentPlan.value || !currentPlan.value) return
  executing.value = true
  try {
    await executePlan(currentPlan.value.id)
    ElMessage.success('预案执行已启动')
    currentPlan.value.status = 'executing'
    progressData.value = []
    startProgressPolling(currentPlan.value.id)
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

const cancelCurrentPlan = async () => {
  if (!canCancelCurrentPlan.value || !currentPlan.value) return
  try {
    await ElMessageBox.confirm('确定要取消正在执行的预案吗？', '取消确认', {
      confirmButtonText: '确定取消',
      cancelButtonText: '继续执行',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await cancelPlan(currentPlan.value.id)
    ElMessage.success('取消指令已发送')
  } catch (err: unknown) {
    if (err instanceof Error) {
      ElMessage.error(err.message || '取消预案失败')
    } else {
      ElMessage.error('取消预案失败')
    }
  }
}

const handleActionStatusChange = async (actionId: string, newStatus: string) => {
  if (!currentPlan.value) return
  try {
    await updateActionStatus(currentPlan.value.id, actionId, newStatus)
    // Update local progress data
    const action = progressData.value.find((a) => a.action_id === actionId)
    if (action) {
      action.status = newStatus as ActionProgress['status']
    }
  } catch (err: unknown) {
    if (err instanceof Error) {
      ElMessage.error(err.message || '更新行动状态失败')
    } else {
      ElMessage.error('更新行动状态失败')
    }
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

const statusTagType = (status: string): any => {
  const map: Record<string, string> = {
    draft: 'info',
    approved: 'success',
    executing: 'warning',
    completed: '',
    failed: 'danger',
    cancelled: 'info'
  }
  return map[status] || 'info'
}

const formatAuditAction = (action: string) => {
  const map: Record<string, string> = {
    approve: '批准',
    edit_after_approve: '批准后编辑',
  }
  return map[action] || action
}

const formatChangeValue = (value: string | null) => {
  if (value === null || value === undefined) return '-'
  return value.length > 120 ? `${value.slice(0, 120)}...` : value
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

.detail-header-bar {
  display: flex;
  align-items: center;
  gap: 12px;
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

.section-title .section-add-btn {
  margin-left: 12px;
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
