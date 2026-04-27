<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>操作日志</h1>
      <span class="sub">// audit · security trail</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} records</span>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="操作类型">
          <el-input v-model="queryParams.action" placeholder="如 CREATE_STATION" clearable />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker v-model="dateRange" type="datetimerange" range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">操作日志</span>
        <span class="mono">immutable trail</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="actorUsername" label="操作人" width="120" />
        <el-table-column prop="action" label="操作类型" width="160" />
        <el-table-column prop="targetType" label="目标类型" width="120" />
        <el-table-column prop="targetId" label="目标ID" width="200" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP地址" width="140" />
        <el-table-column prop="detail" label="详情" min-width="200">
          <template #default="{ row }">
            <span class="detail-text">{{ JSON.stringify(row.detail) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="操作时间" width="170">
          <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="fetchData"
        @current-change="fetchData"
      />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import { getAuditLogs } from '@/api/system'
import { formatDate } from '@/utils/format'
import type { AuditLog } from '@/types'

const loading = ref(false)
const tableData = ref<AuditLog[]>([])
const total = ref(0)
const dateRange = ref<string[]>([])

const queryParams = reactive({ page: 1, size: 20, action: '', start: '', end: '' })

async function fetchData() {
  loading.value = true
  if (dateRange.value?.length === 2) { queryParams.start = dateRange.value[0]; queryParams.end = dateRange.value[1] }
  try {
    const res = await getAuditLogs(queryParams)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

function handleSearch() { queryParams.page = 1; fetchData() }
function handleReset() { queryParams.action = ''; dateRange.value = []; queryParams.start = ''; queryParams.end = ''; handleSearch() }

onMounted(fetchData)
</script>

<style scoped>
.table-title { font-size: 16px; font-weight: 600; }
.detail-text { font-size: 12px; color: #909399; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; max-width: 300px; }
</style>
