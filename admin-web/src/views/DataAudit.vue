<template>
  <div>
    <h1 class="page-title">数据审计</h1>

    <div class="toolbar">
      <el-radio-group v-model="status" @change="load">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button v-for="c in counts" :key="c.status" :label="c.status">{{ c.status }} ({{ c.c }})</el-radio-button>
      </el-radio-group>
      <el-button size="small" @click="load">刷新</el-button>
    </div>

    <el-table :data="sessions" v-loading="loading" border size="small">
      <el-table-column prop="id" label="场次" width="70" />
      <el-table-column prop="guardian_name" label="守望师" width="110" />
      <el-table-column prop="phone" label="手机号" width="120" />
      <el-table-column prop="game_mode" label="模式" width="90" />
      <el-table-column prop="card_count" label="选牌数" width="80" align="center" />
      <el-table-column prop="final_score" label="得分" width="70" />
      <el-table-column label="开始时间" min-width="160">
        <template #default="{ row }">{{ fmt(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }"><el-tag size="small" :type="tagType(row.status)">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="setStatus(row, 'normal')">标正常</el-button>
          <el-button size="small" type="warning" @click="setStatus(row, 'trash')">移入回收</el-button>
          <el-popconfirm title="彻底删除该场次（含事件）？" @confirm="remove(row)">
            <template #reference><el-button size="small" type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { auditSessions, setSessionStatus, deleteSession } from '../api/admin'

const status = ref('')
const counts = ref([])
const sessions = ref([])
const loading = ref(false)
function fmt(ts) { return ts ? new Date(Number(ts)).toLocaleString('zh-CN', { hour12: false }) : '' }
function tagType(s) { return { active: 'success', auto_finished: 'info', trash: 'danger', normal: '' }[s] || '' }

async function load() {
  loading.value = true
  try {
    const { data } = await auditSessions(status.value || undefined)
    counts.value = data.counts
    sessions.value = data.sessions
  } catch (e) { ElMessage.error(e.response?.data?.error || '加载失败') }
  finally { loading.value = false }
}

async function setStatus(row, s) {
  try { await setSessionStatus(row.id, s); ElMessage.success('已更新'); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '更新失败') }
}
async function remove(row) {
  try { await deleteSession(row.id); ElMessage.success('已删除'); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
}

onMounted(load)
</script>
