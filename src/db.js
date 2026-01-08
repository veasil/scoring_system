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
  try {
    await dbRun(`ALTER TABLE users ADD COLUMN guardian_name TEXT`);
  } catch (e) {
    // 列已存在，忽略错误
  }

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
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
  `);

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
