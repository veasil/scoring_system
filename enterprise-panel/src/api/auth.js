import api from './index'

export const loginByPassword = (username, password) =>
  api.post('/api/auth/login', { username, password })
