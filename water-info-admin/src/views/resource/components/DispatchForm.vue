<template>
  <el-dialog :model-value="visible" title="创建调度单" width="520px" destroy-on-close @close="handleClose">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="选择资源" prop="resourceId">
        <el-select
          v-model="form.resourceId"
          filterable
          remote
          :remote-method="searchResources"
          :loading="searching"
          placeholder="输入资源名称搜索"
          style="width: 100%"
          @change="syncSelectedResource"
        >
          <el-option
            v-for="resource in resourceOptions"
            :key="resource.id"
            :label="`${resource.name} (${resource.quantity} ${resource.unit} · ${resource.location})`"
            :value="resource.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="调度数量" prop="quantity">
        <el-input-number v-model="form.quantity" :min="1" :max="selectedResourceQty" style="width: 100%" />
      </el-form-item>
      <el-form-item label="调出地点" prop="fromLocation">
        <el-input v-model="form.fromLocation" placeholder="调出地点" />
      </el-form-item>
      <el-form-item label="调入地点" prop="toLocation">
        <el-input v-model="form.toLocation" placeholder="调入地点" />
      </el-form-item>
      <el-form-item label="关联预案">
        <el-input v-model="form.planId" placeholder="预案ID（可选）" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注说明" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createDispatch, getAvailableResources } from '@/api/resource'
import type { Resource } from '@/types'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  success: []
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const searching = ref(false)
const resourceOptions = ref<Resource[]>([])

const form = reactive({
  resourceId: '',
  quantity: 1,
  fromLocation: '',
  toLocation: '',
  planId: '',
  notes: '',
})

const selectedResourceQty = computed(() => {
  const resource = resourceOptions.value.find((item) => item.id === form.resourceId)
  return resource?.quantity || 9999
})

const rules: FormRules = {
  resourceId: [{ required: true, message: '请选择资源', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入调度数量', trigger: 'blur' }],
  fromLocation: [{ required: true, message: '请输入调出地点', trigger: 'blur' }],
  toLocation: [{ required: true, message: '请输入调入地点', trigger: 'blur' }],
}

async function searchResources(query: string) {
  searching.value = true
  try {
    const res = await getAvailableResources()
    const normalizedQuery = query.trim().toLowerCase()
    resourceOptions.value = (res.data || []).filter((resource) => {
      if (!normalizedQuery) return true
      return [resource.name, resource.location, resource.type].some((value) =>
        value.toLowerCase().includes(normalizedQuery),
      )
    })
  } finally {
    searching.value = false
  }
}

function syncSelectedResource() {
  const resource = resourceOptions.value.find((item) => item.id === form.resourceId)
  if (resource) {
    form.fromLocation = resource.location
    form.quantity = Math.min(form.quantity, resource.quantity)
  }
}

watch(
  () => props.visible,
  async (visible) => {
    if (!visible) return
    Object.assign(form, { resourceId: '', quantity: 1, fromLocation: '', toLocation: '', planId: '', notes: '' })
    resourceOptions.value = []
    await searchResources('')
  },
)

function handleClose() {
  formRef.value?.resetFields()
  emit('update:visible', false)
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createDispatch({
      resourceId: form.resourceId,
      quantity: form.quantity,
      fromLocation: form.fromLocation,
      toLocation: form.toLocation,
      planId: form.planId || undefined,
      notes: form.notes || undefined,
    })
    ElMessage.success('调度单创建成功')
    emit('success')
    handleClose()
  } finally {
    submitting.value = false
  }
}
</script>
