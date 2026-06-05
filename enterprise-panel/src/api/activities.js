import api from './index'

export const getActivities = () => api.get('/api/enterprise/activities')
export const createActivity = (data) => api.post('/api/enterprise/activities', data)
export const updateActivity = (id, data) => api.put(`/api/enterprise/activities/${id}`, data)
export const getActivitySessions = (id) => api.get(`/api/enterprise/activities/${id}/sessions`)
