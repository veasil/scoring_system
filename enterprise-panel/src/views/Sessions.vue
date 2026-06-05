<template>
  <div>
    <h3 style="margin-bottom:16px">游戏场次</h3>

    <el-card shadow="hover">
      <div style="display:flex; gap:12px; margin-bottom:16px">
        <el-select v-model="filter.memberId" placeholder="按成员筛选" clearable style="width:200px" @change="loadData">
          <el-option v-for="m in memberOptions" :key="m.id" :label="m.guardian_name || m.phone" :value="m.id" />
        </el-select>
      </div>
      <el-table :data="sessions" v-loading="loading" stripe>
        <el-table-column prop="guardian_name" label="守望师" width="120" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column label="开始时间" width="180">
          <template #default="{ row }">{{ formatDate(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="game_mode" label="模式" width="100" />
        <el-table-column prop="final_score" label="得分" width="80" />
      </el-table>
      <el-pagination
        v-if="total > pageSize"
        style="margin-top:16px; justify-content:center"
        layout="prev, pager, next"
        :total="total"
        :page-size="pageSize"
        v-model:current-page="currentPage"
        @current-change="loadData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getSessions } from '../api/sessions'
import { getMembers } from '../api/members'
import { formatDate } from '../utils/format'

const sessions = ref([])
const memberOptions = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filter = reactive({ memberId: null })

async function loadData() {
  loading.value = true
  try {
    const { data } = await getSessions({ page: currentPage.value, limit: pageSize, memberId: filter.memberId || undefined })
    sessions.value = data.sessions
    total.value = data.total
  } catch { /* empty */ }
  loading.value = false
}

onMounted(async () => {
  try {
    const { data } = await getMembers()
    memberOptions.value = data.members
  } catch { /* empty */ }
  await loadData()
})
</script>
