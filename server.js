import express from "express";
import cors from "cors";
import morgan from "morgan";
import dotenv from "dotenv";
import jwt from "jsonwebtoken";
import bcrypt from "bcryptjs";
import fetch from "node-fetch";
import path from "path";
import { fileURLToPath } from "url";
import { initDb, dbRun, dbGet, dbAll } from "./src/db.js";

dotenv.config();

const app = express();
const PORT = Number(process.env.PORT || 3000);
const JWT_SECRET = process.env.JWT_SECRET || "dev_secret_change_me";

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

// ======== API: SMS mock login ========
app.post("/api/auth/sms/send", async (req, res) => {
  const phone = normalizePhone(req.body?.phone || req.body?.mobile);
  if (!phone) return res.status(400).json({ error: "缺少手机号" });
  if (phone.length < 6) return res.status(400).json({ error: "手机号格式不正确" });

  const now = Date.now();
  const existing = smsStore.get(phone);
  if (existing && now - existing.lastSent < SMS_RESEND_INTERVAL_MS) {
    const waitSec = Math.ceil((SMS_RESEND_INTERVAL_MS - (now - existing.lastSent)) / 1000);
    return res.status(429).json({ error: `发送过于频繁，请${waitSec}秒后重试` });
  }

  const code = generateSmsCode();
  smsStore.set(phone, { code, expiresAt: now + SMS_CODE_TTL_MS, lastSent: now });
  console.log(`[sms-mock] phone=${phone} code=${code}`);

  // mockCode 仅供本地调试使用；真实环境应改为调用短信服务商接口
  res.json({ ok: true, mockCode: code, expiresInSeconds: Math.floor(SMS_CODE_TTL_MS / 1000) });
});

app.post("/api/auth/sms/verify", async (req, res) => {
  const phone = normalizePhone(req.body?.phone || req.body?.mobile);
  const code = String(req.body?.code || "").trim();
  if (!phone || !code) return res.status(400).json({ error: "手机号或验证码缺失" });

  const record = smsStore.get(phone);
  if (!record) return res.status(400).json({ error: "请先获取验证码" });
  const now = Date.now();
  if (now > record.expiresAt) {
    smsStore.delete(phone);
    return res.status(400).json({ error: "验证码已过期" });
  }
  if (record.code !== code) return res.status(400).json({ error: "验证码错误" });

  let user = await dbGet("SELECT id, username FROM users WHERE username = ?", [phone]);
  if (!user) {
    const r = await dbRun("INSERT INTO users(username) VALUES(?)", [phone]);
    user = { id: r.lastID, username: phone };
  }

  const token = signToken(user);
  smsStore.delete(phone);
  res.json({ user, token });
});

// 前端会调用，但我们这里不维护 server-side session，所以直接返回 ok
app.post("/api/auth/logout", async (_req, res) => res.json({ ok: true }));

app.get("/api/me", authMiddleware, async (req, res) => {
  res.json({ user: { id: req.user.uid, username: req.user.username } });
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

// ======== API: LLM proxy（可选） ========
// 你原 index.html 里把 Key 写死在前端了（非常危险），这里提供一个安全的后端代理。
app.post("/api/llm/story", authMiddleware, async (req, res) => {
  const prompt = req.body?.prompt;
  if (!prompt) return res.status(400).json({ error: "缺少 prompt" });

  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) return res.status(400).json({ error: "后端未配置 DEEPSEEK_API_KEY" });

  const model = process.env.DEEPSEEK_MODEL || "deepseek-reasoner";

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
        max_tokens: 800,
        temperature: 0.7
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
const HOST = process.env.HOST || '8.210.121.92';
app.listen(PORT, HOST, () => {
  console.log(`✅ Server running on http://${HOST}:${PORT}`);
  console.log(`🌐 Local access: http://localhost:${PORT}`);
});
