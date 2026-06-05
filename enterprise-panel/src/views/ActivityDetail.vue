<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" style="margin-bottom:20px">
      <template #content>
        {{ activity?.name || '活动详情' }}
        <el-tag v-if="activity?.activity_code" type="info" style="margin-left:8px">{{ activity.activity_code }}</el-tag>
      </template>
    </el-page-header>

    <el-card shadow="hover">
      <template #header>参与场次</template>
      <el-table :data="sessions" stripe size="small" empty-text="暂无场次">
        <el-table-column prop="table_no" label="桌号" width="80" />
        <el-table-column prop="guardian_name" label="守望师" width="120" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column label="开始时间" width="180">
          <template #default="{ row }">{{ formatDate(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="game_mode" label="模式" width="100" />
        <el-table-column prop="final_score" label="得分" width="80" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getActivitySessions } from '../api/activities'
import { formatDate } from '../utils/format'

const route = useRoute()
const loading = ref(false)
const activity = ref(null)
const sessions = ref([])

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await getActivitySessions(route.params.id)
    activity.value = data.activity
    sessions.value = data.sessions
  } catch { /* empty */ }
  loading.value = false
})
</script>
