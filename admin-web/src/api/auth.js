import api from './index'

// 开发者密钥登录（boss 级）
export const devLogin = (key) => api.post('/api/auth/dev-login', { key })

// 发送短信验证码
export const sendSmsCode = (phone) => api.post('/api/auth/sms/send', { phone })

// 三要素登录（手机号 + 密码 + 验证码），返回 role 由前端校验是否可进后台
export const loginByPassword = (phone, password, code) =>
  api.post('/api/auth/login', { phone, password, code })
