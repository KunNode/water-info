<template>
  <div class="plan-management">
    <div class="page-header">
      <h2 class="page-title">应急预案管理</h2>
    </div>

    <!-- Filter Form -->
    <el-card shadow="never" class="filter-card">
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
    </el-card>

    <!-- Table -->
    <el-card shadow="never" class="table-card">
      <el-table :data="tableData" v-loading="loading" border stripe style="width: 100%">
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column prop="riskLevel" label="风险等级" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getRiskTagType(row.riskLevel)" effect="dark">
              {{ getRiskLabel(row.riskLevel) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">
              {{ getStatusLabel(row.status) }}
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
    </el-card>

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
            <el-tag :type="getStatusTagType(currentPlan.status)" size="small">
              {{ getStatusLabel(currentPlan.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="摘要" :span="2">
            {{ currentPlan.summary }}
          </el-descriptions-item>
        </el-descriptions>

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
import { ref, reactive, onMounted } from 'vue'
import { Search, Document, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPlans, getPlan, executePlan } from '@/api/flood'
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

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    draft: '草稿',
    approved: '已批准',
    executing: '执行中',
    completed: '已完成'
  }
  return map[status] || status || '未知'
}

const getStatusTagType = (status: string): any => {
  const map: Record<string, string> = {
    draft: 'info',
    approved: 'primary',
    executing: 'warning',
    completed: 'success'
  }
  return map[status] || 'info'
}
</script>

<style scoped>
.plan-management {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.filter-card {
  margin-bottom: 16px;
}

.table-card {
  margin-bottom: 16px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.plan-detail {
  padding: 0 16px;
}

.mb-4 {
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 24px 0 12px 0;
  color: #303133;
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
  background-color: #409EFF;
  border-radius: 2px;
}
</style>
