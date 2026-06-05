<template>
  <div>
    <h1 class="page-title">OSS 文件管理</h1>

    <el-alert v-if="notConfigured" type="warning" :closable="false" show-icon
      title="服务器未配置 OSS" description="设置 ALIBABA_CLOUD_ACCESS_KEY_* / OSS_* 后即可浏览与删除文件。" style="margin-bottom:12px" />

    <div class="toolbar">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item><a @click="goto('')">根目录</a></el-breadcrumb-item>
        <el-breadcrumb-item v-for="(seg, i) in crumbs" :key="i"><a @click="goto(crumbPrefix(i))">{{ seg }}</a></el-breadcrumb-item>
      </el-breadcrumb>
      <el-button size="small" @click="load">刷新</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border size="small">
      <el-table-column label="名称" min-width="320">
        <template #default="{ row }">
          <span v-if="row.type === 'folder'" style="cursor:pointer; color:#409eff" @click="goto(row.raw)">📁 {{ row.display }}</span>
          <span v-else>📄 {{ row.display }}</span>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="110">
        <template #default="{ row }">{{ row.type === 'folder' ? '—' : human(row.size) }}</template>
      </el-table-column>
      <el-table-column label="修改时间" width="180">
        <template #default="{ row }">{{ row.type === 'folder' ? '—' : fmt(row.lastModified) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <template v-if="row.type === 'file'">
            <el-button size="small" link type="primary" @click="copyUrl(row.url)">复制链接</el-button>
            <el-popconfirm title="删除该文件？" @confirm="del(row)">
              <template #reference><el-button size="small" link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="nextMarker" style="margin-top:12px; text-align:center">
      <el-button size="small" @click="loadMore">加载更多</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listOssFiles, deleteOssFile } from '../api/admin'

const prefix = ref('')
const rows = ref([])
const loading = ref(false)
const notConfigured = ref(false)
const nextMarker = ref(null)

const crumbs = computed(() => prefix.value.split('/').filter(Boolean))
function crumbPrefix(i) { return crumbs.value.slice(0, i + 1).join('/') + '/' }
function fmt(ts) { return ts ? new Date(ts).toLocaleString('zh-CN', { hour12: false }) : '' }
function human(b) { if (b == null) return ''; const u = ['B', 'KB', 'MB', 'GB']; let i = 0, n = b; while (n >= 1024 && i < 3) { n /= 1024; i++ } return n.toFixed(i ? 1 : 0) + u[i] }

function toRows(data) {
  const folders = (data.folders || []).map(f => ({ type: 'folder', raw: f, display: f.replace(prefix.value, '').replace(/\/$/, '') }))
  const files = (data.files || []).filter(f => f.name !== prefix.value).map(f => ({
    type: 'file', raw: f.name, display: f.name.replace(prefix.value, ''), url: f.url, size: f.size, lastModified: f.lastModified
  }))
  return [...folders, ...files]
}

async function load() {
  loading.value = true; notConfigured.value = false; nextMarker.value = null
  try {
    const { data } = await listOssFiles({ prefix: prefix.value || undefined, maxKeys: 100 })
    rows.value = toRows(data)
    nextMarker.value = data.nextMarker || null
  } catch (e) {
    if ((e.response?.data?.error || '').includes('未配置 OSS')) notConfigured.value = true
    else ElMessage.error(e.response?.data?.error || '加载失败')
    rows.value = []
  } finally { loading.value = false }
}
async function loadMore() {
  try {
    const { data } = await listOssFiles({ prefix: prefix.value || undefined, marker: nextMarker.value, maxKeys: 100 })
    rows.value = [...rows.value, ...toRows(data)]
    nextMarker.value = data.nextMarker || null
  } catch (e) { ElMessage.error(e.response?.data?.error || '加载失败') }
}
function goto(p) { prefix.value = p; load() }

async function del(row) {
  try { await deleteOssFile(row.raw); ElMessage.success('已删除'); load() }
  catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
}
async function copyUrl(url) {
  try { await navigator.clipboard.writeText(url); ElMessage.success('链接已复制') }
  catch { ElMessage.warning(url) }
}

onMounted(load)
</script>
