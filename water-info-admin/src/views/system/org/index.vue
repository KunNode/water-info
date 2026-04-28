<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>组织机构</h1>
      <span class="sub">// organization · command hierarchy</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} orgs</span>
      <el-button type="primary" :icon="Plus" @click="handleAdd">新增机构</el-button>
    </div>

    <div class="fm-admin-search">
      <el-form inline>
        <el-form-item label="关键词">
          <el-input v-model="keyword" placeholder="名称/编码" clearable @keyup.enter="fetchData" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchData">搜索</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">机构列表</span>
        <span class="mono">{{ total }} records</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="code" label="编码" width="150" />
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="region" label="区域" width="150" />
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
      <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" style="margin-top: 16px; justify-content: flex-end" @current-change="fetchData" />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editRow ? '编辑机构' : '新增机构'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" :disabled="!!editRow" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="区域">
          <el-input v-model="form.region" />
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
import { getOrgs, createOrg, updateOrg, deleteOrg } from '@/api/system'
import { formatDate } from '@/utils/format'
import type { Org } from '@/types'

const loading = ref(false)
const tableData = ref<Org[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const dialogVisible = ref(false)
const editRow = ref<Org | null>(null)
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({ code: '', name: '', region: '' })
const rules: FormRules = {
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getOrgs({ page: page.value, size: 20, keyword: keyword.value })
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

function handleAdd() { editRow.value = null; Object.assign(form, { code: '', name: '', region: '' }); dialogVisible.value = true }
function handleEdit(row: Org) { editRow.value = row; Object.assign(form, { code: row.code, name: row.name, region: row.region }); dialogVisible.value = true }

async function handleDelete(row: Org) {
  await ElMessageBox.confirm(`确认删除「${row.name}」？`, '提示', { type: 'warning' })
  await deleteOrg(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editRow.value) { await updateOrg(editRow.value.id, form) } else { await createOrg(form) }
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
