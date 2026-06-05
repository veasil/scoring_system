# WQT 伍力全开 · 计分系统

> 《AI在5000天·伍力全开》儿童数智免疫力桌游配套数字生态系统。

玩家（守望者）可通过微信扫码或手机号注册与登录，参与情境卡牌游戏。每次选择影响五维属性值：安全力 / 脑波力 / 实感力 / 创心力 / 沟通力。运营人员通过管理后台管理卡牌内容、用户等级和活动场次。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 API | Node.js + Express (ESM)，端口 8080 |
| 管理后台 | Python 3.12 + Streamlit |
| 前端 | 原生 HTML / CSS / JS（Express 静态托管） |
| 数据库 | SQLite × 2（主库 + 卡牌库） |
| 对象存储 | 阿里云 OSS（香港区） |
| 短信验证 | Bmob SMS |
| 认证 | JWT（7 天有效，Bearer Token） |
| 加密 | AES-256-CBC（系统设置落库加密） |

---

## 快速启动

```bash
# 安装依赖
npm install
pip install -r admin-panel/requirements.txt

# 复制并填写环境变量
cp .env.example .env

# 启动后端（端口 8080）
node server.js

# 启动管理后台（端口 8501）
streamlit run admin-panel/app.py --server.address=localhost
```

---

## 目录结构

```
wqt-auth-backend/
├── server.js                  # 后端主入口，所有 API 路由
├── src/
│   ├── db.js                  # 主库（wqt.db）初始化 + 工具函数
│   ├── cards-db.js            # 卡牌库（cards.db），支持 SQLite/飞书切换
│   └── bmob.js                # Bmob 短信服务封装
├── admin-panel/
│   ├── app.py                 # Streamlit 管理后台
│   └── db_utils.py            # 直连 wqt.db 的查询工具，含 AES 解密
├── public/                    # 前端静态文件
│   ├── index.html             # 主页（桌游模式 + 监督模式）
│   ├── complete-profile.html  # 新用户填守望师名页
│   ├── my.html                # 我的页面
│   └── js/starfield.js        # 星空穿越欢迎动画
├── data/
│   ├── wqt.db                 # 主数据库（.gitignore）
│   └── cards.db               # 卡牌数据库（.gitignore）
├── docs/
│   ├── DEPLOY.md              # 部署说明
│   └── operations-manual.md   # 运营手册
└── scripts/                   # 部署脚本、Nginx 配置
```

---

## 核心 API

```
认证    POST /api/auth/sms/send|verify
        POST /api/auth/login|register|logout
用户    GET  /api/me
        POST /api/auth/complete-profile
游戏    POST /api/game/start|finish|event
        GET  /api/game/last-session|session/:id
卡牌    GET  /api/cards
        GET|POST /api/admin/cards
        PUT  /api/cards/:id
        DELETE /api/cards/:id
OSS     GET  /api/admin/oss/files
        DELETE /api/admin/oss/files
LLM     POST /api/llm/story
设置    GET  /api/settings
```

---

## 数据库 Schema

**wqt.db（主库）**

| 表 | 主要字段 |
|----|---------|
| `users` | id, phone, wechat_openid, guardian_name, role(`boss`/`operator`/`watcher`/`enterprise`), watcher_level |
| `game_sessions` | id, user_id, started_at, ended_at, final_score, location, game_mode, status |
| `game_events` | id, session_id, type(`card_choice`/`skill_used`/`game_start`/`game_end`), payload |
| `system_settings` | key, value（AES-256-CBC 加密） |
| `sms_codes` | phone, code_hash, expires_at |

**cards.db（卡牌库）**

| 表 | 主要字段 |
|----|---------|
| `cards` | id, key, safety_type, event, phase, options_json, status(`pending`/`active`/`rejected`/`deleted`), version |

`options_json` 结构：`{"A":{"text":"...","consequence":"...","attributeEffects":{"安全力":1,...}},...}`

---

## 环境变量（.env）

```bash
PORT=8080
JWT_SECRET=
SETTINGS_ENCRYPTION_KEY=        # 32字节hex，AES-256密钥

# 阿里云 OSS
ALIBABA_CLOUD_ACCESS_KEY_ID=
ALIBABA_CLOUD_ACCESS_KEY_SECRET=
OSS_BUCKET_NAME=
OSS_ENDPOINT=
OSS_CDN_DOMAIN=

# Bmob 短信
BMOB_APP_ID=
BMOB_REST_API_KEY=

# 管理后台
BACKEND_URL=http://localhost:8080
DEV_KEY=                         # admin 登录密钥
```

---

## 管理后台

| 页面 | 功能 |
|------|------|
| 驾驶舱 | 核心指标概览 |
| 用户管理 | 用户列表、角色设置、场次统计 |
| 卡牌管理 | 卡牌增删改、状态流转 |
| OSS 文件管理 | 阿里云 OSS 文件浏览/删除 |
| 游戏分析 | 场次统计、卡牌分析 |
| 数据审计 | 逐场次审查 |
| 复盘测试 | LLM 复盘报告生成测试 |
| 系统设置 | 系统配置（AES 加密存储） |

---

## 部署

详见 [docs/DEPLOY.md](docs/DEPLOY.md) 和 [docs/operations-manual.md](docs/operations-manual.md)。
