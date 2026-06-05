<template>
  <el-dialog v-model="visible" :title="title" width="420px">
    <el-radio-group v-model="mode" style="margin-bottom:14px">
      <el-radio-button value="date">指定到期日</el-radio-button>
      <el-radio-button value="permanent">永久会员</el-radio-button>
      <el-radio-button value="none">未开通</el-radio-button>
    </el-radio-group>

    <div v-if="mode === 'date'">
      <el-date-picker v-model="pickedDay" type="date" value-format="x"
        placeholder="选择到期日" style="width:100%" :disabled-date="isPast" />
      <p class="hint">到期时间为所选日期当天 23:59:59，到期后该账号将无法登录。</p>
    </div>
    <p v-else-if="mode === 'permanent'" class="hint">设为永久会员，永不过期。</p>
    <p v-else class="hint">清空有效期 = 未开通会员，该账号将立即无法登录。</p>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="confirm">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { PERMANENT_UNTIL, endOfDay } from '../utils/membership'

const visible = defineModel('visible', { default: false })
const props = defineProps({
  title: { type: String, default: '设置会员有效期' },
  current: { type: [Number, String, null], default: null },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['save'])

const mode = ref('date')
const pickedDay = ref(null)

// 每次打开按 current 初始化 mode/日期
watch(visible, (open) => {
  if (!open) return
  const v = props.current == null ? null : Number(props.current)
  if (v == null) { mode.value = 'none'; pickedDay.value = null }
  else if (v >= PERMANENT_UNTIL) { mode.value = 'permanent'; pickedDay.value = null }
  else { mode.value = 'date'; pickedDay.value = v }
})

function isPast(date) {
  return date.getTime() < Date.now() - 86400000
}

function confirm() {
  let validUntil
  if (mode.value === 'permanent') validUntil = PERMANENT_UNTIL
  else if (mode.value === 'none') validUntil = null
  else {
    if (!pickedDay.value) return ElMessage.warning('请选择到期日')
    validUntil = endOfDay(pickedDay.value)
  }
  emit('save', validUntil)
}
</script>

<style scoped>
.hint { color: #909399; font-size: 12px; margin-top: 8px; }
</style>
