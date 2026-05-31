import { randomUUID } from "crypto";
import { dbRun, dbGet, dbAll } from "../db.js";

/**
 * 单设备登录核心：每个用户在 user_sessions 中只保留一条有效会话。
 * 登录成功时调用 rotateSession：删除该用户旧会话 + 写入新会话，
 * 旧设备持有的 token（jti 已被删）在下一次请求即被 authMiddleware 判定失效。
 *
 * @returns {Promise<string>} 新会话的 jti（写入 JWT）
 */
export async function rotateSession(userId, { deviceInfo = null, ip = null } = {}) {
  const jti = randomUUID();
  const now = Date.now();
  await dbRun("DELETE FROM user_sessions WHERE user_id = ?", [userId]);
  await dbRun(
    "INSERT INTO user_sessions(user_id, jti, device_info, ip, created_at, last_seen_at) VALUES(?,?,?,?,?,?)",
    [userId, jti, deviceInfo, ip, now, now]
  );
  return jti;
}

// 校验 token 的 jti 是否仍是该用户当前有效会话（无 jti 的旧 token 一律失效）
export async function isSessionValid(userId, jti) {
  if (!jti) return false;
  const row = await dbGet(
    "SELECT id FROM user_sessions WHERE user_id = ? AND jti = ?",
    [userId, jti]
  );
  return !!row;
}

// 刷新最后活跃时间（best-effort，失败不影响请求）
export async function touchSession(jti) {
  if (!jti) return;
  await dbRun("UPDATE user_sessions SET last_seen_at = ? WHERE jti = ?", [Date.now(), jti]);
}

// 登出：删除当前会话
export async function revokeSession(jti) {
  if (!jti) return;
  await dbRun("DELETE FROM user_sessions WHERE jti = ?", [jti]);
}

// 管理员强制下线：删除某用户全部会话
export async function revokeUserSessions(userId) {
  await dbRun("DELETE FROM user_sessions WHERE user_id = ?", [userId]);
}

// 列出某用户的在线会话（后台展示"当前登录设备"）
export async function listUserSessions(userId) {
  return dbAll(
    "SELECT id, jti, device_info, ip, created_at, last_seen_at FROM user_sessions WHERE user_id = ? ORDER BY last_seen_at DESC",
    [userId]
  );
}
