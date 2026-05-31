import { Router } from "express";
import { dbGet, dbRun } from "../db.js";
import { authMiddleware } from "../middleware/auth.js";
import { requireRole } from "../middleware/rbac.js";
import { listUserSessions, revokeUserSessions } from "../services/sessions.js";

const router = Router();

// 解析 validUntil 入参：接受毫秒时间戳、ISO 字符串，或 null（表示不限期）
function parseValidUntil(input) {
  if (input === null || input === undefined || input === "") return { ok: true, value: null };
  if (typeof input === "number") return { ok: true, value: input };
  const n = Number(input);
  if (Number.isFinite(n) && String(input).trim() !== "") return { ok: true, value: n };
  const t = Date.parse(input);
  if (!Number.isNaN(t)) return { ok: true, value: t };
  return { ok: false };
}

// ======== 组织有效期（组织统一到期）========
router.put("/api/admin/organizations/:id/validity", authMiddleware, requireRole("boss"), async (req, res) => {
  const org = await dbGet("SELECT id FROM organizations WHERE id = ?", [req.params.id]);
  if (!org) return res.status(404).json({ error: "组织不存在" });

  const parsed = parseValidUntil(req.body?.validUntil);
  if (!parsed.ok) return res.status(400).json({ error: "validUntil 格式不正确" });

  await dbRun("UPDATE organizations SET valid_until = ?, updated_at = ? WHERE id = ?", [parsed.value, Date.now(), req.params.id]);
  res.json({ ok: true, validUntil: parsed.value });
});

// ======== 个人独立用户有效期 ========
router.put("/api/admin/users/:id/validity", authMiddleware, requireRole("boss"), async (req, res) => {
  const user = await dbGet("SELECT id, enterprise_id FROM users WHERE id = ?", [req.params.id]);
  if (!user) return res.status(404).json({ error: "用户不存在" });
  if (user.enterprise_id) {
    return res.status(400).json({ error: "该用户属于组织，请在组织上设置有效期（组织统一到期）" });
  }

  const parsed = parseValidUntil(req.body?.validUntil);
  if (!parsed.ok) return res.status(400).json({ error: "validUntil 格式不正确" });

  await dbRun("UPDATE users SET valid_until = ? WHERE id = ?", [parsed.value, req.params.id]);
  res.json({ ok: true, validUntil: parsed.value });
});

// ======== 查看某用户在线会话（当前登录设备）========
router.get("/api/admin/users/:id/sessions", authMiddleware, requireRole("boss"), async (req, res) => {
  const sessions = await listUserSessions(req.params.id);
  res.json({ sessions });
});

// ======== 强制下线某用户（删除其全部会话）========
router.delete("/api/admin/users/:id/sessions", authMiddleware, requireRole("boss"), async (req, res) => {
  await revokeUserSessions(req.params.id);
  res.json({ ok: true });
});

export default router;
