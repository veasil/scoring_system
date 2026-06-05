# WQT 伍力全开 · 计分系统

> 《AI在5000天·伍力全开》儿童数智免疫力桌游配套数字生态系统。
> 生产环境部署在 **Zeabur（香港专属服务器）+ PostgreSQL**。

玩家（守望者）通过手机号注册 / 登录，参与情境卡牌游戏。每次选择影响五维属性值：安全力 / 脑波力 / 实感力 / 创心力 / 沟通力。运营人员通过 admin-web 后台管理卡牌内容、用户等级和活动场次；组织管理员通过 enterprise-panel 管理本组织成员与活动。

---

## 部署架构（Zeabur）

**单个 Node 服务 = 后端 API + 三个前端**。Express 同时静态托管三套前端，无需额外服务：

| 路径 | 内容 | 来源 |
|------|------|------|
| `/` | 游戏主页（玩家端） | `public/`（已在仓库，无需构建） |
| `/enterprise` | 组织管理面板（Vue 3 SPA） | `enterprise-panel/dist`（**构建期生成**） |
| `/admin` | 中台管理后台（Vue 3 SPA，**取代旧 Streamlit**） | `admin-web/dist`（**构建期生成**） |
| `/api/*` | 后端 REST API | `server.js` + `src/routes/` |

**构建 → 启动流程（Zeabur / Nixpacks 自动执行）**：

```bash
npm install              # 安装后端依赖
npm run build            # 构建两个 SPA：分别 npm install + vite build 到各自 dist/
npm start                # node server.js，监听 0.0.0.0:8080
```

> `enterprise-panel/dist` 与 `admin-web/dist` 都在 `.gitignore`，**容器内由 `npm run build` 现场编译**。若 `/enterprise` 或 `/admin` 打不开，第一时间查构建日志里这两步 `vite build` 是否成功。

### 数据库

生产用 **PostgreSQL**（Zeabur 托管），主库与卡牌库**共用同一个 PG 数据库**（表名不冲突）。

| 数据库逻辑 | 表 | 连接来源 |
|-----------|----|---------|
| 主库 | users / organizations / game_sessions / game_events / activities / invite_codes / system_settings / user_sessions / sms_codes 等 | `DATABASE_URL` |
| 卡牌库 | cards / card_versions / cards_released / card_groups | `CARDS_DATABASE_URL`，未设则回退 `DATABASE_URL` |

- 代码默认数据源就是 PostgreSQL（`CARDS_SOURCE` 默认 `postgres`）。本地开发可设 `CARDS_SOURCE=sqlite` 回退 SQLite。
- SQLite→PG 的兼容层在 `src/sql-pg.js`（占位符 `?`→`$n`、`INSERT OR IGNORE`→`ON CONFLICT`、自动 `RETURNING id`、瞬时断连重试），现有调用点零改动。
- 全库统一**毫秒级 Unix 时间戳**（`(extract(epoch from now())*1000)::bigint`）。

---

## 环境变量（在 Zeabur 服务 Variables 配置）

| 变量 | 必填 | 说明 |
|------|:----:|------|
| `DATABASE_URL` | ✅ | PostgreSQL 连接串。**生产用 Zeabur 内网引用** `${POSTGRES_CONNECTION_STRING}`，不要填公网 IP:Port（公网代理会随机断连且耗流量）。 |
| `SETTINGS_ENCRYPTION_KEY` | ✅ | 32 字节 hex，AES-256-CBC 密钥。**必须与数据迁移时一致**，否则 `system_settings` 里加密的 OSS / 三方凭证无法解密 → OSS 初始化失败。 |
| `JWT_SECRET` | ✅ | 强随机串（≥64 字节 hex）。更换会使存量 token 失效，需重新登录。 |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` | ✅ | LLM（复盘报告 / 生成卡牌）。本项目 LLM 用 **DeepSeek**。 |
| `BMOB_APP_ID` / `BMOB_REST_KEY` | ✅ | Bmob 短信验证码。 |
| `CARDS_DATABASE_URL` | ⬜ | 卡牌库单独的 PG 连接串；不设则与主库共库。 |
| `DATABASE_SSL` | ⬜ | **内网连接保持不设 / `false`**；置 `true` 会导致内网握手失败。仅连公网端点调试时才用 `true`。 |
| `PORT` | ⬜ | 默认 8080。 |
| `DEV_KEY` | ⬜ | admin/boss 开发登录密钥（也存于 system_settings）。 |

> ⚠️ **OSS 凭证不在环境变量里**——它们以 AES 加密形式存在 `system_settings` 表，运行时用 `SETTINGS_ENCRYPTION_KEY` 解密。所以「OSS 初始化失败」九成是 `DATABASE_URL` 或 `SETTINGS_ENCRYPTION_KEY` 配错。

### 健康启动日志（正常应看到）

```
✅ Main database initialized (PostgreSQL)
✅ [PostgreSQL] Cards database initialized
✅ OSS Client initialized.
✅ Server running on http://0.0.0.0:8080
```

任意一行变成 SQLite / `❌ OSS Client NOT initialized` 即为配置异常，对照上表排查。

---

## 自定义域名

Zeabur 服务 → Networking / Domains → 添加 `www.ai5000days.com` → 按面板提示在 DNS 商配置记录（专属服务器一般是指向服务器 IP 的 A 记录）。HTTPS 证书由 Zeabur 自动签发并续期。切换前可先用 Zeabur 默认的 `*.zeabur.app` 域名验证。

---

## 数据迁移（一次性）

把旧 SQLite 数据导入 PostgreSQL：

```bash
# 幂等，可重复运行；ON CONFLICT DO NOTHING + 自动重置 IDENTITY 序列
npm run migrate:pg -- "<DATABASE_URL>" ./_migration/wqt.db ./_migration/cards.db
```

`_migration/`（含密钥与 sqlite 导出）已被 `.gitignore` 忽略，**严禁提交**。

---

## 本地开发

```bash
npm install
# 后端（默认连 PostgreSQL；想用本地 sqlite 则设 CARDS_SOURCE=sqlite 且 DATABASE_URL 指向本地 PG）
node server.js
# 前端（开发态，Vite proxy → 8080）
cd enterprise-panel && npm run dev      # 5173
cd admin-web && npm run dev
```

---

## 目录结构

```
wqt-auth-backend/
├── server.js                  # 后端主入口；同时静态托管三套前端
├── src/
│   ├── sql-pg.js              # SQLite→PostgreSQL 兼容层（占位符/RETURNING/重试）
│   ├── db.js                  # 主库（PG）初始化 + dbRun/dbGet/dbAll
│   ├── cards-db.js            # 卡牌库工厂，PostgresCardsSource（默认）/SQLite/飞书
│   ├── account.js            # 账号有效期 / 会员资产核心逻辑
│   ├── config.js             # 运行期配置 + AES 加解密
│   ├── bmob.js               # Bmob 短信封装
│   ├── middleware/           # auth.js（JWT）、rbac.js（角色/组织权限）
│   ├── services/             # sessions.js（单设备会话）、sms.js（验证码）
│   └── routes/               # auth.routes.js、account-admin.routes.js
├── public/                    # 游戏前端（玩家端，原生 HTML/CSS/JS）
├── enterprise-panel/          # 组织管理 SPA（Vue 3）→ 构建到 dist，挂 /enterprise
├── admin-web/                 # 中台管理 SPA（Vue 3，取代 Streamlit）→ 构建到 dist，挂 /admin
├── admin-panel/               # ⚠️ 已废弃的 Streamlit 后台（不再部署，仅留档）
├── scripts/
│   └── migrate_sqlite_to_pg.mjs   # SQLite→PG 数据迁移
└── docs/                      # 部署 / 运营 / 安全审计文档
```

> **admin-panel（Streamlit）已退役**，由 admin-web 取代，不参与 Zeabur 部署。仓库保留仅作历史参考。

---

## 核心 API（节选）

```
认证   POST /api/auth/login（手机号+密码+验证码 + 单设备会话轮换）
       POST /api/auth/sms/send|verify   POST /api/auth/register-with-invite
用户   GET  /api/me   PUT /api/me/password   POST /api/auth/complete-profile
游戏   POST /api/game/start|finish|event   GET /api/game/last-session|session/:id
卡牌   GET  /api/cards[?group_id=:id]   GET/POST /api/admin/cards   PUT/DELETE /api/cards/:id
组织   POST/GET/PUT/DELETE /api/admin/organizations（boss）
       GET /api/enterprise/info|dashboard|members|activities|sessions（组织管理员）
OSS    GET/DELETE /api/admin/oss/files   POST /api/upload/audio|report
LLM    POST /api/llm/story   POST /api/admin/generate-card
设置   GET  /api/settings
```

完整端点与领域约定见 [CLAUDE.md](CLAUDE.md)。

---

## 角色模型

| role | enterprise_id | 含义 |
|------|--------------|------|
| `boss` | — | 超级管理员，全权限 |
| `operator` | — | 运营，模块级权限 |
| `enterprise` | X | 组织 X 的管理员 |
| `watcher` | X | 组织 X 的成员 |
| `watcher` | NULL | 独立个人用户 |

---

## 关键约定

- **事件类型**（`game_events.type`）：`card_choice` / `skill_used` / `game_start` / `game_end`。
- **卡牌三表生命周期**：`card_versions`（版本，append-only）→promote→ `cards`（沙盒）→release→ `cards_released`（前端快照）。前端经 `GET /api/cards?group_id` 读卡牌组的有序快照。
- **system_settings**：敏感项 AES-256-CBC 加密落库，靠 `SETTINGS_ENCRYPTION_KEY` 解密。
- **单设备会话**：每用户仅一条有效 `user_sessions`，新登录覆盖旧的。

更多踩坑记录与领域细节见 [CLAUDE.md](CLAUDE.md)。
