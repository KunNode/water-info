<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>调度记录</h1>
      <span class="sub">// resource dispatch tracking</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} total</span>
      <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">
        创建调度单
      </el-button>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">TOTAL</div>
        <div class="value">{{ total }}</div>
        <div class="hint">调度记录</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">PENDING</div>
        <div class="value">{{ pendingCount }}</div>
        <div class="hint">待调度</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">IN TRANSIT</div>
        <div class="value">{{ dispatchedCount }}</div>
        <div class="hint">运输中</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">AI SOURCE</div>
        <div class="value">{{ aiCount }}</div>
        <div class="hint">AI自动调度</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option v-for="(item, key) in dispatchStatusMap" :key="key" :label="item.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="queryParams.source" placeholder="全部" clearable>
            <el-option v-for="(label, key) in dispatchSourceMap" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="预案ID">
          <el-input v-model="queryParams.planId" placeholder="预案ID" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">调度记录</span>
        <span class="mono">{{ queryParams.page }} / {{ Math.max(1, Math.ceil(total / queryParams.size)) }} page</span>
        <span class="sp" />
        <span class="fm-tag">显示 {{ tableData.length }} 条</span>
      </div>
      <div class="fm-admin-table__body">
        <el-table v-loading="loading" :data="tableData" stripe>
          <el-table-column prop="resourceName" label="资源名称" min-width="150" />
          <el-table-column prop="resourceType" label="类型" width="90">
            <template #default="{ row }">
              <el-tag size="small">{{ resourceTypeMap[row.resourceType] || row.resourceType }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量" width="80" />
          <el-table-column prop="fromLocation" label="调出地点" min-width="130" />
          <el-table-column prop="toLocation" label="调入地点" min-width="130" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="dispatchStatusMap[row.status]?.type || 'info'" size="small">
                {{ dispatchStatusMap[row.status]?.label || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="100">
            <template #default="{ row }">
              <el-tag :type="row.source === 'AI' ? 'warning' : undefined" size="small">
                {{ dispatchSourceMap[row.source] || row.source }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="planId" label="关联预案" width="130">
            <template #default="{ row }">{{ row.planId || '-' }}</template>
          </el-table-column>
          <el-table-column prop="createdAt" label="创建时间" width="170">
            <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'PENDING'"
                v-permission="['ADMIN', 'OPERATOR']"
                link
                type="primary"
                @click="handleStatusUpdate(row, 'DISPATCHED')"
              >
                调度
              </el-button>
              <el-button
                v-if="row.status === 'DISPATCHED'"
                v-permission="['ADMIN', 'OPERATOR']"
                link
                type="success"
                @click="handleStatusUpdate(row, 'ARRIVED')"
              >
                到达
              </el-button>
              <el-button
                v-if="row.status === 'ARRIVED'"
                v-permission="['ADMIN', 'OPERATOR']"
                link
                type="warning"
                @click="handleStatusUpdate(row, 'RETURNED')"
              >
                归还
              </el-button>
              <el-button
                v-if="row.status === 'PENDING' || row.status === 'DISPATCHED'"
                v-permission="['ADMIN']"
                link
                type="danger"
                @click="handleStatusUpdate(row, 'CANCELLED')"
              >
                取消
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          style="margin-top: 16px; justify-content: flex-end"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </div>

    <DispatchForm v-model:visible="formVisible" @success="fetchData" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { getDispatches, updateDispatchStatus } from '@/api/resource'
import { dispatchSourceMap, dispatchStatusMap, formatDate, resourceTypeMap } from '@/utils/format'
import DispatchForm from '../components/DispatchForm.vue'
import type { DispatchSource, DispatchStatus, ResourceDispatch } from '@/types'

const loading = ref(false)
const tableData = ref<ResourceDispatch[]>([])
const total = ref(0)
const formVisible = ref(false)

const queryParams = reactive({
  page: 1,
  size: 20,
  status: '' as '' | DispatchStatus,
  source: '' as '' | DispatchSource,
  planId: '',
  resourceId: '',
})

const pendingCount = computed(() => tableData.value.filter((dispatch) => dispatch.status === 'PENDING').length)
const dispatchedCount = computed(() => tableData.value.filter((dispatch) => dispatch.status === 'DISPATCHED').length)
const aiCount = computed(() => tableData.value.filter((dispatch) => dispatch.source === 'AI').length)

async function fetchData() {
  loading.value = true
  try {
    const res = await getDispatches(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  queryParams.page = 1
  fetchData()
}

function handleReset() {
  queryParams.status = ''
  queryParams.source = ''
  queryParams.planId = ''
  handleSearch()
}

function handleAdd() {
  formVisible.value = true
}

async function handleStatusUpdate(row: ResourceDispatch, newStatus: DispatchStatus) {
  const labels: Record<DispatchStatus, string> = {
    PENDING: '待调度',
    DISPATCHED: '调度',
    ARRIVED: '确认到达',
    RETURNED: '归还',
    CANCELLED: '取消',
  }
  await ElMessageBox.confirm(`确认将调度单状态变更为「${labels[newStatus]}」？`, '提示', { type: 'warning' })
  await updateDispatchStatus(row.id, { status: newStatus })
  ElMessage.success('状态更新成功')
  fetchData()
}

onMounted(fetchData)
</script>
