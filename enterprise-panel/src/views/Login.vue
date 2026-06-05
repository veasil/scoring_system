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
            :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item label="验证码">
          <div style="display:flex; gap:8px; width:100%">
            <el-input v-model="form.code" placeholder="请输入短信验证码" :prefix-icon="Message"
              @keyup.enter="handleLogin" style="flex:1" />
            <el-button :disabled="countdown > 0 || sending" :loading="sending" @click="handleSendCode"
              style="width:120px">
              {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
            </el-button>
          </div>
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
import { reactive, ref, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { loginByPassword, sendSmsCode } from '../api/auth'
import { Phone, Lock, Message } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ phone: '', password: '', code: '' })
const loading = ref(false)
const error = ref('')

// 发送验证码 + 60 秒倒计时
const sending = ref(false)
const countdown = ref(0)
let timer = null
function startCountdown() {
  countdown.value = 60
  timer = setInterval(() => {
    if (--countdown.value <= 0) clearInterval(timer)
  }, 1000)
}
onBeforeUnmount(() => clearInterval(timer))

async function handleSendCode() {
  error.value = ''
  if (!form.phone) { error.value = '请先填写手机号'; return }
  sending.value = true
  try {
    const { data } = await sendSmsCode(form.phone)
    // 开发环境会直接返回模拟验证码，方便测试
    ElMessage.success(data.mockCode ? `验证码已发送（测试码：${data.mockCode}）` : '验证码已发送')
    startCountdown()
  } catch (e) {
    error.value = e.response?.data?.error || '验证码发送失败'
  } finally {
    sending.value = false
  }
}

async function handleLogin() {
  error.value = ''
  if (!form.phone || !form.password || !form.code) { error.value = '请填写手机号、密码和验证码'; return }
  loading.value = true
  try {
    const { data } = await loginByPassword(form.phone, form.password, form.code)
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
