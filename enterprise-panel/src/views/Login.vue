<template>
  <div class="login-wrapper">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <h2 style="text-align:center; margin:0">组织管理后台</h2>
      </template>
      <el-form :model="form" @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="请输入手机号" :prefix-icon="Phone" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码"
            :prefix-icon="Lock" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="handleLogin" style="width:100%">
          登 录
        </el-button>
      </el-form>
      <div v-if="error" style="color:#f56c6c; text-align:center; margin-top:12px; font-size:14px">
        {{ error }}
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { loginByPassword } from '../api/auth'
import { Phone, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ phone: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  error.value = ''
  if (!form.phone || !form.password) { error.value = '请填写手机号和密码'; return }
  loading.value = true
  try {
    const { data } = await loginByPassword(form.phone, form.password)
    if (data.user.role !== 'enterprise') {
      error.value = '该账号不是组织管理员'
      return
    }
    auth.setAuth(data.token, data.user)
    router.push({ name: 'Dashboard' })
  } catch (e) {
    error.value = e.response?.data?.error || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 400px;
  max-width: 90vw;
}
</style>
