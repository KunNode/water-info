<template>
  <div class="page-container">
    <div class="search-bar">
      <el-form :model="queryParams" inline>
        <el-form-item label="站点">
          <el-input v-model="queryParams.stationId" placeholder="站点ID" clearable />
        </el-form-item>
        <el-form-item label="指标类型">
          <el-select v-model="queryParams.metricType" placeholder="全部" clearable>
            <el-option label="水位" value="WATER_LEVEL" />
            <el-option label="降雨量" value="RAINFALL" />
            <el-option label="流量" value="FLOW" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.enabled" placeholder="全部" clearable>
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="table-card">
      <div class="table-header">
        <span class="table-title">阈值规则</span>
        <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">新增规则</el-button>
      </div>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="stationName" label="站点" min-width="150" />
        <el-table-column prop="metricType" label="指标" width="90" />
        <el-table-column prop="level" label="告警等级" width="90">
          <template #default="{ row }">
            <el-tag :color="alarmLevelMap[row.level]?.color" effect="dark" size="small" style="border: none; color: #fff">
              {{ alarmLevelMap[row.level]?.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="thresholdValue" label="阈值" width="100" />
        <el-table-column prop="durationMin" label="持续时间(分)" width="120" />
        <el-table-column prop="rateThreshold" label="变化率阈值" width="110" />
        <el-table-column prop="enabled" label="状态" width="90">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="handleToggle(row)" v-permission="['ADMIN', 'OPERATOR']" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
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
    <el-dialog v-model="dialogVisible" :title="editRow ? '编辑规则' : '新增规则'" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="站点ID" prop="stationId">
          <el-input v-model="form.stationId" placeholder="请输入站点ID" />
        </el-form-item>
        <el-form-item label="指标类型" prop="metricType">
          <el-select v-model="form.metricType" style="width: 100%">
            <el-option label="水位" value="WATER_LEVEL" />
            <el-option label="降雨量" value="RAINFALL" />
            <el-option label="流量" value="FLOW" />
          </el-select>
        </el-form-item>
        <el-form-item label="告警等级" prop="level">
          <el-select v-model="form.level" style="width: 100%">
            <el-option v-for="(info, key) in alarmLevelMap" :key="key" :label="info.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值" prop="thresholdValue">
          <el-input-number v-model="form.thresholdValue" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="持续时间(分)">
          <el-input-number v-model="form.durationMin" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="变化率阈值">
          <el-input-number v-model="form.rateThreshold" :precision="2" style="width: 100%" />
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
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getThresholdRules, createThresholdRule, updateThresholdRule, enableThresholdRule, disableThresholdRule, deleteThresholdRule } from '@/api/threshold'
import { alarmLevelMap } from '@/utils/format'
import type { ThresholdRule, AlarmLevel } from '@/types'

const loading = ref(false)
const tableData = ref<ThresholdRule[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const editRow = ref<ThresholdRule | null>(null)
const formRef = ref<FormInstance>()
const submitting = ref(false)

const queryParams = reactive({ page: 1, size: 20, stationId: '', metricType: '', enabled: undefined as boolean | undefined })
const form = reactive({ stationId: '', metricType: '', level: '' as string, thresholdValue: 0, durationMin: 0, rateThreshold: 0 })
const rules: FormRules = {
  stationId: [{ required: true, message: '请输入站点ID', trigger: 'blur' }],
  metricType: [{ required: true, message: '请选择指标类型', trigger: 'change' }],
  level: [{ required: true, message: '请选择告警等级', trigger: 'change' }],
  thresholdValue: [{ required: true, message: '请输入阈值', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getThresholdRules(queryParams)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

function handleSearch() { queryParams.page = 1; fetchData() }
function handleReset() { queryParams.stationId = ''; queryParams.metricType = ''; queryParams.enabled = undefined; handleSearch() }

function handleAdd() { editRow.value = null; Object.assign(form, { stationId: '', metricType: '', level: '', thresholdValue: 0, durationMin: 0, rateThreshold: 0 }); dialogVisible.value = true }
function handleEdit(row: ThresholdRule) { editRow.value = row; Object.assign(form, { stationId: row.stationId, metricType: row.metricType, level: row.level, thresholdValue: row.thresholdValue, durationMin: row.durationMin, rateThreshold: row.rateThreshold }); dialogVisible.value = true }

async function handleToggle(row: ThresholdRule) {
  try {
    if (row.enabled) { await enableThresholdRule(row.id) } else { await disableThresholdRule(row.id) }
    ElMessage.success(row.enabled ? '已启用' : '已禁用')
  } catch { row.enabled = !row.enabled }
}

async function handleDelete(row: ThresholdRule) {
  await ElMessageBox.confirm('确认删除该规则？', '提示', { type: 'warning' })
  await deleteThresholdRule(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editRow.value) { await updateThresholdRule(editRow.value.id, form as any) } else { await createThresholdRule(form as any) }
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
