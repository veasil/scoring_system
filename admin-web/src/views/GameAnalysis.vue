<template>
  <div>
    <h1 class="page-title">游戏分析</h1>

    <el-row :gutter="16" v-loading="loading">
      <el-col :span="6"><stat title="对局场次" :value="sessions.length" color="#409eff" /></el-col>
      <el-col :span="6"><stat title="选牌总数" :value="totalChoices" color="#67c23a" /></el-col>
      <el-col :span="6"><stat title="失败选择" :value="failCount" color="#f56c6c" /></el-col>
      <el-col :span="6"><stat title="涉及卡牌" :value="cardStat.length" color="#e6a23c" /></el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12"><el-card header="选项分布 (A/B/C)"><div ref="choiceChart" style="height:280px"></div></el-card></el-col>
      <el-col :span="12"><el-card header="阶段分布"><div ref="phaseChart" style="height:280px"></div></el-card></el-col>
    </el-row>

    <el-card header="每张卡牌被选次数" style="margin-top:16px">
      <el-table :data="cardStat" size="small" max-height="320" border>
        <el-table-column prop="cardId" label="卡牌ID" width="90" sortable />
        <el-table-column prop="total" label="被选次数" width="100" sortable />
        <el-table-column prop="A" label="选A" width="70" />
        <el-table-column prop="B" label="选B" width="70" />
        <el-table-column prop="C" label="选C" width="70" />
        <el-table-column prop="fail" label="失败次数" width="90" />
      </el-table>
    </el-card>

    <el-card header="场次列表" style="margin-top:16px">
      <el-table :data="sessions" size="small" max-height="360" border>
        <el-table-column prop="id" label="场次" width="70" />
        <el-table-column prop="guardian_name" label="守望师" width="110" />
        <el-table-column prop="phone" label="手机号" width="120" />
        <el-table-column prop="game_mode" label="模式" width="90" />
        <el-table-column prop="card_count" label="选牌数" width="80" />
        <el-table-column prop="final_score" label="得分" width="70" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }"><el-button size="small" @click="openEvents(row)">明细</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="evDrawer" :title="`场次 #${current?.id} 事件明细`" size="640px">
      <el-timeline>
        <el-timeline-item v-for="(e, i) in events" :key="i" :timestamp="fmt(e.ts)" placement="top">
          <el-tag size="small" style="margin-right:6px">{{ e.type }}</el-tag>
          <span style="font-size:13px">{{ summarize(e) }}</span>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-if="events.length === 0" description="无事件" />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, h } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { statsSessions, statsCards, sessionEvents } from '../api/admin'

const loading = ref(false)
const sessions = ref([])
const totalChoices = ref(0)
const choices = ref([])   // 解析后的 card_choice payload 列表
const choiceChart = ref(null)
const phaseChart = ref(null)

const stat = {
  props: ['title', 'value', 'color'],
  render() {
    return h('div', { style: `background:#fff;border-radius:8px;padding:18px;border-left:4px solid ${this.color}` }, [
      h('div', { style: 'color:#909399;font-size:13px' }, this.title),
      h('div', { style: 'font-size:26px;font-weight:700;margin-top:6px' }, String(this.value ?? 0))
    ])
  }
}

const failCount = computed(() => choices.value.filter(c => c.wasFailure).length)
const cardStat = computed(() => {
  const m = new Map()
  for (const c of choices.value) {
    const id = c.cardId ?? '?'
    if (!m.has(id)) m.set(id, { cardId: id, total: 0, A: 0, B: 0, C: 0, fail: 0 })
    const r = m.get(id); r.total++; if (r[c.choice] !== undefined) r[c.choice]++; if (c.wasFailure) r.fail++
  }
  return [...m.values()].sort((a, b) => b.total - a.total)
})

function fmt(ts) { return ts ? new Date(Number(ts)).toLocaleString('zh-CN', { hour12: false }) : '' }

async function load() {
  loading.value = true
  try {
    const [s, c] = await Promise.all([statsSessions(), statsCards()])
    sessions.value = s.data.sessions
    totalChoices.value = c.data.totalChoices
    choices.value = (c.data.events || []).map(e => { try { return JSON.parse(e.payload) } catch { return {} } })
    await nextTick(); renderCharts()
  } catch (e) { ElMessage.error(e.response?.data?.error || '加载失败') }
  finally { loading.value = false }
}

function renderCharts() {
  const byChoice = { A: 0, B: 0, C: 0 }
  const byPhase = {}
  for (const c of choices.value) {
    if (byChoice[c.choice] !== undefined) byChoice[c.choice]++
    const p = c.phase || '未知'; byPhase[p] = (byPhase[p] || 0) + 1
  }
  if (choiceChart.value) {
    echarts.init(choiceChart.value).setOption({
      tooltip: {}, xAxis: { type: 'category', data: ['A', 'B', 'C'] }, yAxis: { type: 'value' },
      series: [{ type: 'bar', data: [byChoice.A, byChoice.B, byChoice.C], itemStyle: { color: '#409eff' }, barWidth: '50%' }]
    })
  }
  if (phaseChart.value) {
    echarts.init(phaseChart.value).setOption({
      tooltip: { trigger: 'item' }, legend: { bottom: 0 },
      series: [{ type: 'pie', radius: ['40%', '65%'], data: Object.entries(byPhase).map(([name, value]) => ({ name, value })) }]
    })
  }
}

const evDrawer = ref(false)
const current = ref(null)
const events = ref([])
async function openEvents(row) {
  current.value = row; evDrawer.value = true; events.value = []
  try { const { data } = await sessionEvents(row.id); events.value = data.events }
  catch (e) { ElMessage.error(e.response?.data?.error || '加载明细失败') }
}
function summarize(e) {
  try {
    const p = JSON.parse(e.payload)
    if (e.type === 'card_choice') return `卡#${p.cardId} 选${p.choice}${p.wasFailure ? ' (失败)' : ''}`
    if (e.type === 'skill_use') return `技能 ${p.skill || ''}`
    return e.payload?.slice(0, 60) || ''
  } catch { return '' }
}

onMounted(load)
</script>
