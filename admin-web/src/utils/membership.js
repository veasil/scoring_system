// 会员有效期口径（与后端 src/account.js 一致）
//   null            → 未开通会员
//   PERMANENT_UNTIL → 永久会员
//   未来时间戳        → 有效，到期某日
//   过去时间戳        → 已过期
export const PERMANENT_UNTIL = 253402300799000

// 返回用于 el-tag 的 { type, text }
export function membershipTag(validUntil) {
  if (validUntil == null) return { type: 'info', text: '未开通' }
  const d = Number(validUntil)
  if (d >= PERMANENT_UNTIL) return { type: 'primary', text: '永久' }
  const now = Date.now()
  if (now > d) return { type: 'danger', text: `已过期 ${Math.ceil((now - d) / 86400000)} 天` }
  return { type: 'success', text: `有效至 ${new Date(d).toLocaleDateString('zh-CN')}` }
}

// 日期选择器给出的当天 0 点毫秒 → 当天 23:59:59.999
export const endOfDay = (ms) => Number(ms) + 86399999
