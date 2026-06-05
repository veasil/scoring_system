export function formatDate(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
}

export function formatDateShort(ts) {
  if (!ts) return '-'
  const d = new Date(ts)
  return d.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
}

export const LEVEL_LABELS = {
  initial: '初始守望者',
  advanced: '进阶守望者',
  mentor: '导师级守望者'
}

// 会员有效期徽标（口径与后端 src/account.js 一致）。企业端只读展示。
export const PERMANENT_UNTIL = 253402300799000
export function membershipBadge(validUntil) {
  if (validUntil == null) return { type: 'info', text: '未开通', days: null }
  const d = Number(validUntil)
  if (d >= PERMANENT_UNTIL) return { type: 'success', text: '长期有效', days: null }
  const days = Math.ceil((d - Date.now()) / 86400000)
  if (days < 0) return { type: 'danger', text: `已过期 ${-days} 天`, days }
  return { type: days <= 7 ? 'warning' : 'success', text: `有效至 ${formatDateShort(d)}`, days }
}
