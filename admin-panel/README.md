# WQT 企业级中台管理系统 (Admin Panel)

基于 Python Streamlit 构建的企业级中台管理系统，提供数据驾驶舱、用户全景视图及业务数据分析功能。

## 🛠️ 技术栈
- **核心框架**: Streamlit
- **数据处理**: Pandas, SQLite3
- **并发控制**: WAL Mode + 自动重试机制 (Retry Logic)

## 🚀 快速开始

### 1. 环境准备
确保已安装 Python 3.8+。
```bash
cd admin-panel
pip install -r requirements.txt
```

### 2. 启动服务
```bash
streamlit run app.py --server.port 8501
```
启动后访问: [http://localhost:8501](http://localhost:8501)

## 🔐 登录指南

系统支持两种登录模式：

### 1. 开发者上帝模式 (Developer Mode)
*   **用途**: 系统维护、最高权限管理。
*   **密钥**: `sj0127wqt`
*   **权限**: 可查看及修改所有数据，包括提升普通用户为管理员。

### 2. 业务用户登录 (User Login)
*   **用途**: 日常业务查看。
*   **方式**: 输入已注册用户的手机号。
*   **权限管理**:
    *   **Admin**: 拥有管理权限 (根据 `users` 表 `role` 字段)。
    *   **User**: 仅查看权限。

## 🎛️ 核心功能模块

### 1. 驾驶舱 (Cockpit)
*   实时核心指标：用户总量、游戏场次、今日活跃。
*   数据可视化：用户增长趋势图、每日活跃度分布。

### 2. 用户全景视图 (User 360)
*   **搜索**: 支持手机号、ID、昵称模糊搜索。
*   **权限管理**: 管理员可在线修改用户角色（User <-> Admin）。

### 3. 业务数据分析
*   **得分分布**: 游戏难度与玩家水平分析。
*   **事件日志**: 查看底层 `game_events` 原始数据，辅助排查问题。

## ⚠️ 数据库说明
*   系统自动连接上级目录的 `data/wqt.db`。
*   **并发保护**: 已自动开启 SQLite WAL 模式，并内置写入重试机制，防止 Windows 环境下的 "Database File Locked" 错误。
