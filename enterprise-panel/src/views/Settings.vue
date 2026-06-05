<template>
  <div v-loading="loading">
    <h3 style="margin-bottom:20px">组织设置</h3>
    <el-card shadow="hover" style="max-width:600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="组织名称">{{ org.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="组织简介">{{ org.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="成员上限">{{ org.maxMembers }}</el-descriptions-item>
        <el-descriptions-item label="当前成员">{{ org.currentMembers }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(org.createdAt) }}</el-descriptions-item>
      </el-descriptions>
      <el-alert type="info" :closable="false" style="margin-top:16px">
        如需修改组织名称或成员上限，请联系管理员。
      </el-alert>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getOrgInfo } from '../api/dashboard'
import { formatDate } from '../utils/format'

const loading = ref(false)
const org = ref({})

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await getOrgInfo()
    org.value = data.organization
  } catch { /* empty */ }
  loading.value = false
})
</script>
