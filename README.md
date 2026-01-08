# 伍力全开｜登录 + 数据库（本地可跑模板）

一个基于 Node.js + Express + SQLite 的数智素养教育游戏系统，集成了用户认证、游戏数据管理、AI 复盘分析等功能。

## 🚀 快速开始

```bash
cd wqt-auth-backend
cp .env.example .env
npm i
npm run dev
```

访问地址：http://127.0.0.1:8080/

> **注意**：你原项目里还有 `styles.css / cards-data.js / global-state.js ...` 等文件。
> 需要把它们一起放到 `public/` 目录下，保持相对路径不变（例如 `public/styles.css`）。

## 📋 功能特性

### 🔐 用户认证系统
- **账号登录/注册**：支持用户名密码注册登录
- **短信验证登录**：集成 Bmob 短信服务（可配置）
- **微信登录预留**：提供微信扫码登录接口框架
- **JWT Token 管理**：安全的会话管理
- **登录状态持久化**：本地存储用户状态

### 🎮 游戏核心功能
- **三种游戏模式**：
  - 桌游模式：传统卡牌游戏体验
  - 玩家模式：个人游戏界面
  - 监督模式：教师/家长监控界面
- **五力属性系统**：安全力、脑波力、实感力、创心力、沟通力
- **数智技能系统**：每种属性对应的特殊技能
- **阶段进度管理**：启蒙期→成长期→青春期
- **失败重置机制**：属性归零触发阶段失败

### 📊 数据管理
- **游戏会话记录**：完整的游戏过程追踪
- **事件日志系统**：详细记录每个操作
- **SQLite 数据库**：轻量级本地数据存储
- **数据导出功能**：支持游戏数据导出

### 🤖 AI 复盘系统
- **智能数据提取**：识别游戏中的关键时刻
- **三步式复盘流程**：
  1. 数据分析：提取"有意思"的游戏数据
  2. 故事生成：AI 生成温馨的成长故事
  3. 报告输出：生成精美的 HTML 复盘报告
- **LLM 集成**：支持 DeepSeek API 调用
- **多格式输出**：Markdown + HTML 双格式

### 🎵 多媒体功能
- **录音系统**：支持游戏过程录音
- **音效系统**：丰富的游戏音效反馈
- **可拖拽录音器**：灵活的录音控制界面

## 🏗️ 技术架构

### 后端技术栈
- **Node.js + Express**：服务器框架
- **SQLite3**：数据库
- **JWT**：身份认证
- **bcryptjs**：密码加密
- **node-fetch**：HTTP 请求
- **cors**：跨域支持

### 前端技术栈
- **原生 JavaScript**：核心逻辑
- **HTML5 + CSS3**：界面展示
- **Web Audio API**：录音功能
- **Canvas API**：波形显示
- **Fetch API**：网络请求

### 数据库设计
```sql
-- 用户表
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE,
  password_hash TEXT,
  phone TEXT UNIQUE,
  created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- 游戏会话表
CREATE TABLE game_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  started_at INTEGER,
  ended_at INTEGER,
  final_score INTEGER,
  payload_json TEXT,
  FOREIGN KEY (user_id) REFERENCES users (id)
);

-- 游戏事件表
CREATE TABLE game_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER,
  type TEXT,
  payload_json TEXT,
  ts INTEGER DEFAULT (strftime('%s', 'now') * 1000),
  FOREIGN KEY (session_id) REFERENCES game_sessions (id)
);
```

## 📁 项目结构

```
wqt-auth-backend/
├── public/                 # 前端静态文件
│   ├── index.html         # 主游戏界面
│   ├── cards-data.js      # 卡牌数据（45张卡牌）
│   ├── global-state.js    # 全局状态管理
│   ├── game-review.js     # AI复盘模块
│   ├── advanced-review.js # 复盘功能集成
│   ├── test-game-review.html # 复盘功能测试页面
│   ├── audio-recorder.js  # 录音功能
│   ├── sound-effects.js   # 音效系统
│   ├── supervisor-controller.js # 监督模式控制器
│   └── styles.css         # 样式文件
├── src/
│   └── db.js             # 数据库操作
├── data/                 # 数据文件
│   └── wqt.db           # SQLite数据库文件
├── server.js            # 服务器入口
├── package.json         # 项目配置
├── .env.example         # 环境变量模板
└── README.md           # 项目文档
```

## 🎯 游戏机制详解

### 卡牌系统
- **总计 45 张卡牌**，分布在三个成长阶段
- **五大安全类型**：身体安全、心理安全、社交安全、经济安全、数字权益
- **每张卡牌包含**：
  - 情境描述
  - 3个选择选项（A/B/C）
  - 属性影响效果
  - 结果反馈文本

### 属性系统
- **初始值**：每个属性起始为 3 点
- **取值范围**：0-10 点
- **失败机制**：任一属性降至 0 触发阶段失败
- **重置规则**：失败后根据进度回退并重置属性

### 技能系统
- **安全力技能**：检测并提升危险属性（值为1的属性+1）
- **脑波力技能**：直接+1脑波力
- **实感力技能**：直接+1实感力
- **创心力技能**：+1创心力，并可创建自定义选项D
- **沟通力技能**：直接+1沟通力

## 🔧 配置说明

### 环境变量配置（.env）
```bash
# 服务器配置
PORT=8080
HOST=localhost
JWT_SECRET=your_jwt_secret_here

# DeepSeek AI配置（用于复盘功能）
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_MODEL=deepseek-reasoner

# Bmob短信服务配置
BMOB_APP_ID=your_bmob_app_id
BMOB_REST_KEY=your_bmob_rest_key

# 微信登录配置（预留，需要完善）
WECHAT_APPID=your_wechat_appid
WECHAT_SECRET=your_wechat_secret
```

### Bmob短信服务配置
1. 访问 [Bmob官网](https://www.bmobapp.com/) 注册账号
2. 创建应用获取 Application ID 和 REST API Key
3. 在 `.env` 文件中配置相应密钥
4. 未配置时自动使用开发模式（控制台输出验证码）

### 数据库初始化
数据库会在首次启动时自动创建，包含：
- 用户表（users）：存储用户信息和守望师名字
- 游戏会话表（game_sessions）  
- 游戏事件表（game_events）
- SMS验证码表（sms_codes）

## 🎮 使用指南

### 基本游戏流程
1. **用户注册/登录**：通过短信验证码登录
2. **完善资料**：新用户需要输入守望师名字
3. **开始新游戏**：点击"新游戏"按钮
4. **卡牌游戏**：
   - 输入卡牌编号（1-45）
   - 查看事件描述
   - 选择应对方案（A/B/C）
   - 使用数智技能（可选）
   - 确认选择并查看结果
5. **游戏结束**：完成15张卡牌或失败3次
6. **复盘分析**：生成AI复盘报告

### 登录方式
- **短信登录**：输入手机号获取验证码
- **开发者模式**：绕过短信验证直接登录
- **微信登录**：预留接口，需要配置微信开放平台

### 复盘功能使用
1. **完成游戏**：至少完成几张卡牌
2. **点击复盘**：在游戏界面点击"复盘"按钮
3. **AI分析**：系统自动分析游戏数据
4. **生成报告**：
   - 第一部分：游戏历程回顾
   - 第二部分：洞察与启示
   - 自动生成HTML报告并下载

### 测试复盘功能
访问 `http://127.0.0.1:8080/test-game-review.html` 进行复盘功能测试：
- 模块加载测试
- 数据提取测试  
- 故事生成测试
- HTML报告生成测试
- 完整流程测试

## 🔌 API 接口

### 认证相关
```javascript
POST /api/auth/register     // 用户注册
POST /api/auth/login        // 用户登录
POST /api/auth/logout       // 用户登出
GET  /api/me               // 获取当前用户信息

// 短信登录
POST /api/auth/sms/send    // 发送验证码
POST /api/auth/sms/verify  // 验证登录

// 微信登录（预留）
GET  /api/auth/wechat/qr   // 获取登录二维码
GET  /api/auth/wechat/poll // 轮询登录状态
```

### 游戏相关
```javascript
POST /api/game/start       // 开始游戏会话
POST /api/game/finish      // 结束游戏会话
POST /api/game/event       // 记录游戏事件
GET  /api/game/last-session    // 获取最近会话
GET  /api/game/session/:id     // 获取指定会话
```

### AI服务
```javascript
POST /api/llm/story        // LLM故事生成（需要认证）
```

## 🧪 测试功能

### 复盘模块测试
项目包含完整的测试套件（`test-game-review.html`）：

1. **模块加载测试**：验证复盘模块正确加载
2. **数据提取测试**：测试游戏数据分析功能
3. **故事生成测试**：测试AI故事生成（模拟）
4. **HTML生成测试**：测试报告HTML生成
5. **完整流程测试**：端到端功能验证

### 运行测试
```bash
# 启动服务器
npm run dev

# 访问测试页面
http://127.0.0.1:8080/test-game-review.html
```

## 🔒 安全特性

### 数据安全
- **密码加密**：使用 bcryptjs 加密存储
- **JWT Token**：安全的会话管理
- **SQL注入防护**：参数化查询
- **XSS防护**：输入输出转义

### 隐私保护
- **本地数据库**：数据存储在本地
- **API密钥保护**：LLM密钥存储在后端
- **用户数据隔离**：按用户ID隔离数据访问

## 🚧 开发计划

### 已实现功能 ✅
- [x] 用户认证系统
- [x] 基础游戏逻辑
- [x] 数据库设计
- [x] AI复盘系统
- [x] 录音功能
- [x] 音效系统
- [x] 测试套件

### 待完善功能 🔄
- [ ] 微信登录完整实现
- [ ] 游戏数据可视化
- [ ] 多人游戏模式
- [ ] 成就系统
- [ ] 游戏回放功能
- [ ] 移动端适配

### 扩展方向 🎯
- [ ] 教师管理后台
- [ ] 班级管理功能
- [ ] 学习分析报告
- [ ] 游戏内容编辑器
- [ ] 多语言支持

## 📦 版本控制 & 部署

### Git 初始化和上传

#### 首次上传到GitHub
```bash
# 1. 初始化Git仓库（如果还没有）
git init

# 2. 添加所有文件到暂存区
git add .

# 3. 提交初始版本
git commit -m "feat: 初始化伍力全开游戏系统

- 完成用户认证系统（短信登录、开发者模式）
- 实现核心游戏逻辑（45张卡牌、五力属性系统）
- 集成AI复盘功能（DeepSeek API）
- 添加录音和音效系统
- 完成SQLite数据库设计
- 支持三种游戏模式（桌游、玩家、监督）"

# 4. 添加远程仓库（替换为你的GitHub仓库地址）
git remote add origin https://github.com/你的用户名/wqt-auth-backend.git

# 5. 推送到GitHub
git branch -M main
git push -u origin main
```

#### 日常开发流程
```bash
# 查看当前状态
git status

# 添加修改的文件
git add .
# 或添加特定文件
git add src/db.js public/index.html

# 提交更改
git commit -m "fix: 修复游戏会话记录bug"

# 推送到远程仓库
git push

# 拉取最新代码
git pull
```

#### 分支管理
```bash
# 创建并切换到新分支
git checkout -b feature/ai-enhancement

# 查看所有分支
git branch -a

# 切换分支
git checkout main

# 合并分支
git merge feature/ai-enhancement

# 删除已合并的分支
git branch -d feature/ai-enhancement
```

### 项目文件说明

#### 已配置的 .gitignore
```
node_modules     # npm依赖包
.env            # 环境变量（包含API密钥）
dist            # 构建输出目录
build           # 构建临时目录
wqt.db          # SQLite数据库文件
app.db          # 备用数据库文件
app.sqlite      # SQLite文件
```

#### 需要上传的重要文件
- ✅ `src/` - 后端核心代码
- ✅ `public/` - 前端静态文件
- ✅ `server.js` - 服务器入口
- ✅ `package.json` - 项目配置
- ✅ `.env.example` - 环境变量模板
- ✅ `README.md` - 项目文档
- ✅ `.gitignore` - Git忽略规则

#### 不会上传的文件（已在.gitignore中）
- ❌ `node_modules/` - 依赖包（通过npm install安装）
- ❌ `.env` - 环境变量（包含敏感信息）
- ❌ `wqt.db` - 数据库文件（本地数据）

#### ⚠️ 重要安全提醒
如果你发现 `.env` 文件已经被提交到 GitHub，需要立即移除：
```bash
# 从Git跟踪中移除.env文件（保留本地文件）
git rm --cached .env

# 提交这个更改
git commit -m "security: 从版本控制中移除.env文件"

# 推送到远程仓库
git push

# 确保.gitignore包含.env
echo ".env" >> .gitignore
```

**注意**：即使从Git中移除了 `.env` 文件，GitHub的历史记录中仍然可能包含敏感信息。如果 `.env` 中包含重要的API密钥，建议：
1. 立即更换所有暴露的API密钥
2. 考虑使用 `git filter-branch` 或 BFG Repo-Cleaner 清理历史记录

### 部署建议

#### 本地开发
```bash
# 克隆项目
git clone https://github.com/你的用户名/wqt-auth-backend.git
cd wqt-auth-backend

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的API密钥

# 启动开发服务器
npm run dev
```

#### 服务器部署
```bash
# 1. 在服务器上克隆项目
git clone https://github.com/你的用户名/wqt-auth-backend.git
cd wqt-auth-backend

# 2. 安装依赖
npm install --production

# 3. 配置环境变量
cp .env.example .env
vim .env  # 配置生产环境的API密钥

# 4. 使用PM2启动（推荐）
npm install -g pm2
pm2 start server.js --name "wqt-game"
pm2 startup
pm2 save

# 5. 配置Nginx反向代理（可选）
# 将80端口请求转发到8080端口
```

## 🤝 贡献指南

### 开发环境搭建
```bash
# 克隆项目
git clone https://github.com/你的用户名/wqt-auth-backend.git
cd wqt-auth-backend

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 启动开发服务器
npm run dev
```

### 代码规范
- 使用 ES6+ 语法
- 遵循 RESTful API 设计
- 添加适当的错误处理
- 编写清晰的注释
- 保持代码简洁可读

### 提交规范
```bash
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 代码重构
test: 测试相关
chore: 构建/工具相关
```

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- **杨红樱儿童文学风格**：复盘故事的写作风格参考
- **DeepSeek AI**：提供LLM服务支持
- **Bmob**：短信验证服务
- **SQLite**：轻量级数据库解决方案

## 📞 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 发起 Pull Request
- 邮件联系：[your-email@example.com]

---

**让每一次选择都成为成长的阶梯，在AI时代做最好的自己！** 🌟