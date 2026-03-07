<template>
  <div class="page-container">
    <!-- Search bar -->
    <div class="search-bar">
      <el-form :model="queryParams" inline>
        <el-form-item label="关键词">
          <el-input v-model="queryParams.keyword" placeholder="站点名称/编码" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="站点类型">
          <el-select v-model="queryParams.type" placeholder="全部" clearable>
            <el-option v-for="(label, key) in stationTypeMap" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option label="正常" value="ACTIVE" />
            <el-option label="停用" value="INACTIVE" />
            <el-option label="维护" value="MAINTENANCE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- Table -->
    <div class="table-card">
      <div class="table-header">
        <span class="table-title">站点列表</span>
        <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">新增站点</el-button>
      </div>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="code" label="站点编码" width="130" />
        <el-table-column prop="name" label="站点名称" min-width="150" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ stationTypeMap[row.type] || row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="riverBasin" label="流域" width="120" />
        <el-table-column prop="adminRegion" label="行政区划" width="120" />
        <el-table-column prop="lat" label="纬度" width="100">
          <template #default="{ row }">{{ formatNumber(row.lat, 4) }}</template>
        </el-table-column>
        <el-table-column prop="lon" label="经度" width="100">
          <template #default="{ row }">{{ formatNumber(row.lon, 4) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'MAINTENANCE' ? 'warning' : 'info'" size="small">
              {{ row.status === 'ACTIVE' ? '正常' : row.status === 'MAINTENANCE' ? '维护' : '停用' }}
            </el-tag>
          </template>
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

    <!-- Form dialog -->
    <StationForm
      v-model:visible="formVisible"
      :data="currentRow"
      @success="fetchData"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getStations, deleteStation } from '@/api/station'
import { formatDate, formatNumber, stationTypeMap } from '@/utils/format'
import StationForm from './components/StationForm.vue'
import type { Station, StationType, StationStatus } from '@/types'

const loading = ref(false)
const tableData = ref<Station[]>([])
const total = ref(0)
const formVisible = ref(false)
const currentRow = ref<Station | null>(null)

const queryParams = reactive({
  page: 1,
  size: 20,
  keyword: '',
  type: '' as '' | StationType,
  status: '' as '' | StationStatus,
})

async function fetchData() {
  loading.value = true
  try {
    const res = await getStations(queryParams as any)
    // Backend returns { records, total, page, size, pages } structure
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
  queryParams.type = ''
  queryParams.status = ''
  handleSearch()
}

function handleAdd() {
  currentRow.value = null
  formVisible.value = true
}

function handleEdit(row: Station) {
  currentRow.value = { ...row }
  formVisible.value = true
}

async function handleDelete(row: Station) {
  await ElMessageBox.confirm(`确认删除站点「${row.name}」？`, '提示', { type: 'warning' })
  await deleteStation(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.table-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
