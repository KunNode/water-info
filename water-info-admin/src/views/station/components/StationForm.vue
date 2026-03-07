<template>
  <el-dialog :model-value="visible" :title="isEdit ? '编辑站点' : '新增站点'" width="580px" @close="handleClose" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="站点编码" prop="code">
        <el-input v-model="form.code" placeholder="请输入站点编码" :disabled="isEdit" />
      </el-form-item>
      <el-form-item label="站点名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入站点名称" />
      </el-form-item>
      <el-form-item label="站点类型" prop="type">
        <el-select v-model="form.type" placeholder="请选择类型" style="width: 100%">
          <el-option v-for="(label, key) in stationTypeMap" :key="key" :label="label" :value="key" />
        </el-select>
      </el-form-item>
      <el-form-item label="流域">
        <el-input v-model="form.riverBasin" placeholder="请输入流域" />
      </el-form-item>
      <el-form-item label="行政区划">
        <el-input v-model="form.adminRegion" placeholder="请输入行政区划" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="纬度">
            <el-input-number v-model="form.lat" :precision="6" :step="0.01" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="经度">
            <el-input-number v-model="form.lon" :precision="6" :step="0.01" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="高程">
        <el-input-number v-model="form.elevation" :precision="2" :step="0.1" style="width: 100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createStation, updateStation } from '@/api/station'
import { stationTypeMap } from '@/utils/format'
import type { Station, StationType } from '@/types'

const props = defineProps<{
  visible: boolean
  data: Station | null
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  success: []
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const isEdit = computed(() => !!props.data?.id)

const form = reactive({
  code: '',
  name: '',
  type: '' as '' | StationType,
  riverBasin: '',
  adminRegion: '',
  lat: undefined as number | undefined,
  lon: undefined as number | undefined,
  elevation: undefined as number | undefined,
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入站点编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入站点名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择站点类型', trigger: 'change' }],
}

watch(
  () => props.visible,
  (val) => {
    if (val && props.data) {
      Object.assign(form, {
        code: props.data.code,
        name: props.data.name,
        type: props.data.type,
        riverBasin: props.data.riverBasin,
        adminRegion: props.data.adminRegion,
        lat: props.data.lat,
        lon: props.data.lon,
        elevation: props.data.elevation,
      })
    } else if (val) {
      Object.assign(form, { code: '', name: '', type: '', riverBasin: '', adminRegion: '', lat: undefined, lon: undefined, elevation: undefined })
    }
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
    if (isEdit.value) {
      await updateStation(props.data!.id, form as any)
    } else {
      await createStation(form as any)
    }
    ElMessage.success(isEdit.value ? '编辑成功' : '新增成功')
    emit('success')
    handleClose()
  } finally {
    submitting.value = false
  }
}
</script>
