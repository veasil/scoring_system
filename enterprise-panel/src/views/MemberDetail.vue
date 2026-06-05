<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" style="margin-bottom:20px">
      <template #content>
        {{ member?.guardian_name || member?.phone || '成员详情' }}
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-bottom:20px">
      <el-col :span="8">
        <el-card shadow="hover"><el-statistic title="总场次" :value="stats.totalGames" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover"><el-statistic title="平均分" :value="stats.avgScore" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="手机号" :value="member?.phone || '-'" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover">
      <template #header>游戏记录</template>
      <el-table :data="stats.sessions" stripe size="small" empty-text="暂无记录">
        <el-table-column label="开始时间" width="180">
          <template #default="{ row }">{{ formatDate(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="结束时间" width="180">
          <template #default="{ row }">{{ formatDate(row.ended_at) }}</template>
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
import { getMemberStats } from '../api/members'
import { formatDate } from '../utils/format'

const route = useRoute()
const loading = ref(false)
const member = ref(null)
const stats = ref({ totalGames: 0, avgScore: 0, sessions: [] })

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await getMemberStats(route.params.id)
    member.value = data.member
    stats.value = data.stats
  } catch { /* empty */ }
  loading.value = false
})
</script>
