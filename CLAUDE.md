# WQT 项目知识库

> 此文件由 Claude 自动维护，记录项目踩坑经验与关键约定。
> 每次修复 bug 后说"记录一下"即可自动追加。

## 项目关键约定

### 数据库事件类型枚举

游戏事件 `game_events.type` 的合法值（前后端必须保持一致）：

| 值 | 含义 |
|----|------|
| `card_choice` | 玩家选择了一张卡牌的选项 |
| `skill_used` | 玩家使用了数智技能 |
| `game_start` | 游戏开始 |
| `game_end` | 游戏结束 |

> 新增事件类型时，同步更新此表，并检查 `admin-panel/app.py` 中所有 SQL 查询。

### 卡牌生命周期状态

`cards.status` 合法值：`pending` → `active` / `rejected` / `deleted`

### 双数据库路径

| 数据库 | 默认路径 | 环境变量 |
|--------|----------|----------|
| 主库（用户/会话/事件）| `./data/wqt.db` | `DB_PATH` |
| 卡牌库 | `./data/cards.db` | `CARDS_DB_PATH` |

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

**现象**: 新用户在 `complete-profile.html` 填完守望师名字跳回首页时，星空穿越欢迎动画再次播放，用户感觉像是应用重启了。
**根因**: `js/starfield.js` 没有区分"首次加载"和"从其他页面跳转回来"两种场景，每次初始化都会播放动画。
**修复**: 在 `complete-profile.html` 提交成功后跳转前写入 `sessionStorage.setItem('skip_intro', 'true')`；`starfield.js` 初始化时检测该标记，存在则直接隐藏 `#welcome-screen` 并清除标记。
**关键点**: 页面间传递"一次性状态"用 `sessionStorage`（关闭 Tab 即清除），不要用 `localStorage`（会持久化影响下次真正的首次访问）。
