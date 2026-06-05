import api from './index'

export const getMembers = () => api.get('/api/enterprise/members')
export const createMember = (data) => api.post('/api/enterprise/members', data)
export const updateMember = (id, data) => api.put(`/api/enterprise/members/${id}`, data)
export const deleteMember = (id) => api.delete(`/api/enterprise/members/${id}`)
export const getMemberStats = (id) => api.get(`/api/enterprise/members/${id}/stats`)
