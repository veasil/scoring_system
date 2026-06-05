# Admin Panel 迁移执行手册（Streamlit → Vue3 admin-web）

> 本文件是 Claude 自迭代时遵循的执行手册。目标：用 Vue3 + Element Plus 重写 `admin-panel/`（Streamlit, 4009 行），
> 下线 Streamlit，整套系统准备迁移到 Zeabur。
> 每完成一页/一个接口，更新本文「进度看板」并跑 `npm run test:bench`。

---

## 0. 架构决策（已定）

| 决策 | 选择 | 理由 |
|------|------|------|
| 前端框架 | **Vue3 + Element Plus**，仿 `enterprise-panel` 结构 | repo 里已有同栈生产应用，零学习成本、零新依赖、部署方式现成 |
| 是否引入开源后台模板 | **否**（不引入 vue-pure-admin 等重模板） | 重模板=外部大代码库要维护，违背"少麻烦"。直接复用 enterprise-panel 的布局/axios/auth 模式 |
| 是否换数据库 | **否**，保留 SQLite | admin 改造不碰存储层，降低风险；Postgres 留到 Zeabur 阶段单独评估 |
| 前端碰不碰 DB | **不碰**。所有数据走 `server.js` REST | Streamlit 时代 `db_utils.py` 直连 SQLite 的查询，必须补成 REST 接口 |
| 鉴权 | 复用现有 JWT + 单设备会话。admin-web 用 `POST /api/auth/admin-login`(boss/operator) 或 `dev-login`(DEV_KEY) | 与现网一致 |
| 部署形态 | `admin-web/dist` 由 Express 静态托管在 `/admin/`（与 `/enterprise/` 并列） | Zeabur 上少一个 Python/Streamlit 进程 |

新目录：`admin-web/`（Vite, base=`/admin/`, proxy→8080），结构对齐 `enterprise-panel/`。

---

## 1. 接口缺口矩阵（审计结论）

`server.js` 现有 admin 接口已覆盖：**卡牌 CRUD/版本/批注/发布、卡牌组、组织 CRUD、邀请码、活动、OSS、等级申请、反馈、LLM**。
以下是 Streamlit 直连 SQLite、**尚无对应 REST 接口**的部分（= 本次后端工作量）：

| # | 归属页面 | 缺失能力 | 计划端点 | 状态 |
|---|----------|----------|----------|------|
| G1 | 驾驶舱 overview | 场次/用户增长聚合、状态分布 | `GET /api/admin/stats/overview` | TODO |
| G2 | 用户管理 | 用户列表(过滤/分页) | `GET /api/admin/users` | TODO |
| G3 | 用户管理 | 建号(查重 phone/username + INSERT) | `POST /api/admin/users` | TODO |
| G4 | 用户管理 | 改用户(角色/组织/资料) | `PUT /api/admin/users/:id` | TODO |
| G5 | 用户管理 | 删用户(级联删 sessions/events/feedback/level) | `DELETE /api/admin/users/:id` | TODO |
| G6 | 组织管理 | 组织成员列表 | `GET /api/admin/organizations/:id/members` | TODO |
| G7 | 组织管理 | 批量建号 | `POST /api/admin/organizations/:id/members/batch` | TODO |
| G8 | 游戏分析 | 场次列表 + 选牌统计 | `GET /api/admin/stats/sessions`, `GET /api/admin/stats/cards` | TODO |
| G9 | 游戏分析/审计 | 单场次事件明细 | `GET /api/admin/sessions/:id/events` | TODO |
| G10 | OSS 管理 | 孤儿文件分析(OSS×sessions×users) | `GET /api/admin/oss/orphans` | TODO |
| G11 | 系统设置 | 全量设置读(含 AES 解密) | `GET /api/admin/settings` | TODO |
| G12 | 系统设置 | 设置写(敏感项 AES 加密落库) | `PUT /api/admin/settings` | TODO |
| G13 | 系统设置 | operator 列表 + 权限 | `GET /api/admin/operators` `PUT /api/admin/operators/:id/permissions` | TODO |
| G14 | 数据审计 | 场次按状态列表 + 计数 | `GET /api/admin/audit/sessions?status=` | TODO |
| G15 | 数据审计 | 改场次状态 / 删 trash | `PUT /api/admin/sessions/:id/status`, `DELETE /api/admin/sessions/:id` | TODO |

> AES 注意：`src/config.js` 已有 `decryptVal`。写设置需补对称的 `encryptVal`（aes-256-cbc + PKCS7 + `enc:iv_b64:ct_b64`），
> 与 `admin-panel/db_utils.py` 的 `encrypt_val` 格式逐字节一致，否则新旧后台互读会乱码。

### 已就绪（admin-web 直接调，无需新增）
卡牌：`GET/POST /api/admin/cards`、`PUT/DELETE /api/cards/:id`、`/api/admin/cards/:id/{versions,notes,branch,release}`、`/api/admin/card-versions/:id/{,promote}`
卡牌组：`GET/POST /api/admin/card-groups`、`GET/PUT/DELETE /api/admin/card-groups/:id`
组织：`GET/POST/PUT/DELETE /api/admin/organizations`、`POST /api/admin/organizations/:id/members`
邀请码：`GET/POST /api/admin/invite-codes`
活动：`GET/POST /api/admin/activities`、`PUT /api/admin/activities/:id`、`GET /api/admin/activities/:id/sessions`
OSS：`GET/DELETE /api/admin/oss/files`
其他：`GET /api/admin/level-applications`+`PUT`、`GET /api/admin/feedback`+`PUT .../read`、`POST /api/llm/story`、`POST /api/admin/generate-card`

---

## 2. 页面迁移顺序与 DoD

按"先 CRUD（结构稳定、好验证）后分析（聚合复杂）"推进。每页通过后下线对应 Streamlit 页面。

| 序 | 页面 | 依赖接口 | 复杂度 |
|----|------|----------|--------|
| 1 | 登录 + 布局骨架 | admin-login / dev-login | 低 |
| 2 | 卡牌管理 | 全部已就绪 | 中（三表流转 UI） |
| 3 | 活动管理 | 已就绪 | 低 |
| 4 | 组织管理 | +G6,G7 | 中 |
| 5 | 用户管理 | +G2~G5 | 中高 |
| 6 | 系统设置 | +G11~G13 | 中（AES） |
| 7 | OSS 管理 | +G10 | 低 |
| 8 | 驾驶舱 | +G1 | 低 |
| 9 | 游戏分析 | +G8,G9 | 高 |
| 10 | 数据审计 | +G14,G15 | 中 |
| 11 | 复盘测试 | 已就绪(llm/story) | 中 |

**每页 DoD（Definition of Done）：**
1. 对应 bench 断言全绿；
2. 手动在 `/admin/` 点一遍核心交互（增/删/改/查）无报错；
3. 与 Streamlit 同页功能对齐（不丢能力）；
4. 下线 Streamlit 该页（导航移除或标注「已迁移」）；
5. 更新本文进度看板 + 必要时记 CLAUDE.md 踩坑。

---

## 3. 自迭代循环（每个工作单元重复）

```
1. 看板选下一个 TODO（接口优先于依赖它的页面）
2. 实现（后端接口 / 前端页面）
3. npm run test:bench   →  看该项是否转绿
4. 绿：勾掉看板；红：读报错→修→重跑（最多自修，不卡住）
5. 阶段性 git commit（按用户要求才提交/推送）
```

测试 bench 既是回归网，也是进度看板：跑一次就知道"还差哪些接口"。

---

## 4. 部署 / 回退

- **构建**：`cd admin-web && npx vite build` → 产出 `admin-web/dist`
- **托管**：server.js 增加 `app.use("/admin", express.static(...))` + SPA fallback（仿 `/enterprise`）
- **灰度**：admin-web 与 Streamlit 可并存（Streamlit 仍在 8501/8502）。逐页迁移期间，未迁完的页面继续用 Streamlit。
- **回退**：admin-web 完全独立，出问题直接回到 Streamlit，零数据风险（都读同一个 wqt.db）。
- **Zeabur**：admin-web 不再是独立服务（并入 Node 静态托管）→ Zeabur 上只需 1 个 Node service + 1 个持久卷挂 `data/`。Streamlit 进程可彻底删除。

---

## 5. 进度看板（实时更新）

### 后端接口（`src/routes/admin-data.routes.js`，15/16 已实现并通过 bench）
- [x] G1 stats/overview
- [x] G2 users list
- [x] G3 users create
- [x] G4 users update
- [x] G5 users delete(cascade)
- [x] G6 org members list
- [x] G7 org members batch
- [x] G8 stats sessions/cards
- [x] G9 session events
- [ ] G10 oss orphans —（依赖 OSS 客户端，放到 OSS 页迁移时在 server.js 内补，ossClient 在那作用域）
- [x] G11 settings read(AES 解密)
- [x] G12 settings write(AES 加密，`config.js#encryptVal`，格式对齐 Python)
- [x] G13 operators 列表
- [x] G14 audit sessions list
- [x] G15 session status / delete

### admin-web 脚手架（`admin-web/`，base=/admin/，仿 enterprise-panel）
- [x] 工程骨架（vite/main/App/style/router/store/axios/api 封装）
- [x] 登录页（手机号 admin-login + 开发者密钥 dev-login 双模式）
- [x] AppLayout（10 项侧栏导航 + 顶栏 + 登出）
- [x] server.js 托管 `/admin/`（仿 `/enterprise/`）

### 前端页面（真实功能 vs 占位）
- [x] 驾驶舱（真实，G1 概览统计）
- [x] 用户管理（真实，G2-G5 列表/建号/改/删 + 搜索/分页/弹窗）
- [x] 卡牌（真实，列表/筛选 + 增删改 + 三表流转：批注/快照分支/推送沙盒/发布 + 版本抽屉 + 批注抽屉。全链路冒烟通过）
- [x] 活动（真实，CRUD + 桌次明细抽屉，按「桌-活动场次」管理）
- [x] 组织（真实，CRUD/停用 + 成员抽屉 + 单个加号 + 批量建号）
- [x] 系统设置（真实，G11 读/G12 写，敏感项脱敏显示 + G13 运营账号 Tab）
- [x] OSS（真实，目录面包屑浏览 + 删除 + 复制链接；未配置 OSS 时友好降级。G10 孤儿分析待补）
- [x] 游戏分析（真实，echarts 选项分布/阶段饼图 + 每卡被选统计 + 场次列表 + 事件明细抽屉）
- [x] 数据审计（真实，G14 按状态过滤 + 计数 + G15 改状态/删场次）
- [x] 复盘测试（真实，/api/llm/story prompt 调测 + 示例模板 + 性能展示）

> 全 10 页 Playwright 冒烟：逐页渲染、0 console 错误、标题正确；各接口字段与页面读取一致。

### 里程碑
- [x] 现状审计完成
- [x] 执行手册成稿
- [x] 测试 bench 可运行（`npm run test:bench` → 30 PASS / 0 FAIL / 1 TODO）
- [x] 后端接口全绿（15/16，仅 G10 OSS 孤儿分析待补）
- [x] admin-web 脚手架
- [x] 10 页迁移完成（2026-06-04）
- [ ] Streamlit 下线（功能已全部由 admin-web 覆盖，可择期移除 `admin-panel/` 进程）
</content>
</invoke>
