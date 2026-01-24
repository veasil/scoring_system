import express from "express";
import cors from "cors";
import morgan from "morgan";
import dotenv from "dotenv";
import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import fetch from "node-fetch";
import path from "path";
import { fileURLToPath } from "url";
import { initDb, dbRun, dbGet, dbAll, saveSmsCode, verifySmsCode, addGameEvent, getGameEvents } from "./src/db.js";
import { BmobSMS } from "./src/bmob.js";

dotenv.config();

const app = express();
const PORT = Number(process.env.PORT || 8080);
const JWT_SECRET = process.env.JWT_SECRET || "dev_secret_change_me";

// 初始化Bmob短信服务
const bmobSMS = process.env.BMOB_APP_ID && process.env.BMOB_REST_KEY 
  ? new BmobSMS(process.env.BMOB_APP_ID, process.env.BMOB_REST_KEY)
  : null;

await initDb();

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
  try {
    // 测试数据库连接
    const userCount = await dbGet("SELECT COUNT(*) as count FROM users");
    const sessionCount = await dbGet("SELECT COUNT(*) as count FROM game_sessions");
    const eventCount = await dbGet("SELECT COUNT(*) as count FROM game_events");
    
    res.json({
      ok: true,
      database: {
        connected: true,
        tables: {
          users: userCount.count,
          game_sessions: sessionCount.count,
          game_events: eventCount.count
        }
      }
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: error.message,
      database: { connected: false }
    });
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
  const r = await dbRun("INSERT INTO game_sessions(user_id, started_at) VALUES(?, ?)", [userId, ts]);
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
