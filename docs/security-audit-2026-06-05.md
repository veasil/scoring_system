# 🛡️ wqt-auth-backend 上线安全体检报告

> 体检日期：2026-06-05 ｜ 依据：《MVP 上线安全自检宝典》12 安全域 / 88 检查项 ｜ 仅用于本项目合法自查

**体检范围**：整体上线体检（12 域）
**技术栈**：Node/Express + SQLite ×2 + JWT(Bearer) + Bmob 短信 + 阿里云 OSS + DeepSeek LLM
**UGC**：有（守望师名/反馈）｜**支付**：无

**一句话结论：🔴 不建议上线** —— 存在 3 类致命问题，其中"凭手机号即可登录管理后台"和"普通用户能调几乎所有管理接口"属于可直接被接管系统的级别。

整体印象：新拆分到 `src/routes/` 的代码（account-admin、admin-data）安全做得很规范（统一 `boss` 守卫、参数化查询、组织隔离）；问题几乎全集中在 `server.js` 里的旧内联接口——它们只挂了"登录校验"却漏了"角色校验"。典型的"重构做了一半"留下的权限断层。

---

## 🔴 致命（必须上线前堵住）

### F1. 管理后台登录只认手机号，不要密码、不要验证码

**证据**：`src/routes/auth.routes.js:111-138` `/api/auth/admin-login`

```js
const phone = normalizePhone(req.body?.phone);
const user = await dbGet("...WHERE phone = ?",[phone]);
if (!allowedRoles.includes(user.role)) return 403;
const token = await issueSession(...);   // ← 直接发 boss/operator token
```

任何人只要知道（或撞到）一个 boss/operator 的手机号，POST 一下就拿到**完整管理员令牌**。教科书级"认证缺失/垂直越权"。

**正确做法**：管理后台登录必须与普通登录一样走"手机号+密码+验证码"三要素，校验 `password_hash` 和 `verifyCode` 后再签发。

**🤖 修复指令**：给 `/api/auth/admin-login` 加上和 `/api/auth/login` 相同的密码校验(`bcrypt.compareSync`)和短信验证码校验(`verifyCode` consume=true)，三者全过才签发 token；boss/operator 角色检查保留。

### F2. 几乎所有旧版 /api/admin/* 接口缺角色校验，普通用户即可调用

**证据**：`server.js` 里这些接口**只有 `authMiddleware`、没有 `requireRole`**，而 `authMiddleware`（`src/middleware/auth.js`）只验 token/会话/有效期、**不验角色**。任意 `role='watcher'` 的登录用户都能调：

| 接口 | 行号 | 后果 |
|------|------|------|
| `DELETE /api/admin/oss/files` | 1897 | **任意用户删光 OSS 全部文件** |
| `PUT /api/admin/users/:id/level` | 2113 | 改任意用户等级 |
| `PUT /api/admin/level-applications/:id` | 2080 | 自助审批自己的升级申请 |
| `POST /api/admin/generate-card` | 1377 | 白嫖你的 DeepSeek 额度 |
| `POST/PUT/DELETE /api/cards`、card-groups、card-versions、notes、release/promote/branch | 1259–2368 | 任意篡改/删除卡牌库与版本 |
| `GET /api/admin/oss/files`、activities、feedback | 1855… | 越权读数据 |

对比正面例子：`account-admin.routes.js` / `admin-data.routes.js` 用 `const boss=[authMiddleware,requireRole("boss")]` 全部守住了——旧接口照抄即可。

**🤖 修复指令**：给 `server.js` 里所有 `/api/admin/*` 和 `/api/cards` 写接口补上 `requireRole('boss')`（运营相关的按需 `'operator'`），采用默认拒绝白名单制：未声明角色的管理接口一律 403。复用 `src/middleware/rbac.js` 的 `requireRole`，列出补了哪些接口。

### F3. 短信发送接口在生产环境零防护（轰炸 + 话费欺诈）

**证据**：`src/services/sms.js:33-52`。那个 60 秒重发间隔**只在 `!bmobSMS`（开发模拟）分支里有**；一旦配了 Bmob（生产），直接 `await bmobSMS.sendSmsCode(phone)`，**无每日上限、无 IP 限流、无图形验证码/滑块**。`auth.routes.js:141-158` 的 `/api/auth/sms/send` 也没加任何前置人机校验。换个手机号就能无限刷。

**🤖 修复指令**：给短信验证码发送接口加防刷三件套：①发送前强制校验图形验证码或行为验证码 token（接入腾讯云天御/网易易盾）；②后端用内存或 Redis 限流：同手机号 60 秒不重发且每日≤10 条、同 IP 每小时≤20 次，且对 Bmob 真实发送分支也生效（不要只在 mock 分支）；③验证码 5 分钟过期、用一次即失效。

---

## 🟠 高危（上线后尽快，最好上线前）

- **H1 验证码可暴力猜测** —— `sms.js:60-78` 校验无尝试次数限制、错码不锁定（mock 分支错码连删都不删）。6 位码可被脚本撞开。➜ 校验失败累计 5 次即锁定/作废该码。
- **H2 登录无防爆破/撞库** —— `auth.routes.js:45-85` 密码错误无锁定、无限流。➜ 按 IP+账号双维度限速，连错 5 次要求图形验证码。
- **H3 硬编码默认密钥** —— `DEV_KEY` 默认 `"sj0127wqt"`（`auth.routes.js:92`、`server.js:1601`），`JWT_SECRET` 默认 `"dev_secret_change_me"`（`auth.js:9,33`）。未在 env 配置就等于用源码里公开的密钥。`/api/admin/cards/bulk-upsert`（`server.js:1595`）整个就靠这个默认 DEV_KEY 把门。➜ 启动时若这俩为默认值/缺失就**拒绝启动**，强制 .env 配强随机值。
- **H4 安全响应头缺失** —— `server.js` 未引入 helmet，无 HSTS/CSP/X-Frame-Options。➜ `app.use(helmet())`。
- **H5 CORS 回显任意来源** —— `server.js:181` `cors({origin:true})`。`credentials:false` 已降低危害（Bearer 不走 Cookie），但仍建议改成自己的域名白名单。
- **H6 上传无内容审核/真实类型校验** —— `server.js:1798-1818` 仅 50MB 大小限制，音频与 HTML 报告无内容安全审核（违法内容会嫁祸到你账号）。✅ 好的一面：文件名服务端固定，**无路径遍历、无任意扩展名**。➜ 接入阿里云内容安全，上传前过审。

---

## 🟡 中危 / 需人工确认

- **⚠️ 账号枚举** —— `register-with-invite` 返回"该手机号已注册"(409，`auth.routes.js:205`)、`admin-login` 返回"用户不存在"(404)。可据此判断号码是否注册。（主登录 `/api/auth/login` 已做统一"手机号或密码错误"✅）
- **❓ ICP 备案 / 隐私政策 / 同意弹窗**（合规域致命，0/1 门槛）—— 代码看不出，**需确认**：境内服务器是否已备案？是否有隐私政策页 + 首次同意弹窗 + 删号/撤回授权入口？
- **❓ HTTPS 强制 / WAF / CDN / DDoS / 数据库备份 / 监控告警 / 证书自动续期** —— 属运维层，需在 nginx/云控制台核对（`scripts/nginx_admin.conf` 未逐项验证）。
- **❓ 应急一键熔断开关 / 下线预案**（P6）—— 注册开关有 `ALLOW_SELF_REGISTRATION`✅，但短信/卡牌等高危功能缺秒级熔断开关。

---

## ✅ 已做对的（继续保持）

SQL 全程参数化查询（无注入）· 密码 bcrypt 哈希 · 水平越权 `game/session/:id` 按 `user_id` 校验、enterprise 接口 `requireEnterprise`+组织隔离 · 新版 `admin-data`/`account-admin` 路由 `boss` 守卫齐全 · LLM API Key 在服务端 env 未下发前端 · 登录验证码 `consume=true` 防重放 · 单设备会话 + jti 吊销 · `.env` 已 gitignore

---

## 放行清单（按这个顺序堵）

1. **F1** admin-login 补密码+验证码 ← 5 分钟能改，危害最大
2. **F2** 给旧 `/api/admin/*` 批量补 `requireRole`（尤其 OSS DELETE、users/:id/level、generate-card）
3. **F3** 短信发送补限流+人机验证（对 Bmob 真实分支生效）
4. **H3** 启动校验，禁止默认 DEV_KEY/JWT_SECRET 上线
5. 其余 H/中危跟进
