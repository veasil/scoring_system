import api from './index'

// 概览（G1）
export const getOverview = () => api.get('/api/admin/stats/overview')

// 用户（G2-G5）
export const listUsers = (params) => api.get('/api/admin/users', { params })
export const createUser = (body) => api.post('/api/admin/users', body)
export const updateUser = (id, body) => api.put(`/api/admin/users/${id}`, body)
export const deleteUser = (id) => api.delete(`/api/admin/users/${id}`)

// 组织（已就绪 + G6/G7）
export const listOrgs = () => api.get('/api/admin/organizations')
export const createOrg = (body) => api.post('/api/admin/organizations', body)
export const updateOrg = (id, body) => api.put(`/api/admin/organizations/${id}`, body)
export const deleteOrg = (id) => api.delete(`/api/admin/organizations/${id}`)
export const listOrgMembers = (id) => api.get(`/api/admin/organizations/${id}/members`)
export const addOrgMember = (id, body) => api.post(`/api/admin/organizations/${id}/members`, body)
export const batchCreateMembers = (id, members) => api.post(`/api/admin/organizations/${id}/members/batch`, { members })

// 账号资产 / 会员有效期 & 在线设备
export const setOrgValidity = (id, validUntil) => api.put(`/api/admin/organizations/${id}/validity`, { validUntil })
export const setUserValidity = (id, validUntil) => api.put(`/api/admin/users/${id}/validity`, { validUntil })
export const getUserSessions = (id) => api.get(`/api/admin/users/${id}/sessions`)
export const revokeUserSessions = (id) => api.delete(`/api/admin/users/${id}/sessions`)

// 邀请码（已就绪）
export const listInviteCodes = () => api.get('/api/admin/invite-codes')
export const createInviteCode = (body) => api.post('/api/admin/invite-codes', body)

// 卡牌（已就绪）
export const listCards = (params) => api.get('/api/admin/cards', { params })
export const createCard = (body) => api.post('/api/cards', body)
export const updateCard = (id, body) => api.put(`/api/cards/${id}`, body)
export const deleteCard = (id) => api.delete(`/api/cards/${id}`)
export const generateCard = (body) => api.post('/api/admin/generate-card', body)
// 版本（card_versions）
export const listCardVersions = (id) => api.get(`/api/admin/cards/${id}/versions`)
export const branchCard = (id, body) => api.post(`/api/admin/cards/${id}/branch`, body)
export const updateCardVersion = (verId, body) => api.put(`/api/admin/card-versions/${verId}`, body)
export const promoteCardVersion = (verId) => api.post(`/api/admin/card-versions/${verId}/promote`)
export const deleteCardVersion = (id, verId) => api.delete(`/api/admin/cards/${id}/versions/${verId}`)
export const releaseCard = (id, body) => api.post(`/api/admin/cards/${id}/release`, body)
// 批注（notes）
export const listCardNotes = (id) => api.get(`/api/admin/cards/${id}/notes`)
export const addCardNote = (id, body) => api.post(`/api/admin/cards/${id}/notes`, body)
export const updateCardNote = (id, noteId, body) => api.put(`/api/admin/cards/${id}/notes/${noteId}`, body)
export const deleteCardNote = (id, noteId) => api.delete(`/api/admin/cards/${id}/notes/${noteId}`)
// 卡牌组
export const listCardGroups = () => api.get('/api/admin/card-groups')

// 活动（已就绪）
export const listActivities = () => api.get('/api/admin/activities')
export const createActivity = (body) => api.post('/api/admin/activities', body)
export const updateActivity = (id, body) => api.put(`/api/admin/activities/${id}`, body)
export const listActivitySessions = (id) => api.get(`/api/admin/activities/${id}/sessions`)

// OSS（已就绪）
export const listOssFiles = (params) => api.get('/api/admin/oss/files', { params })
export const deleteOssFile = (filename) => api.delete('/api/admin/oss/files', { data: { filename } })

// 游戏分析（G8/G9）
export const statsSessions = (params) => api.get('/api/admin/stats/sessions', { params })
export const statsCards = () => api.get('/api/admin/stats/cards')
export const sessionEvents = (id) => api.get(`/api/admin/sessions/${id}/events`)

// 数据审计（G14/G15）
export const auditSessions = (status) => api.get('/api/admin/audit/sessions', { params: { status } })
export const setSessionStatus = (id, status) => api.put(`/api/admin/sessions/${id}/status`, { status })
export const deleteSession = (id) => api.delete(`/api/admin/sessions/${id}`)

// 系统设置（G11/G12）
export const getSettings = () => api.get('/api/admin/settings')
export const putSetting = (key, value, description) => api.put('/api/admin/settings', { key, value, description })
export const listOperators = () => api.get('/api/admin/operators')

// 复盘测试（已就绪）
export const generateStory = (body) => api.post('/api/llm/story', body)
