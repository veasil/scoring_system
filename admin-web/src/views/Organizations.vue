<template>
  <div>
    <h1 class="page-title">组织管理</h1>
    <div class="toolbar">
      <el-button type="primary" @click="load">刷新</el-button>
      <el-button type="success" @click="openCreate">新建组织</el-button>
      <span style="color:#909399">共 {{ orgs.length }} 个组织</span>
    </div>

    <el-table :data="orgs" v-loading="loading" border size="small">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="组织名称" min-width="150" />
      <el-table-column prop="owner_name" label="管理员" width="110" />
      <el-table-column prop="owner_phone" label="管理员手机" width="130" />
      <el-table-column label="成员" width="100" align="center">
        <template #default="{ row }">{{ row.current_members }} / {{ row.max_members }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'active' ? 'success' : 'danger'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="会员有效期" width="140">
        <template #default="{ row }">
          <el-tag size="small" :type="membershipTag(row.valid_until).type">{{ membershipTag(row.valid_until).text }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="340" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openMembers(row)">成员</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="warning" @click="openValidity(row)">续期</el-button>
          <el-popconfirm title="停用该组织？" @confirm="suspend(row)">
            <template #reference><el-button size="small" type="danger" :disabled="row.status !== 'active'">停用</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建 / 编辑 -->
    <el-dialog v-model="dialog" :title="editing ? '编辑组织' : '新建组织'" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="组织名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="最大成员数"><el-input-number v-model="form.maxMembers" :min="1" :max="9999" /></el-form-item>
        <template v-if="!editing">
          <el-form-item label="初始有效期">
            <el-radio-group v-model="form.validMode">
              <el-radio-button value="permanent">永久</el-radio-button>
              <el-radio-button value="date">指定</el-radio-button>
              <el-radio-button value="none">未开通</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="form.validMode === 'date'" label="到期日">
            <el-date-picker v-model="form.validDay" type="date" value-format="x" placeholder="选择到期日" style="width:100%" />
          </el-form-item>
        </template>
        <template v-if="!editing">
          <el-divider content-position="left">组织管理员</el-divider>
          <el-form-item label="管理员手机"><el-input v-model="form.adminPhone" /></el-form-item>
          <el-form-item label="管理员姓名"><el-input v-model="form.adminName" /></el-form-item>
          <el-form-item label="初始密码"><el-input v-model="form.adminPassword" placeholder="留空=手机号后6位" /></el-form-item>
        </template>
        <el-form-item label="状态" v-if="editing">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="active" value="active" />
            <el-option label="suspended" value="suspended" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 成员 -->
    <el-drawer v-model="memDrawer" :title="`成员 · ${current?.name}`" size="680px">
      <div class="toolbar">
        <el-button size="small" type="success" @click="addDialog = true">加成员</el-button>
        <el-button size="small" @click="batchDialog = true">批量建号</el-button>
        <span style="color:#909399">共 {{ members.length }} 人</span>
      </div>
      <el-table :data="members" size="small" border>
        <el-table-column prop="id" label="ID" width="56" />
        <el-table-column prop="guardian_name" label="守望师" width="110" />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column prop="role" label="角色" width="100" />
        <el-table-column label="资料" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_profile_complete ? 'success' : 'info'">{{ row.is_profile_complete ? '已完善' : '待完善' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 加单个成员 -->
    <el-dialog v-model="addDialog" title="加成员" width="400px">
      <el-form :model="memForm" label-width="80px">
        <el-form-item label="手机号"><el-input v-model="memForm.phone" /></el-form-item>
        <el-form-item label="守望师名"><el-input v-model="memForm.guardianName" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="memForm.password" placeholder="留空=手机后6位" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialog = false">取消</el-button>
        <el-button type="primary" @click="addMember">添加</el-button>
      </template>
    </el-dialog>

    <!-- 批量建号 -->
    <el-dialog v-model="batchDialog" title="批量建号" width="480px">
      <p style="color:#909399; font-size:13px">每行一个，格式：<code>手机号,守望师名</code>（姓名可省）</p>
      <el-input v-model="batchText" type="textarea" :rows="8" placeholder="13800000001,小明&#10;13800000002,小红" />
      <template #footer>
        <el-button @click="batchDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="batchCreate">提交</el-button>
      </template>
    </el-dialog>

    <!-- 续期 -->
    <ValidityEditor v-model:visible="validityDialog" :title="`续期 · ${validityTarget?.name || ''}`"
      :current="validityTarget?.valid_until" :loading="savingValidity" @save="onSaveValidity" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listOrgs, createOrg, updateOrg, deleteOrg, listOrgMembers, addOrgMember, batchCreateMembers, setOrgValidity } from '../api/admin'
import ValidityEditor from '../components/ValidityEditor.vue'
import { PERMANENT_UNTIL, endOfDay, membershipTag } from '../utils/membership'

const orgs = ref([])
const loading = ref(false)
async function load() {
  loading.value = true
  try { const { data } = await listOrgs(); orgs.value = data.organizations }
  catch (e) { ElMessage.error(e.response?.data?.error || '加载失败') }
  finally { loading.value = false }
}

const dialog = ref(false)
const editing = ref(false)
const saving = ref(false)
const editId = ref(null)
const form = reactive({ name: '', description: '', maxMembers: 50, adminPhone: '', adminName: '', adminPassword: '', status: 'active', validMode: 'permanent', validDay: null })

function openCreate() {
  editing.value = false; editId.value = null
  Object.assign(form, { name: '', description: '', maxMembers: 50, adminPhone: '', adminName: '', adminPassword: '', status: 'active', validMode: 'permanent', validDay: null })
  dialog.value = true
}

// 创建表单 → 初始有效期值
function initialValidity() {
  if (form.validMode === 'permanent') return PERMANENT_UNTIL
  if (form.validMode === 'none') return null
  return form.validDay ? endOfDay(form.validDay) : PERMANENT_UNTIL
}
function openEdit(row) {
  editing.value = true; editId.value = row.id
  Object.assign(form, { name: row.name, description: row.description || '', maxMembers: row.max_members, status: row.status })
  dialog.value = true
}
async function save() {
  if (!form.name.trim()) return ElMessage.warning('请填写组织名称')
  saving.value = true
  try {
    if (editing.value) {
      await updateOrg(editId.value, { name: form.name, description: form.description, maxMembers: form.maxMembers, status: form.status })
    } else {
      if (!form.adminPhone.trim()) { saving.value = false; return ElMessage.warning('请填写管理员手机号') }
      const { data } = await createOrg({ orgName: form.name, description: form.description, maxMembers: form.maxMembers, adminPhone: form.adminPhone, adminName: form.adminName, adminPassword: form.adminPassword || undefined })
      const vu = initialValidity()
      if (vu != null && data?.organization?.id) await setOrgValidity(data.organization.id, vu)
    }
    ElMessage.success('已保存'); dialog.value = false; load()
  } catch (e) { ElMessage.error(e.response?.data?.error || '保存失败') }
  finally { saving.value = false }
}
async function suspend(row) {
  try { await deleteOrg(row.id); ElMessage.success('已停用'); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '操作失败') }
}

// 续期
const validityDialog = ref(false)
const validityTarget = ref(null)
const savingValidity = ref(false)
function openValidity(row) { validityTarget.value = row; validityDialog.value = true }
async function onSaveValidity(validUntil) {
  savingValidity.value = true
  try {
    await setOrgValidity(validityTarget.value.id, validUntil)
    ElMessage.success('已更新会员有效期')
    validityDialog.value = false
    load()
  } catch (e) { ElMessage.error(e.response?.data?.error || '更新失败') }
  finally { savingValidity.value = false }
}

// 成员
const memDrawer = ref(false)
const current = ref(null)
const members = ref([])
async function openMembers(row) {
  current.value = row; memDrawer.value = true; loadMembers()
}
async function loadMembers() {
  try { const { data } = await listOrgMembers(current.value.id); members.value = data.members }
  catch (e) { ElMessage.error(e.response?.data?.error || '加载成员失败') }
}

const addDialog = ref(false)
const memForm = reactive({ phone: '', guardianName: '', password: '' })
async function addMember() {
  if (!memForm.phone.trim()) return ElMessage.warning('请填写手机号')
  try {
    await addOrgMember(current.value.id, { phone: memForm.phone, guardianName: memForm.guardianName || null, password: memForm.password || undefined })
    ElMessage.success('已添加'); addDialog.value = false
    Object.assign(memForm, { phone: '', guardianName: '', password: '' })
    loadMembers(); load()
  } catch (e) { ElMessage.error(e.response?.data?.error || '添加失败') }
}

const batchDialog = ref(false)
const batchText = ref('')
async function batchCreate() {
  const list = batchText.value.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
    const [phone, guardianName] = l.split(',').map(s => (s || '').trim())
    return { phone, guardianName: guardianName || null }
  })
  if (!list.length) return ElMessage.warning('请输入至少一行')
  saving.value = true
  try {
    const { data } = await batchCreateMembers(current.value.id, list)
    ElMessage.success(`成功 ${data.createdCount} 个，跳过 ${data.skipped.length} 个`)
    batchDialog.value = false; batchText.value = ''
    loadMembers(); load()
  } catch (e) { ElMessage.error(e.response?.data?.error || '批量建号失败') }
  finally { saving.value = false }
}

onMounted(load)
</script>
