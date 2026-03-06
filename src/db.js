import sqlite3 from "sqlite3";
import fs from "fs";
import path from "path";
import bcrypt from "bcryptjs";

const DB_PATH = process.env.DB_PATH || "./data/wqt.db";

let db;

export async function initDb() {
  const dir = path.dirname(DB_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  db = new sqlite3.Database(DB_PATH);

  // users 表
  await dbRun(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE,
      phone TEXT UNIQUE,
      wechat_openid TEXT UNIQUE,
      unionid TEXT,
      password_hash TEXT,
      guardian_name TEXT,
      is_profile_complete INTEGER DEFAULT 0,
      created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000)
    );
  `);

  // 添加缺失的列（如果不存在）
  const userCols = [
    `ALTER TABLE users ADD COLUMN guardian_name TEXT`,
    `ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'watcher'`,
    `ALTER TABLE users ADD COLUMN enterprise_id INTEGER`,
    `ALTER TABLE users ADD COLUMN watcher_level TEXT DEFAULT 'initial'`,
  ];
  for (const sql of userCols) {
    try { await dbRun(sql); } catch (e) { /* 列已存在，忽略 */ }
  }

  // 存量角色迁移：admin → boss，user → watcher
  await dbRun(`UPDATE users SET role = 'boss' WHERE role = 'admin'`);
  await dbRun(`UPDATE users SET role = 'watcher' WHERE role = 'user' OR role IS NULL`);

  // sms_codes 表（临时验证码）
  await dbRun(`
    CREATE TABLE IF NOT EXISTS sms_codes (
      phone TEXT PRIMARY KEY,
      code_hash TEXT NOT NULL,
      expires_at INTEGER NOT NULL,
      created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000)
    );
  `);

  // game_sessions 表（一局游戏）
  await dbRun(`
    CREATE TABLE IF NOT EXISTS game_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      started_at INTEGER,
      ended_at INTEGER,
      final_score INTEGER,
      payload_json TEXT,
      location TEXT,
      players_json TEXT,
      game_mode TEXT,
      game_settings_json TEXT,
      status TEXT DEFAULT 'active',
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
  `);

  // 为已存在的旧表补全缺失列
  const sessionCols = [
    `ALTER TABLE game_sessions ADD COLUMN location TEXT`,
    `ALTER TABLE game_sessions ADD COLUMN players_json TEXT`,
    `ALTER TABLE game_sessions ADD COLUMN game_mode TEXT`,
    `ALTER TABLE game_sessions ADD COLUMN game_settings_json TEXT`,
    `ALTER TABLE game_sessions ADD COLUMN status TEXT DEFAULT 'active'`,
  ];
  for (const sql of sessionCols) {
    try { await dbRun(sql); } catch (e) { /* 列已存在，忽略 */ }
  }

  // game_events 表（游戏事件）
  await dbRun(`
    CREATE TABLE IF NOT EXISTS game_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id INTEGER NOT NULL,
      ts INTEGER NOT NULL,
      type TEXT NOT NULL,
      payload TEXT,
      FOREIGN KEY(session_id) REFERENCES game_sessions(id)
    );
  `);

  // system_settings 表 (用于存配置)
  await dbRun(`
    CREATE TABLE IF NOT EXISTS system_settings (
      key TEXT PRIMARY KEY,
      value TEXT,
      description TEXT,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // activities 表（活动场次）
  await dbRun(`
    CREATE TABLE IF NOT EXISTS activities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      organizer TEXT,
      activity_code TEXT UNIQUE,
      started_at INTEGER,
      ended_at INTEGER,
      created_by INTEGER REFERENCES users(id),
      status TEXT DEFAULT 'active',
      created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000)
    )
  `);

  // activity_sessions 关联表（活动 → 游戏桌）
  await dbRun(`
    CREATE TABLE IF NOT EXISTS activity_sessions (
      activity_id INTEGER REFERENCES activities(id),
      session_id INTEGER REFERENCES game_sessions(id),
      table_no INTEGER,
      PRIMARY KEY (activity_id, session_id)
    )
  `);

  // watcher_level_applications 守望者等级申请
  await dbRun(`
    CREATE TABLE IF NOT EXISTS watcher_level_applications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER REFERENCES users(id),
      from_level TEXT,
      to_level TEXT,
      reason TEXT,
      status TEXT DEFAULT 'pending',
      reviewed_by INTEGER REFERENCES users(id),
      reviewed_at INTEGER,
      note TEXT,
      created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000)
    )
  `);

  // watcher_level_logs 等级变更日志
  await dbRun(`
    CREATE TABLE IF NOT EXISTS watcher_level_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER REFERENCES users(id),
      old_level TEXT,
      new_level TEXT,
      source TEXT DEFAULT 'manual',
      changed_by INTEGER REFERENCES users(id),
      changed_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000),
      note TEXT
    )
  `);

  // user_feedback 感想与反馈
  await dbRun(`
    CREATE TABLE IF NOT EXISTS user_feedback (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER REFERENCES users(id),
      type TEXT DEFAULT 'reflection',
      content TEXT NOT NULL,
      activity_id INTEGER,
      session_id INTEGER,
      created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000),
      reviewed INTEGER DEFAULT 0
    )
  `);

  // 预设默认配置 (Seed)
  const defaults = [
    ["DEV_KEY", "sj0127wqt", "开发者登录密钥（boss 级别）"],
    ["operator_permissions", "{}", "各运营账号权限配置 {user_id: [modules]}"],
    ["DEFAULT_GAME_TIME", "5000", "游戏默认倒计时时长（秒）"],
    ["GAME_MODES", JSON.stringify([
      { id: 'standard', name: '标准版', desc: '体验 15 张卡牌', time: 5000, detail: '启蒙5 / 成长5 / 青春5', targetCards: 15, distribution: { '启蒙期': 5, '成长期': 5, '青春期': 5 } },
      { id: 'essence', name: '精华版', desc: '体验 9 张卡牌', time: 3600, detail: '启蒙3 / 成长3 / 青春3', targetCards: 9, distribution: { '启蒙期': 3, '成长期': 3, '青春期': 3 } }
    ]), "游戏模式定义（JSON格式）"],
    ["ATTRIBUTES_CONFIG", JSON.stringify({
      initial: 3,
      min: 0,
      max: 10,
      failureThreshold: 0
    }), "伍力值评分规则配置"],
    ["BRANDING_INFO", JSON.stringify({
      title: "《AI在5000天·伍力全开》伍力值计分系统",
      copyright: "© 2026 上海伍仟天数字科技有限公司 | 保留所有权利",
      welcome_title: "欢迎来到AI 5000天<br>伍力全开的世界！"
    }), "站点品牌与文本信息"]
  ];
  for (const [key, val, desc] of defaults) {
    const exists = await dbGet("SELECT 1 FROM system_settings WHERE key = ?", [key]);
    if (!exists) {
      await dbRun("INSERT INTO system_settings (key, value, description) VALUES (?, ?, ?)", [key, val, desc]);
    }
  }

  console.log('✅ Main database initialized');
}

export async function getSystemSetting(key, defaultValue = null) {
  const row = await dbGet("SELECT value FROM system_settings WHERE key = ?", [key]);
  return row ? row.value : defaultValue;
}

export async function getAllSettings() {
  return await dbAll("SELECT key, value, description FROM system_settings");
}

export function dbRun(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function (err) {
      if (err) reject(err);
      else resolve({ lastID: this.lastID, changes: this.changes });
    });
  });
}

export function dbGet(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.get(sql, params, (err, row) => {
      if (err) reject(err);
      else resolve(row);
    });
  });
}

export function dbAll(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows);
    });
  });
}

// SMS 验证码相关操作
export async function saveSmsCode(phone, code) {
  const codeHash = bcrypt.hashSync(code, 10);
  const expiresAt = Date.now() + 5 * 60 * 1000; // 5分钟过期
  await dbRun(
    "INSERT OR REPLACE INTO sms_codes(phone, code_hash, expires_at) VALUES(?, ?, ?)",
    [phone, codeHash, expiresAt]
  );
}

export async function verifySmsCode(phone, code) {
  const record = await dbGet(
    "SELECT code_hash, expires_at FROM sms_codes WHERE phone = ?",
    [phone]
  );
  if (!record) return false;
  if (Date.now() > record.expires_at) {
    await dbRun("DELETE FROM sms_codes WHERE phone = ?", [phone]);
    return false;
  }
  const valid = bcrypt.compareSync(code, record.code_hash);
  if (valid) {
    await dbRun("DELETE FROM sms_codes WHERE phone = ?", [phone]);
  }
  return valid;
}

// 游戏事件记录
export async function addGameEvent(sessionId, type, payload = {}) {
  await dbRun(
    "INSERT INTO game_events(session_id, ts, type, payload) VALUES(?, ?, ?, ?)",
    [sessionId, Date.now(), type, JSON.stringify(payload)]
  );
}

// 获取某局游戏的所有事件
export async function getGameEvents(sessionId) {
  return await dbAll(
    "SELECT * FROM game_events WHERE session_id = ? ORDER BY ts ASC",
    [sessionId]
  );
}
