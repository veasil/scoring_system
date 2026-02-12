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

const app = express();
const PORT = Number(process.env.PORT || 8080);
const JWT_SECRET = process.env.JWT_SECRET || "dev_secret_change_me";

// OSS & Upload
import OSS from "ali-oss";
import multer from "multer";

const ossConfig = {
  accessKeyId: process.env.ALIBABA_CLOUD_ACCESS_KEY_ID,
  accessKeySecret: process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
  bucket: process.env.OSS_BUCKET_NAME || "ai5000days-scoring-system-hk",
  secure: true // 强制使用 HTTPS
};

// 优先使用标准 Endpoint 进行 API 操作（避免自定义域名 SSL 证书报错）
if (process.env.OSS_ENDPOINT) {
  ossConfig.endpoint = process.env.OSS_ENDPOINT;
} else {
  ossConfig.region = (process.env.OSS_REGION || "oss-cn-hongkong").startsWith("oss-")
    ? process.env.OSS_REGION
    : `oss-${process.env.OSS_REGION}`;
}
// 注意：不为了 API 操作开启 cname 模式，防止 SSL 校验失败。
// 自定义域名仅用于生成对外访问链接。

const ossClient = process.env.ALIBABA_CLOUD_ACCESS_KEY_ID && process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET
  ? new OSS(ossConfig)
  : null;

if (ossClient) {
  console.log("✅ OSS Client initialized.");
  console.log("   Bucket:", ossConfig.bucket);
  console.log("   Region/Endpoint:", ossConfig.region || ossConfig.endpoint);
} else {
  console.log("❌ OSS Client NOT initialized.");
  console.log("   ALIBABA_CLOUD_ACCESS_KEY_ID present:", !!process.env.ALIBABA_CLOUD_ACCESS_KEY_ID);
  console.log("   ALIBABA_CLOUD_ACCESS_KEY_SECRET present:", !!process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET);
  console.log("   Current ENV Keys:", Object.keys(process.env).filter(k => k.includes("OSS") || k.includes("ALI")));
}

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 50 * 1024 * 1024 } // 50MB limit
});

// ... (skipping Bmob init for brevity, it remains unchanged) ...

// ======== API: Upload to OSS ========
app.get("/api/test-oss", async (req, res) => {
  if (!ossClient) return res.status(500).json({ error: "OSS Client not initialized" });
  try {
    console.log("Testing OSS connection...");
    const result = await ossClient.list({ 'max-keys': 1 });
    console.log("OSS connection success:", result.res.status);
    res.json({ ok: true, region: ossClient.options.region, bucket: ossClient.options.bucket, result });
  } catch (e) {
    console.error("OSS Test Error:", e);
    res.status(500).json({ ok: false, error: e.message, code: e.code, name: e.name });
  }
});



// 初始化Bmob短信服务
const bmobSMS = process.env.BMOB_APP_ID && process.env.BMOB_REST_KEY
  ? new BmobSMS(process.env.BMOB_APP_ID, process.env.BMOB_REST_KEY)
  : null;

await initDb();
await initCardsDb(); // 初始化独立卡牌数据库

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
function signToken(user) {
  return jwt.sign({ uid: user.id, username: user.username }, JWT_SECRET, { expiresIn: "7d" });
}

async function authMiddleware(req, res, next) {
  const auth = req.headers.authorization || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : null;
  if (!token) return res.status(401).json({ error: "未登录" });
  try {
    const payload = jwt.verify(token, JWT_SECRET);
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
  let user = await dbGet("SELECT id, username FROM users WHERE username = ?", [username]);

  if (!user) {
    // 自动创建
    const hash = bcrypt.hashSync("dev123456", 10);
    const r = await dbRun("INSERT INTO users(username, password_hash) VALUES(?, ?)", [username, hash]);
    user = { id: r.lastID, username };
  }

  const token = signToken(user);
  res.json({
    user: { id: user.id, username: user.username, isProfileComplete: true },
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
  const user = await dbGet("SELECT id, username, phone, guardian_name FROM users WHERE id = ?", [req.user.uid]);
  if (!user) return res.status(404).json({ error: "用户不存在" });

  res.json({
    user: {
      id: user.id,
      username: user.username || user.phone,
      phone: user.phone,
      guardianName: user.guardian_name,
      isProfileComplete: !!user.guardian_name
    }
  });
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

    // Version increment
    const newVersion = (existing.version || 0) + 1;
    const updatedAt = Date.now();

    // If status is becoming 'deleted', set deleted_at?
    let deletedAt = existing.deleted_at;
    if (status === 'deleted' && existing.status !== 'deleted') {
      deletedAt = Date.now();
    } else if (status !== 'deleted') {
      deletedAt = null; // Restore from recycle bin
    }

    await cardsDbRun(
      `UPDATE cards SET safety_type=?, event=?, phase=?, options_json=?, status=?, version=?, updated_at=?, deleted_at=? WHERE id=?`,
      [safetyType, event, phase, optionsJson, status, newVersion, updatedAt, deletedAt, id]
    );

    res.json({ ok: true, id, version: newVersion, status });

  } catch (e) {
    console.error("Update Card Error:", e);
    res.status(500).json({ error: "Failed to update card: " + e.message });
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
