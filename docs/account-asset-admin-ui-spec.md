# 账号资产管理 — admin-panel UI 实现规格（交接文档）

> 给负责写 admin-panel（Streamlit）UI 的同学/agent。
> 后端已完成并通过测试 bench（`node tests/auth.bench.mjs`，23/23）。本文档说明数据模型、可调用的接口、以及 UI 应呈现的内容。
> 关联代码：`src/account.js`、`src/services/sessions.js`、`src/routes/account-admin.routes.js`。

---

## 一、要做什么

在 admin-panel 里给 **boss** 提供"账号资产"管理能力，分两块：

1. **会员有效期（组织统一到期）**
   - 组织：在 `org_management_page()`（🏢 组织管理）里，给每个组织加"有效期至 + 续期"控件。
   - 个人独立用户：在 `user_management_page()`（👤 用户管理）里，给 `enterprise_id` 为空的用户加"有效期至"控件。
2. **在线设备（单设备登录）**
   - 在用户列表/详情里展示"当前登录设备"，并提供"强制下线"按钮。

---

## 二、数据模型（已迁移，wqt.db）

```
users.valid_until        INTEGER  毫秒时间戳；仅【独立个人用户】(enterprise_id 为空) 使用；NULL=永久
organizations.valid_until INTEGER  毫秒时间戳；【组织统一到期】，名下成员全部跟随；NULL=永久

user_sessions  id, user_id, jti(UNIQUE), device_info(登录时的 User-Agent), ip,
               created_at(ms), last_seen_at(ms)
               每个用户最多一条有效会话；新登录会删旧建新（踢掉旧设备）
```

### 有效期判定规则（`src/account.js` resolveValidity，UI 展示口径要一致）
| 账号类型 | 生效到期 | UI 处理 |
|---------|---------|---------|
| `boss` / `operator` | 永不过期 | 不显示有效期控件 |
| 有 `enterprise_id`（组织成员/管理员）| 跟随**组织** valid_until + 组织 status | 用户行只**只读展示**组织到期；编辑入口在组织页 |
| 独立 `watcher`（enterprise_id 为空）| 用**自身** valid_until | 用户行可直接编辑 |

到期/停用时鉴权返回 403，`code` 取值：`ORG_EXPIRED` / `ACCOUNT_EXPIRED` / `ORG_SUSPENDED` / `ORG_NOT_FOUND`。

---

## 三、可调用的后端接口（boss token）

> admin-panel 已有 `BACKEND_URL` + boss token 调用模式（见 app.py 现有卡牌接口调用）。**优先走 API**，保证与鉴权逻辑一致。

| 方法 & 路径 | Body | 返回 | 说明 |
|------------|------|------|------|
| `PUT /api/admin/organizations/:id/validity` | `{ "validUntil": <ms数字 / ISO字符串 / null> }` | `{ ok, validUntil }` | 设/清组织有效期。null=永久 |
| `PUT /api/admin/users/:id/validity` | `{ "validUntil": <ms / ISO / null> }` | `{ ok, validUntil }` | 仅独立用户；组织成员会被拒(400) |
| `GET /api/admin/users/:id/sessions` | — | `{ sessions:[{id,jti,device_info,ip,created_at,last_seen_at}] }` | 当前在线设备（0 或 1 条）|
| `DELETE /api/admin/users/:id/sessions` | — | `{ ok }` | 强制下线（删该用户全部会话）|

> 备选：admin-panel 也直连 wqt.db（`db_utils.py`）。有效期是普通列，强制下线＝`DELETE FROM user_sessions WHERE user_id=?`，直接写库也可。但**改有效期建议走 API**（未来可能加副作用）。

---

## 四、UI 呈现要点

- **时间显示**：`valid_until` / `last_seen_at` 是毫秒时间戳，用现有 `BEIJING_TZ`(UTC+8) 转北京时间展示。
- **状态标签**：`永久`（NULL）/ `有效至 YYYY-MM-DD`（未来）/ `已过期 N 天`（过去，红色）。
- **续期控件**：日期选择器 → 转成当天 23:59:59 的毫秒时间戳传 `validUntil`；"设为永久"按钮传 `null`。
- **组织页**：每个组织一行有效期 + 续期；过期组织在列表里高亮提示（其成员已全部无法登录）。
- **用户页**：
  - 组织成员：只读显示"跟随组织（到期 …）"，不提供编辑。
  - 独立用户：可编辑有效期。
  - 每个用户显示"在线设备"：有会话则展示 `device_info` + `last_seen_at` + [强制下线] 按钮；无则显示"离线"。

---

## 五、登录流程已变更（仅作背景，UI 不用改后台登录）

- 终端用户主登录 `POST /api/auth/login` 现需 **手机号+密码+验证码** 三要素。
- admin-panel 自身登录走 `POST /api/auth/admin-login`（手机号，仅 boss/operator），**未变**，照常用。
- 单设备：任何账号新登录会踢掉旧会话；boss 在 admin-panel 重新登录也会刷新自己的会话。

---

## 六、自验

后端改动可随时回归：`node tests/auth.bench.mjs`（用临时库，不碰真实 data/）。
