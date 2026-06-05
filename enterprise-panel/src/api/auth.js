import api from './index'

export const sendSmsCode = (phone) =>
  api.post('/api/auth/sms/send', { phone })

export const loginByPassword = (phone, password, code) =>
  api.post('/api/auth/login', { phone, password, code })
