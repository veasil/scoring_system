import api from './index'

// 开发者密钥登录（boss 级）
export const devLogin = (key) => api.post('/api/auth/dev-login', { key })

// 管理后台手机号登录（仅 boss/operator，无需验证码）
export const adminLogin = (phone) => api.post('/api/auth/admin-login', { phone })
