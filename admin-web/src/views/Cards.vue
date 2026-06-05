<template>
  <div>
    <h1 class="page-title">卡牌管理</h1>

    <div class="toolbar">
      <el-input v-model="q" placeholder="搜索 事件/编号" clearable style="width:240px" @keyup.enter="load" />
      <el-select v-model="status" placeholder="状态" clearable style="width:140px" @change="load">
        <el-option label="测试中 (pending)" value="pending" />
        <el-option label="沙盒就绪 (active)" value="active" />
      </el-select>
      <el-select v-model="safetyFilter" placeholder="安全力类型" clearable style="width:150px">
        <el-option v-for="s in SAFETY_TYPES" :key="s" :label="s" :value="s" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
      <el-button type="success" @click="openCreate">新建卡牌</el-button>
      <span style="color:#909399">共 {{ filtered.length }} 张</span>
    </div>

    <el-table :data="filtered" v-loading="loading" border size="small" style="margin-top:4px">
      <el-table-column prop="key" label="编号" width="70" sortable />
      <el-table-column prop="safetyType" label="安全力" width="100">
        <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.safetyType }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="phase" label="阶段" width="90">
        <template #default="{ row }"><el-tag size="small" type="info">{{ row.phase }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="event" label="事件" min-width="280" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="批注" width="64" align="center">
        <template #default="{ row }">
          <el-badge :value="noteCount(row)" :hidden="noteCount(row) === 0" type="warning">
            <span style="color:#909399">📝</span>
          </el-badge>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" @click="openVersions(row)">版本</el-button>
          <el-button size="small" @click="openNotes(row)">批注</el-button>
          <el-button size="small" type="warning" :disabled="row.status !== 'active'" @click="doRelease(row)">发布</el-button>
          <el-popconfirm title="确认删除该卡牌？" @confirm="remove(row)">
            <template #reference><el-button size="small" type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建 / 编辑卡牌 -->
    <el-dialog v-model="dialog" :title="editing ? `编辑卡牌 #${form.key}` : '新建卡牌'" width="760px" top="5vh">
      <el-form :model="form" label-width="80px">
        <div style="display:flex; gap:12px">
          <el-form-item label="安全力" style="flex:1">
            <el-select v-model="form.safetyType" style="width:100%">
              <el-option v-for="s in SAFETY_TYPES" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="阶段" style="flex:1">
            <el-select v-model="form.phase" style="width:100%">
              <el-option v-for="p in PHASES" :key="p" :label="p" :value="p" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态" style="flex:1" v-if="editing">
            <el-select v-model="form.status" style="width:100%">
              <el-option label="测试中 (pending)" value="pending" />
              <el-option label="沙盒就绪 (active)" value="active" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="事件">
          <el-input v-model="form.event" type="textarea" :rows="3" placeholder="描述卡牌情境事件" />
        </el-form-item>

        <el-divider content-position="left">三个选项与五力影响</el-divider>
        <div v-for="opt in OPTION_KEYS" :key="opt" class="opt-block">
          <div class="opt-head">选项 {{ opt }}</div>
          <el-input v-model="form.options[opt].text" placeholder="选项文本" size="small" style="margin-bottom:6px" />
          <el-input v-model="form.options[opt].consequence" type="textarea" :rows="2" placeholder="后果描述" size="small" />
          <div class="attr-row">
            <span v-for="a in ATTRS" :key="a" class="attr-item">
              <label>{{ a }}</label>
              <el-input-number v-model="form.options[opt].attributeEffects[a]" :min="-3" :max="3" size="small" controls-position="right" style="width:96px" />
            </span>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 版本历史 -->
    <el-drawer v-model="verDrawer" :title="`版本历史 · 卡牌 #${current?.key}`" size="520px">
      <div style="margin-bottom:12px">
        <el-button size="small" type="primary" @click="doBranch">从当前沙盒快照新版本</el-button>
      </div>
      <el-timeline v-loading="verLoading">
        <el-timeline-item v-for="v in versions" :key="v.id"
          :timestamp="fmt(v.created_at)" :type="v.is_current ? 'primary' : ''" placement="top">
          <el-card shadow="never" body-style="padding:10px">
            <div style="display:flex; justify-content:space-between; align-items:center">
              <div>
                <strong>{{ v.version_label }}</strong>
                <el-tag size="small" style="margin-left:6px">v{{ v.version }}</el-tag>
                <el-tag size="small" :type="v.branch === 'main' ? 'success' : 'warning'" style="margin-left:4px">{{ v.branch }}</el-tag>
                <el-tag v-if="v.is_current" size="small" type="primary" style="margin-left:4px">当前</el-tag>
              </div>
            </div>
            <div v-if="v.note" style="color:#909399; font-size:12px; margin-top:4px">{{ v.note }}</div>
            <div style="margin-top:8px">
              <el-button size="small" type="primary" plain :disabled="v.is_current" @click="doPromote(v)">推送到沙盒</el-button>
              <el-popconfirm title="删除此版本？" @confirm="doDeleteVersion(v)">
                <template #reference><el-button size="small" type="danger" plain :disabled="v.is_current">删除</el-button></template>
              </el-popconfirm>
            </div>
          </el-card>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-if="!verLoading && versions.length === 0" description="暂无版本" />
    </el-drawer>

    <!-- 批注 -->
    <el-drawer v-model="noteDrawer" :title="`批注 · 卡牌 #${current?.key}`" size="460px">
      <div class="note-add">
        <el-input v-model="newNote" type="textarea" :rows="2" placeholder="写一条待优化建议…" />
        <el-button type="primary" size="small" style="margin-top:6px" :loading="noteSaving" @click="addNote">添加批注</el-button>
      </div>
      <el-divider />
      <div v-for="n in notes" :key="n.id" class="note-item" :class="{ done: n.completed }">
        <el-checkbox :model-value="n.completed" @change="toggleNote(n)" />
        <div style="flex:1">
          <div>{{ n.content }}</div>
          <div style="color:#c0c4cc; font-size:11px">{{ n.author_name || n.author }} · {{ fmt(n.created_at) }}</div>
        </div>
        <el-button link type="danger" size="small" @click="delNote(n)">删除</el-button>
      </div>
      <el-empty v-if="notes.length === 0" description="暂无批注" />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listCards, createCard, updateCard, deleteCard, releaseCard,
  listCardVersions, branchCard, promoteCardVersion, deleteCardVersion,
  listCardNotes, addCardNote, updateCardNote, deleteCardNote
} from '../api/admin'

const SAFETY_TYPES = ['身体安全', '心理安全', '社交安全', '经济安全', '数字权益']
const PHASES = ['启蒙期', '成长期', '青春期']
const ATTRS = ['安全力', '脑波力', '实感力', '创心力', '沟通力']
const OPTION_KEYS = ['A', 'B', 'C']

const cards = ref([])
const loading = ref(false)
const q = ref('')
const status = ref('')
const safetyFilter = ref('')

const filtered = computed(() => {
  let list = cards.value
  if (safetyFilter.value) list = list.filter(c => c.safetyType === safetyFilter.value)
  return list
})

function emptyOptions() {
  const o = {}
  for (const k of OPTION_KEYS) {
    o[k] = { text: '', consequence: '', attributeEffects: Object.fromEntries(ATTRS.map(a => [a, 0])) }
  }
  return o
}

function statusLabel(s) { return { pending: '测试中', active: '沙盒就绪', deleted: '已删除' }[s] || s }
function statusType(s) { return { pending: 'info', active: 'success', deleted: 'danger' }[s] || '' }
function noteCount(row) {
  try { return (JSON.parse(row.notes || '[]')).filter(n => !n.completed).length } catch { return 0 }
}
function fmt(ts) { return ts ? new Date(Number(ts)).toLocaleString('zh-CN', { hour12: false }) : '' }

async function load() {
  loading.value = true
  try {
    const params = {}
    if (status.value) params.status = status.value
    const { data } = await listCards(params)
    let list = data.cards
    if (q.value) {
      const kw = q.value.trim().toLowerCase()
      list = list.filter(c => String(c.key).includes(kw) || (c.event || '').toLowerCase().includes(kw))
    }
    cards.value = list
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '加载失败')
  } finally { loading.value = false }
}

// ===== 新建 / 编辑 =====
const dialog = ref(false)
const editing = ref(false)
const saving = ref(false)
const editId = ref(null)
const form = reactive({ key: '', safetyType: SAFETY_TYPES[0], phase: PHASES[0], event: '', status: 'pending', options: emptyOptions() })

function fillForm(src) {
  form.key = src?.key ?? ''
  form.safetyType = src?.safetyType || SAFETY_TYPES[0]
  form.phase = src?.phase || PHASES[0]
  form.event = src?.event || ''
  form.status = src?.status || 'pending'
  const base = emptyOptions()
  if (src?.options) {
    for (const k of OPTION_KEYS) {
      const so = src.options[k]
      if (so) {
        base[k].text = so.text || ''
        base[k].consequence = so.consequence || ''
        for (const a of ATTRS) base[k].attributeEffects[a] = Number(so.attributeEffects?.[a] || 0)
      }
    }
  }
  form.options = base
}

function openCreate() { editing.value = false; editId.value = null; fillForm(null); dialog.value = true }
function openEdit(row) { editing.value = true; editId.value = row.id; fillForm(row); dialog.value = true }

async function save() {
  if (!form.event.trim()) return ElMessage.warning('请填写事件描述')
  saving.value = true
  try {
    const body = { safetyType: form.safetyType, event: form.event, phase: form.phase, options: form.options }
    if (editing.value) {
      body.status = form.status
      await updateCard(editId.value, body)
    } else {
      await createCard(body)
    }
    ElMessage.success('已保存')
    dialog.value = false
    load()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally { saving.value = false }
}

async function remove(row) {
  try { await deleteCard(row.id); ElMessage.success('已删除'); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
}

async function doRelease(row) {
  try {
    await ElMessageBox.confirm(`将卡牌 #${row.key} 发布到游戏（写入 cards_released）？`, '发布确认', { type: 'warning' })
  } catch { return }
  try { await releaseCard(row.id, {}); ElMessage.success('已发布到游戏') }
  catch (e) { ElMessage.error(e.response?.data?.error || '发布失败') }
}

// ===== 版本 =====
const current = ref(null)
const verDrawer = ref(false)
const verLoading = ref(false)
const versions = ref([])

function openVersions(row) { current.value = row; verDrawer.value = true; loadVersions() }
async function loadVersions() {
  verLoading.value = true
  try { const { data } = await listCardVersions(current.value.id); versions.value = data.versions }
  catch (e) { ElMessage.error(e.response?.data?.error || '加载版本失败') }
  finally { verLoading.value = false }
}
async function doBranch() {
  try {
    const { value } = await ElMessageBox.prompt('版本标签', '快照新版本', { inputValue: `v${new Date().toISOString().slice(0, 10)}-测试版` })
    await branchCard(current.value.id, { version_label: value, branch: 'test' })
    ElMessage.success('已快照'); loadVersions()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.response?.data?.error || '快照失败') }
}
async function doPromote(v) {
  try { await promoteCardVersion(v.id); ElMessage.success('已推送到沙盒'); loadVersions(); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '推送失败') }
}
async function doDeleteVersion(v) {
  try { await deleteCardVersion(current.value.id, v.id); ElMessage.success('已删除'); loadVersions() }
  catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
}

// ===== 批注 =====
const noteDrawer = ref(false)
const notes = ref([])
const newNote = ref('')
const noteSaving = ref(false)

function openNotes(row) { current.value = row; noteDrawer.value = true; loadNotes() }
async function loadNotes() {
  try { const { data } = await listCardNotes(current.value.id); notes.value = data.notes }
  catch (e) { ElMessage.error(e.response?.data?.error || '加载批注失败') }
}
async function addNote() {
  if (!newNote.value.trim()) return
  noteSaving.value = true
  try { await addCardNote(current.value.id, { content: newNote.value.trim() }); newNote.value = ''; loadNotes(); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '添加失败') }
  finally { noteSaving.value = false }
}
async function toggleNote(n) {
  try { await updateCardNote(current.value.id, n.id, { completed: !n.completed }); loadNotes(); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '操作失败') }
}
async function delNote(n) {
  try { await deleteCardNote(current.value.id, n.id); loadNotes(); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
}

onMounted(load)
</script>

<style scoped>
.opt-block { border: 1px solid #ebeef5; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }
.opt-head { font-weight: 600; margin-bottom: 6px; color: #409eff; }
.attr-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }
.attr-item { display: flex; flex-direction: column; align-items: flex-start; }
.attr-item label { font-size: 12px; color: #909399; margin-bottom: 2px; }
.note-item { display: flex; gap: 8px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid #f2f6fc; }
.note-item.done { opacity: 0.5; text-decoration: line-through; }
.note-add { margin-bottom: 4px; }
</style>
