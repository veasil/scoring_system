# WQT 项目知识库

> 此文件由 Claude 自动维护。开发前必读。
> 每次修复 bug 后说"记录一下"即可自动追加踩坑记录。

---

## 项目简介

**《AI在5000天·伍力全开》伍力值计分系统**
一个儿童安全教育桌游的数字化计分平台。玩家（守望者）通过微信扫码/手机号登录，参与情境卡牌游戏，每次选择影响五维属性值（安全力/脑波力/实感力/创心力/沟通力）。运营人员通过 admin-panel 管理卡牌内容、用户等级和活动场次。

---

## 技术栈

| 层 | 技术 | 启动方式 |
|----|------|----------|
| 后端 API | Node.js + Express (ESM) | `node server.js`（端口 8080）|
| 管理后台 | Python 3.12 + Streamlit | `streamlit run admin-panel/app.py` |
| 前端 | 原生 HTML/CSS/JS | Express 静态托管 `public/` |
| 数据库 | SQLite × 2 | 自动初始化 |
| 对象存储 | 阿里云 OSS（香港区）| ali-oss SDK |
| 短信验证 | Bmob SMS | `src/bmob.js` |
| 认证 | JWT（7天有效）| Bearer Token |
| 加密 | AES-256-CBC | 敏感系统设置落库加密 |

---

## 目录结构

```
wqt-auth-backend/
├── server.js              # 后端主入口，所有 API 路由
├── src/
│   ├── db.js              # 主库（wqt.db）初始化 + 工具函数
│   ├── cards-db.js        # 卡牌库（cards.db），工厂模式，支持 SQLite/飞书切换
│   └── bmob.js            # Bmob 短信服务封装
├── admin-panel/
│   ├── app.py             # Streamlit 管理后台（2100+ 行）
│   └── db_utils.py        # 直连 wqt.db 的查询工具，含 AES 解密
├── public/                # 前端静态文件（Express 托管）
│   ├── index.html         # 主页（桌游模式 + 监督模式）
│   ├── complete-profile.html  # 新用户填守望师名页
│   ├── js/starfield.js    # 星空穿越欢迎动画
│   ├── cards-data.js      # 卡牌数据（前端用，与 cards.db 同步）
│   ├── css/               # 模块化样式（base/auth/game/header/modal...）
│   └── 23/2.webp          # 卡牌背景图（蓝黄渐变电路板纹理）
├── data/
│   ├── wqt.db             # 主数据库
│   └── cards.db           # 卡牌数据库（独立，可切换数据源）
├── scripts/               # 部署脚本、迁移脚本、nginx 配置
├── implementation_plan.md # 当前迭代详细规划（Task 1-6）
└── .env                   # 环境变量（不提交）
```

---

## 数据库 Schema（当前）

### wqt.db（主库）
```
users            id, username, phone, wechat_openid, unionid,
                 password_hash, guardian_name, is_profile_complete,
                 created_at, role('admin'|'user')

game_sessions    id, user_id, started_at, ended_at, final_score,
                 payload_json, location, players_json, game_mode,
                 game_settings_json, status('active'|'flagged'...)

game_events      id, session_id, ts, type, payload
                 [type 枚举见下方"关键约定"]

system_settings  key, value(AES加密), description, updated_at
sms_codes        phone, code_hash, expires_at, created_at
```

### cards.db（卡牌库）
```
cards   id, key(唯一业务ID), safety_type, event, phase,
        options_json, status('pending'|'active'|'rejected'|'deleted'),
        version(整数), created_at, updated_at, deleted_at
```
`options_json` 结构：`{"A":{"text":"...","consequence":"...","attributeEffects":{"安全力":1,...}},...}`

---

## Admin Panel 页面一览

| 导航项 | 函数 | 功能 |
|--------|------|------|
| 🎛️ 驾驶舱 | `overview_page()` | 核心指标概览 |
| 👤 用户管理 | `user_management_page()` | 用户列表、角色设置、OSS关联 |
| 🎴 卡牌管理 | `card_management_page()` | 卡牌增删改、状态流转 |
| 📂 OSS 文件管理 | `oss_management_page()` | 阿里云 OSS 文件浏览/删除 |
| 🎮 游戏分析 | `game_analysis_page()` | 场次统计、卡牌分析 |
| 🧹 数据审计 | `data_audit_page()` | 逐场次审查 |
| 🔬 复盘测试 | `review_testing_page()` | LLM 复盘报告生成测试 |
| ⚙️ 系统设置 | `system_settings_page()` | 系统配置（AES加密存储）|

**登录**：`admin` 账号用 DEV_KEY；普通用户用手机号 + 密码，role=admin 才进入后台。
**数据访问**：admin-panel 直连 `wqt.db`（`db_utils.py`），同时调用 `BACKEND_URL` 的 REST API 操作卡牌。

---

## 关键 API 端点（server.js）

```
认证：POST /api/auth/sms/send|verify  POST /api/auth/login|register|logout
用户：GET  /api/me   POST /api/auth/complete-profile
游戏：POST /api/game/start|finish|event   GET /api/game/last-session|session/:id
卡牌：GET  /api/cards（公开）  GET/POST /api/admin/cards（需auth）
      PUT  /api/cards/:id      DELETE /api/cards/:id
      POST /api/admin/generate-card（LLM生成）
OSS： GET  /api/admin/oss/files   DELETE /api/admin/oss/files
上传：POST /api/upload/audio|report
LLM： POST /api/llm/story
设置：GET  /api/settings
```

---

## 项目关键约定

### 事件类型枚举（game_events.type）

| 值 | 含义 |
|----|------|
| `card_choice` | 玩家选择了一张卡牌的选项 |
| `skill_used` | 玩家使用了数智技能 |
| `game_start` | 游戏开始 |
| `game_end` | 游戏结束 |

> 新增事件类型时同步更新此表，并检查 `admin-panel/app.py` 所有 SQL 查询。

### 卡牌生命周期状态
`cards.status` 合法值：`pending` → `active` / `rejected` / `deleted`

### 双数据库路径

| 数据库 | 默认路径 | 环境变量 |
|--------|----------|----------|
| 主库 | `./data/wqt.db` | `DB_PATH` |
| 卡牌库 | `./data/cards.db` | `CARDS_DB_PATH` |

卡牌库数据源可通过 `CARDS_SOURCE=feishu` 切换到飞书多维表格（当前为占位实现）。

### 时间戳规范
全库统一用 **毫秒级 Unix 时间戳**（`strftime('%s','now')*1000`）。
admin-panel 显示时统一转北京时间（UTC+8，`BEIJING_TZ`）。

### Session 命名规范
展示格式：`时间-守望师名`，如 `2025-03-01 张三`

---

## 当前迭代计划（Task 1-6）

详见 `implementation_plan.md`。优先级：**Task 4（权限重构）> Task 1（卡牌升级）> Task 3（活动管理）> Task 2（OSS视图）> Task 5（前端"我的"）> Task 6（运营手册）**

核心变更预告：
- `users.role` 将扩展为 `boss/operator/watcher/enterprise`（含子账号 `enterprise_id` 字段）
- 守望者等级 `watcher_level` 字段新增，需线上申请+人工审批流程
- 卡牌新增版本分支（release/draft）、批注功能
- 新增 `activities`、`activity_sessions`、`watcher_level_applications` 等表

---

## 踩坑记录

<!-- entries below -->

### 🔧 [2026-02-26] admin 卡牌数显示为 0

**现象**: 管理后台"数据审计"页面所有场次的卡牌数均显示为 0，但数据库中有实际的选牌记录。
**根因**: `admin-panel/app.py` 的 SQL 查询中事件类型写的是 `card_selected`，但 `game_events` 表实际存储的是 `card_choice`。
**修复**: 将两处 SQL 中 `type = 'card_selected'` 改为 `type = 'card_choice'`（`data_audit_page` 的 `tab_review` 和 `tab_all`）。
**关键点**: 前后端事件类型字符串必须以本表"事件类型枚举"为准；admin panel 的统计查询改动后用 `inspect_db.py` 验证。

---

### 🔧 [2026-02-26] 完善资料后返回首页重播欢迎动画

**现象**: 新用户在 `complete-profile.html` 填完守望师名字跳回首页时，星空穿越欢迎动画再次播放。
**根因**: `js/starfield.js` 没有区分"首次加载"和"从其他页面跳转回来"两种场景。
**修复**: 在 `complete-profile.html` 提交成功后跳转前写入 `sessionStorage.setItem('skip_intro', 'true')`；`starfield.js` 初始化时检测该标记，存在则直接隐藏 `#welcome-screen` 并清除标记。
**关键点**: 页面间传递"一次性状态"用 `sessionStorage`（关闭 Tab 即清除），不要用 `localStorage`。
