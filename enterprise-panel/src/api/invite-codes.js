import api from './index'

export const getInviteCodes = () => api.get('/api/enterprise/invite-codes')
export const createInviteCode = (data) => api.post('/api/enterprise/invite-codes', data)
