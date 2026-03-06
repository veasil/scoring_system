import express from "express";
import cors from "cors";
import morgan from "morgan";
import dotenv from "dotenv";
import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import fetch from "node-fetch";
import path from "path";
import { fileURLToPath } from "url";
import { initDb, dbRun, dbGet, dbAll, saveSmsCode, verifySmsCode, addGameEvent, getGameEvents, getSystemSetting, getAllSettings } from "./src/db.js";
import { initCardsDb, cardsDbRun, cardsDbGet, cardsDbAll } from "./src/cards-db.js";
import { BmobSMS } from "./src/bmob.js";

dotenv.config();



import crypto from "crypto";
await initDb();
await initCardsDb(); // 初始化独立卡牌数据库

// Encryption Helper
function decryptVal(val) {
  if (!val || typeof val !== 'string' || !val.startsWith("enc:")) return val;
  const keyHex = process.env.SETTINGS_ENCRYPTION_KEY;
  if (!keyHex) return val;

  try {
    const parts = val.split(":");
    if (parts.length !== 3) return val;

    // Key
    const key = Buffer.from(keyHex, 'hex');
    // IV
    const iv = Buffer.from(parts[1], 'base64');
    // Ciphertext
    const ciphertext = Buffer.from(parts[2], 'base64');

    const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
    let decrypted = decipher.update(ciphertext);
    decrypted = Buffer.concat([decrypted, decipher.final()]);
    return decrypted.toString('utf-8');
  } catch (e) {
    console.error("Decryption failed:", e.message);
    return val;
  }
}

// Load system settings from DB and merge with process.env
// DB settings take precedence over process.env for these keys
const dbSettings = await getAllSettings();
const config = { ...process.env };

if (dbSettings && dbSettings.length > 0) {
  dbSettings.forEach(s => {
    // Only override if value is not empty
    if (s.value && String(s.value).trim()) {
      config[s.key] = decryptVal(s.value);
    }
  });
}


const app = express();
const PORT = Number(config.PORT || 8080);
const JWT_SECRET = config.JWT_SECRET || "dev_secret_change_me";

// OSS & Upload
import OSS from "ali-oss";
import multer from "multer";

const ossConfig = {
  accessKeyId: config.ALIBABA_CLOUD_ACCESS_KEY_ID,
  accessKeySecret: config.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
  bucket: config.OSS_BUCKET_NAME || "ai5000days-scoring-system-hk",
  secure: true // 强制使用 HTTPS
};

// 优先使用标准 Endpoint 进行 API 操作（避免自定义域名 SSL 证书报错）
if (config.OSS_ENDPOINT) {
  ossConfig.endpoint = config.OSS_ENDPOINT;
} else {
  ossConfig.region = (config.OSS_REGION || "oss-cn-hongkong").startsWith("oss-")
    ? config.OSS_REGION
    : `oss-${config.OSS_REGION}`;
}
// 注意：不为了 API 操作开启 cname 模式，防止 SSL 校验失败。
// 自定义域名仅用于生成对外访问链接。
// OSS Client Init
const ossClient = config.ALIBABA_CLOUD_ACCESS_KEY_ID && config.ALIBABA_CLOUD_ACCESS_KEY_SECRET
  ? new OSS(ossConfig)
  : null;

if (ossClient) {
  console.log("✅ OSS Client initialized.");
  console.log("   Bucket:", ossConfig.bucket);
  console.log("   Region/Endpoint:", ossConfig.region || ossConfig.endpoint);
} else {
  console.log("❌ OSS Client NOT initialized.");
  console.log("   ALIBABA_CLOUD_ACCESS_KEY_ID present:", !!config.ALIBABA_CLOUD_ACCESS_KEY_ID);
  console.log("   ALIBABA_CLOUD_ACCESS_KEY_SECRET present:", !!config.ALIBABA_CLOUD_ACCESS_KEY_SECRET);
}

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 50 * 1024 * 1024 } // 50MB limit
});


// 初始化Bmob短信服务
const bmobSMS = config.BMOB_APP_ID && config.BMOB_REST_KEY
  ? new BmobSMS(config.BMOB_APP_ID, config.BMOB_REST_KEY)
  : null;




app.use(morgan("dev"));
app.use(express.json({ limit: "2mb" }));

// 本地开发：同域访问最省事；如果你前后端分离，这里把 origin 改成你的前端地址
app.use(cors({
  origin: true,
  credentials: false
}));

// 静态资源
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
app.use(express.static(path.join(__dirname, "public")));

// ======== SMS mock storage ========
const smsStore = new Map(); // phone => { code, expiresAt, lastSent }
const SMS_CODE_TTL_MS = 5 * 60 * 1000;
const SMS_RESEND_INTERVAL_MS = 60 * 1000;

function normalizePhone(input) {
  if (!input) return "";
  return String(input).replace(/\D/g, "");
}

function generateSmsCode() {
  return String(Math.floor(100000 + Math.random() * 900000));
}

// ======== Auth helpers ========
const SERVER_ENV = config.SERVER_ENV || 'prod';

function signToken(user) {
  return jwt.sign({ uid: user.id, username: user.username, env: SERVER_ENV }, JWT_SECRET, { expiresIn: "7d" });
}

async function authMiddleware(req, res, next) {
  const auth = req.headers.authorization || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : null;
  if (!token) return res.status(401).json({ error: "未登录" });
  try {
    const payload = jwt.verify(token, JWT_SECRET);
    // 校验环境标记：新 token 含 env 字段，必须与当前服务器环境匹配
    if (payload.env && payload.env !== SERVER_ENV) {
      return res.status(401).json({ error: "你已在其他环境登录，请重新登录", code: "ENV_MISMATCH" });
    }
    req.user = payload;
    next();
  } catch (e) {
    return res.status(401).json({ error: "登录已过期，请重新登录" });
  }
}

// ======== API: 数据库测试 ========
app.get("/api/db/test", async (req, res) => {
  // ... (omitted for brevity)
});

// ======== API: System Settings ========
app.get("/api/settings", async (req, res) => {
  try {
    const settings = await getAllSettings();
    // 过滤掉敏感或不适合前端直接看到的配置（如果有的话）
    // 目前全部返回
    res.json({ ok: true, settings });
  } catch (e) {
    res.status(500).json({ error: "Failed to fetch settings" });
  }
});

// ======== API: auth ========
app.post("/api/auth/register", async (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) return res.status(400).json({ error: "缺少用户名或密码" });
  if (String(username).length < 2) return res.status(400).json({ error: "用户名太短" });
  if (String(password).length < 6) return res.status(400).json({ error: "密码至少 6 位" });

  const exists = await dbGet("SELECT id FROM users WHERE username = ?", [username]);
  if (exists) return res.status(409).json({ error: "用户名已存在" });

  const hash = bcrypt.hashSync(password, 10);
  const r = await dbRun("INSERT INTO users(username, password_hash) VALUES(?, ?)", [username, hash]);
  const user = { id: r.lastID, username };
  const token = signToken(user);
  res.json({ user, token });
});

app.post("/api/auth/login", async (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) return res.status(400).json({ error: "缺少用户名或密码" });

  const user = await dbGet("SELECT id, username, password_hash FROM users WHERE username = ?", [username]);
  if (!user) return res.status(401).json({ error: "用户名或密码错误" });

  const ok = bcrypt.compareSync(password, user.password_hash);
  if (!ok) return res.status(401).json({ error: "用户名或密码错误" });

  const token = signToken(user);
  res.json({ user: { id: user.id, username: user.username }, token });
});

// 开发者登录接口 (替代前端 Key 校验)
app.post("/api/auth/dev-login", async (req, res) => {
  const { key } = req.body || {};
  if (!key) return res.status(400).json({ error: "缺少密钥" });

  const dbDevKey = await getSystemSetting("DEV_KEY", "sj0127wqt");
  if (key !== dbDevKey) {
    return res.status(401).json({ error: "开发者密钥错误" });
  }

  // 开发者用户固定逻辑
  const username = 'dev_user';
  let user = await dbGet("SELECT id, username, role FROM users WHERE username = ?", [username]);

  if (!user) {
    // 自动创建，角色为 boss
    const hash = bcrypt.hashSync("dev123456", 10);
    const r = await dbRun("INSERT INTO users(username, password_hash, role) VALUES(?, ?, 'boss')", [username, hash]);
    user = { id: r.lastID, username, role: 'boss' };
  } else if (user.role !== 'boss') {
    // 确保 dev_user 始终是 boss
    await dbRun("UPDATE users SET role='boss' WHERE id=?", [user.id]);
    user.role = 'boss';
  }

  const token = signToken(user);
  res.json({
    user: { id: user.id, username: user.username, role: user.role, isProfileComplete: true },
    token
  });
});

// Admin Panel 专用手机号登录接口（无需短信验证码，仅限 boss/operator 角色）
app.post("/api/auth/admin-login", async (req, res) => {
  const phone = normalizePhone(req.body?.phone || "");
  if (!phone) return res.status(400).json({ error: "缺少手机号" });

  const user = await dbGet(
    "SELECT id, phone, username, guardian_name, role FROM users WHERE phone = ?",
    [phone]
  );

  if (!user) return res.status(404).json({ error: "用户不存在" });

  const allowedRoles = ["boss", "operator"];
  if (!allowedRoles.includes(user.role)) {
    return res.status(403).json({ error: "⛔ 仅 boss 和运营账号可登录管理后台" });
  }

  const token = signToken({ id: user.id, username: user.phone || user.username });
  res.json({
    user: {
      id: user.id,
      username: user.username || user.phone,
      phone: user.phone,
      guardianName: user.guardian_name,
      role: user.role,
      isProfileComplete: true
    },
    token
  });
});

// ======== API: SMS login ========
app.post("/api/auth/sms/send", async (req, res) => {
  const phone = normalizePhone(req.body?.phone || req.body?.mobile);
  if (!phone) return res.status(400).json({ error: "缺少手机号" });
  if (phone.length < 6) return res.status(400).json({ error: "手机号格式不正确" });

  // 开发环境：直接返回模拟验证码
  if (!bmobSMS) {
    const mockCode = generateSmsCode();
    const now = Date.now();
    const expiresAt = now + SMS_CODE_TTL_MS;

    // 检查发送间隔
    const existing = smsStore.get(phone);
    if (existing && (now - existing.lastSent) < SMS_RESEND_INTERVAL_MS) {
      const waitSec = Math.ceil((SMS_RESEND_INTERVAL_MS - (now - existing.lastSent)) / 1000);
      return res.status(429).json({ error: `请等待 ${waitSec} 秒后重试` });
    }

    smsStore.set(phone, {
      code: mockCode,
      expiresAt,
      lastSent: now
    });

    console.log(`📱 模拟短信验证码 [${phone}]: ${mockCode}`);

    return res.json({
      ok: true,
      mockCode, // 开发环境直接返回验证码
      expiresInSeconds: Math.floor(SMS_CODE_TTL_MS / 1000),
      message: "开发环境模拟短信已发送"
    });
  }

  try {
    const result = await bmobSMS.sendSmsCode(phone);
    res.json({ ok: true, smsId: result.smsId });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

app.post("/api/auth/sms/verify", async (req, res) => {
  const phone = normalizePhone(req.body?.phone || req.body?.mobile);
  const code = String(req.body?.code || "").trim();
  if (!phone || !code) return res.status(400).json({ error: "手机号或验证码缺失" });

  // 开发环境：使用本地存储验证
  if (!bmobSMS) {
    const stored = smsStore.get(phone);
    if (!stored) {
      return res.status(400).json({ error: "验证码不存在或已过期" });
    }

    if (Date.now() > stored.expiresAt) {
      smsStore.delete(phone);
      return res.status(400).json({ error: "验证码已过期" });
    }

    if (stored.code !== code) {
      return res.status(400).json({ error: "验证码错误" });
    }

    // 验证成功，删除验证码
    smsStore.delete(phone);

    // 检查用户是否存在
    let user = await dbGet("SELECT id, phone, guardian_name FROM users WHERE phone = ?", [phone]);
    if (!user) {
      // 新用户，创建记录
      const r = await dbRun("INSERT INTO users(phone) VALUES(?)", [phone]);
      user = { id: r.lastID, phone, guardian_name: null };
    }

    const token = signToken({ id: user.id, username: user.phone });
    return res.json({
      user: {
        id: user.id,
        username: user.phone,
        guardianName: user.guardian_name,
        isNewUser: !user.guardian_name
      },
      token
    });
  }

  try {
    await bmobSMS.verifySmsCode(phone, code);

    // Bmob 验证成功，检查用户是否存在
    let user = await dbGet("SELECT id, phone, guardian_name FROM users WHERE phone = ?", [phone]);
    if (!user) {
      // 新用户，创建记录
      const r = await dbRun("INSERT INTO users(phone) VALUES(?)", [phone]);
      user = { id: r.lastID, phone, guardian_name: null };
    }

    const token = signToken({ id: user.id, username: user.phone });
    res.json({
      user: {
        id: user.id,
        username: user.phone,
        guardianName: user.guardian_name,
        isNewUser: !user.guardian_name
      },
      token
    });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// 前端会调用，但我们这里不维护 server-side session，所以直接返回 ok
app.post("/api/auth/logout", async (_req, res) => res.json({ ok: true }));

app.get("/api/me", authMiddleware, async (req, res) => {
  const user = await dbGet(
    "SELECT id, username, phone, guardian_name, role, watcher_level, enterprise_id FROM users WHERE id = ?",
    [req.user.uid]
  );
  if (!user) return res.status(404).json({ error: "用户不存在" });

  res.json({
    user: {
      id: user.id,
      username: user.username || user.phone,
      phone: user.phone,
      guardianName: user.guardian_name,
      isProfileComplete: !!user.guardian_name,
      role: user.role || 'watcher',
      watcherLevel: user.watcher_level || 'initial',
      enterpriseId: user.enterprise_id || null
    }
  });
});

// 我的活动列表
app.get("/api/me/activities", authMiddleware, async (req, res) => {
  const uid = req.user.uid;
  try {
    const rows = await dbAll(`
      SELECT a.id, a.name, a.activity_code, a.started_at, a.ended_at,
             as2.table_no, gs.final_score, gs.started_at as session_started,
             gs.ended_at as session_ended, gs.id as session_id
      FROM activity_sessions as2
      JOIN activities a ON a.id = as2.activity_id
      JOIN game_sessions gs ON gs.id = as2.session_id
      WHERE gs.user_id = ?
      ORDER BY gs.started_at DESC
    `, [uid]);
    res.json({ activities: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 提交感想/反馈
app.post("/api/me/feedback", authMiddleware, async (req, res) => {
  const uid = req.user.uid;
  const { type = 'reflection', content, activity_id, session_id } = req.body || {};
  if (!content || !String(content).trim()) return res.status(400).json({ error: "内容不能为空" });
  try {
    const result = await dbRun(
      "INSERT INTO user_feedback(user_id, type, content, activity_id, session_id) VALUES(?,?,?,?,?)",
      [uid, type, content.trim(), activity_id || null, session_id || null]
    );
    res.json({ ok: true, id: result.lastID });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 提交升级申请
app.post("/api/me/level-application", authMiddleware, async (req, res) => {
  const uid = req.user.uid;
  const { reason } = req.body || {};
  try {
    const user = await dbGet("SELECT watcher_level FROM users WHERE id = ?", [uid]);
    if (!user) return res.status(404).json({ error: "用户不存在" });

    // 检查是否已有 pending 申请
    const existing = await dbGet(
      "SELECT id FROM watcher_level_applications WHERE user_id = ? AND status = 'pending'", [uid]
    );
    if (existing) return res.status(400).json({ error: "已有待审核的申请，请等待" });

    const levelMap = { initial: 'advanced', advanced: 'mentor' };
    const toLevel = levelMap[user.watcher_level];
    if (!toLevel) return res.status(400).json({ error: "已是最高等级，无需申请" });

    const result = await dbRun(
      "INSERT INTO watcher_level_applications(user_id, from_level, to_level, reason) VALUES(?,?,?,?)",
      [uid, user.watcher_level, toLevel, reason || null]
    );
    res.json({ ok: true, id: result.lastID, fromLevel: user.watcher_level, toLevel });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 查询升级申请状态
app.get("/api/me/level-application", authMiddleware, async (req, res) => {
  const uid = req.user.uid;
  try {
    const row = await dbGet(
      "SELECT * FROM watcher_level_applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
      [uid]
    );
    res.json({ application: row || null });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ======== API: 企业账号子账号管理 ========
app.get("/api/enterprise/members", authMiddleware, async (req, res) => {
  const uid = req.user.uid;
  try {
    const me = await dbGet("SELECT role FROM users WHERE id = ?", [uid]);
    if (!me || me.role !== 'enterprise') return res.status(403).json({ error: "无权限" });
    const members = await dbAll(
      "SELECT id, username, phone, guardian_name, watcher_level, created_at FROM users WHERE enterprise_id = ?",
      [uid]
    );
    res.json({ members });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/api/enterprise/members/:id/stats", authMiddleware, async (req, res) => {
  const uid = req.user.uid;
  const memberId = req.params.id;
  try {
    const me = await dbGet("SELECT role FROM users WHERE id = ?", [uid]);
    if (!me || me.role !== 'enterprise') return res.status(403).json({ error: "无权限" });
    const member = await dbGet("SELECT enterprise_id FROM users WHERE id = ?", [memberId]);
    if (!member || String(member.enterprise_id) !== String(uid)) return res.status(403).json({ error: "非旗下子账号" });

    const sessions = await dbAll(
      "SELECT id, started_at, ended_at, final_score, game_mode FROM game_sessions WHERE user_id = ? ORDER BY started_at DESC",
      [memberId]
    );
    const totalGames = sessions.length;
    const avgScore = totalGames ? Math.round(sessions.reduce((s, r) => s + (r.final_score || 0), 0) / totalGames) : 0;
    res.json({ stats: { totalGames, avgScore, sessions } });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 完善用户资料
app.post("/api/auth/complete-profile", authMiddleware, async (req, res) => {
  const { guardianName, wechatOpenid } = req.body || {};
  if (!guardianName || String(guardianName).trim().length < 1) {
    return res.status(400).json({ error: "请输入守望师名字" });
  }

  const userId = req.user.uid;
  const updateFields = ["guardian_name = ?"];
  const updateValues = [String(guardianName).trim()];

  // 如果提供了微信openid，也一起更新
  if (wechatOpenid && String(wechatOpenid).trim()) {
    updateFields.push("wechat_openid = ?");
    updateValues.push(String(wechatOpenid).trim());
  }

  updateValues.push(userId);

  await dbRun(
    `UPDATE users SET ${updateFields.join(", ")} WHERE id = ?`,
    updateValues
  );

  const user = await dbGet("SELECT id, username, phone, guardian_name, wechat_openid FROM users WHERE id = ?", [userId]);
  res.json({
    user: {
      id: user.id,
      username: user.username || user.phone,
      phone: user.phone,
      guardianName: user.guardian_name,
      wechatOpenid: user.wechat_openid,
      isProfileComplete: true
    }
  });
});

// ======== API: game ========
app.post("/api/game/start", authMiddleware, async (req, res) => {
  const userId = req.user.uid;
  const ts = Number(req.body?.ts || Date.now());
  const { location, players, mode, settings } = req.body || {};

  const playersJson = players ? JSON.stringify(players) : null;
  const settingsJson = settings ? JSON.stringify(settings) : null;

  const r = await dbRun(
    "INSERT INTO game_sessions(user_id, started_at, location, players_json, game_mode, game_settings_json) VALUES(?, ?, ?, ?, ?, ?)",
    [userId, ts, location, playersJson, mode, settingsJson]
  );
  res.json({ ok: true, sessionId: r.lastID });
});

app.post("/api/game/finish", authMiddleware, async (req, res) => {
  const userId = req.user.uid;
  const { sessionId, endedAt, finalScore, payload } = req.body || {};
  if (!sessionId) return res.status(400).json({ error: "缺少 sessionId" });

  await dbRun(
    "UPDATE game_sessions SET ended_at=?, final_score=?, payload_json=? WHERE id=? AND user_id=?",
    [Number(endedAt || Date.now()), Number(finalScore || 0), JSON.stringify(payload || {}), sessionId, userId]
  );

  res.json({ ok: true });
});

app.post("/api/game/event", authMiddleware, async (req, res) => {
  const userId = req.user.uid;
  const { sessionId, type, payload } = req.body || {};
  if (!sessionId || !type) return res.status(400).json({ error: "ç¼ºå°‘ sessionId æˆ– type" });

  const session = await dbGet("SELECT id FROM game_sessions WHERE id = ? AND user_id = ?", [sessionId, userId]);
  if (!session) return res.status(404).json({ error: "æ¸¸æˆä¸å­˜åœ¨" });

  await addGameEvent(sessionId, String(type), payload || {});
  res.json({ ok: true });
});

app.get("/api/game/last-session", authMiddleware, async (req, res) => {
  const userId = req.user.uid;
  const session = await dbGet(
    "SELECT * FROM game_sessions WHERE user_id = ? ORDER BY started_at DESC LIMIT 1",
    [userId]
  );
  res.json({ session: session || null });
});

app.get("/api/game/session/:id", authMiddleware, async (req, res) => {
  const userId = req.user.uid;
  const sessionId = Number(req.params.id);
  if (!sessionId) return res.status(400).json({ error: "sessionId ä¸æ­£ç¡®" });

  const session = await dbGet("SELECT * FROM game_sessions WHERE id = ? AND user_id = ?", [sessionId, userId]);
  if (!session) return res.status(404).json({ error: "æ¸¸æˆä¸å­˜åœ¨" });

  const events = await getGameEvents(sessionId);
  res.json({ session, events });
});

// ======== API: Cards Management ========

// 1. Get all cards (Public Game API - Active only)
app.get("/api/cards", async (req, res) => {
  try {
    const cards = await cardsDbAll("SELECT * FROM cards WHERE status = 'active' ORDER BY id ASC");
    const formattedCards = cards.map(c => ({
      id: c.id,
      key: c.key,
      safetyType: c.safety_type,
      event: c.event,
      phase: c.phase,
      status: c.status,
      version: c.version,
      options: JSON.parse(c.options_json)
    }));
    res.json({ cards: formattedCards });
  } catch (e) {
    res.status(500).json({ error: "Failed to fetch cards: " + e.message });
  }
});

// 2. Get all cards (Admin API - Filterable)
app.get("/api/admin/cards", authMiddleware, async (req, res) => {
  try {
    const { status } = req.query;
    let sql = "SELECT * FROM cards";
    const params = [];

    if (status) {
      sql += " WHERE status = ?";
      params.push(status);
    } else {
      // Default to showing all except deleted? Or just all? 
      // Let's show all for admin if no status specified, or maybe excluding deleted by default unless requested.
      // For now, simple logic: all.
    }

    sql += " ORDER BY id DESC"; // Newest first for admin

    const cards = await cardsDbAll(sql, params);
    const formattedCards = cards.map(c => ({
      id: c.id,
      key: c.key,
      safetyType: c.safety_type,
      event: c.event,
      phase: c.phase,
      status: c.status,
      version: c.version,
      branch: c.branch || 'release',
      version_label: c.version_label || null,
      audio_url: c.audio_url || null,
      updatedAt: c.updated_at,
      options: JSON.parse(c.options_json)
    }));
    res.json({ cards: formattedCards });
  } catch (e) {
    res.status(500).json({ error: "Failed to fetch admin cards: " + e.message });
  }
});

// 2. Generate card using LLM
import fs from "fs"; // Ensure fs is imported if not already, though usually better at top.
// Since we are inside a module, we can use fs.promises or just fs.
// Let's use fs.promises for async reading.
import { promises as fsPromises } from "fs";

app.post("/api/admin/generate-card", authMiddleware, async (req, res) => {
  const { topic, content } = req.body;
  if (!topic && !content) return res.status(400).json({ error: "Missing topic or content" });

  // Read the prompt template
  const promptPath = path.join(__dirname, "cards-generation-prompt.md");
  let systemPrompt;
  try {
    systemPrompt = await fsPromises.readFile(promptPath, "utf-8");
  } catch (e) {
    console.error("Failed to read prompt file:", e);
    return res.status(500).json({ error: "Failed to read prompt template" });
  }

  // Construct the full user message
  const userMessage = `请根据以下信息生成卡牌 JSON：\n${topic ? `Topic: ${topic}\n` : ""}${content ? `Content: ${content}` : ""}`;

  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) return res.status(500).json({ error: "Server missing DEEPSEEK_API_KEY" });

  const model = process.env.DEEPSEEK_MODEL || "deepseek-chat";

  try {
    const response = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userMessage }
        ],
        temperature: 1.0, // Creativity
        response_format: { type: "json_object" } // Force JSON if supported, or just trust prompt
      })
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`DeepSeek API error: ${response.status} ${errText}`);
    }

    const data = await response.json();
    const generatedContent = data.choices[0].message.content;

    let cardJson;
    try {
      cardJson = JSON.parse(generatedContent);
    } catch (e) {
      // Try to extract JSON from code block if present
      const match = generatedContent.match(/```json\n([\s\S]*?)\n```/);
      if (match) {
        cardJson = JSON.parse(match[1]);
      } else {
        throw new Error("Failed to parse JSON from LLM response");
      }
    }

    res.json({ card: cardJson, raw: generatedContent });

  } catch (e) {
    console.error("Card Generation Error:", e);
    res.status(500).json({ error: e.message });
  }
});

// 3. Save a new card
app.post("/api/cards", authMiddleware, async (req, res) => {
  const card = req.body;

  // Basic validation
  if (!card.safetyType || !card.event || !card.phase || !card.options) {
    return res.status(400).json({ error: "Invalid card data structure" });
  }

  try {
    // Find next key if not provided or if provided key already exists
    let key = card.key;
    let exists = false;

    if (key) {
      const row = await cardsDbGet("SELECT 1 FROM cards WHERE key = ?", [key]);
      if (row) exists = true;
    }

    if (!key || exists) {
      // Auto-generate a key (max + 1)
      const maxKeyRow = await cardsDbGet("SELECT MAX(key) as k FROM cards");
      const maxKey = maxKeyRow?.k || 0;
      key = maxKey + 1;
    }

    const optionsJson = JSON.stringify(card.options);

    // New cards start as 'pending'
    const status = 'pending';
    const version = 1;
    const createdAt = Date.now();

    const result = await cardsDbRun(
      `INSERT INTO cards (key, safety_type, event, phase, options_json, status, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [key, card.safetyType, card.event, card.phase, optionsJson, status, version, createdAt, createdAt]
    );

    res.json({ ok: true, id: result.lastID, key, status });
  } catch (e) {
    console.error("Save Card Error:", e);
    res.status(500).json({ error: "Failed to save card: " + e.message });
  }
});

// 4. Update Card (Edit / Approve / Reject / Restore)
app.put("/api/cards/:id", authMiddleware, async (req, res) => {
  const { id } = req.params;
  const updates = req.body; // Expects partial object or full object

  try {
    const existing = await cardsDbGet("SELECT * FROM cards WHERE id = ?", [id]);
    if (!existing) return res.status(404).json({ error: "Card not found" });

    // Prepare updates
    const safetyType = updates.safetyType || existing.safety_type;
    const event = updates.event || existing.event;
    const phase = updates.phase || existing.phase;
    const status = updates.status || existing.status;
    const optionsJson = updates.options ? JSON.stringify(updates.options) : existing.options_json;
    const audioUrl = updates.audio_url !== undefined ? (updates.audio_url || null) : existing.audio_url;

    // 当普通修改时，打上测试版标签和包含当前日期的标签
    const branch = 'draft';
    const nowStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const submitterName = req.user.username || String(req.user.uid);
    const versionDescSuffix = updates.versionDesc ? ` · ${updates.versionDesc}` : '';
    const versionLabel = `v${existing.version || 1}.${nowStr}版 — ${submitterName}${versionDescSuffix}`;
    const newVersion = existing.version || 1; // 测试版保存不自增 version 绝对值
    const updatedAt = Date.now();

    // 保存旧版本到 card_versions 表
    await cardsDbRun(
      `INSERT INTO card_versions (card_id, key, safety_type, event, phase, options_json, status, version, version_label, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        existing.id,
        existing.key,
        existing.safety_type,
        existing.event,
        existing.phase,
        existing.options_json,
        existing.status,
        existing.version || 1,
        existing.version_label || null,
        existing.updated_at || existing.created_at || Date.now()
      ]
    );

    // Version increment (在普通保存里剥离自增逻辑，挪到了正式发版才会发生)
    let deletedAt = existing.deleted_at;
    if (status === 'deleted' && existing.status !== 'deleted') {
      deletedAt = Date.now();
    } else if (status !== 'deleted') {
      deletedAt = null;
    }

    await cardsDbRun(
      `UPDATE cards SET safety_type=?, event=?, phase=?, options_json=?, status=?, version=?, version_label=?, branch=?, audio_url=?, updated_at=?, deleted_at=? WHERE id=?`,
      [safetyType, event, phase, optionsJson, status, newVersion, versionLabel, branch, audioUrl, updatedAt, deletedAt, id]
    );

    res.json({ ok: true, id, version: newVersion, versionLabel, branch, status });

  } catch (e) {
    console.error("Update Card Error:", e);
    res.status(500).json({ error: "Failed to update card: " + e.message });
  }
});

// 4.5 Bulk Publish API (Admin 批量发版)
app.post("/api/admin/cards/bulk-publish", authMiddleware, async (req, res) => {
  const { cardIds, secretKey } = req.body;
  if (!cardIds || !Array.isArray(cardIds) || cardIds.length === 0) {
    return res.status(400).json({ error: "No cardIds provided" });
  }

  // Verify secret key using DEV_KEY from DB or ENV
  const { getSystemSetting } = require("./db"); // Make sure to use existing getSystemSetting
  let devKey = process.env.DEV_KEY || "sj0127wqt";
  try {
    const sysDbRow = await dbGet("SELECT setting_value FROM system_settings WHERE setting_key = 'DEV_KEY'");
    if (sysDbRow && sysDbRow.setting_value) devKey = sysDbRow.setting_value;
  } catch (e) { } // ignore if settings table not ready

  if (secretKey !== devKey) {
    return res.status(403).json({ error: "密钥不正确，拒绝发布！" });
  }

  try {
    const results = [];
    const nowStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    for (const id of cardIds) {
      const existing = await cardsDbGet("SELECT * FROM cards WHERE id = ?", [id]);
      if (!existing) continue;

      // 保存旧版本到 card_versions 表
      await cardsDbRun(
        `INSERT INTO card_versions (card_id, key, safety_type, event, phase, options_json, status, version, version_label, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          existing.id,
          existing.key,
          existing.safety_type,
          existing.event,
          existing.phase,
          existing.options_json,
          existing.status,
          existing.version || 1,
          existing.version_label || null,
          existing.updated_at || existing.created_at || Date.now()
        ]
      );

      // 发版: branch改release, version增加, 名字去日期
      const newVersion = (existing.version || 0) + 1;
      const versionLabel = `v${newVersion}版`;
      const updatedAt = Date.now();

      await cardsDbRun(
        `UPDATE cards SET status=?, version=?, version_label=?, branch=?, updated_at=? WHERE id=?`,
        ['active', newVersion, versionLabel, 'release', updatedAt, id]
      );

      results.push({ id, newVersion, versionLabel });
    }

    res.json({ ok: true, results });
  } catch (e) {
    console.error("Bulk Publish Error:", e);
    res.status(500).json({ error: "Failed to bulk publish cards: " + e.message });
  }
});

// 5. Soft Delete Card (Shortcut)
app.delete("/api/cards/:id", authMiddleware, async (req, res) => {
  const { id } = req.params;
  try {
    const existing = await cardsDbGet("SELECT * FROM cards WHERE id = ?", [id]);
    if (!existing) return res.status(404).json({ error: "Card not found" });

    const newVersion = (existing.version || 0) + 1;
    const now = Date.now();

    await cardsDbRun(
      `UPDATE cards SET status='deleted', version=?, updated_at=?, deleted_at=? WHERE id=?`,
      [newVersion, now, now, id]
    );

    res.json({ ok: true, id, status: 'deleted' });
  } catch (e) {
    res.status(500).json({ error: "Failed to delete card: " + e.message });
  }
});

// ======== API: LLM proxy（可选） ========
// 你原 index.html 里把 Key 写死在前端了（非常危险），这里提供一个安全的后端代理。
app.post("/api/llm/story", authMiddleware, async (req, res) => {
  const prompt = req.body?.prompt;
  if (!prompt) return res.status(400).json({ error: "缺少 prompt" });

  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) return res.status(400).json({ error: "后端未配置 DEEPSEEK_API_KEY" });

  const model = process.env.DEEPSEEK_MODEL || "deepseek-chat";
  const rawMaxTokens = Number(req.body?.max_tokens);
  const maxTokens = Number.isFinite(rawMaxTokens) ? Math.min(Math.max(rawMaxTokens, 200), 2400) : 1200;
  const rawTemperature = Number(req.body?.temperature);
  const temperature = Number.isFinite(rawTemperature) ? Math.min(Math.max(rawTemperature, 0), 1.2) : 0.7;

  try {
    const r = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: maxTokens,
        temperature
      })
    });

    if (!r.ok) {
      const t = await r.text().catch(() => "");
      return res.status(502).json({ error: `LLM 调用失败(${r.status}) ${t?.slice(0, 200)}` });
    }

    const data = await r.json();
    const story = data?.choices?.[0]?.message?.content || "";
    res.json({ story });
  } catch (e) {
    res.status(502).json({ error: "LLM 网络请求失败" });
  }
});

// ======== API: Upload to OSS ========
app.post("/api/upload/audio", authMiddleware, upload.single("file"), async (req, res) => {
  if (!ossClient) return res.status(500).json({ error: "服务器未配置 OSS" });
  if (!req.file) return res.status(400).json({ error: "未上传文件" });

  try {
    const filename = `game-audio/user_${req.user.uid}_${Date.now()}.webm`;
    const result = await ossClient.put(filename, req.file.buffer);

    // 生成访问链接
    let url = result.url;
    if (process.env.ALIYUN_OSS_CUSTOM_DOMAIN) {
      const domain = process.env.ALIYUN_OSS_CUSTOM_DOMAIN.replace(/\/$/, "");
      url = `${domain}/${result.name}`;
    }

    res.json({ ok: true, url });
  } catch (e) {
    console.error("OSS Upload Error:", e);
    res.status(500).json({ error: "上传失败: " + e.message });
  }
});

app.post("/api/upload/report", authMiddleware, async (req, res) => {
  if (!ossClient) return res.status(500).json({ error: "服务器未配置 OSS" });

  const { html, markdown } = req.body || {};
  if (!html && !markdown) return res.status(400).json({ error: "缺少报告内容" });

  try {
    const timestamp = Date.now();
    const resultUrls = {};
    const customDomain = process.env.ALIYUN_OSS_CUSTOM_DOMAIN
      ? process.env.ALIYUN_OSS_CUSTOM_DOMAIN.replace(/\/$/, "")
      : null;

    if (html) {
      const filename = `game-review/report_${req.user.uid}_${timestamp}.html`;
      const r = await ossClient.put(filename, Buffer.from(html));
      resultUrls.htmlUrl = customDomain ? `${customDomain}/${r.name}` : r.url;
    }

    if (markdown) {
      const filename = `game-review/report_${req.user.uid}_${timestamp}.md`;
      const r = await ossClient.put(filename, Buffer.from(markdown));
      resultUrls.markdownUrl = customDomain ? `${customDomain}/${r.name}` : r.url;
    }

    res.json({ ok: true, ...resultUrls });
  } catch (e) {
    console.error("OSS Upload Error:", e);
    res.status(500).json({ error: "上传失败: " + e.message });
  }
});



// ======== API: OSS Management (Admin) ========
app.get("/api/admin/oss/files", authMiddleware, async (req, res) => {
  if (!ossClient) return res.status(500).json({ error: "服务器未配置 OSS" });

  try {
    const { prefix, marker, maxKeys, delimiter } = req.query;
    const query = {
      prefix: prefix || null,
      marker: marker || null,
      'max-keys': maxKeys ? Number(maxKeys) : 20,
      delimiter: delimiter || "/" // Default to directory mode
    };

    // ossClient.list returns { objects: [], prefixes: [], nextMarker: string, res: ... }
    const result = await ossClient.list(query);

    const customDomain = process.env.ALIYUN_OSS_CUSTOM_DOMAIN
      ? process.env.ALIYUN_OSS_CUSTOM_DOMAIN.replace(/\/$/, "")
      : null;

    const files = (result.objects || []).map(obj => ({
      name: obj.name,
      url: customDomain ? `${customDomain}/${obj.name}` : obj.url,
      size: obj.size,
      lastModified: obj.lastModified
    }));

    // Prefixes are subdirectories
    const folders = result.prefixes || [];

    res.json({
      ok: true,
      files,
      folders,
      nextMarker: result.nextMarker,
      isTruncated: result.isTruncated
    });
  } catch (e) {
    console.error("OSS List Error:", e);
    res.status(500).json({ error: "获取文件列表失败: " + e.message });
  }
});

app.delete("/api/admin/oss/files", authMiddleware, async (req, res) => {
  if (!ossClient) return res.status(500).json({ error: "服务器未配置 OSS" });

  const { filename } = req.body; // Expect JSON body: { "filename": "path/to/file" }
  if (!filename) return res.status(400).json({ error: "未指定文件名" });

  try {
    // ossClient.delete returns result object
    const result = await ossClient.delete(filename);
    console.log(`🗑️ Deleted OSS file: ${filename}`, result.res.status);

    res.json({ ok: true, filename });
  } catch (e) {
    console.error("OSS Delete Error:", e);
    res.status(500).json({ error: "删除文件失败: " + e.message });
  }
});

// ======== API: 活动管理 ========

// 生成活动码 ACT-001 格式
async function generateActivityCode() {
  const row = await dbGet("SELECT MAX(id) as maxId FROM activities");
  const nextNum = (row?.maxId || 0) + 1;
  return `ACT-${String(nextNum).padStart(3, '0')}`;
}

app.get("/api/admin/activities", authMiddleware, async (req, res) => {
  try {
    const rows = await dbAll(`
      SELECT a.*,
        COUNT(DISTINCT as2.session_id) as table_count,
        COUNT(DISTINCT gs.user_id) as participant_count,
        ROUND(AVG(gs.final_score), 1) as avg_score
      FROM activities a
      LEFT JOIN activity_sessions as2 ON as2.activity_id = a.id
      LEFT JOIN game_sessions gs ON gs.id = as2.session_id
      GROUP BY a.id
      ORDER BY a.created_at DESC
    `);
    res.json({ activities: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/api/admin/activities", authMiddleware, async (req, res) => {
  const { name, organizer, started_at, ended_at } = req.body || {};
  if (!name) return res.status(400).json({ error: "活动名称不能为空" });
  try {
    const code = await generateActivityCode();
    const result = await dbRun(
      "INSERT INTO activities(name, organizer, activity_code, started_at, ended_at, created_by) VALUES(?,?,?,?,?,?)",
      [name, organizer || null, code, started_at || null, ended_at || null, req.user.uid]
    );
    res.json({ ok: true, id: result.lastID, activity_code: code });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.put("/api/admin/activities/:id", authMiddleware, async (req, res) => {
  const { id } = req.params;
  const { name, organizer, started_at, ended_at, status } = req.body || {};
  try {
    const existing = await dbGet("SELECT * FROM activities WHERE id = ?", [id]);
    if (!existing) return res.status(404).json({ error: "活动不存在" });
    await dbRun(
      "UPDATE activities SET name=?, organizer=?, started_at=?, ended_at=?, status=? WHERE id=?",
      [name || existing.name, organizer ?? existing.organizer, started_at ?? existing.started_at,
      ended_at ?? existing.ended_at, status || existing.status, id]
    );
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/api/admin/activities/:id/sessions", authMiddleware, async (req, res) => {
  try {
    const rows = await dbAll(`
      SELECT gs.id, gs.started_at, gs.ended_at, gs.final_score, gs.game_mode,
             u.guardian_name, u.phone, as2.table_no
      FROM activity_sessions as2
      JOIN game_sessions gs ON gs.id = as2.session_id
      JOIN users u ON u.id = gs.user_id
      WHERE as2.activity_id = ?
      ORDER BY as2.table_no ASC
    `, [req.params.id]);
    res.json({ sessions: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 游戏开始时关联活动（通过活动码）
app.post("/api/game/join-activity", authMiddleware, async (req, res) => {
  const { activity_code, session_id } = req.body || {};
  if (!activity_code || !session_id) return res.status(400).json({ error: "缺少参数" });
  try {
    const activity = await dbGet("SELECT * FROM activities WHERE activity_code = ? AND status = 'active'", [activity_code]);
    if (!activity) return res.status(404).json({ error: "活动码无效或活动已结束" });

    // 获取该活动当前最大桌号
    const maxTable = await dbGet("SELECT MAX(table_no) as max FROM activity_sessions WHERE activity_id = ?", [activity.id]);
    const table_no = (maxTable?.max || 0) + 1;

    await dbRun(
      "INSERT OR IGNORE INTO activity_sessions(activity_id, session_id, table_no) VALUES(?,?,?)",
      [activity.id, session_id, table_no]
    );
    res.json({ ok: true, activity_id: activity.id, activity_name: activity.name, table_no });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ======== API: Admin 等级申请管理 ========
app.get("/api/admin/level-applications", authMiddleware, async (req, res) => {
  const { status = 'pending' } = req.query;
  try {
    const rows = await dbAll(`
      SELECT la.*, u.guardian_name, u.phone, u.username
      FROM watcher_level_applications la
      JOIN users u ON u.id = la.user_id
      WHERE la.status = ?
      ORDER BY la.created_at DESC
    `, [status]);
    res.json({ applications: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.put("/api/admin/level-applications/:id", authMiddleware, async (req, res) => {
  const { id } = req.params;
  const { action, note } = req.body || {}; // action: 'approve' | 'reject'
  if (!['approve', 'reject'].includes(action)) return res.status(400).json({ error: "action 必须为 approve 或 reject" });
  try {
    const app_row = await dbGet("SELECT * FROM watcher_level_applications WHERE id = ?", [id]);
    if (!app_row) return res.status(404).json({ error: "申请不存在" });
    if (app_row.status !== 'pending') return res.status(400).json({ error: "申请已处理" });

    const newStatus = action === 'approve' ? 'approved' : 'rejected';
    const now = Date.now();
    await dbRun(
      "UPDATE watcher_level_applications SET status=?, reviewed_by=?, reviewed_at=?, note=? WHERE id=?",
      [newStatus, req.user.uid, now, note || null, id]
    );

    if (action === 'approve') {
      // 更新用户等级
      const oldLevel = app_row.from_level;
      const newLevel = app_row.to_level;
      await dbRun("UPDATE users SET watcher_level=? WHERE id=?", [newLevel, app_row.user_id]);
      await dbRun(
        "INSERT INTO watcher_level_logs(user_id, old_level, new_level, source, changed_by, note) VALUES(?,?,?,?,?,?)",
        [app_row.user_id, oldLevel, newLevel, 'application', req.user.uid, note || null]
      );
    }
    res.json({ ok: true, newStatus });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Admin 手动调整用户等级（boss 专用）
app.put("/api/admin/users/:id/level", authMiddleware, async (req, res) => {
  const { id } = req.params;
  const { level, note } = req.body || {};
  const validLevels = ['initial', 'advanced', 'mentor'];
  if (!validLevels.includes(level)) return res.status(400).json({ error: "等级值无效" });
  try {
    const user = await dbGet("SELECT watcher_level FROM users WHERE id = ?", [id]);
    if (!user) return res.status(404).json({ error: "用户不存在" });
    await dbRun("UPDATE users SET watcher_level=? WHERE id=?", [level, id]);
    await dbRun(
      "INSERT INTO watcher_level_logs(user_id, old_level, new_level, source, changed_by, note) VALUES(?,?,?,?,?,?)",
      [id, user.watcher_level, level, 'manual', req.user.uid, note || null]
    );
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Admin 获取用户感想/反馈列表
app.get("/api/admin/feedback", authMiddleware, async (req, res) => {
  const { reviewed } = req.query;
  try {
    let sql = `
      SELECT f.*, u.guardian_name, u.phone
      FROM user_feedback f
      JOIN users u ON u.id = f.user_id
    `;
    const params = [];
    if (reviewed !== undefined) { sql += " WHERE f.reviewed = ?"; params.push(Number(reviewed)); }
    sql += " ORDER BY f.created_at DESC";
    const rows = await dbAll(sql, params);
    res.json({ feedback: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.put("/api/admin/feedback/:id/read", authMiddleware, async (req, res) => {
  try {
    await dbRun("UPDATE user_feedback SET reviewed=1 WHERE id=?", [req.params.id]);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ======== API: 卡牌版本和批注 ========
app.get("/api/admin/cards/:id/versions", authMiddleware, async (req, res) => {
  try {
    const id = req.params.id;
    const current = await cardsDbGet("SELECT * FROM cards WHERE id = ?", [id]);
    if (!current) return res.json({ versions: [] });

    const history = await cardsDbAll("SELECT * FROM card_versions WHERE card_id = ? ORDER BY version DESC", [id]);

    // 合并当前与历史版本，并在返回结构中增加 options 解析，方便前端覆盖式还原
    const versions = [current, ...history].map(c => {
      const isHistory = c.card_id !== undefined;
      return {
        id: isHistory ? `history_${c.id}` : c.id,
        version: c.version,
        version_label: c.version_label,
        branch: c.branch || 'release',
        status: c.status,
        updated_at: c.updated_at || c.created_at,
        event: c.event,
        safety_type: c.safety_type,
        safetyType: c.safety_type, // 前端使用驼峰结构映射
        phase: c.phase,
        options: JSON.parse(c.options_json) // 前端还原时需要这个完整数据
      };
    });

    // 降序排列
    versions.sort((a, b) => b.version - a.version);

    res.json({ versions });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/api/admin/cards/:id/notes", authMiddleware, async (req, res) => {
  try {
    const card = await cardsDbGet("SELECT notes FROM cards WHERE id = ?", [req.params.id]);
    if (!card) return res.status(404).json({ error: "卡牌不存在" });
    const notes = card.notes ? JSON.parse(card.notes) : [];
    res.json({ notes });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/api/admin/cards/:id/notes", authMiddleware, async (req, res) => {
  const { content, selected_text } = req.body || {};
  if (!content) return res.status(400).json({ error: "批注内容不能为空" });
  try {
    const card = await cardsDbGet("SELECT notes FROM cards WHERE id = ?", [req.params.id]);
    if (!card) return res.status(404).json({ error: "卡牌不存在" });
    const notes = card.notes ? JSON.parse(card.notes) : [];
    const ts = Date.now();
    notes.push({ id: ts, author: req.user.uid, author_name: req.user.username || null, content, selected_text: selected_text || null, completed: false, created_at: ts });
    await cardsDbRun("UPDATE cards SET notes=? WHERE id=?", [JSON.stringify(notes), req.params.id]);
    res.json({ ok: true, notes });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 编辑批注（修改内容 or 标记完成）
app.put("/api/admin/cards/:id/notes/:noteId", authMiddleware, async (req, res) => {
  const { content, completed } = req.body || {};
  try {
    const card = await cardsDbGet("SELECT notes FROM cards WHERE id = ?", [req.params.id]);
    if (!card) return res.status(404).json({ error: "卡牌不存在" });
    const notes = card.notes ? JSON.parse(card.notes) : [];
    const nid = parseInt(req.params.noteId);
    const idx = notes.findIndex(n => n.id === nid || n.created_at === nid);
    if (idx === -1) return res.status(404).json({ error: "批注不存在" });
    if (content !== undefined) notes[idx].content = content;
    if (completed !== undefined) notes[idx].completed = completed;
    await cardsDbRun("UPDATE cards SET notes=? WHERE id=?", [JSON.stringify(notes), req.params.id]);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 删除批注
app.delete("/api/admin/cards/:id/notes/:noteId", authMiddleware, async (req, res) => {
  try {
    const card = await cardsDbGet("SELECT notes FROM cards WHERE id = ?", [req.params.id]);
    if (!card) return res.status(404).json({ error: "卡牌不存在" });
    const notes = card.notes ? JSON.parse(card.notes) : [];
    const nid = parseInt(req.params.noteId);
    const filtered = notes.filter(n => n.id !== nid && n.created_at !== nid);
    if (filtered.length === notes.length) return res.status(404).json({ error: "批注不存在" });
    await cardsDbRun("UPDATE cards SET notes=? WHERE id=?", [JSON.stringify(filtered), req.params.id]);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 创建测试分支（复制 release → draft）
app.post("/api/admin/cards/:id/branch", authMiddleware, async (req, res) => {
  const { version_label } = req.body || {};
  try {
    const src = await cardsDbGet("SELECT * FROM cards WHERE id = ?", [req.params.id]);
    if (!src) return res.status(404).json({ error: "卡牌不存在" });
    const label = version_label || `v${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-测试版`;
    const now = Date.now();
    const result = await cardsDbRun(
      `INSERT INTO cards(key, safety_type, event, phase, options_json, status, version, branch, parent_id, version_label, created_at, updated_at)
       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)`,
      [src.key, src.safety_type, src.event, src.phase, src.options_json,
        'pending', (src.version || 1), 'draft', src.id, label, now, now]
    );
    res.json({ ok: true, id: result.lastID, version_label: label });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// 发布：draft → release（覆盖原版本内容）
app.post("/api/admin/cards/:id/publish", authMiddleware, async (req, res) => {
  const { version_label } = req.body || {};
  try {
    const draft = await cardsDbGet("SELECT * FROM cards WHERE id = ? AND branch = 'draft'", [req.params.id]);
    if (!draft) return res.status(404).json({ error: "找不到测试版卡牌" });
    const now = Date.now();
    const label = version_label || `${new Date().getFullYear()}版`;
    await cardsDbRun(
      `UPDATE cards SET safety_type=?, event=?, phase=?, options_json=?, branch='release',
       status='active', version=version+1, version_label=?, updated_at=? WHERE id=?`,
      [draft.safety_type, draft.event, draft.phase, draft.options_json, label, now, draft.parent_id || draft.id]
    );
    // 将草稿标记为已合并（deleted）
    await cardsDbRun("UPDATE cards SET status='deleted', deleted_at=? WHERE id=?", [now, draft.id]);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ======== API: WeChat login placeholders ========
// 这里给你“接口形状”，便于前端先跑通 UI。
// 真正可用的微信登录，需要你根据选定场景实现：
// - 网站应用扫码登录（PC 浏览器）
// - 公众号网页授权（微信内打开）
// - 小程序登录（建议做成小程序/企业微信）
app.get("/api/auth/wechat/qr", async (_req, res) => {
  // 未配置就返回错误，让前端显示“暂不可用”
  if (!process.env.WECHAT_APPID) return res.status(400).json({ error: "未配置微信参数（WECHAT_APPID 等）" });

  // TODO：这里应该生成登录会话、拼出二维码 URL
  // 为了演示：返回一个占位二维码（不会登录成功）
  const sessionId = `demo_${Date.now()}`;
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent("WECHAT_LOGIN_DEMO")}`;
  res.json({ sessionId, qrUrl });
});

app.get("/api/auth/wechat/poll", async (_req, res) => {
  // TODO：真实实现应检查 sessionId 对应的扫码状态，并在成功时创建/绑定用户，签发 token
  res.json({ ok: false });
});

// ======== Start ========
const HOST = process.env.HOST || '0.0.0.0';
app.listen(PORT, HOST, () => {
  console.log(`✅ Server running on http://${HOST}:${PORT}`);
  console.log(`🌐 Public access via your server IP: http://127.0.0.1:${PORT}`);
});
