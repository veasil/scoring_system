<template>
  <div>
    <h1 class="page-title">驾驶舱</h1>
    <el-row :gutter="16" v-loading="loading">
      <el-col :span="6"><stat-card title="用户总数" :value="d.totalUsers" color="#409eff" /></el-col>
      <el-col :span="6"><stat-card title="组织数" :value="d.totalOrgs" color="#67c23a" /></el-col>
      <el-col :span="6"><stat-card title="对局总数" :value="d.totalSessions" color="#e6a23c" /></el-col>
      <el-col :span="6"><stat-card title="近14天新增用户" :value="recentSignups" color="#f56c6c" /></el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card header="角色分布">
          <el-table :data="d.usersByRole" size="small">
            <el-table-column prop="role" label="角色" />
            <el-table-column prop="c" label="数量" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="对局状态分布">
          <el-table :data="d.sessionsByStatus" size="small">
            <el-table-column prop="status" label="状态" />
            <el-table-column prop="c" label="数量" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card header="近 14 天对局趋势" style="margin-top:16px">
      <el-table :data="d.dailySessions" size="small" max-height="260">
        <el-table-column prop="d" label="日期" />
        <el-table-column prop="c" label="对局数" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h } from 'vue'
import { ElMessage } from 'element-plus'
import { getOverview } from '../api/admin'

const loading = ref(false)
const d = reactive({
  totalUsers: 0, totalOrgs: 0, totalSessions: 0,
  usersByRole: [], sessionsByStatus: [], dailySignups: [], dailySessions: []
})
const recentSignups = computed(() => d.dailySignups.reduce((s, x) => s + x.c, 0))

const StatCard = {
  props: ['title', 'value', 'color'],
  render() {
    return h('div', { style: `background:#fff;border-radius:8px;padding:20px;border-left:4px solid ${this.color}` }, [
      h('div', { style: 'color:#909399;font-size:13px' }, this.title),
      h('div', { style: 'font-size:28px;font-weight:700;margin-top:8px' }, String(this.value ?? 0))
    ])
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await getOverview()
    Object.assign(d, data)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '加载失败')
  } finally { loading.value = false }
})
</script>
