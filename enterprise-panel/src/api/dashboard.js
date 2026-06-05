import api from './index'

export const getDashboard = () => api.get('/api/enterprise/dashboard')
export const getOrgInfo = () => api.get('/api/enterprise/info')
