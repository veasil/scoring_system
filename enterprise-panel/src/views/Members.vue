<template>
  <div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
      <h3>成员管理</h3>
      <div style="display:flex; gap:8px; align-items:center">
        <el-tag v-if="org" :type="orgBadge.type" effect="plain">成员有效期跟随组织：{{ orgBadge.text }}</el-tag>
        <el-tag v-if="quota">{{ quota.used }} / {{ quota.max }} 人</el-tag>
        <el-button type="primary" :icon="Plus" @click="showAddDialog = true">添加成员</el-button>
      </div>
    </div>

    <el-card shadow="hover">
      <el-table :data="members" v-loading="loading" stripe>
        <el-table-column prop="real_name" label="真实姓名" width="120" />
        <el-table-column prop="guardian_name" label="昵称" width="120" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column label="等级" width="120">
          <template #default="{ row }">{{ LEVEL_LABELS[row.watcher_level] || row.watcher_level }}</template>
        </el-table-column>
        <el-table-column prop="total_games" label="游戏次数" width="100" />
        <el-table-column label="最近活跃" width="180">
          <template #default="{ row }">{{ formatDate(row.last_active) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push({ name: 'MemberDetail', params: { id: row.id } })">详情</el-button>
            <el-button size="small" type="danger" @click="handleRemove(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加成员弹窗 -->
    <el-dialog v-model="showAddDialog" title="添加成员" width="440px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="手机号" required>
          <el-input v-model="addForm.phone" placeholder="手机号" />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="addForm.realName" placeholder="真实姓名" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="addForm.guardianName" placeholder="昵称/守望师名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="addForm.password" placeholder="留空则默认手机号后6位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAdd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getMembers, createMember, deleteMember } from '../api/members'
import { getOrgInfo } from '../api/dashboard'
import { formatDate, LEVEL_LABELS, membershipBadge } from '../utils/format'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const members = ref([])
const quota = ref(null)
const org = ref(null)
const orgBadge = computed(() => membershipBadge(org.value?.validUntil))
const loading = ref(false)
const showAddDialog = ref(false)
const addLoading = ref(false)
const addForm = reactive({ phone: '', guardianName: '', realName: '', password: '' })

async function loadData() {
  loading.value = true
  try {
    const [m, info] = await Promise.all([getMembers(), getOrgInfo()])
    members.value = m.data.members
    quota.value = m.data.quota
    org.value = info.data.organization
  } catch { /* empty */ }
  loading.value = false
}

async function handleAdd() {
  if (!addForm.phone) { ElMessage.warning('请输入手机号'); return }
  addLoading.value = true
  try {
    await createMember(addForm)
    ElMessage.success('添加成功')
    showAddDialog.value = false
    Object.assign(addForm, { phone: '', guardianName: '', realName: '', password: '' })
    await loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '添加失败')
  }
  addLoading.value = false
}

async function handleRemove(row) {
  try {
    await ElMessageBox.confirm(`确定移除 ${row.guardian_name || row.phone}？`, '提示', { type: 'warning' })
    await deleteMember(row.id)
    ElMessage.success('已移除')
    await loadData()
  } catch { /* cancelled */ }
}

onMounted(loadData)
</script>
