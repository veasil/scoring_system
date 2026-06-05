<template>
  <div class="login-wrapper">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <h2 style="text-align:center; margin:0">WQT 中台管理系统</h2>
      </template>
      <el-radio-group v-model="mode" style="margin-bottom:16px; width:100%; display:flex">
        <el-radio-button value="phone" style="flex:1">手机号登录</el-radio-button>
        <el-radio-button value="key" style="flex:1">开发者密钥</el-radio-button>
      </el-radio-group>

      <el-form v-if="mode === 'phone'" @submit.prevent="handlePhone" label-position="top">
        <el-form-item label="管理员手机号（boss / 运营）">
          <el-input v-model="phone" placeholder="请输入手机号" :prefix-icon="Phone"
            @keyup.enter="handlePhone" />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="handlePhone" style="width:100%">登 录</el-button>
      </el-form>

      <el-form v-else @submit.prevent="handleKey" label-position="top">
        <el-form-item label="开发者密钥（DEV_KEY）">
          <el-input v-model="key" type="password" placeholder="请输入开发者密钥" :prefix-icon="Lock"
            show-password @keyup.enter="handleKey" />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="handleKey" style="width:100%">登 录</el-button>
      </el-form>

      <div v-if="error" style="color:#f56c6c; text-align:center; margin-top:12px; font-size:14px">{{ error }}</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { devLogin, adminLogin } from '../api/auth'
import { Phone, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const mode = ref('phone')
const phone = ref('')
const key = ref('')
const loading = ref(false)
const error = ref('')

async function finish(data) {
  auth.setAuth(data.token, data.user)
  router.push({ name: 'Overview' })
}

async function handlePhone() {
  error.value = ''
  if (!phone.value) { error.value = '请输入手机号'; return }
  loading.value = true
  try {
    const { data } = await adminLogin(phone.value)
    await finish(data)
  } catch (e) {
    error.value = e.response?.data?.error || '登录失败'
  } finally { loading.value = false }
}

async function handleKey() {
  error.value = ''
  if (!key.value) { error.value = '请输入开发者密钥'; return }
  loading.value = true
  try {
    const { data } = await devLogin(key.value)
    await finish(data)
  } catch (e) {
    error.value = e.response?.data?.error || '登录失败'
  } finally { loading.value = false }
}
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1f2d3d 0%, #409eff 100%);
}
.login-card { width: 420px; max-width: 90vw; }
</style>
