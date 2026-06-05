<template>
  <div>
    <h1 class="page-title">系统设置</h1>

    <el-tabs v-model="tab">
      <el-tab-pane label="系统配置" name="settings">
        <div class="toolbar">
          <el-button type="primary" @click="loadSettings">刷新</el-button>
          <el-button type="success" @click="openCreate">新增配置项</el-button>
          <span style="color:#909399">敏感项（含 KEY/SECRET）以 AES 加密落库，列表已脱敏显示</span>
        </div>
        <el-table :data="settings" v-loading="loading" border size="small">
          <el-table-column prop="key" label="键" width="240" />
          <el-table-column label="值" min-width="240">
            <template #default="{ row }">
              <span v-if="row.sensitive" style="color:#e6a23c">{{ mask(row.value) }}</span>
              <span v-else>{{ row.value }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="160" />
          <el-table-column label="敏感" width="70" align="center">
            <template #default="{ row }"><el-tag v-if="row.sensitive" size="small" type="warning">敏感</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }"><el-button size="small" @click="openEdit(row)">编辑</el-button></template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="运营账号" name="operators">
        <div class="toolbar">
          <el-button type="primary" @click="loadOperators">刷新</el-button>
          <span style="color:#909399">role = operator 的账号；admin-panel 仅 boss/运营可登录</span>
        </div>
        <el-table :data="operators" border size="small">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="guardian_name" label="姓名" width="140" />
          <el-table-column prop="phone" label="手机号" width="140" />
          <el-table-column prop="username" label="用户名" />
          <el-table-column label="创建时间" min-width="160">
            <template #default="{ row }">{{ fmt(row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="operators.length === 0" description="暂无运营账号（可在用户管理里把角色设为 operator）" />
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialog" :title="creating ? '新增配置项' : `编辑 ${form.key}`" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="键"><el-input v-model="form.key" :disabled="!creating" /></el-form-item>
        <el-form-item label="值"><el-input v-model="form.value" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="form.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, putSetting, listOperators } from '../api/admin'

const tab = ref('settings')
const settings = ref([])
const operators = ref([])
const loading = ref(false)
function fmt(ts) { return ts ? new Date(Number(ts)).toLocaleString('zh-CN', { hour12: false }) : '' }
function mask(v) { if (!v) return '(空)'; const s = String(v); return s.length <= 4 ? '****' : s.slice(0, 2) + '****' + s.slice(-2) }

async function loadSettings() {
  loading.value = true
  try { const { data } = await getSettings(); settings.value = data.settings }
  catch (e) { ElMessage.error(e.response?.data?.error || '加载失败') }
  finally { loading.value = false }
}
async function loadOperators() {
  try { const { data } = await listOperators(); operators.value = data.operators }
  catch (e) { ElMessage.error(e.response?.data?.error || '加载失败') }
}

const dialog = ref(false)
const creating = ref(false)
const saving = ref(false)
const form = reactive({ key: '', value: '', description: '' })

function openCreate() { creating.value = true; Object.assign(form, { key: '', value: '', description: '' }); dialog.value = true }
function openEdit(row) { creating.value = false; Object.assign(form, { key: row.key, value: row.value || '', description: row.description || '' }); dialog.value = true }
async function save() {
  if (!form.key.trim()) return ElMessage.warning('请填写键')
  saving.value = true
  try {
    await putSetting(form.key, form.value, form.description || null)
    ElMessage.success('已保存'); dialog.value = false; loadSettings()
  } catch (e) { ElMessage.error(e.response?.data?.error || '保存失败') }
  finally { saving.value = false }
}

onMounted(() => { loadSettings(); loadOperators() })
</script>
