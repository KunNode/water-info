<template>
  <div class="fm-threshold-page">
    <div class="fm-page-head">
      <h1>阈值规则</h1>
      <span class="sub">// severity rules · {{ total }} 条</span>
      <span class="sp" />
      <router-link to="/warning/alarm" class="fm-btn fm-btn--ghost">
        <el-icon><Bell /></el-icon>
        <span>返回告警</span>
      </router-link>
      <el-button
        v-permission="['ADMIN', 'OPERATOR']"
        type="primary"
        :icon="Plus"
        @click="handleAdd"
      >新增规则</el-button>
    </div>

    <div class="fm-card fm-threshold-page__search">
      <el-form :model="queryParams" inline>
        <el-form-item label="站点">
          <el-input v-model="queryParams.stationId" placeholder="站点 ID" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="指标类型">
          <el-select v-model="queryParams.metricType" placeholder="全部" clearable style="width: 140px">
            <el-option label="水位" value="WATER_LEVEL" />
            <el-option label="降雨量" value="RAINFALL" />
            <el-option label="流量" value="FLOW" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.enabled" placeholder="全部" clearable style="width: 120px">
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

    <div class="fm-card fm-threshold-page__table">
      <div class="fm-card__head">
        <span class="title">规则列表</span>
        <span class="mono">{{ enabledCount }} / {{ total }} 启用中</span>
      </div>

      <el-table v-loading="loading" :data="tableData" stripe class="fm-threshold-table">
        <el-table-column prop="stationName" label="站点" min-width="150" />
        <el-table-column prop="metricType" label="指标" width="110">
          <template #default="{ row }">
            <span class="fm-tag">{{ metricTypeMap[row.metricType] || row.metricType }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="告警等级" width="110">
          <template #default="{ row }">
            <span class="fm-tag" :class="levelTagKind(row.level)">
              <span class="fm-dot" :class="levelDotKind(row.level)" />
              {{ alarmLevelMap[row.level]?.label }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="thresholdValue" label="阈值" width="110">
          <template #default="{ row }">
            <span class="mono-cell">{{ row.thresholdValue }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="durationMin" label="持续 (min)" width="112">
          <template #default="{ row }">
            <span class="mono-cell">{{ row.durationMin ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="rateThreshold" label="变化率" width="110">
          <template #default="{ row }">
            <span class="mono-cell">{{ row.rateThreshold ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="96">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              v-permission="['ADMIN', 'OPERATOR']"
              @change="handleToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="['ADMIN', 'OPERATOR']" link type="primary" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button v-permission="['ADMIN']" link type="danger" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="fm-threshold-page__foot">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editRow ? '编辑规则' : '新增规则'"
      width="520px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="站点 ID" prop="stationId">
          <el-input v-model="form.stationId" placeholder="请输入站点 ID" />
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
            <el-option
              v-for="(info, key) in alarmLevelMap"
              :key="key"
              :label="info.label"
              :value="key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值" prop="thresholdValue">
          <el-input-number v-model="form.thresholdValue" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="持续时间 (min)">
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
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessageBox, ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Search, Refresh, Plus, Bell } from '@element-plus/icons-vue'
import {
  getThresholdRules,
  createThresholdRule,
  updateThresholdRule,
  enableThresholdRule,
  disableThresholdRule,
  deleteThresholdRule,
} from '@/api/threshold'
import { alarmLevelMap, metricTypeMap } from '@/utils/format'
import type { ThresholdRule } from '@/types'

const loading = ref(false)
const tableData = ref<ThresholdRule[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const editRow = ref<ThresholdRule | null>(null)
const formRef = ref<FormInstance>()
const submitting = ref(false)

const queryParams = reactive({
  page: 1,
  size: 20,
  stationId: '',
  metricType: '',
  enabled: undefined as boolean | undefined,
})

const form = reactive({
  stationId: '',
  metricType: '',
  level: '' as string,
  thresholdValue: 0,
  durationMin: 0,
  rateThreshold: 0,
})

const rules: FormRules = {
  stationId: [{ required: true, message: '请输入站点 ID', trigger: 'blur' }],
  metricType: [{ required: true, message: '请选择指标类型', trigger: 'change' }],
  level: [{ required: true, message: '请选择告警等级', trigger: 'change' }],
  thresholdValue: [{ required: true, message: '请输入阈值', trigger: 'blur' }],
}

const enabledCount = computed(() => tableData.value.filter((r) => r.enabled).length)

async function fetchData() {
  loading.value = true
  try {
    const res = await getThresholdRules(queryParams)
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
  queryParams.stationId = ''
  queryParams.metricType = ''
  queryParams.enabled = undefined
  handleSearch()
}

function handleAdd() {
  editRow.value = null
  Object.assign(form, {
    stationId: '',
    metricType: '',
    level: '',
    thresholdValue: 0,
    durationMin: 0,
    rateThreshold: 0,
  })
  dialogVisible.value = true
}

function handleEdit(row: ThresholdRule) {
  editRow.value = row
  Object.assign(form, {
    stationId: row.stationId,
    metricType: row.metricType,
    level: row.level,
    thresholdValue: row.thresholdValue,
    durationMin: row.durationMin,
    rateThreshold: row.rateThreshold,
  })
  dialogVisible.value = true
}

async function handleToggle(row: ThresholdRule) {
  try {
    if (row.enabled) {
      await enableThresholdRule(row.id)
    } else {
      await disableThresholdRule(row.id)
    }
    ElMessage.success(row.enabled ? '已启用' : '已禁用')
  } catch {
    row.enabled = !row.enabled
  }
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
    if (editRow.value) {
      await updateThresholdRule(editRow.value.id, form as any)
    } else {
      await createThresholdRule(form as any)
    }
    ElMessage.success(editRow.value ? '编辑成功' : '新增成功')
    dialogVisible.value = false
    fetchData()
  } finally {
    submitting.value = false
  }
}

function levelTagKind(level: string): string {
  if (level === 'CRITICAL') return 'fm-tag--danger'
  if (level === 'HIGH') return 'fm-tag--warn'
  if (level === 'MEDIUM') return 'fm-tag--info'
  return ''
}
function levelDotKind(level: string): string {
  if (level === 'CRITICAL' || level === 'HIGH') return 'danger'
  if (level === 'MEDIUM') return 'warn'
  return 'off'
}

onMounted(fetchData)
</script>

<style scoped lang="scss">
.fm-threshold-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fm-threshold-page__search {
  padding: 16px 18px;

  :deep(.el-form) { margin: 0; }
  :deep(.el-form-item) {
    margin-bottom: 0;
    margin-right: 16px;
  }
}

.fm-threshold-page__foot {
  padding: 14px 16px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--fm-line);
}

.mono-cell {
  font-family: var(--fm-font-mono);
  font-size: 11.5px;
  color: var(--fm-fg-soft);
  letter-spacing: 0.04em;
}

.fm-threshold-table :deep(.el-table) {
  border: none;
}
.fm-threshold-table :deep(.el-table__inner-wrapper::before) {
  background-color: var(--fm-line);
}
</style>
