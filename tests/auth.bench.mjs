// 账号资产/登录子系统 端到端测试 bench
// 用法：node tests/auth.bench.mjs
// 行为：用临时数据库拉起真实 server.js，跑完一整套登录/单设备/到期/会话场景，
//       全部用临时 DB，不触碰 data/ 真实库。任一断言失败则退出码 1。

import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TMP = process.env.CLAUDE_JOB_DIR
  ? path.join(process.env.CLAUDE_JOB_DIR, "tmp")
  : path.join(ROOT, ".tmp-bench");
fs.mkdirSync(TMP, { recursive: true });

const PORT = 18099;
const BASE = `http://127.0.0.1:${PORT}`;
const DB_PATH = path.join(TMP, "bench_wqt.db");
const CARDS_DB_PATH = path.join(TMP, "bench_cards.db");

// 清空旧的临时库
for (const f of [DB_PATH, CARDS_DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm", CARDS_DB_PATH + "-wal", CARDS_DB_PATH + "-shm"]) {
  try { fs.unlinkSync(f); } catch {}
}

let passed = 0, failed = 0;
function check(name, cond, extra = "") {
  if (cond) { passed++; console.log(`  ✓ ${name}`); }
  else { failed++; console.log(`  ✗ ${name}  ${extra}`); }
}

async function api(method, p, { token, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(BASE + p, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let json = null;
  try { json = await res.json(); } catch {}
  return { status: res.status, json };
}

function startServer() {
  return new Promise((resolve, reject) => {
    const child = spawn("node", ["server.js"], {
      cwd: ROOT,
      env: {
        ...process.env,
        PORT: String(PORT),
        HOST: "127.0.0.1",
        SERVER_ENV: "test",
        JWT_SECRET: "bench_secret",
        DB_PATH,
        CARDS_DB_PATH,
        BMOB_APP_ID: "",      // 强制走开发环境 mock 短信
        BMOB_REST_KEY: "",
        SMS_RESEND_INTERVAL_MS: "0",  // 测试中不限制重发间隔
        SMS_DAILY_LIMIT: "0",         // 测试中不限制每日条数
        SMS_IP_HOURLY_LIMIT: "0",     // 测试中不限制单 IP 频次
        SMS_CODE_TTL_MS: "300000",
        ALIBABA_CLOUD_ACCESS_KEY_ID: "",   // 不初始化 OSS
        ALIBABA_CLOUD_ACCESS_KEY_SECRET: "",
      },
    });
    let out = "";
    const timer = setTimeout(() => reject(new Error("server start timeout\n" + out)), 20000);
    child.stdout.on("data", (d) => {
      out += d.toString();
      if (out.includes("Server running")) { clearTimeout(timer); resolve(child); }
    });
    child.stderr.on("data", (d) => { out += d.toString(); });
    child.on("exit", (code) => { if (code !== 0) { clearTimeout(timer); reject(new Error(`server exited ${code}\n` + out)); } });
  });
}

const ADMIN_PHONE = "13900000001";
const ADMIN_PWD = "secret123";
const PERMANENT_UNTIL = 253402300799000; // 永久会员哨兵，与 src/account.js 一致

async function getCode(phone) {
  const r = await api("POST", "/api/auth/sms/send", { body: { phone } });
  return r.json?.mockCode;
}

async function run() {
  const server = await startServer();
  try {
    // 0. 抽离未破坏：公开路由仍可用
    let r = await api("GET", "/api/settings");
    check("GET /api/settings 200", r.status === 200);
    r = await api("GET", "/api/cards");
    check("GET /api/cards 200 且有卡牌", r.status === 200 && Array.isArray(r.json?.cards) && r.json.cards.length > 0, `status=${r.status} n=${r.json?.cards?.length}`);

    // 1. dev-login (boss)
    r = await api("POST", "/api/auth/dev-login", { body: { key: "sj0127wqt" } });
    check("dev-login 200 role=boss", r.status === 200 && r.json?.user?.role === "boss", JSON.stringify(r.json));
    const bossToken1 = r.json.token;

    r = await api("GET", "/api/me", { token: bossToken1 });
    check("boss /api/me 200", r.status === 200, JSON.stringify(r.json));

    // 2. 创建组织 + 组织管理员（验证 server.js 抽离后 requireRole/normalizePhone 仍工作）
    r = await api("POST", "/api/admin/organizations", {
      token: bossToken1,
      body: { orgName: "测试组织", adminPhone: ADMIN_PHONE, adminName: "测试管理员", adminPassword: ADMIN_PWD, maxMembers: 10 },
    });
    check("创建组织+管理员 200", r.status === 200 && r.json?.organization?.id, JSON.stringify(r.json));
    const orgId = r.json.organization.id;
    const adminUserId = r.json.adminUser.id;

    // 2.5 新建组织默认未开通会员（valid_until=NULL）→ 成员登录被拒
    let code = await getCode(ADMIN_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: ADMIN_PWD, code } });
    check("新建组织未开通 → 403 ORG_NO_MEMBERSHIP", r.status === 403 && r.json?.code === "ORG_NO_MEMBERSHIP", JSON.stringify(r.json));

    // 开通组织为永久会员，后续登录用例才能通过
    r = await api("PUT", `/api/admin/organizations/${orgId}/validity`, { token: bossToken1, body: { validUntil: PERMANENT_UNTIL } });
    check("开通组织(永久) 200", r.status === 200, JSON.stringify(r.json));

    // 3. 三要素登录
    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: ADMIN_PWD } });
    check("登录缺验证码 → 400", r.status === 400, JSON.stringify(r.json));

    code = await getCode(ADMIN_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: ADMIN_PWD, code: "000000" } });
    check("登录错验证码 → 400", r.status === 400, JSON.stringify(r.json));

    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: "wrongpwd", code } });
    check("登录错密码 → 401", r.status === 401, JSON.stringify(r.json));

    code = await getCode(ADMIN_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: ADMIN_PWD, code } });
    check("三要素正确 → 200 拿到 token", r.status === 200 && r.json?.token, JSON.stringify(r.json));
    const adminToken1 = r.json.token;

    // 4. 单设备：再次登录踢掉旧设备
    code = await getCode(ADMIN_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: ADMIN_PWD, code } });
    const adminToken2 = r.json.token;
    check("二次登录 200", r.status === 200 && adminToken2 && adminToken2 !== adminToken1);

    r = await api("GET", "/api/me", { token: adminToken1 });
    check("旧设备 token → 401 SESSION_REVOKED", r.status === 401 && r.json?.code === "SESSION_REVOKED", JSON.stringify(r.json));

    r = await api("GET", "/api/me", { token: adminToken2 });
    check("新设备 token → 200", r.status === 200, JSON.stringify(r.json));

    // 5. 组织统一到期
    r = await api("PUT", `/api/admin/organizations/${orgId}/validity`, { token: bossToken1, body: { validUntil: Date.now() - 1000 } });
    check("设置组织过期 200", r.status === 200, JSON.stringify(r.json));

    r = await api("GET", "/api/me", { token: adminToken2 });
    check("过期组织成员 /api/me → 403 ORG_EXPIRED", r.status === 403 && r.json?.code === "ORG_EXPIRED", JSON.stringify(r.json));

    r = await api("GET", "/api/me", { token: bossToken1 });
    check("boss 不受组织到期影响 → 200", r.status === 200, JSON.stringify(r.json));

    code = await getCode(ADMIN_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: ADMIN_PWD, code } });
    check("过期组织登录 → 403 ORG_EXPIRED", r.status === 403 && r.json?.code === "ORG_EXPIRED", JSON.stringify(r.json));

    // 6. 续期后恢复
    r = await api("PUT", `/api/admin/organizations/${orgId}/validity`, { token: bossToken1, body: { validUntil: Date.now() + 86400000 } });
    check("续期 200", r.status === 200);
    code = await getCode(ADMIN_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: ADMIN_PWD, code } });
    check("续期后可登录 → 200", r.status === 200 && r.json?.token, JSON.stringify(r.json));
    const adminToken3 = r.json.token;

    // 7. 后台查看在线会话 + 强制下线
    r = await api("GET", `/api/admin/users/${adminUserId}/sessions`, { token: bossToken1 });
    check("查看在线会话 200 且有 1 条", r.status === 200 && r.json?.sessions?.length === 1, JSON.stringify(r.json));

    r = await api("DELETE", `/api/admin/users/${adminUserId}/sessions`, { token: bossToken1 });
    check("强制下线 200", r.status === 200);
    r = await api("GET", "/api/me", { token: adminToken3 });
    check("被强制下线后 → 401 SESSION_REVOKED", r.status === 401 && r.json?.code === "SESSION_REVOKED", JSON.stringify(r.json));

    // 8. 登出撤销会话
    code = await getCode(ADMIN_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: ADMIN_PHONE, password: ADMIN_PWD, code } });
    const adminToken4 = r.json.token;
    await api("POST", "/api/auth/logout", { token: adminToken4 });
    r = await api("GET", "/api/me", { token: adminToken4 });
    check("登出后 token → 401", r.status === 401, JSON.stringify(r.json));

    // 8.5 独立用户（无组织）会员资产：默认未开通 → 开通 → 登录
    const SOLO_PHONE = "13700000007";
    const SOLO_PWD = "solo123456";
    r = await api("POST", "/api/admin/users", { token: bossToken1, body: { phone: SOLO_PHONE, password: SOLO_PWD, role: "watcher" } });
    check("创建独立用户 200", r.status === 200 && r.json?.id, JSON.stringify(r.json));
    const soloId = r.json.id;

    code = await getCode(SOLO_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: SOLO_PHONE, password: SOLO_PWD, code } });
    check("独立用户未开通 → 403 NO_MEMBERSHIP", r.status === 403 && r.json?.code === "NO_MEMBERSHIP", JSON.stringify(r.json));

    r = await api("PUT", `/api/admin/users/${soloId}/validity`, { token: bossToken1, body: { validUntil: PERMANENT_UNTIL } });
    check("开通独立用户(永久) 200", r.status === 200, JSON.stringify(r.json));
    code = await getCode(SOLO_PHONE);
    r = await api("POST", "/api/auth/login", { body: { phone: SOLO_PHONE, password: SOLO_PWD, code } });
    check("开通后独立用户登录 → 200", r.status === 200 && r.json?.token, JSON.stringify(r.json));

    // 组织成员不能单独设有效期（后端拒绝，有效期跟随组织）
    r = await api("PUT", `/api/admin/users/${adminUserId}/validity`, { token: bossToken1, body: { validUntil: PERMANENT_UNTIL } });
    check("给组织成员单独设有效期 → 400", r.status === 400, JSON.stringify(r.json));

    // 9. 微信占位路由已删除
    r = await api("GET", "/api/auth/wechat/qr");
    check("微信路由已删除 → 404", r.status === 404, `status=${r.status}`);
  } finally {
    server.kill();
  }

  console.log(`\n结果：${passed} 通过 / ${failed} 失败`);
  process.exit(failed === 0 ? 0 : 1);
}

run().catch((e) => { console.error("BENCH ERROR:", e); process.exit(1); });
