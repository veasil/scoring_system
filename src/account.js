import { dbGet } from "./db.js";

// 平台运营人员永不过期
const EXEMPT_ROLES = new Set(["boss", "operator"]);

// 永久会员哨兵值（9999-12-31 23:59:59 UTC 的毫秒时间戳）。
// 选极远未来时间戳的好处：resolveValidity 里 now > valid_until 天然永不触发，无需特判。
export const PERMANENT_UNTIL = 253402300799000;

/**
 * 解析账号有效期（会员资产核心，组织统一到期）。
 *
 * 取值口径：
 *   - NULL              → 未开通会员，拒绝登录
 *   - PERMANENT_UNTIL   → 永久会员
 *   - 未来时间戳         → 有效，到期某日
 *   - 过去时间戳         → 已过期
 *
 * 账号类型规则：
 *   - boss / operator：永不过期（豁免，NULL 也放行）
 *   - 有 enterprise_id（组织成员/管理员）：跟随【组织】的 valid_until + status
 *   - 独立 watcher（enterprise_id 为空）：用【用户自身】的 valid_until
 *
 * @returns {Promise<{valid:boolean, until:(number|null), reason:(string|null)}>}
 *   reason 取值：USER_NOT_FOUND | ORG_NOT_FOUND | ORG_SUSPENDED |
 *               ORG_NO_MEMBERSHIP | ORG_EXPIRED | NO_MEMBERSHIP | ACCOUNT_EXPIRED
 */
export async function resolveValidity(userId) {
  const user = await dbGet(
    "SELECT id, role, enterprise_id, valid_until FROM users WHERE id = ?",
    [userId]
  );
  if (!user) return { valid: false, until: null, reason: "USER_NOT_FOUND" };
  if (EXEMPT_ROLES.has(user.role)) return { valid: true, until: null, reason: null };

  const now = Date.now();

  if (user.enterprise_id) {
    const org = await dbGet(
      "SELECT status, valid_until FROM organizations WHERE id = ?",
      [user.enterprise_id]
    );
    if (!org) return { valid: false, until: null, reason: "ORG_NOT_FOUND" };
    if (org.status !== "active") {
      return { valid: false, until: org.valid_until ?? null, reason: "ORG_SUSPENDED" };
    }
    if (org.valid_until == null) {
      return { valid: false, until: null, reason: "ORG_NO_MEMBERSHIP" };
    }
    if (now > org.valid_until) {
      return { valid: false, until: org.valid_until, reason: "ORG_EXPIRED" };
    }
    return { valid: true, until: org.valid_until, reason: null };
  }

  // 独立个人用户
  if (user.valid_until == null) {
    return { valid: false, until: null, reason: "NO_MEMBERSHIP" };
  }
  if (now > user.valid_until) {
    return { valid: false, until: user.valid_until, reason: "ACCOUNT_EXPIRED" };
  }
  return { valid: true, until: user.valid_until, reason: null };
}
