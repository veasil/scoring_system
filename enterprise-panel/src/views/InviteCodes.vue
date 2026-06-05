<template>
  <div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
      <h3>邀请码管理</h3>
      <el-button type="primary" :icon="Plus" @click="showCreate = true">生成邀请码</el-button>
    </div>

    <el-card shadow="hover">
      <el-table :data="codes" v-loading="loading" stripe>
        <el-table-column prop="code" label="邀请码" width="140">
          <template #default="{ row }">
            <el-tag effect="plain" style="font-family:monospace; letter-spacing:1px">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="Date.now() > row.expires_at" type="info">已过期</el-tag>
            <el-tag v-else-if="row.used_count >= row.max_uses" type="warning">已用完</el-tag>
            <el-tag v-else type="success">可用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="使用情况" width="100">
          <template #default="{ row }">{{ row.used_count }} / {{ row.max_uses }}</template>
        </el-table-column>
        <el-table-column label="过期时间" width="180">
          <template #default="{ row }">{{ formatDate(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreate" title="生成邀请码" width="400px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="可用次数">
          <el-input-number v-model="form.maxUses" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="有效天数">
          <el-input-number v-model="form.expiresInDays" :min="1" :max="30" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getInviteCodes, createInviteCode } from '../api/invite-codes'
import { formatDate } from '../utils/format'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const codes = ref([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const form = reactive({ maxUses: 1, expiresInDays: 3 })

async function loadData() {
  loading.value = true
  try {
    const { data } = await getInviteCodes()
    codes.value = data.codes
  } catch { /* empty */ }
  loading.value = false
}

async function handleCreate() {
  creating.value = true
  try {
    const { data } = await createInviteCode(form)
    ElMessage.success(`邀请码已生成：${data.code}`)
    showCreate.value = false
    await loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '生成失败')
  }
  creating.value = false
}

onMounted(loadData)
</script>
