<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>传感器管理</h1>
      <span class="sub">// device fleet · telemetry edge</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--ok">{{ onlineCount }} online</span>
      <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">
        新增传感器
      </el-button>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">DEVICES</div>
        <div class="value">{{ total }}</div>
        <div class="hint">设备总数</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">ONLINE</div>
        <div class="value">{{ onlineCount }}</div>
        <div class="hint">当前在线</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">OFFLINE</div>
        <div class="value">{{ offlineCount }}</div>
        <div class="hint">需要巡检</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">METRICS</div>
        <div class="value">{{ metricCount }}</div>
        <div class="hint">采集指标类型</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="所属站点">
          <el-input v-model="queryParams.stationId" placeholder="站点ID" clearable />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="queryParams.type" placeholder="全部" clearable>
            <el-option label="水位" value="WATER_LEVEL" />
            <el-option label="降雨量" value="RAINFALL" />
            <el-option label="流量" value="FLOW" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option label="在线" value="ONLINE" />
            <el-option label="离线" value="OFFLINE" />
            <el-option label="维护" value="MAINTENANCE" />
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
        <span class="title">传感器列表</span>
        <span class="mono">{{ total }} records</span>
        <span class="sp" />
        <span class="fm-tag">显示 {{ tableData.length }} 条</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="stationName" label="所属站点" min-width="150" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="samplingIntervalSec" label="采样间隔(秒)" width="120" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ONLINE' ? 'success' : row.status === 'MAINTENANCE' ? 'warning' : 'danger'" size="small">
              {{ row.status === 'ONLINE' ? '在线' : row.status === 'MAINTENANCE' ? '维护' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastSeenAt" label="最后心跳" width="170">
          <template #default="{ row }">{{ formatDate(row.lastSeenAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
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

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editRow ? '编辑传感器' : '新增传感器'" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="所属站点" prop="stationId">
          <el-input v-model="form.stationId" placeholder="站点ID" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="form.type" placeholder="请选择" style="width: 100%">
            <el-option label="水位" value="WATER_LEVEL" />
            <el-option label="降雨量" value="RAINFALL" />
            <el-option label="流量" value="FLOW" />
          </el-select>
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" placeholder="如 m, mm, m³/s" />
        </el-form-item>
        <el-form-item label="采样间隔(秒)">
          <el-input-number v-model="form.samplingIntervalSec" :min="1" style="width: 100%" />
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
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessageBox, ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getSensors, createSensor, updateSensor, deleteSensor } from '@/api/sensor'
import { formatDate } from '@/utils/format'
import type { Sensor, SensorStatus } from '@/types'

const loading = ref(false)
const tableData = ref<Sensor[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const editRow = ref<Sensor | null>(null)
const formRef = ref<FormInstance>()
const submitting = ref(false)

const queryParams = reactive({ page: 1, size: 20, stationId: '', type: '' as string, status: '' as '' | SensorStatus })
const form = reactive({ stationId: '', type: '', unit: '', samplingIntervalSec: 60 })
const rules: FormRules = {
  stationId: [{ required: true, message: '请输入站点ID', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

const onlineCount = computed(() => tableData.value.filter((item) => item.status === 'ONLINE').length)
const offlineCount = computed(() => tableData.value.filter((item) => item.status === 'OFFLINE').length)
const metricCount = computed(() => new Set(tableData.value.map((item) => item.type).filter(Boolean)).size)

async function fetchData() {
  loading.value = true
  try {
    const res = await getSensors(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() { queryParams.page = 1; fetchData() }
function handleReset() { queryParams.stationId = ''; queryParams.type = ''; queryParams.status = ''; handleSearch() }

function handleAdd() { editRow.value = null; Object.assign(form, { stationId: '', type: '', unit: '', samplingIntervalSec: 60 }); dialogVisible.value = true }
function handleEdit(row: Sensor) { editRow.value = row; Object.assign(form, { stationId: row.stationId, type: row.type, unit: row.unit, samplingIntervalSec: row.samplingIntervalSec }); dialogVisible.value = true }

async function handleDelete(row: Sensor) {
  await ElMessageBox.confirm('确认删除该传感器？', '提示', { type: 'warning' })
  await deleteSensor(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editRow.value) { await updateSensor(editRow.value.id, form) }
    else { await createSensor(form) }
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
