<template>
  <div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px">
      <h3>活动管理</h3>
      <el-button type="primary" :icon="Plus" @click="showCreate = true">创建活动</el-button>
    </div>

    <el-card shadow="hover">
      <el-table :data="activities" v-loading="loading" stripe>
        <el-table-column prop="name" label="活动名称" min-width="160" />
        <el-table-column prop="activity_code" label="活动码" width="120">
          <template #default="{ row }">
            <el-tag type="info" effect="plain">{{ row.activity_code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="organizer" label="组织者" width="120" />
        <el-table-column prop="table_count" label="桌数" width="80" />
        <el-table-column prop="participant_count" label="参与人数" width="100" />
        <el-table-column prop="avg_score" label="均分" width="80" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '进行中' : '已归档' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push({ name: 'ActivityDetail', params: { id: row.id } })">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreate" title="创建活动" width="440px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="活动名称" required>
          <el-input v-model="form.name" placeholder="如：2026春季安全培训" />
        </el-form-item>
        <el-form-item label="组织者">
          <el-input v-model="form.organizer" placeholder="负责人姓名" />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="form.started_at" type="datetime" placeholder="可选" value-format="x" style="width:100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="form.ended_at" type="datetime" placeholder="可选" value-format="x" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getActivities, createActivity } from '../api/activities'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const activities = ref([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const form = reactive({ name: '', organizer: '', started_at: null, ended_at: null })

async function loadData() {
  loading.value = true
  try {
    const { data } = await getActivities()
    activities.value = data.activities
  } catch { /* empty */ }
  loading.value = false
}

async function handleCreate() {
  if (!form.name) { ElMessage.warning('请输入活动名称'); return }
  creating.value = true
  try {
    const { data } = await createActivity(form)
    ElMessage.success(`活动已创建，活动码：${data.activity_code}`)
    showCreate.value = false
    Object.assign(form, { name: '', organizer: '', started_at: null, ended_at: null })
    await loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '创建失败')
  }
  creating.value = false
}

onMounted(loadData)
</script>
