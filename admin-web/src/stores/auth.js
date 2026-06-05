import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

// 注意：用独立的 storage key（aw_*），与 enterprise-panel(ep_*) 隔离，避免同域 token 串号
export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('aw_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('aw_user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)

  function setAuth(t, u) {
    token.value = t
    user.value = u
    localStorage.setItem('aw_token', t)
    localStorage.setItem('aw_user', JSON.stringify(u))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('aw_token')
    localStorage.removeItem('aw_user')
  }

  async function fetchMe() {
    try {
      const { data } = await api.get('/api/me')
      user.value = data.user || data
      localStorage.setItem('aw_user', JSON.stringify(user.value))
    } catch {
      logout()
    }
  }

  return { token, user, isLoggedIn, setAuth, logout, fetchMe }
})
