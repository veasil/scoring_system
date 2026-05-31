import { dbGet } from "../db.js";

// 角色校验：要求当前用户的 role 在给定集合内
export function requireRole(...roles) {
  return async (req, res, next) => {
    const user = await dbGet("SELECT id, role, enterprise_id FROM users WHERE id = ?", [req.user.uid]);
    if (!user || !roles.includes(user.role)) {
      return res.status(403).json({ error: "无权限" });
    }
    req.userRow = user;
    next();
  };
}

// 组织管理员校验：解析 enterprise_id 对应的组织，挂到 req.org
export async function requireEnterprise(req, res, next) {
  const user = await dbGet("SELECT id, role, enterprise_id FROM users WHERE id = ?", [req.user.uid]);
  if (!user || user.role !== "enterprise" || !user.enterprise_id) {
    return res.status(403).json({ error: "仅组织管理员可访问" });
  }
  const org = await dbGet("SELECT * FROM organizations WHERE id = ? AND status = 'active'", [user.enterprise_id]);
  if (!org) {
    return res.status(403).json({ error: "组织不存在或已停用" });
  }
  req.userRow = user;
  req.org = org;
  next();
}
