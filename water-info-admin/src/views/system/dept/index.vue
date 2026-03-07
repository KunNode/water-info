<template>
  <div class="page-container">
    <div class="search-bar">
      <el-form inline>
        <el-form-item label="组织">
          <el-input v-model="queryParams.orgId" placeholder="组织ID" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchData">搜索</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="table-card">
      <div class="table-header">
        <span class="table-title">部门管理</span>
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增部门</el-button>
      </div>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="name" label="部门名称" min-width="200" />
        <el-table-column prop="orgId" label="所属组织" width="200" show-overflow-tooltip />
        <el-table-column prop="parentId" label="上级部门" width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.parentId || '无' }}</template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="queryParams.page" :page-size="20" :total="total" layout="total, prev, pager, next" style="margin-top: 16px; justify-content: flex-end" @current-change="fetchData" />
    </div>

    <el-dialog v-model="dialogVisible" :title="editRow ? '编辑部门' : '新增部门'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="组织ID" prop="orgId">
          <el-input v-model="form.orgId" />
        </el-form-item>
        <el-form-item label="部门名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="上级部门">
          <el-input v-model="form.parentId" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessageBox, ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import { getDepts, createDept, updateDept, deleteDept } from '@/api/system'
import { formatDate } from '@/utils/format'
import type { Dept } from '@/types'

const loading = ref(false)
const tableData = ref<Dept[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const editRow = ref<Dept | null>(null)
const formRef = ref<FormInstance>()
const submitting = ref(false)

const queryParams = reactive({ page: 1, size: 20, orgId: '' })
const form = reactive({ orgId: '', name: '', parentId: '' })
const rules: FormRules = {
  orgId: [{ required: true, message: '请输入组织ID', trigger: 'blur' }],
  name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getDepts(queryParams)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

function handleAdd() { editRow.value = null; Object.assign(form, { orgId: '', name: '', parentId: '' }); dialogVisible.value = true }
function handleEdit(row: Dept) { editRow.value = row; Object.assign(form, { orgId: row.orgId, name: row.name, parentId: row.parentId || '' }); dialogVisible.value = true }

async function handleDelete(row: Dept) {
  await ElMessageBox.confirm(`确认删除「${row.name}」？`, '提示', { type: 'warning' })
  await deleteDept(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editRow.value) { await updateDept(editRow.value.id, form) } else { await createDept(form) }
    ElMessage.success(editRow.value ? '编辑成功' : '新增成功')
    dialogVisible.value = false
    fetchData()
  } finally { submitting.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.table-title { font-size: 16px; font-weight: 600; }
</style>
