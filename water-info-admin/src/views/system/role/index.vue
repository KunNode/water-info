<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>角色 & 权限</h1>
      <span class="sub">// RBAC · permission matrix</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} roles</span>
    </div>

    <div class="fm-grid g-12">
      <div class="fm-card" style="grid-column: span 4">
        <div class="fm-card__head">
          <span class="title">角色概览</span>
          <span class="mono">scope</span>
        </div>
        <div class="fm-card__body role-stack">
          <div v-for="role in tableData" :key="role.id" class="role-chip">
            <span class="mono-cell">{{ role.code }}</span>
            <strong>{{ role.name }}</strong>
          </div>
        </div>
      </div>

      <div class="fm-admin-table" style="grid-column: span 8">
        <div class="fm-admin-table__head">
          <span class="title">角色列表</span>
          <span class="mono">{{ total }} records</span>
      </div>
        <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
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

<style scoped lang="scss">
.role-stack {
  display: grid;
  gap: 10px;
}
.role-chip {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--fm-line);
  border-radius: var(--fm-radius-sm);
  background: var(--fm-bg-2);
}
</style>
