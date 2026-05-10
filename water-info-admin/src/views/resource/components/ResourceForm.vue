<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑资源' : '新增资源'"
    width="600px"
    destroy-on-close
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="资源类型" prop="type">
        <el-select v-model="form.type" placeholder="请选择类型" style="width: 100%" :disabled="isEdit">
          <el-option v-for="(label, key) in resourceTypeMap" :key="key" :label="label" :value="key" />
        </el-select>
      </el-form-item>
      <el-form-item label="资源名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入资源名称" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="数量" prop="quantity">
            <el-input-number v-model="form.quantity" :min="0" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="单位" prop="unit">
            <el-input v-model="form.unit" placeholder="个/人/辆/台" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="存放地点" prop="location">
        <el-input v-model="form.location" placeholder="请输入存放/驻扎地点" />
      </el-form-item>
      <el-form-item v-if="isEdit" label="状态" prop="status">
        <el-select v-model="form.status" placeholder="请选择状态" style="width: 100%">
          <el-option v-for="(item, key) in resourceStatusMap" :key="key" :label="item.label" :value="key" />
        </el-select>
      </el-form-item>

      <template v-if="form.type === 'MATERIAL'">
        <el-divider content-position="left">物资信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="品牌">
              <el-input v-model="materialAttrs.brand" placeholder="品牌" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规格">
              <el-input v-model="materialAttrs.spec" placeholder="规格型号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="有效期">
              <el-date-picker
                v-model="materialAttrs.expiry_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最低库存">
              <el-input-number v-model="materialAttrs.min_stock_alert" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <template v-if="form.type === 'PERSONNEL'">
        <el-divider content-position="left">人员信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="队伍人数">
              <el-input-number v-model="personnelAttrs.team_size" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-input v-model="personnelAttrs.leader" placeholder="负责人姓名" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="联系电话">
          <el-input v-model="personnelAttrs.contact" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="技能标签">
          <el-select
            v-model="personnelAttrs.skills"
            multiple
            filterable
            allow-create
            placeholder="输入技能标签"
            style="width: 100%"
          >
            <el-option label="水上救援" value="水上救援" />
            <el-option label="急救" value="急救" />
            <el-option label="排水作业" value="排水作业" />
            <el-option label="堤防加固" value="堤防加固" />
            <el-option label="通信保障" value="通信保障" />
          </el-select>
        </el-form-item>
      </template>

      <template v-if="form.type === 'VEHICLE'">
        <el-divider content-position="left">车辆信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="车牌号">
              <el-input v-model="vehicleAttrs.plate_number" placeholder="车牌号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="载重/容量">
              <el-input v-model="vehicleAttrs.capacity" placeholder="如：5吨" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="燃料类型">
          <el-select v-model="vehicleAttrs.fuel_type" placeholder="选择燃料类型" style="width: 100%" clearable>
            <el-option label="柴油" value="柴油" />
            <el-option label="汽油" value="汽油" />
            <el-option label="电动" value="电动" />
            <el-option label="混合动力" value="混合动力" />
          </el-select>
        </el-form-item>
      </template>

      <el-form-item label="备注">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="备注说明" />
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
import { createResource, updateResource } from '@/api/resource'
import { resourceStatusMap, resourceTypeMap } from '@/utils/format'
import type { CreateResourceRequest, Resource, ResourceStatus, ResourceType, UpdateResourceRequest } from '@/types'

const props = defineProps<{
  visible: boolean
  data: Resource | null
  defaultType?: ResourceType
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  success: []
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const isEdit = computed(() => !!props.data?.id)

const form = reactive({
  type: '' as '' | ResourceType,
  name: '',
  quantity: 0,
  unit: '',
  location: '',
  status: 'AVAILABLE' as ResourceStatus,
  description: '',
})

const materialAttrs = reactive({
  brand: '',
  spec: '',
  expiry_date: '',
  min_stock_alert: 0,
})

const personnelAttrs = reactive({
  team_size: 1,
  leader: '',
  contact: '',
  skills: [] as string[],
})

const vehicleAttrs = reactive({
  plate_number: '',
  capacity: '',
  fuel_type: '',
})

const rules: FormRules = {
  type: [{ required: true, message: '请选择资源类型', trigger: 'change' }],
  name: [{ required: true, message: '请输入资源名称', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }],
  location: [{ required: true, message: '请输入存放地点', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

function getAttributes(): Record<string, any> {
  if (form.type === 'MATERIAL') return { ...materialAttrs }
  if (form.type === 'PERSONNEL') return { ...personnelAttrs }
  if (form.type === 'VEHICLE') return { ...vehicleAttrs }
  return {}
}

function setAttributes(attrs: Record<string, any>) {
  Object.assign(materialAttrs, {
    brand: attrs.brand || '',
    spec: attrs.spec || '',
    expiry_date: attrs.expiry_date || '',
    min_stock_alert: attrs.min_stock_alert || 0,
  })
  Object.assign(personnelAttrs, {
    team_size: attrs.team_size || 1,
    leader: attrs.leader || '',
    contact: attrs.contact || '',
    skills: attrs.skills || [],
  })
  Object.assign(vehicleAttrs, {
    plate_number: attrs.plate_number || '',
    capacity: attrs.capacity || '',
    fuel_type: attrs.fuel_type || '',
  })
}

function resetForm() {
  Object.assign(form, {
    type: props.defaultType || '',
    name: '',
    quantity: 0,
    unit: '',
    location: '',
    status: 'AVAILABLE',
    description: '',
  })
  setAttributes({})
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    if (props.data) {
      Object.assign(form, {
        type: props.data.type,
        name: props.data.name,
        quantity: props.data.quantity,
        unit: props.data.unit,
        location: props.data.location,
        status: props.data.status,
        description: props.data.description || '',
      })
      setAttributes(props.data.attributes || {})
    } else {
      resetForm()
    }
  },
)

function handleClose() {
  formRef.value?.resetFields()
  emit('update:visible', false)
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || !form.type) return

  submitting.value = true
  try {
    if (isEdit.value) {
      const payload: UpdateResourceRequest = {
        name: form.name,
        quantity: form.quantity,
        unit: form.unit,
        location: form.location,
        status: form.status,
        attributes: getAttributes(),
        description: form.description,
      }
      await updateResource(props.data!.id, payload)
    } else {
      const payload: CreateResourceRequest = {
        type: form.type,
        name: form.name,
        quantity: form.quantity,
        unit: form.unit,
        location: form.location,
        attributes: getAttributes(),
        description: form.description,
      }
      await createResource(payload)
    }
    ElMessage.success(isEdit.value ? '编辑成功' : '新增成功')
    emit('success')
    handleClose()
  } finally {
    submitting.value = false
  }
}
</script>
