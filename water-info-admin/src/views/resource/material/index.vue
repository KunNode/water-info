<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>物资管理</h1>
      <span class="sub">// emergency materials inventory</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} total</span>
      <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">
        新增物资
      </el-button>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">TOTAL</div>
        <div class="value">{{ total }}</div>
        <div class="hint">物资种类</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">AVAILABLE</div>
        <div class="value">{{ availableCount }}</div>
        <div class="hint">可用物资</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">QUANTITY</div>
        <div class="value">{{ totalQuantity }}</div>
        <div class="hint">总库存量</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">LOW STOCK</div>
        <div class="value">{{ lowStockCount }}</div>
        <div class="hint">库存预警</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="关键词">
          <el-input v-model="queryParams.keyword" placeholder="物资名称/存放地点" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option v-for="(item, key) in resourceStatusMap" :key="key" :label="item.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">物资列表</span>
        <span class="mono">{{ queryParams.page }} / {{ Math.max(1, Math.ceil(total / queryParams.size)) }} page</span>
        <span class="sp" />
        <span class="fm-tag">显示 {{ tableData.length }} 条</span>
      </div>
      <div class="fm-admin-table__body">
        <el-table v-loading="loading" :data="tableData" stripe>
          <el-table-column prop="name" label="物资名称" min-width="150" />
          <el-table-column prop="quantity" label="库存数量" width="110">
            <template #default="{ row }">
              <span :class="{ 'text-danger': isLowStock(row) }">{{ row.quantity }} {{ row.unit }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="location" label="存放地点" min-width="150" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="resourceStatusMap[row.status]?.type || 'info'" size="small">
                {{ resourceStatusMap[row.status]?.label || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="规格" width="120">
            <template #default="{ row }">{{ row.attributes?.spec || '-' }}</template>
          </el-table-column>
          <el-table-column label="品牌" width="100">
            <template #default="{ row }">{{ row.attributes?.brand || '-' }}</template>
          </el-table-column>
          <el-table-column prop="createdAt" label="创建时间" width="170">
            <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button v-permission="['ADMIN', 'OPERATOR']" link type="primary" @click="handleEdit(row)">编辑</el-button>
              <el-button v-permission="['ADMIN']" link type="danger" @click="handleDelete(row)">删除</el-button>
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

    <ResourceForm v-model:visible="formVisible" :data="currentRow" default-type="MATERIAL" @success="fetchData" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { deleteResource, getResources } from '@/api/resource'
import { formatDate, resourceStatusMap } from '@/utils/format'
import ResourceForm from '../components/ResourceForm.vue'
import type { Resource, ResourceStatus } from '@/types'

const loading = ref(false)
const tableData = ref<Resource[]>([])
const total = ref(0)
const formVisible = ref(false)
const currentRow = ref<Resource | null>(null)

const queryParams = reactive({
  page: 1,
  size: 20,
  keyword: '',
  type: 'MATERIAL' as const,
  status: '' as '' | ResourceStatus,
})

const availableCount = computed(() => tableData.value.filter((resource) => resource.status === 'AVAILABLE').length)
const totalQuantity = computed(() => tableData.value.reduce((sum, resource) => sum + resource.quantity, 0))
const lowStockCount = computed(() => tableData.value.filter(isLowStock).length)

function isLowStock(row: Resource): boolean {
  const alert = row.attributes?.min_stock_alert
  return typeof alert === 'number' && alert > 0 && row.quantity < alert
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getResources(queryParams as any)
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
  queryParams.keyword = ''
  queryParams.status = ''
  handleSearch()
}

function handleAdd() {
  currentRow.value = null
  formVisible.value = true
}

function handleEdit(row: Resource) {
  currentRow.value = { ...row }
  formVisible.value = true
}

async function handleDelete(row: Resource) {
  await ElMessageBox.confirm(`确认删除物资「${row.name}」？`, '提示', { type: 'warning' })
  await deleteResource(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.text-danger {
  color: var(--el-color-danger);
  font-weight: 600;
}
</style>
