<template>
  <div class="page-container">
    <div class="table-card">
      <div class="table-header">
        <span class="table-title">角色管理</span>
      </div>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="code" label="角色编码" width="150" />
        <el-table-column prop="name" label="角色名称" width="150" />
        <el-table-column prop="description" label="描述" min-width="250" />
        <el-table-column prop="createdAt" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        :page-size="20"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="fetchData"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getRoles } from '@/api/system'
import { formatDate } from '@/utils/format'
import type { Role } from '@/types'

const loading = ref(false)
const tableData = ref<Role[]>([])
const total = ref(0)
const page = ref(1)

async function fetchData() {
  loading.value = true
  try {
    const res = await getRoles({ page: page.value, size: 20 })
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.table-title { font-size: 16px; font-weight: 600; }
</style>
