import api from './index'

export const getSessions = (params) => api.get('/api/enterprise/sessions', { params })
